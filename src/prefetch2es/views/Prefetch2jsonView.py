# coding: utf-8
import sys
from multiprocessing import cpu_count

from prefetch2es.views.BaseView import BaseView
from prefetch2es.models.Prefetch2es import get_prefetch_files
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
            help="Comma-separated tags for Standard and Timeline records.",
        )

    def run(self):
        view = self
        input_diagnostics = []
        input_files = get_prefetch_files(
            [self.args.prefetch_file], input_diagnostics
        )
        view.log(f"Converting {self.args.prefetch_file}.", self.args.quiet)

        if self.args.multiprocess:
            message = (
                f"Multiprocessing enabled (up to {min(cpu_count(), len(input_files))} workers)."
                if len(input_files) > 1
                else "One input file; processing serially."
            )
            view.log(message, self.args.quiet)

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
            input_files=input_files,
            input_diagnostics=input_diagnostics,
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
