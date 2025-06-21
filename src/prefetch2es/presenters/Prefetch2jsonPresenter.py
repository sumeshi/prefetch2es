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
    ):
        self.input_path = Path(input_path).resolve()
        self.output_path: Path = (
            Path(output_path)
            if output_path
            else Path(self.input_path).with_suffix(".json")
        )
        self.is_quiet = is_quiet
        self.multiprocess = multiprocess
        self.chunk_size = chunk_size
        self.timeline_mode = timeline_mode
        self.tags = tags

    def export_json(self) -> None:
        r = Prefetch2es(self.input_path)

        # Use unified generation function with timeline mode parameter
        if self.timeline_mode:
            generator = (
                r.gen_timeline_records(
                    multiprocess=self.multiprocess,
                    chunk_size=self.chunk_size,
                    tags=self.tags,
                )
                if self.is_quiet
                else tqdm(
                    r.gen_timeline_records(
                        multiprocess=self.multiprocess,
                        chunk_size=self.chunk_size,
                        tags=self.tags,
                    )
                )
            )
        else:
            generator = (
                r.gen_records(
                    multiprocess=self.multiprocess,
                    chunk_size=self.chunk_size,
                )
                if self.is_quiet
                else tqdm(
                    r.gen_records(
                        multiprocess=self.multiprocess,
                        chunk_size=self.chunk_size,
                    )
                )
            )

        self.output_path.write_text(
            orjson.dumps(
                list(chain.from_iterable(generator)), option=orjson.OPT_INDENT_2
            ).decode("utf-8")
        )
