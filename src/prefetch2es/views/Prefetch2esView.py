# coding: utf-8
from typing import List
from pathlib import Path
from multiprocessing import cpu_count

from prefetch2es.views.BaseView import BaseView
from prefetch2es.presenters.Prefetch2esPresenter import Prefetch2esPresenter


class Prefetch2esView(BaseView):

    def __init__(self):
        super().__init__()
        self.define_options()
        self.args = self.parser.parse_args()

    def define_options(self):
        self.parser.add_argument(
            "prefetch_files",
            nargs="+",
            type=str,
            help="Windows Prefetch files (.pf) or directories containing them.",
        )
        self.parser.add_argument(
            "--host", default="localhost", help="ElasticSearch host"
        )
        self.parser.add_argument(
            "--port", default=9200, help="ElasticSearch port number"
        )
        self.parser.add_argument("--index", default="prefetch2es", help="Index name")
        self.parser.add_argument(
            "--scheme", default="http", help="Scheme to use (http, https)"
        )
        self.parser.add_argument(
            "--pipeline", default="", help="Ingest pipeline to use"
        )
        self.parser.add_argument(
            "--login", default="", help="Login to use to connect to Elastic database"
        )
        self.parser.add_argument(
            "--pwd", default="", help="Password associated with the login"
        )
        self.parser.add_argument(
            "--timeline",
            action="store_true",
            help="Enable timeline analysis mode (separates records by type)",
        )
        self.parser.add_argument(
            "--tags",
            default="",
            help="Comma-separated tags to add to each record for identification (e.g., hostname, domain name)",
        )

    def __list_prefetch_files(self, prefetch_files: List[str]) -> List[Path]:
        prefetch_path_list = list()
        for prefetch_file in prefetch_files:
            if Path(prefetch_file).is_dir():
                prefetch_path_list.extend(Path(prefetch_file).glob("**/*.pf"))
            else:
                prefetch_path_list.append(Path(prefetch_file))

        return prefetch_path_list

    def run(self):
        view = Prefetch2esView()
        prefetch_files = self.__list_prefetch_files(self.args.prefetch_files)

        if self.args.multiprocess:
            view.log(f"Multi-Process: {cpu_count()}", self.args.quiet)

        if self.args.timeline:
            view.log("Timeline analysis mode enabled", self.args.quiet)

        for prefetch_file in prefetch_files:
            view.log(f"Currently Importing {prefetch_file}.", self.args.quiet)

            Prefetch2esPresenter(
                input_path=prefetch_file,
                host=self.args.host,
                port=int(self.args.port),
                index=self.args.index,
                scheme=self.args.scheme,
                pipeline=self.args.pipeline,
                login=self.args.login,
                pwd=self.args.pwd,
                is_quiet=self.args.quiet,
                multiprocess=self.args.multiprocess,
                chunk_size=int(self.args.size),
                logger=self.log,
                timeline_mode=self.args.timeline,
                tags=self.args.tags,
            ).bulk_import()

        view.log("Import completed.", self.args.quiet)


def entry_point():
    Prefetch2esView().run()


if __name__ == "__main__":
    entry_point()
