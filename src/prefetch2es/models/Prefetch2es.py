# coding: utf-8
import sys
import os
import stat
from datetime import datetime
from pathlib import Path
from typing import List, Generator, Iterable, Union, Sequence
from functools import partial


import pyscca

from .MultiprocessingUtils import SafeMultiprocessingMixin
from .MultiprocessingUtils import mp as mp
from .MultiprocessingUtils import ordered_pool_results as _ordered_pool_results

FILETIME_ZERO = datetime(1601, 1, 1, 0, 0, 0)


def validate_chunk_size(chunk_size: int) -> None:
    if type(chunk_size) is not int or chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")


def normalize_tags(tags: Union[str, Sequence[str], None]) -> List[str]:
    """Normalize comma-separated strings or tag sequences, preserving order."""
    if tags is None:
        user_tags = []
    elif isinstance(tags, str):
        user_tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
    else:
        user_tags = [tag.strip() for tag in tags if tag.strip()]

    result = []
    for tag in ["prefetch", *user_tags]:
        if tag not in result:
            result.append(tag)
    return result


def safe_last_run_times(p: pyscca.file) -> List[str]:
    """Read available last-run timestamps without trusting run_count."""
    times = []
    for i in range(8):
        try:
            value = p.get_last_run_time(i)
        except OSError:
            break
        if value is None or value == FILETIME_ZERO:
            continue
        times.append(f"{value}Z".replace(" ", "T"))
    return times


def process_prefetch_file(filepath: Path, tags: Union[str, Sequence[str]] = "") -> dict:
    """Process a single prefetch file and return its data.

    Args:
        filepath (Path): Path to the prefetch file

    Returns:
        dict: Prefetch file data
    """
    p = pyscca.file()
    with filepath.open(mode="rb") as file_object:
        try:
            p.open_file_object(file_object)
            # Parse tags from comma-separated string
            base_tags = normalize_tags(tags)
            last_exec_times = safe_last_run_times(p)

            return {
                "name": p.executable_filename,
                "filenames": [name for name in p.filenames],
                "exec_count": p.run_count,
                "last_exec_times": last_exec_times,
                "format_version": p.format_version,
                "prefetch_hash": format(p.prefetch_hash, "x").upper(),
                "number_of_volumes": p.number_of_volumes,
                "number_of_filenames": p.number_of_filenames,
                "number_of_file_metrics_entries": p.number_of_file_metrics_entries,
                "metrics": [
                    {
                        "filename": metrics.filename,
                        "file_reference": hex(metrics.file_reference).upper(),
                    }
                    for metrics in p.file_metrics_entries
                ],
                "volumes": [
                    {
                        "path": volume.device_path,
                        "creation_time": f"{volume.get_creation_time()}Z".replace(
                            " ", "T"
                        ),
                        "serial_number": format(volume.serial_number, "x").upper(),
                    }
                    for volume in p.volumes
                ],
                "source_file": str(filepath),
                "tags": base_tags,
            }
        finally:
            p.close()


def process_prefetch_file_timeline(
    filepath: Path, tags: Union[str, Sequence[str]]
) -> List[dict]:
    """Process a single prefetch file and return its timeline data.

    Args:
        filepath (Path): Path to the prefetch file
        tags (str): Additional tags for timeline records (comma-separated)

    Returns:
        List[dict]: Timeline-formatted prefetch file data.
    """
    p = pyscca.file()
    with filepath.open(mode="rb") as file_object:
        try:
            p.open_file_object(file_object)
            # Parse tags from comma-separated string
            base_tags = normalize_tags(tags)
            last_exec_times = safe_last_run_times(p)

            timeline_records = []
            for exec_time in last_exec_times:
                timeline_records.append(
                    {
                        "@timestamp": exec_time,
                        "event": {
                            "action": "prefetch-executed",
                            "category": ["process"],
                            "type": ["start"],
                            "kind": "event",
                            "provider": "prefetch",
                            "module": "windows",
                            "dataset": "windows.prefetch",
                        },
                        "process": {
                            "name": p.executable_filename,
                            "start": exec_time,
                        },
                        "windows": {
                            "prefetch": {
                                "exec_count": p.run_count,
                                "hash": {
                                    "prefetch": format(p.prefetch_hash, "x").upper()
                                },
                                "format_version": p.format_version,
                                "volumes": [
                                    {
                                        "path": volume.device_path,
                                        "creation_time": f"{volume.get_creation_time()}Z".replace(
                                            " ", "T"
                                        ),
                                        "serial_number": format(
                                            volume.serial_number, "x"
                                        ).upper(),
                                    }
                                    for volume in p.volumes
                                ],
                                "metrics": [
                                    {
                                        "filename": metrics.filename,
                                        "file_reference": hex(
                                            metrics.file_reference
                                        ).upper(),
                                    }
                                    for metrics in p.file_metrics_entries
                                ],
                            }
                        },
                        "log": {"file": {"path": str(filepath)}},
                        "tags": base_tags,
                    }
                )

            return timeline_records
        finally:
            p.close()


