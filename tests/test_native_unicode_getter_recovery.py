"""Unreadable native UTF-16 metadata does not discard execution evidence."""

from pathlib import Path
import runpy
import subprocess
import sys

import orjson
import pytest

from prefetch2es import PartialExtractionError, prefetch2json

model = __import__("prefetch2es.models.Prefetch2es", fromlist=["Prefetch2es"])
FIXTURE = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / ".github" / "artifact_fixture.py")
)["create_timestamp_artifact"]
VALID = 130968655538095417
BAD_FIELDS = {
    "metric": (348, "metrics[0].filename", "metric_index"),
    "volume": (480, "volumes[0].path", "volume_index"),
}


def corrupt_native_string(source, kind):
    offset, _, _ = BAD_FIELDS[kind]
    payload = bytearray(source.read_bytes())
    payload[offset : offset + 2] = b"\x00\xd8"
    source.write_bytes(payload)


def metadata(record, timeline):
    return record["windows"]["prefetch"] if timeline else record


@pytest.mark.parametrize("kind", ["metric", "volume"])
@pytest.mark.parametrize("timeline", [False, True])
@pytest.mark.parametrize("multiprocess", [False, True])
def test_native_getter_failure_retains_records_and_other_metadata(
    tmp_path, monkeypatch, kind, timeline, multiprocess
):
    sources = [
        FIXTURE(tmp_path / label, [VALID, VALID + 10_000_000])
        for label in ("a-good", "b-bad", "c-good")
    ]
    corrupt_native_string(sources[1], kind)
    originals = [source.read_bytes() for source in sources]
    monkeypatch.setattr(model.Prefetch2es, "get_cpu_count", lambda self: 2)

    reader = model.Prefetch2es(sources)
    generate = reader.gen_timeline_records if timeline else reader.gen_records
    records = []
    with pytest.raises(PartialExtractionError):
        for chunk in generate(multiprocess=multiprocess, chunk_size=1):
            records.extend(chunk)

    expected_count = 6 if timeline else 3
    assert len(records) == reader.generated_records == expected_count
    assert reader.successful_files == 2
    native_diagnostics = [
        diagnostic
        for diagnostic in reader.diagnostics
        if diagnostic.get("stage") == "native_metadata"
    ]
    assert len(native_diagnostics) == 1
    diagnostic = native_diagnostics[0]
    assert diagnostic["source_file"] == str(sources[1])
    assert diagnostic["field"] == BAD_FIELDS[kind][1]
    assert diagnostic[BAD_FIELDS[kind][2]] == 0
    assert diagnostic["error"].startswith("OSError:")
    affected = [
        record
        for record in records
        if (record["log"]["file"]["path"] if timeline else record["source_file"])
        == str(sources[1])
    ]
    assert len(affected) == (2 if timeline else 1)
    for record in affected:
        data = metadata(record, timeline)
        if timeline:
            assert record["@timestamp"]
        else:
            assert data["last_exec_times"]
        assert data["metrics"]
        assert data["volumes"]
        if kind == "metric":
            assert data["metrics"][0]["filename"] is None
            # The filename array is separately readable and preserves the prior
            # invalid-Unicode recovery behavior.
            if not timeline:
                assert data["filenames"][0].startswith(r"\ud800")
        else:
            assert data["volumes"][0]["path"] is None
            assert data["volumes"][0]["serial_number"] == "4D2"
    orjson.dumps(records)
    assert [source.read_bytes() for source in sources] == originals


@pytest.mark.parametrize("kind", ["metric", "volume"])
@pytest.mark.parametrize("timeline", [False, True])
def test_native_getter_cli_keeps_healthy_output_and_input_unchanged(
    tmp_path, kind, timeline
):
    inputs = tmp_path / "inputs"
    sources = [
        FIXTURE(inputs / label, [VALID, VALID + 10_000_000])
        for label in ("a-good", "b-bad", "c-good")
    ]
    corrupt_native_string(sources[1], kind)
    originals = [source.read_bytes() for source in sources]
    output = tmp_path / "records.jsonl"
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from prefetch2es.views.Prefetch2jsonView import entry_point; entry_point()",
            str(inputs),
            "--timeline" if timeline else "--no-timeline",
            "--format",
            "jsonl",
            "--quiet",
            "--size",
            "1",
            "-o",
            str(output),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert BAD_FIELDS[kind][1] in result.stderr
    assert "OSError:" in result.stderr
    records = [orjson.loads(line) for line in output.read_bytes().splitlines()]
    assert len(records) == (6 if timeline else 3)
    paths = [
        record["log"]["file"]["path"] if timeline else record["source_file"]
        for record in records
    ]
    assert paths.count(str(sources[0])) == (2 if timeline else 1)
    assert paths.count(str(sources[1])) == (2 if timeline else 1)
    assert paths.count(str(sources[2])) == (2 if timeline else 1)
    affected = [
        record for record, path in zip(records, paths) if path == str(sources[1])
    ]
    for record in affected:
        data = metadata(record, timeline)
        assert data["metrics"] and data["volumes"]
        if kind == "metric":
            assert data["metrics"][0]["filename"] is None
        else:
            assert data["volumes"][0]["path"] is None
    assert not list(tmp_path.glob(".records.*.tmp"))
    assert [source.read_bytes() for source in sources] == originals

