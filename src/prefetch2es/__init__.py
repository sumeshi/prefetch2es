# coding: utf-8
from typing import List
from pathlib import Path

from prefetch2es.models.Prefetch2es import Prefetch2es
from prefetch2es.presenters.Prefetch2esPresenter import Prefetch2esPresenter


# for use via python-script!


def prefetch2es(
    input_path: str,
    host: str = "localhost",
    port: int = 9200,
    index: str = "prefetch2es",
    scheme: str = "http",
    pipeline: str = "",
    login: str = "",
    pwd: str = "",
    multiprocess: bool = False,
    chunk_size: int = 500,
    timeline_mode: bool = False,
    tags: str = "",
) -> None:
    """Fast import of Windows Prefetch into Elasticsearch.
    Args:
        input_path (str):
            Windows Prefetch files or directory to import into Elasticsearch.

        host (str, optional):
            Elasticsearch host address. Defaults to "localhost".

        port (int, optional):
            Elasticsearch port number. Defaults to 9200.

        index (str, optional):
            Name of the index to create. Defaults to "prefetch2es".

        scheme (str, optional):
            Elasticsearch address scheme. Defaults to "http".

        pipeline (str, optional):
            Elasticsearch Ingest Pipeline. Defaults to "".

        login (str, optional):
            Elasticsearch login to connect into.

        pwd (str, optional):
            Elasticsearch password associated with the login provided.

        multiprocess (bool, optional):
            Flag to run multiprocessing.

        chunk_size (int, optional):
            Size of the chunk to be processed for each process.

        timeline_mode (bool, optional):
            Enable timeline analysis mode - creates specialized records
            for Prefetch timeline analysis.

        tags (str, optional):
            Additional tags for timeline records (comma-separated).
    """

    Prefetch2esPresenter(
        input_path=Path(input_path),
        host=host,
        port=int(port),
        index=index,
        scheme=scheme,
        pipeline=pipeline,
        login=login,
        pwd=pwd,
        is_quiet=True,
        multiprocess=multiprocess,
        chunk_size=int(chunk_size),
        timeline_mode=timeline_mode,
        tags=tags,
    ).bulk_import()


def prefetch2json(
    filepath: str,
    multiprocess: bool = False,
    chunk_size: int = 500,
    timeline_mode: bool = False,
    tags: str = "",
) -> List[dict]:
    """Convert Windows Prefetch to List[dict].

    Args:
        filepath (str): Input Prefetch file or directory.
        multiprocess (bool): Flag to run multiprocessing.
        chunk_size (int): Size of the chunk to be processed for each process.
        timeline_mode (bool): Enable timeline analysis mode - creates specialized records.
        tags (str): Additional tags for timeline records (comma-separated).

    Note:
        Since the content of the file is loaded into memory at once,
        it requires the same amount of memory as the file to be loaded.
    """
    prefetch = Prefetch2es(Path(filepath).resolve())
    if timeline_mode:
        timeline_records: List[dict] = sum(
            list(
                prefetch.gen_timeline_records(
                    multiprocess=multiprocess, chunk_size=chunk_size, tags=tags
                )
            ),
            list(),
        )
        return timeline_records
    else:
        standard_records: List[dict] = sum(
            list(
                prefetch.gen_records(multiprocess=multiprocess, chunk_size=chunk_size)
            ),
            list(),
        )
        return standard_records