def get_prefetch_files(
    input_paths: Sequence[Union[str, Path]], diagnostics: List[dict] | None = None
) -> List[Path]:
    """Expand usable Prefetch inputs and record paths that cannot be processed."""
    files = []
    seen = set()

    def record_scan_error(error, directory=None):
        if diagnostics is not None:
            diagnostics.append(
                {
                    "source_file": str(directory or error.filename),
                    "error": f"Cannot enumerate input: {error}",
                }
            )

    for input_path in input_paths:
        path = Path(input_path)
        try:
            path = path.resolve()
            mode = path.stat().st_mode
            is_file = stat.S_ISREG(mode)
            is_directory = stat.S_ISDIR(mode)
        except OSError as error:
            record_scan_error(error, path)
            continue
        error_count = len(diagnostics) if diagnostics is not None else 0
        candidates: Iterable[Path]
        if is_file:
            candidates = [path]
        elif is_directory:
            candidates = (
                Path(directory) / name
                for directory, _, names in os.walk(path, onerror=record_scan_error)
                for name in names
                if Path(name).suffix.lower() == ".pf"
            )
        else:
            if diagnostics is not None:
                diagnostics.append(
                    {
                        "source_file": str(path),
                        "error": "Input path does not exist or is not a file/directory.",
                    }
                )
            continue
        found = False
        for candidate in candidates:
            try:
                if not stat.S_ISREG(candidate.stat().st_mode):
                    continue
            except OSError as error:
                record_scan_error(error, candidate.parent)
                continue
            found = True
            resolved = candidate.resolve()
            if resolved not in seen:
                files.append(resolved)
                seen.add(resolved)
        if (
            not found
            and is_directory
            and diagnostics is not None
            and len(diagnostics) == error_count
        ):
            diagnostics.append(
                {"source_file": str(path), "error": "No Prefetch files found."}
            )
    return files


class PartialExtractionError(RuntimeError):
    """Completed processing with failed files; successful output is partial."""

    def __init__(self, diagnostics, records=None):
        self.diagnostics = diagnostics
        self.records = records
        super().__init__(
            f"Partial extraction: {len(diagnostics)} failure(s); output is incomplete."
        )


def process_prefetch_task(filepath: Path, tags="", timeline_mode=False):
    """Return one file's records or its serializable processing exception."""
    try:
        records = (
            process_prefetch_file_timeline(filepath, tags)
            if timeline_mode
            else [process_prefetch_file(filepath, tags)]
        )
        return filepath, records, None
    except Exception as error:
        return filepath, [], error


class Prefetch2es(SafeMultiprocessingMixin):
    """Prefetch file processor with multiprocessing support"""

    def __init__(
        self,
        input_path: Union[str, Path, Sequence[Path]],
        input_diagnostics: Sequence[dict] = (),
    ) -> None:
        """Initialize Prefetch2es.

        Args:
            input_path: Prefetch file, directory, or already enumerated files.
        """
        self.path = (
            Path(input_path).resolve()
            if isinstance(input_path, (str, Path))
            else list(dict.fromkeys(Path(path).resolve() for path in input_path))
        )
        self.input_diagnostics = list(input_diagnostics)
        self.diagnostics: List[dict] = []
        self.successful_files = 0
        self.generated_records = 0

    def _get_prefetch_files(self) -> List[Path]:
        """Get list of prefetch files to process.

        Returns:
            List[Path]: List of prefetch file paths
        """
        if isinstance(self.path, Path):
            return get_prefetch_files([self.path], self.diagnostics)
        # Keep the discovery snapshot so vanished files fail inside their task.
        return list(self.path)

    def gen_records(
        self,
        multiprocess: bool = False,
        chunk_size: int = 1000,
        tags: Union[str, Sequence[str]] = "",
    ) -> Generator[List[dict], None, None]:
        """Generate prefetch records.

        Args:
            multiprocess (bool): Flag to run multiprocessing.
            chunk_size (int): Maximum documents per output chunk.

        Yields:
            Generator[List[dict], None, None]: Yields List[dict] of prefetch records.
        """
        yield from self._gen_records(
            multiprocess, chunk_size, tags, False
        )

    def gen_timeline_records(
        self,
        multiprocess: bool = False,
        chunk_size: int = 1000,
        tags: Union[str, Sequence[str]] = "",
    ) -> Generator[List[dict], None, None]:
        """Generate timeline-formatted prefetch records.

        Args:
            multiprocess (bool): Flag to run multiprocessing.
            chunk_size (int): Maximum documents per output chunk.
            tags (str): Additional tags for timeline records (comma-separated).

        Yields:
            Generator[List[dict], None, None]: Yields List[dict] of timeline-formatted prefetch records.
        """
        yield from self._gen_records(
            multiprocess, chunk_size, tags, True
        )

    def _gen_records(self, multiprocess, chunk_size, tags, timeline):
        validate_chunk_size(chunk_size)
        self.diagnostics = list(self.input_diagnostics)
        files = self._get_prefetch_files()
        self.successful_files = 0
        self.generated_records = 0
        process = partial(process_prefetch_task, tags=tags, timeline_mode=timeline)

        if multiprocess and len(files) > 1:
            ctx = self.get_multiprocessing_context()
            workers = min(self.get_cpu_count(), len(files))
            with ctx.Pool(workers) as pool:
                yield from self._batch_records(
                    _ordered_pool_results(pool, process, files, workers * 2),
                    chunk_size,
                )
        else:
            yield from self._batch_records(
                map(process, files), chunk_size
            )

    def _batch_records(self, results, chunk_size):
        buffer = []
        for diagnostic in self.diagnostics:
            print(
                f"Skipping input {diagnostic['source_file']}: {diagnostic['error']}",
                file=sys.stderr,
            )
        for filepath, records, error in results:
            if error is not None:
                error_text = f"{type(error).__name__}: {error}"
                self.diagnostics.append(
                    {"source_file": str(filepath), "error": error_text}
                )
                message = (
                    f"Error parsing {filepath}: {error_text} "
                    f"({self.successful_files} file(s) parsed successfully, "
                    f"{self.generated_records} record(s) generated)."
                )
                print(message, file=sys.stderr)
                continue
            self.successful_files += 1
            self.generated_records += len(records)
            for record in records:
                buffer.append(record)
                if len(buffer) == chunk_size:
                    yield buffer
                    buffer = []
        if buffer:
            yield buffer
        if self.diagnostics:
            raise PartialExtractionError(self.diagnostics)
