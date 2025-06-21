# coding: utf-8
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
            "prefetch_file", type=str, help="Windows Prefetch file (.pf) to input."
        )
        self.parser.add_argument(
            "--output-file",
            "-o",
            type=str,
            default="",
            help="json file path to output.",
        )
        self.parser.add_argument(
            "--timeline",
            action="store_true",
            help="Enable timeline analysis mode (separates records by type)",
        )
        self.parser.add_argument(
            "--tags",
            default="",
            help="Additional tags for timeline records (comma-separated)",
        )

    def run(self):
        view = Prefetch2jsonView()
        view.log(f"Converting {self.args.prefetch_file}.", self.args.quiet)

        if self.args.multiprocess:
            view.log(f"Multi-Process: {cpu_count()}", self.args.quiet)

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
        ).export_json()

        view.log("Converted.", self.args.quiet)


def entry_point():
    Prefetch2jsonView().run()


if __name__ == "__main__":
    entry_point()
