"""Native strings with invalid Unicode retain originals without aborting exports."""

import hashlib
import importlib
import os
from pathlib import Path
import pickle
import runpy
import subprocess
import sys

import orjson
import pytest

from prefetch2es import PartialExtractionError, prefetch2json

model = importlib.import_module("prefetch2es.models.Prefetch2es")
FIXTURE = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / ".github" / "artifact_fixture.py")
)["create_timestamp_artifact"]
VALID = 130968655538095417
BAD_NAME = "\ud800EST.EXE"
DISPLAY_NAME = r"\ud800EST.EXE"
RAW_NAME = BAD_NAME.encode("utf-16le", "surrogatepass").hex()


def write_name(source, name):
    payload = bytearray(source.read_bytes())
    encoded = name.encode("utf-16le", "surrogatepass")
    assert len(encoded) <= 60
    payload[16:76] = encoded.ljust(60, b"\0")
    source.write_bytes(payload)
    return source


def metadata(record, timeline):
    return record["windows"]["prefetch"] if timeline else record


def name(record, timeline):
    return record["process"]["name"] if timeline else record["name"]


@pytest.mark.parametrize("timeline", [False, True])
def test_native_unicode_recovery_preserves_exact_raw_and_distinguishes_literal_text(
    tmp_path, timeline
):
    source = write_name(FIXTURE(tmp_path, [VALID, VALID + 10000000]), BAD_NAME)
    original = source.read_bytes()
    native = model.pyscca.file()
    try:
        native.open(str(source))
        assert (
            native.executable_filename.encode("utf-16le", "surrogatepass").hex()
            == RAW_NAME
        )
    finally:
        native.close()
    with pytest.raises(PartialExtractionError) as caught:
        prefetch2json(str(source), timeline_mode=timeline)
    error = caught.value
    assert len(error.records) == (2 if timeline else 1)
    field = "process.name" if timeline else "name"
    assert len(error.diagnostics) == 1
    diagnostic = error.diagnostics[0]
    assert diagnostic["source_file"] == str(source)
    assert diagnostic["stage"] == "unicode"
    assert diagnostic["field"] == field
    assert diagnostic["utf16le"] == RAW_NAME
    assert diagnostic["error"].startswith("UnicodeEncodeError:")
    for record in error.records:
        assert name(record, timeline) == DISPLAY_NAME
        assert metadata(record, timeline)["invalid_unicode"] == [
            {"field": field, "utf16le": RAW_NAME}
        ]
        assert metadata(record, timeline)["metrics"]
        orjson.dumps(record)
    transported = pickle.loads(pickle.dumps(error))
    assert transported.records == error.records
    assert transported.diagnostics == error.diagnostics
    assert source.read_bytes() == original
    recovered = error.records
    write_name(source, DISPLAY_NAME)
    literal = prefetch2json(str(source), timeline_mode=timeline)
    assert [name(record, timeline) for record in literal] == [DISPLAY_NAME] * len(
        literal
    )
    assert all(
        "invalid_unicode" not in metadata(record, timeline) for record in literal
    )
    assert [
        hashlib.sha1(orjson.dumps(record, option=orjson.OPT_SORT_KEYS)).hexdigest()
        for record in recovered
    ] != [
        hashlib.sha1(orjson.dumps(record, option=orjson.OPT_SORT_KEYS)).hexdigest()
        for record in literal
    ]


@pytest.mark.parametrize("timeline", [False, True])
@pytest.mark.parametrize("multiprocess", [False, True])
def test_native_unicode_recovers_three_files_and_spawn_reports_partial_failure(
    tmp_path, monkeypatch, timeline, multiprocess
):
    sources = [
        FIXTURE(tmp_path / directory, [VALID, VALID + 10000000])
        for directory in ("a", "b", "c")
    ]
    write_name(sources[1], BAD_NAME)
    monkeypatch.setattr(model.Prefetch2es, "get_cpu_count", lambda self: 2)
    reader = model.Prefetch2es(sources)
    generate = reader.gen_timeline_records if timeline else reader.gen_records
    records = []
    with pytest.raises(PartialExtractionError):
        for chunk in generate(multiprocess=multiprocess, chunk_size=1):
            assert len(chunk) == 1
            records.extend(chunk)
    assert len(records) == reader.generated_records == (6 if timeline else 3)
    assert reader.successful_files == 2
    assert len(reader.diagnostics) == 1
    assert sum(name(record, timeline) == "TEST.EXE" for record in records) == (
        4 if timeline else 2
    )
    assert sum(name(record, timeline) == DISPLAY_NAME for record in records) == (
        2 if timeline else 1
    )
    orjson.dumps(records)
    with pytest.raises(PartialExtractionError) as api:
        prefetch2json(str(tmp_path), timeline_mode=timeline, multiprocess=multiprocess)
    assert sorted(orjson.dumps(record) for record in api.value.records) == sorted(
        orjson.dumps(record) for record in records
    )
    assert api.value.diagnostics == reader.diagnostics


