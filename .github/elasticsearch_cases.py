"""Prefetch execution times and metrics survive real ES indexing."""

from copy import deepcopy
import os
from pathlib import Path
import runpy
from tempfile import TemporaryDirectory
from urllib.parse import unquote, urlsplit

from prefetch2es import PartialExtractionError, prefetch2es, prefetch2json


def expected_source(document):
    return deepcopy(document)


def assert_native_documents(documents, mode):
    assert len(documents) == (2 if mode else 1)
    if mode:
        assert all(document["process"]["name"] == "CALC.EXE" for document in documents)
        assert len({document["@timestamp"] for document in documents}) == 2
        assert all(document["windows"]["prefetch"]["metrics"] for document in documents)
    else:
        assert documents[0]["name"] == "CALC.EXE"
        assert len(documents[0]["last_exec_times"]) == 2


def run_extra_cases(client, transport, new_index, stored_documents, document_id):
    artifact = runpy.run_path(str(Path(__file__).with_name("artifact_fixture.py")))
    with TemporaryDirectory() as directory:
        source = artifact["create_artifact"](Path(directory))
        documents = prefetch2json(str(source), timeline_mode=True)
    index = new_index("metrics-and-dates")
    client.indices.create(
        index=index,
        mappings={
            "properties": {
                "@timestamp": {"type": "date"},
                "process": {"properties": {"start": {"type": "date"}}},
                "windows": {
                    "properties": {
                        "prefetch": {
                            "properties": {
                                "metrics": {
                                    "properties": {
                                        "file_reference": {"type": "keyword"}
                                    }
                                },
                            }
                        }
                    }
                },
            }
        },
    )
    assert transport.bulk_indice(documents, index) == (2, [])
    actual = stored_documents(client, index)
    assert actual == {document_id(document): document for document in documents}
    reference = documents[0]["windows"]["prefetch"]["metrics"][0]["file_reference"]
    assert (
        client.count(
            index=index,
            query={"term": {"windows.prefetch.metrics.file_reference": reference}},
        )["count"]
        == 2
    )
    assert (
        client.count(
            index=index,
            query={
                "range": {
                    "@timestamp": {
                        "gte": "2016-01-01T00:00:00Z",
                        "lt": "2017-01-01T00:00:00Z",
                    }
                }
            },
        )["count"]
        == 2
    )
    address = urlsplit(os.environ["ELASTICSEARCH_URL"])
    with TemporaryDirectory() as directory:
        source = artifact["create_timestamp_artifact"](
            Path(directory), [2**64 - 1, 130968655538095417]
        )
        for timeline in (False, True):
            try:
                prefetch2json(str(source), timeline_mode=timeline)
            except PartialExtractionError as error:
                recovered = error.records
                diagnostics = error.diagnostics
            else:
                raise AssertionError(
                    "An invalid timestamp must report partial extraction"
                )
            assert len(recovered) == len(diagnostics) == 1
            assert diagnostics[0]["timestamp_index"] == 0
            assert diagnostics[0]["raw"] == 2**64 - 1
            index = new_index(f"timestamp-recovery-{timeline}")
            try:
                prefetch2es(
                    str(source),
                    host=address.hostname,
                    port=address.port or (443 if address.scheme == "https" else 80),
                    scheme=address.scheme,
                    login=unquote(address.username or ""),
                    pwd=unquote(address.password or ""),
                    index=index,
                    timeline_mode=timeline,
                    chunk_size=1,
                )
            except PartialExtractionError as error:
                assert error.diagnostics == diagnostics
            else:
                raise AssertionError("ES ingestion must also report partial extraction")
            assert stored_documents(client, index) == {
                document_id(record): record for record in recovered
            }
            field = "@timestamp" if timeline else "last_exec_times"
            assert (
                client.count(
                    index=index,
                    query={"range": {field: {"gte": "2016-01-01", "lt": "2017-01-01"}}},
                )["count"]
                == 1
            )
