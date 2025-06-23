# coding: utf-8
import sys
import os
from itertools import chain
from pathlib import Path
from typing import List, Generator, Iterable, Dict, Union
from itertools import islice
import multiprocessing as mp
from functools import partial


import pyscca


class SafeMultiprocessingMixin:
    """Safe multiprocessing management class for Python 3.13 compatibility"""

    @staticmethod
    def get_multiprocessing_context() -> mp.context.BaseContext:
        """Get safe multiprocessing context"""
        # Use spawn for Python 3.13+ or test environments to avoid fork() issues
        if sys.version_info >= (3, 13) or "pytest" in sys.modules:
            try:
                ctx = mp.get_context("spawn")
            except RuntimeError:
                ctx = mp.get_context()
        else:
            ctx = mp.get_context()

        return ctx

    @staticmethod
    def get_cpu_count() -> int:
        """Get CPU count safely"""
        try:
            return mp.cpu_count()
        except NotImplementedError:
            return os.cpu_count() or 1


def generate_chunks(chunk_size: int, iterable: Iterable) -> Generator:
    """Generate arbitrarily sized chunks from iterable objects.

    Args:
        chunk_size (int): Chunk sizes.
        iterable (Iterable): Original Iterable object.

    Yields:
        Generator: List
    """
    i = iter(iterable)
    piece = list(islice(i, chunk_size))
    while piece:
        yield piece
        piece = list(islice(i, chunk_size))


def process_prefetch_file(filepath: Path, tags: str = "") -> dict:
    """Process a single prefetch file and return its data.

    Args:
        filepath (Path): Path to the prefetch file

    Returns:
        dict: Prefetch file data
    """
    p = pyscca.file()
    p.open_file_object(filepath.open(mode="rb"))

    # Parse tags from comma-separated string
    additional_tags = (
        [tag.strip() for tag in tags.split(",") if tag.strip()] if tags else []
    )
    base_tags = ["prefetch"] + additional_tags

    result = {
        "name": p.executable_filename,
        "filenames": [name for name in p.filenames],
        "exec_count": p.run_count,
        "last_exec_times": [
            f"{p.get_last_run_time(i)}Z".replace(' ', 'T') for i in range(p.run_count if p.run_count < 8 else 8)
        ],
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
                "creation_time": f"{volume.get_creation_time()}Z".replace(' ', 'T'),
                "serial_number": format(volume.serial_number, "x").upper(),
            }
            for volume in p.volumes
        ],
        "source_file": str(filepath),
        "tags": base_tags,
    }

    p.close()
    return result