@pytest.mark.parametrize("timeline", [False, True])
@pytest.mark.parametrize("output_format", ["json", "jsonl"])
@pytest.mark.parametrize("chunk_size", [1, 500])
def test_native_cli_publishes_healthy_and_unicode_recovered_records(
    tmp_path, timeline, output_format, chunk_size
):
    inputs = tmp_path / "inputs"
    sources = [
        FIXTURE(inputs / directory, [VALID, VALID + 10000000])
        for directory in ("a", "b", "c")
    ]
    write_name(sources[1], BAD_NAME)
    original = [source.read_bytes() for source in sources]
    output = tmp_path / ("records." + output_format)
    output.write_bytes(b"old output")
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from prefetch2es.views.Prefetch2jsonView import entry_point; entry_point()",
            str(inputs),
            "--timeline" if timeline else "--no-timeline",
            "--format",
            output_format,
            "--size",
            str(chunk_size),
            "--quiet",
            "-o",
            str(output),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "UnicodeEncodeError" in result.stderr
    assert "Partial extraction: 1 failure(s)" in result.stderr
    assert not result.stdout
    records = (
        orjson.loads(output.read_bytes())
        if output_format == "json"
        else [orjson.loads(line) for line in output.read_bytes().splitlines()]
    )
    assert len(records) == (6 if timeline else 3)
    assert sum(name(record, timeline) == "TEST.EXE" for record in records) == (
        4 if timeline else 2
    )
    assert sum(name(record, timeline) == DISPLAY_NAME for record in records) == (
        2 if timeline else 1
    )
    assert not list(tmp_path.glob(".records.*.tmp"))
    assert [source.read_bytes() for source in sources] == original


@pytest.mark.parametrize("timeline", [False, True])
def test_bad_unicode_in_tags_also_retains_raw_and_mixed_diagnostics(tmp_path, timeline):
    source = write_name(
        FIXTURE(tmp_path, [2**64 - 1, VALID], volume_timestamps=[2**64 - 1]), BAD_NAME
    )
    with pytest.raises(PartialExtractionError) as caught:
        prefetch2json(str(source), timeline_mode=timeline, tags=["tag\udfff"])
    error = caught.value
    assert len(error.records) == 1
    assert {item["stage"] for item in error.diagnostics} == {
        "last_run_time",
        "volume_creation_time",
        "unicode",
    }
    assert error.records[0]["tags"] == ["prefetch", r"tag\udfff"]
    assert len(metadata(error.records[0], timeline)["invalid_unicode"]) == 2
    orjson.dumps(error.records)
    orjson.dumps(error.diagnostics)


@pytest.mark.parametrize("timeline", [False, True])
def test_valid_unicode_names_are_unchanged(tmp_path, timeline):
    source = write_name(FIXTURE(tmp_path, [VALID]), "日本語😀.EXE")
    records = prefetch2json(str(source), timeline_mode=timeline, tags=["調査😀"])
    assert name(records[0], timeline) == "日本語😀.EXE"
    assert records[0]["tags"] == ["prefetch", "調査😀"]
    assert "invalid_unicode" not in metadata(records[0], timeline)


@pytest.mark.skipif(
    os.name == "nt", reason="Windows does not accept surrogate-escaped file names"
)
@pytest.mark.parametrize("timeline", [False, True])
def test_native_non_utf8_source_path_is_serializable_and_retains_original(
    tmp_path, timeline
):
    source = FIXTURE(tmp_path, [VALID])
    destination = source.with_name("raw-\udcff.pf")
    source.rename(destination)
    original = destination.read_bytes()
    with pytest.raises(PartialExtractionError) as caught:
        prefetch2json(str(destination), timeline_mode=timeline)
    error = caught.value
    field = "log.file.path" if timeline else "source_file"
    assert error.diagnostics[0]["field"] == field
    assert (
        error.diagnostics[0]["utf16le"]
        == str(destination).encode("utf-16le", "surrogatepass").hex()
    )
    record = error.records[0]
    display = str(destination).encode("utf-8", "backslashreplace").decode("utf-8")
    assert (
        record["log"]["file"]["path"] if timeline else record["source_file"]
    ) == display
    assert error.diagnostics[0]["source_file"] == display
    assert metadata(record, timeline)["invalid_unicode"][0]["field"] == field
    orjson.dumps(error.records)
    orjson.dumps(error.diagnostics)
    assert destination.read_bytes() == original
