# coding: utf-8
import sys
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
            "--no-verify-certs",
            action="store_true",
            help="Disable TLS certificate verification.",
        )
        self.parser.add_argument(
            "--ca-certs",
            default=None,
            help="Path to a CA certificate bundle for TLS verification.",
        )
        self.parser.add_argument(
            "prefetch_files",
            nargs="+",
            type=str,
            help="Input Prefetch files (.pf) or directories containing them.",
        )
        self.parser.add_argument(
            "--host", default="localhost", help="Elasticsearch host."
        )
        self.parser.add_argument(
            "--port", default=9200, type=int, help="Elasticsearch port."
        )
        self.parser.add_argument(
            "--index", default="prefetch2es", help="Elasticsearch index name."
        )
        self.parser.add_argument(
            "--scheme", default="http", help="Connection scheme (http or https)."
        )
        self.parser.add_argument(
            "--pipeline", default="", help="Elasticsearch ingest pipeline to use."
        )
        self.parser.add_argument(
            "--login",
            default="",
            help="Username for Elasticsearch authentication.",
        )
        self.parser.add_argument(
            "--pwd",
            default="",
            help="Password for Elasticsearch authentication.",
        )
        self.parser.add_argument(
            "--timeline",
            action="store_true",
            help="Enable timeline analysis mode (separate records by type).",
        )
        self.parser.add_argument(
            "--tags",
            default="",
            help=(
                "Comma-separated tags to add to each record "
                "(e.g., hostname, domain name)."
            ),
        )

    def __list_prefetch_files(self, prefetch_files: List[str]) -> List[Path]:
        prefetch_path_list = list()
        for prefetch_file in prefetch_files:
            if Path(prefetch_file).is_dir():
                prefetch_path_list.extend(Path(prefetch_file).glob("**/*.pf"))
            elif Path(prefetch_file).is_file():
                prefetch_path_list.append(Path(prefetch_file))
            else:
                self.parser.error(
                    f"Input path does not exist or is not a file/directory: "
                    f"{prefetch_file}"
                )

        prefetch_path_list = [p for p in prefetch_path_list if p.is_file()]
        if not prefetch_path_list:
            self.parser.error("No Prefetch files found.")
        return prefetch_path_list

    def run(self):
        view = self
        prefetch_files = self.__list_prefetch_files(self.args.prefetch_files)

        if self.args.multiprocess:
            view.log(f"Multiprocessing enabled ({cpu_count()} workers).", self.args.quiet)

        if self.args.timeline:
            view.log("Timeline analysis mode enabled", self.args.quiet)

        for prefetch_file in prefetch_files:
            view.log(f"Importing {prefetch_file}...", self.args.quiet)

            Prefetch2esPresenter(
                input_path=prefetch_file,
                host=self.args.host,
                ca_certs=self.args.ca_certs,
                port=self.args.port,
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
                verify_certs=not self.args.no_verify_certs,
            ).bulk_import()

        view.log("Import completed successfully.", self.args.quiet)


def entry_point():
    try:
        Prefetch2esView().run()
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    entry_point()