def process_prefetch_file_timeline(filepath: Path, tags: str) -> List[dict]:
    """Process a single prefetch file and return its timeline data.

    Args:
        filepath (Path): Path to the prefetch file
        tags (str): Additional tags for timeline records (comma-separated)

    Returns:
        List[dict]: Timeline-formatted prefetch file data.
    """
    p = pyscca.file()
    p.open_file_object(filepath.open(mode="rb"))

    # Parse tags from comma-separated string
    additional_tags = (
        [tag.strip() for tag in tags.split(",") if tag.strip()] if tags else []
    )
    base_tags = ["prefetch"] + additional_tags

    timeline_records = []
    for i in range(p.run_count if p.run_count < 8 else 8):
        timeline_records.append(
            {
                "@timestamp": f"{p.get_last_run_time(i)}Z".replace(' ', 'T'),
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
                    "start": f"{p.get_last_run_time(i)}Z".replace(' ', 'T'),
                },
                "windows": {
                    "prefetch": {
                        "exec_count": p.run_count,
                        "hash": {"prefetch": format(p.prefetch_hash, "x").upper()},
                        "format_version": p.format_version,
                        "volumes": [
                            {
                                "path": volume.device_path,
                                "creation_time": f"{volume.get_creation_time()}Z".replace(' ', 'T'),
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

    p.close()
    return timeline_records


def process_prefetch_chunk(filepaths: List[Path]) -> List[dict]:
    """Process a chunk of prefetch files.

    Args:
        filepaths (List[Path]): List of prefetch file paths

    Returns:
        List[dict]: List of processed prefetch data
    """
    return [process_prefetch_file(filepath) for filepath in filepaths]


def process_timeline_prefetch_chunk(filepaths: List[Path]) -> List[dict]:
    """Process a chunk of prefetch files for timeline analysis.

    Args:
        filepaths (List[Path]): List of prefetch file paths

    Returns:
        List[dict]: List of timeline-formatted prefetch data
    """
    result = []
    for filepath in filepaths:
        timeline_records = process_prefetch_file_timeline(filepath, tags="")
        result.extend(timeline_records)
    return result


def process_timeline_prefetch_chunk_with_tags(
    filepaths: List[Path], tags: str
) -> List[dict]:
    """Process a chunk of prefetch files for timeline analysis with tags.

    Args:
        filepaths (List[Path]): List of prefetch file paths
        tags (str): Additional tags for timeline records (comma-separated)

    Returns:
        List[dict]: List of timeline-formatted prefetch data
    """
    result = []
    for filepath in filepaths:
        timeline_records = process_prefetch_file_timeline(filepath, tags)
        result.extend(timeline_records)
    return result


class Prefetch2es(SafeMultiprocessingMixin):
    """Prefetch file processor with multiprocessing support"""

    def __init__(self, input_path: Union[str, Path]) -> None:
        """Initialize Prefetch2es.

        Args:
            input_path (Union[str, Path]): Path to prefetch file or directory
        """
        self.path = Path(input_path)

    def _get_prefetch_files(self) -> List[Path]:
        """Get list of prefetch files to process.

        Returns:
            List[Path]: List of prefetch file paths
        """
        if self.path.is_file():
            return [self.path]
        elif self.path.is_dir():
            # Find all .pf files in directory
            return list(self.path.glob("*.pf"))
        else:
            raise ValueError(f"Invalid path: {self.path}")

    def gen_records(
        self, multiprocess: bool = False, chunk_size: int = 1000
    ) -> Generator[List[dict], None, None]:
        """Generate prefetch records.

        Args:
            multiprocess (bool): Flag to run multiprocessing.
            chunk_size (int): Size of the chunk to be processed for each process.

        Yields:
            Generator[List[dict], None, None]: Yields List[dict] of prefetch records.
        """
        prefetch_files = self._get_prefetch_files()

        if not prefetch_files:
            return

        if multiprocess and len(prefetch_files) > 1:
            # Use safe context for Python 3.13 compatibility
            ctx = self.get_multiprocessing_context()
            with ctx.Pool(self.get_cpu_count()) as pool:
                results = pool.map_async(
                    process_prefetch_chunk,
                    generate_chunks(chunk_size, prefetch_files),
                )
                yield list(chain.from_iterable(results.get(timeout=None)))
        else:
            # Single process mode
            buffer: List[dict] = []
            for chunk in generate_chunks(chunk_size, prefetch_files):
                processed_chunk = process_prefetch_chunk(chunk)
                buffer.extend(processed_chunk)

                if len(buffer) >= chunk_size:
                    yield buffer
                    buffer = []

            # Yield remaining records
            if buffer:
                yield buffer

    def gen_timeline_records(
        self, multiprocess: bool = False, chunk_size: int = 1000, tags: str = ""
    ) -> Generator[List[dict], None, None]:
        """Generate timeline-formatted prefetch records.

        Args:
            multiprocess (bool): Flag to run multiprocessing.
            chunk_size (int): Size of the chunk to be processed for each process.
            tags (str): Additional tags for timeline records (comma-separated).

        Yields:
            Generator[List[dict], None, None]: Yields List[dict] of timeline-formatted prefetch records.
        """
        prefetch_files = self._get_prefetch_files()

        if not prefetch_files:
            return

        if multiprocess and len(prefetch_files) > 1:
            # Use safe context for Python 3.13 compatibility
            ctx = self.get_multiprocessing_context()
            with ctx.Pool(self.get_cpu_count()) as pool:
                # Create partial function with tags
                process_func = partial(
                    process_timeline_prefetch_chunk_with_tags, tags=tags
                )
                results = pool.map_async(
                    process_func,
                    generate_chunks(chunk_size, prefetch_files),
                )
                yield list(chain.from_iterable(results.get(timeout=None)))
        else:
            # Single process mode
            buffer: List[dict] = []
            for chunk in generate_chunks(chunk_size, prefetch_files):
                processed_chunk = process_timeline_prefetch_chunk_with_tags(chunk, tags)
                buffer.extend(processed_chunk)

                if len(buffer) >= chunk_size:
                    yield buffer
                    buffer = []

            # Yield remaining records
            if buffer:
                yield buffer
