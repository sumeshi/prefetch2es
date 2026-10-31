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
            mode = "timeline" if timeline else "standard"
            index = new_index(f"timestamp-recovery-{mode}")
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

    run_volume_recovery_cases(client, new_index, stored_documents, document_id)
    run_unicode_recovery_cases(client, new_index, stored_documents, document_id)
    run_native_unicode_getter_recovery_cases(
        client, new_index, stored_documents, document_id
    )


def run_volume_recovery_cases(client, new_index, stored_documents, document_id):
    """Recovered volume metadata supports date searches in either arrival order."""
    artifact = runpy.run_path(str(Path(__file__).with_name("artifact_fixture.py")))
    address = urlsplit(os.environ["ELASTICSEARCH_URL"])
    with TemporaryDirectory() as directory:
        sources = {}
        for label, volume_time in (("date", 130968655538095417), ("null", 2**64 - 1)):
            sources[label] = artifact["create_timestamp_artifact"](
                Path(directory) / label,
                [130968655538095417, 130968655548095417],
                volume_timestamps=(volume_time,),
            )
        for timeline in (False, True):
            healthy = prefetch2json(str(sources["date"]), timeline_mode=timeline)
            try:
                prefetch2json(str(sources["null"]), timeline_mode=timeline)
            except PartialExtractionError as error:
                recovered, diagnostics = error.records, error.diagnostics
            else:
                raise AssertionError(
                    "Invalid volume time must report partial extraction"
                )
            expected_count = 2 if timeline else 1
            assert len(healthy) == len(recovered) == expected_count
            assert len(diagnostics) == 1
            assert diagnostics[0]["stage"] == "volume_creation_time"
            assert diagnostics[0]["volume_index"] == 0
            assert diagnostics[0]["raw"] == 2**64 - 1
            for document in recovered:
                metadata = document["windows"]["prefetch"] if timeline else document
                assert metadata["volumes"][0]["creation_time"] is None
                assert metadata["volumes"][0]["path"] == "\\DEVICE\\VOLUME"
                assert metadata["volumes"][0]["serial_number"] == "4D2"
                assert metadata["metrics"]
            mode = "timeline" if timeline else "standard"
            for order in (("date", "null"), ("null", "date")):
                index = new_index(f"volume-recovery-{mode}-{order[0]}-first")
                for label in order:
                    try:
                        prefetch2es(
                            str(sources[label]),
                            host=address.hostname,
                            port=address.port
                            or (443 if address.scheme == "https" else 80),
                            scheme=address.scheme,
                            login=unquote(address.username or ""),
                            pwd=unquote(address.password or ""),
                            index=index,
                            timeline_mode=timeline,
                            chunk_size=1,
                        )
                    except PartialExtractionError as error:
                        assert label == "null" and error.diagnostics == diagnostics
                    else:
                        assert label == "date"
                assert stored_documents(client, index) == {
                    document_id(record): record for record in [*healthy, *recovered]
                }
                field = (
                    "windows.prefetch.volumes.creation_time"
                    if timeline
                    else "volumes.creation_time"
                )
                mapping = client.indices.get_mapping(index=index)[index]["mappings"]
                for part in field.split("."):
                    mapping = mapping["properties"][part]
                assert mapping["type"] == "date"
                assert (
                    client.count(index=index, query={"exists": {"field": field}})[
                        "count"
                    ]
                    == expected_count
                )
                assert (
                    client.count(
                        index=index,
                        query={
                            "range": {field: {"gte": "2016-01-01", "lt": "2017-01-01"}}
                        },
                    )["count"]
                    == expected_count
                )
                execution_field = "@timestamp" if timeline else "last_exec_times"
                assert (
                    client.count(
                        index=index,
                        query={
                            "range": {
                                execution_field: {
                                    "gte": "2016-01-01",
                                    "lt": "2017-01-01",
                                }
                            }
                        },
                    )["count"]
                    == 2 * expected_count
                )


