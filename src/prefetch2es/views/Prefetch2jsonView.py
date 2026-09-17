# coding: utf-8
import sys
from pathlib import Path
from multiprocessing import cpu_count

from prefetch2es.views.BaseView import BaseView
from prefetch2es.presenters.Prefetch2jsonPresenter import Prefetch2jsonPresenter


class Prefetch2jsonView(BaseView):

    def __init__(self):
        super().__init__()
        self.define_options()
        self.args = self.parser.parse_args()

    def define_options(self):
        self.parser.add_argument(
            "--format",
            choices=("json", "jsonl", "ndjson"),
            default="json",
            help=(
                "Output format (default: json). "
                "JSONL/NDJSON writes one record per line."
            ),
        )
        self.parser.add_argument(
            "prefetch_file",
            type=str,
            help="Input Windows Prefetch file (.pf) or directory.",
        )
        self.parser.add_argument(
            "--output-file",
            "-o",
            type=str,
            default="",
            help="Output file path.",
        )
        self.parser.add_argument(
            "--timeline",
            action="store_true",
            help="Enable timeline analysis mode (separate records by type).",
        )
        self.parser.add_argument(
            "--tags",
            default="",
            help="Additional comma-separated tags for timeline records.",
        )

    def run(self):
        view = self
        source = Path(self.args.prefetch_file)
        if not source.is_file() and not source.is_dir():
            self.parser.error(
                f"Input path does not exist or is not a file/directory: {source}"
            )
        if source.is_dir() and not any(p.is_file() for p in source.glob("*.pf")):
            self.parser.error(f"No Prefetch files found: {source}")
        view.log(f"Converting {self.args.prefetch_file}.", self.args.quiet)

        if self.args.multiprocess:
            view.log(f"Multiprocessing enabled ({cpu_count()} workers).", self.args.quiet)

        if self.args.timeline:
            view.log("Timeline analysis mode enabled", self.args.quiet)

        Prefetch2jsonPresenter(
            input_path=self.args.prefetch_file,
            output_path=self.args.output_file,
            is_quiet=self.args.quiet,
            multiprocess=self.args.multiprocess,
            chunk_size=self.args.size,
            timeline_mode=self.args.timeline,
            tags=self.args.tags,
            output_format=self.args.format,
        ).export_json()

        view.log("Conversion completed successfully.", self.args.quiet)


def entry_point():
    try:
        Prefetch2jsonView().run()
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    entry_point()
