# coding: utf-8
from typing import List, Sequence, Union
from pathlib import Path

from prefetch2es.__about__ import __version__
from prefetch2es.models.Prefetch2es import (
    PartialExtractionError,
    Prefetch2es,
    validate_chunk_size,
)
from prefetch2es.presenters.Prefetch2esPresenter import Prefetch2esPresenter

__all__ = ["__version__", "prefetch2es", "prefetch2json", "PartialExtractionError"]


# Public Python API.


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
    timeline_mode: bool = True,
    tags: Union[str, Sequence[str]] = "",
) -> None:
    """Import Windows Prefetch records into Elasticsearch.
    Args:
        input_path (str):
            Windows Prefetch files or a directory to import into Elasticsearch.

        host (str, optional):
            Elasticsearch host address. Defaults to "localhost".

        port (int, optional):
            Elasticsearch port. Defaults to 9200.

        index (str, optional):
            Name of the index to create. Defaults to "prefetch2es".

        scheme (str, optional):
            Connection scheme. Defaults to "http".

        pipeline (str, optional):
            Elasticsearch ingest pipeline. Defaults to "".

        login (str, optional):
            Elasticsearch username.

        pwd (str, optional):
            Password for Elasticsearch authentication.

        multiprocess (bool, optional):
            Enable multiprocessing.

        chunk_size (int, optional):
            Maximum documents per output chunk.

        timeline_mode (bool, optional):
            Enable timeline analysis mode (default: True) and create specialized timeline
            records for Prefetch execution events.

        tags (str or Sequence[str], optional):
            Comma-separated string or sequence of tags to add to records.

    """

    validate_chunk_size(chunk_size)
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
        chunk_size=chunk_size,
        timeline_mode=timeline_mode,
        tags=tags,
    ).bulk_import()


def prefetch2json(
    filepath: str,
    multiprocess: bool = False,
    chunk_size: int = 500,
    timeline_mode: bool = True,
    tags: Union[str, Sequence[str]] = "",
) -> List[dict]:
    """Convert Windows Prefetch files to a list of dictionaries.

    Args:
        filepath (str): Input Prefetch file or directory.
        multiprocess (bool): Flag to run multiprocessing.
        chunk_size (int): Maximum documents per output chunk.
        timeline_mode (bool): Enable timeline analysis mode (default: True).
        tags (str or Sequence[str]): Comma-separated string or sequence of tags.

    Note:
        Since the content of the file is loaded into memory at once,
        it requires the same amount of memory as the file to be loaded.
    """
    validate_chunk_size(chunk_size)
    prefetch = Prefetch2es(Path(filepath).resolve())
    generate = prefetch.gen_timeline_records if timeline_mode else prefetch.gen_records
    records: List[dict] = []
    try:
        for chunk in generate(
            multiprocess=multiprocess,
            chunk_size=chunk_size,
            tags=tags,
        ):
            records.extend(chunk)
    except PartialExtractionError as error:
        error.records = records
        raise
    return records
