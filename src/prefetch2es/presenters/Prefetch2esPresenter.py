# coding: utf-8
from pathlib import Path
from typing import Sequence, Union

from prefetch2es.models.Prefetch2es import Prefetch2es, validate_chunk_size
from prefetch2es.models.ElasticsearchUtils import ElasticsearchUtils


class Prefetch2esPresenter(object):

    def __init__(
        self,
        input_path: Union[Path, Sequence[Path]],
        host: str = "localhost",
        port: int = 9200,
        index: str = "prefetch2es",
        scheme: str = "http",
        pipeline: str = "",
        login: str = "",
        pwd: str = "",
        is_quiet: bool = False,
        multiprocess: bool = False,
        chunk_size: int = 500,
        logger=None,
        timeline_mode: bool = True,
        tags: Union[str, Sequence[str]] = "",
        verify_certs: bool = True,
        ca_certs: str | None = None,
        input_diagnostics: Sequence[dict] = (),
    ):
        validate_chunk_size(chunk_size)
        self.input_path = input_path
        self.host = host
        self.port = port
        self.index = index
        self.scheme = scheme
        self.pipeline = pipeline
        self.login = login
        self.pwd = pwd
        self.is_quiet = is_quiet
        self.multiprocess = multiprocess
        self.chunk_size = chunk_size
        self.logger = logger
        self.timeline_mode = timeline_mode
        self.tags = tags
        self.verify_certs = verify_certs
        self.ca_certs = ca_certs
        self.input_diagnostics = input_diagnostics

    def prefetch2es(self):
        prefetch2es = Prefetch2es(self.input_path, self.input_diagnostics)

        # Timeline mode uses specialized record generation
        if self.timeline_mode:
            for records in prefetch2es.gen_timeline_records(
                multiprocess=self.multiprocess,
                chunk_size=self.chunk_size,
                tags=self.tags,
            ):
                yield records
        else:
            for records in prefetch2es.gen_records(
                multiprocess=self.multiprocess,
                chunk_size=self.chunk_size,
                tags=self.tags,
            ):
                yield records

    def bulk_import(self):
        es = ElasticsearchUtils(
            hostname=self.host,
            port=self.port,
            scheme=self.scheme,
            login=self.login,
            pwd=self.pwd,
            verify_certs=self.verify_certs,
            ca_certs=self.ca_certs,
        )
        chunks = None
        total_success = 0
        batch_count = 0
        try:
            chunks = self.prefetch2es()
            for records in chunks:
                success, failed = es.bulk_indice(records, self.index, self.pipeline)
                total_success += success
                batch_count += 1
                if failed:
                    details = []
                    for item in failed[:3]:
                        for operation, result in item.items():
                            if not isinstance(result, dict):
                                continue
                            error = result.get("error", {})
                            if not isinstance(error, dict):
                                error = {"reason": str(error)}
                            details.append(
                                f"{operation} id={result.get('_id', '?')} "
                                f"status={result.get('status', '?')} "
                                f"{error.get('type', 'error')}: "
                                f"{str(error.get('reason', 'unknown'))[:500]}"
                            )
                    raise RuntimeError(
                        f"Elasticsearch failed to index {len(failed)} document(s); "
                        f"{total_success} indexed before stopping. "
                        + "; ".join(details)
                    )
        finally:
            try:
                close = getattr(chunks, "close", None)
                if close is not None:
                    close()
            finally:
                es.close()
        if self.logger:
            self.logger(
                f"Bulk import completed: {batch_count} batches processed",
                self.is_quiet,
            )
            self.logger(
                f"Successfully indexed: {total_success} documents", self.is_quiet
            )
