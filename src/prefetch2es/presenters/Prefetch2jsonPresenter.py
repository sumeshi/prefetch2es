# coding: utf-8
from itertools import chain
from pathlib import Path

import orjson
from tqdm import tqdm

from prefetch2es.models.Prefetch2es import Prefetch2es


class Prefetch2jsonPresenter(object):
    def __init__(
        self,
        input_path: str,
        output_path: str,
        is_quiet: bool = False,
        multiprocess: bool = False,
        chunk_size: int = 500,
        timeline_mode: bool = False,
        tags: str = "",
        output_format: str = "json",
    ):
        if output_format not in ("json", "jsonl", "ndjson"):
            raise ValueError(f"Invalid output format: {output_format}")
        self.input_path = Path(input_path).resolve()
        self.output_format = output_format
        suffix = ".json" if output_format == "json" else ".jsonl"
        self.output_path = Path(output_path) if output_path else self.input_path.with_suffix(suffix)
        if not output_path and self.output_path == self.input_path and self.input_path.is_dir():
            self.output_path = self.input_path.with_name(self.input_path.name + suffix)
        self.is_quiet = is_quiet
        self.multiprocess = multiprocess
        self.chunk_size = chunk_size
        self.timeline_mode = timeline_mode
        self.tags = tags

    def export_json(self) -> None:
        # Check identity before opening an output (including directory inputs).
        sources = chain((self.input_path,), self.input_path.rglob("*.pf")) if self.input_path.is_dir() else (self.input_path,)
        for source in sources:
            if self.output_path.resolve() == source.resolve() or (
                self.output_path.exists() and source.exists() and self.output_path.samefile(source)
            ):
                raise ValueError(
                    "The output must not overwrite an input file or directory."
                )
            if self.output_path.is_symlink():
                raise ValueError("The output path must not be a symbolic link.")
        model = Prefetch2es(self.input_path)
        kwargs = dict(multiprocess=self.multiprocess, chunk_size=self.chunk_size)
        records = (model.gen_timeline_records(tags=self.tags, **kwargs)
                   if self.timeline_mode else model.gen_records(**kwargs))
        progress = records if self.is_quiet else tqdm(records)
        try:
            if self.output_format == "json":
                self.output_path.write_bytes(orjson.dumps(
                    list(chain.from_iterable(progress)), option=orjson.OPT_INDENT_2
                ))
            else:
                with self.output_path.open("wb") as output:
                    for chunk in progress:
                        for record in chunk:
                            output.write(orjson.dumps(record) + b"\n")
        finally:
            if progress is not records:
                progress.close()
            records.close()