def run_unicode_recovery_cases(client, new_index, stored_documents, document_id):
    """Escaped names remain searchable and exact original code units are stored."""
    artifact = runpy.run_path(str(Path(__file__).with_name("artifact_fixture.py")))
    address = urlsplit(os.environ["ELASTICSEARCH_URL"])
    display = r"\ud800EST.EXE"
    raw = "\ud800EST.EXE".encode("utf-16le", "surrogatepass").hex()
    with TemporaryDirectory() as directory:
        root = Path(directory)
        for label, name in (
            ("a-good", "TEST.EXE"),
            ("b-bad", "\ud800EST.EXE"),
            ("c-literal", display),
        ):
            source = artifact["create_timestamp_artifact"](
                root / label, [130968655538095417, 130968655548095417]
            )
            payload = bytearray(source.read_bytes())
            payload[16:76] = name.encode("utf-16le", "surrogatepass").ljust(60, b"\0")
            source.write_bytes(payload)
        for timeline in (False, True):
            try:
                prefetch2json(str(root), timeline_mode=timeline)
            except PartialExtractionError as error:
                records, diagnostics = error.records, error.diagnostics
            else:
                raise AssertionError("Invalid Unicode must report partial extraction")
            assert len(records) == (6 if timeline else 3)
            assert len(diagnostics) == 1
            assert diagnostics[0]["stage"] == "unicode"
            assert diagnostics[0]["utf16le"] == raw
            mode = "timeline" if timeline else "standard"
            index = new_index(f"unicode-recovery-{mode}")
            try:
                prefetch2es(
                    str(root),
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
                raise AssertionError("ES ingestion must report partial extraction")
            assert stored_documents(client, index) == {
                document_id(record): record for record in records
            }
            name_field = "process.name.keyword" if timeline else "name.keyword"
            raw_field = (
                "windows.prefetch.invalid_unicode.utf16le.keyword"
                if timeline
                else "invalid_unicode.utf16le.keyword"
            )
            assert client.count(index=index, query={"term": {name_field: display}})[
                "count"
            ] == (4 if timeline else 2)
            assert client.count(index=index, query={"term": {raw_field: raw}})[
                "count"
            ] == (2 if timeline else 1)


def run_native_unicode_getter_recovery_cases(
    client, new_index, stored_documents, document_id
):
    """Native string getter failures retain records and index null fields."""
    artifact = runpy.run_path(str(Path(__file__).with_name("artifact_fixture.py")))
    address = urlsplit(os.environ["ELASTICSEARCH_URL"])
    cases = {
        "metric": (348, "metrics[0].filename"),
        "volume": (480, "volumes[0].path"),
    }
    with TemporaryDirectory() as directory:
        for kind, (offset, field) in cases.items():
            root = Path(directory) / kind
            sources = [
                artifact["create_timestamp_artifact"](
                    root / label, [130968655538095417, 130968655548095417]
                )
                for label in ("a-good", "b-bad", "c-good")
            ]
            payload = bytearray(sources[1].read_bytes())
            payload[offset : offset + 2] = b"\x00\xd8"
            sources[1].write_bytes(payload)
            for timeline in (False, True):
                try:
                    prefetch2json(str(root), timeline_mode=timeline)
                except PartialExtractionError as error:
                    records, diagnostics = error.records, error.diagnostics
                else:
                    raise AssertionError(
                        "Unreadable native text must report partial extraction"
                    )
                native_diagnostics = [
                    diagnostic
                    for diagnostic in diagnostics
                    if diagnostic.get("stage") == "native_metadata"
                ]
                assert len(native_diagnostics) == 1
                assert native_diagnostics[0]["field"] == field
                assert len(records) == (6 if timeline else 3)
                mode = "timeline" if timeline else "standard"
                index = new_index(f"native-getter-{kind}-{mode}")
                try:
                    prefetch2es(
                        str(root),
                        host=address.hostname,
                        port=address.port
                        or (443 if address.scheme == "https" else 80),
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
                    raise AssertionError("ES ingestion must report partial extraction")
                assert stored_documents(client, index) == {
                    document_id(record): record for record in records
                }
                affected = [
                    record
                    for record in records
                    if (
                        record["log"]["file"]["path"]
                        if timeline
                        else record["source_file"]
                    )
                    == str(sources[1])
                ]
                assert len(affected) == (2 if timeline else 1)
                for record in affected:
                    metadata = (
                        record["windows"]["prefetch"] if timeline else record
                    )
                    assert metadata["metrics"] and metadata["volumes"]
                    target = (
                        metadata["metrics"][0]["filename"]
                        if kind == "metric"
                        else metadata["volumes"][0]["path"]
                    )
                    assert target is None
