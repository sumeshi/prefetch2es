# coding: utf-8
from itertools import chain
from pathlib import Path
from tempfile import NamedTemporaryFile
import os
import stat
from typing import Sequence, Union

import orjson
from tqdm import tqdm

from prefetch2es.models.Prefetch2es import (
    PartialExtractionError,
    Prefetch2es,
    get_prefetch_files,
    validate_chunk_size,
)


class Prefetch2jsonPresenter(object):
    def __init__(
        self,
        input_path: str,
        output_path: str,
        is_quiet: bool = False,
        multiprocess: bool = False,
        chunk_size: int = 500,
        timeline_mode: bool = False,
        tags: Union[str, Sequence[str]] = "",
        output_format: str = "json",
        input_files: Sequence[Path] | None = None,
        input_diagnostics: Sequence[dict] = (),
    ):
        validate_chunk_size(chunk_size)
        if output_format not in ("json", "jsonl", "ndjson"):
            raise ValueError(f"Invalid output format: {output_format}")
        self.input_path = Path(input_path).resolve()
        self.output_format = output_format
        suffix = ".json" if output_format == "json" else ".jsonl"
        self.output_path = (
            Path(output_path) if output_path else self.input_path.with_suffix(suffix)
        )
        if (
            not output_path
            and self.output_path == self.input_path
            and self.input_path.is_dir()
        ):
            self.output_path = self.input_path.with_name(self.input_path.name + suffix)
        self.is_quiet = is_quiet
        self.multiprocess = multiprocess
        self.chunk_size = chunk_size
        self.timeline_mode = timeline_mode
        self.tags = tags
        self.input_files = input_files
        self.input_diagnostics = input_diagnostics

    def _check_output(self, input_files, input_diagnostics):
        if (
            input_diagnostics
            and self.input_path.is_dir()
            and self.output_path.resolve().is_relative_to(self.input_path)
        ):
            raise ValueError(
                "The output must not be inside an incompletely scanned input directory: "
                f"{self.input_path}"
            )
        sources = chain((self.input_path,), input_files)
        for source in sources:
            if self.output_path.resolve() == source.resolve() or (
                self.output_path.exists()
                and source.exists()
                and self.output_path.samefile(source)
            ):
                raise ValueError(
                    "The output must not overwrite an input file or directory."
                )
            if self.output_path.is_symlink():
                raise ValueError("The output path must not be a symbolic link.")

    def export_json(self) -> None:
        input_diagnostics = list(self.input_diagnostics)
        input_files = (
            get_prefetch_files([self.input_path], input_diagnostics)
            if self.input_files is None
            else list(self.input_files)
        )
        self._check_output(input_files, input_diagnostics)
        model = Prefetch2es(input_files, input_diagnostics)
        generate = (
            model.gen_timeline_records if self.timeline_mode else model.gen_records
        )
        records = generate(
            tags=self.tags,
            multiprocess=self.multiprocess,
            chunk_size=self.chunk_size,
        )
        progress = records if self.is_quiet else tqdm(records)
        temporary_path = None
        partial_error = None
        try:
            with NamedTemporaryFile(
                mode="wb",
                dir=self.output_path.parent,
                prefix=f".{self.output_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as output:
                temporary_path = Path(output.name)
                collected: list[dict] = []
                try:
                    for chunk in progress:
                        if self.output_format == "json":
                            collected.extend(chunk)
                        else:
                            for record in chunk:
                                output.write(orjson.dumps(record) + b"\n")
                except PartialExtractionError as error:
                    partial_error = error
                if partial_error is not None and model.generated_records == 0:
                    raise partial_error
                if self.output_format == "json":
                    output.write(orjson.dumps(collected, option=orjson.OPT_INDENT_2))
            self._check_output(input_files, input_diagnostics)
            if os.name == "posix" and self.output_path.exists():
                temporary_path.chmod(stat.S_IMODE(self.output_path.stat().st_mode))
            os.replace(temporary_path, self.output_path)
            if partial_error is not None:
                raise partial_error
        finally:
            try:
                if progress is not records:
                    progress.close()
                records.close()
            finally:
                if temporary_path is not None:
                    temporary_path.unlink(missing_ok=True)
