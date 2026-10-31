"""Invalid volume dates do not discard readable Prefetch execution evidence."""

import importlib
from pathlib import Path
import pickle
import runpy

import orjson
import pytest

from prefetch2es import PartialExtractionError, prefetch2json

model = importlib.import_module("prefetch2es.models.Prefetch2es")
FIXTURE = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / ".github" / "artifact_fixture.py")
)["create_timestamp_artifact"]
VALID = 130968655538095417
INVALID = 2**64 - 1
TIMES = ["2016-01-10T02:12:33.809541Z", "2016-01-10T02:12:34.809541Z"]


def volumes(record, timeline):
    return record["windows"]["prefetch"]["volumes"] if timeline else record["volumes"]


@pytest.mark.parametrize("timeline", [False, True])
@pytest.mark.parametrize("invalid_index", [0, 1])
def test_native_volume_failure_retains_metadata_later_volumes_and_executions(
    tmp_path, timeline, invalid_index
):
    volume_times = [VALID, VALID, VALID]
    volume_times[invalid_index] = INVALID
    source = FIXTURE(
        tmp_path, [VALID, VALID + 10000000], volume_timestamps=volume_times
    )
    original = source.read_bytes()
    native = model.pyscca.file()
    try:
        native.open(str(source))
        assert native.number_of_volumes == 3
        with pytest.raises(ValueError) as native_error:
            native.volumes[invalid_index].get_creation_time()
        assert native.volumes[invalid_index].get_creation_time_as_integer() == INVALID
    finally:
        native.close()

    process = (
        model.process_prefetch_file_timeline
        if timeline
        else model.process_prefetch_file
    )
    with pytest.raises(PartialExtractionError) as caught:
        process(source, "native")
    error = caught.value
    assert len(error.records) == (2 if timeline else 1)
    assert error.diagnostics == [
        {
            "source_file": str(source),
            "stage": "volume_creation_time",
            "volume_index": invalid_index,
            "raw": INVALID,
            "error": f"ValueError: {native_error.value}",
        }
    ]
    assert (
        [record["@timestamp"] for record in error.records]
        if timeline
        else error.records[0]["last_exec_times"]
    ) == TIMES
    for record in error.records:
        assert volumes(record, timeline) == [
            {
                "path": "\\DEVICE\\VOLUME",
                "creation_time": None if index == invalid_index else TIMES[0],
                "serial_number": format(1234 + index, "X"),
            }
            for index in range(3)
        ]
        data = record["windows"]["prefetch"] if timeline else record
        assert data["metrics"] == [{"filename": "TEST.DLL", "file_reference": "0X0"}]
    transported = pickle.loads(pickle.dumps(error))
    assert transported.records == error.records
    assert transported.diagnostics == error.diagnostics
    if timeline:
        volumes(error.records[0], True)[invalid_index]["creation_time"] = "changed"
        assert volumes(error.records[1], True)[invalid_index]["creation_time"] is None
    assert source.read_bytes() == original


@pytest.mark.parametrize("timeline", [False, True])
@pytest.mark.parametrize("multiprocess", [False, True])
def test_native_api_and_spawn_keep_partial_and_healthy_files(
    tmp_path, monkeypatch, capsys, timeline, multiprocess
):
    bad = FIXTURE(tmp_path / "bad", [VALID], volume_timestamps=[INVALID])
    good = FIXTURE(tmp_path / "good", [VALID])
    monkeypatch.setattr(model.Prefetch2es, "get_cpu_count", lambda self: 2)
    reader = model.Prefetch2es([bad, good])
    generate = reader.gen_timeline_records if timeline else reader.gen_records
    records = []
    with pytest.raises(PartialExtractionError) as caught:
        for chunk in generate(multiprocess=multiprocess, chunk_size=1):
            assert len(chunk) == 1
            records.extend(chunk)
    assert len(records) == reader.generated_records == 2
    assert reader.successful_files == 1
    assert volumes(records[0], timeline)[0]["creation_time"] is None
    assert volumes(records[1], timeline)[0]["creation_time"] == TIMES[0]
    assert caught.value.diagnostics == reader.diagnostics
    assert reader.diagnostics[0]["source_file"] == str(bad)
    assert reader.diagnostics[0]["raw"] == INVALID
    with pytest.raises(PartialExtractionError) as api:
        prefetch2json(str(tmp_path), timeline_mode=timeline, multiprocess=multiprocess)
    assert sorted(orjson.dumps(record) for record in api.value.records) == sorted(
        orjson.dumps(record) for record in records
    )
    assert api.value.diagnostics == reader.diagnostics
    assert "volume[0].creation_time" in capsys.readouterr().err


@pytest.mark.parametrize("timeline", [False, True])
def test_native_execution_and_volume_failures_are_both_reported(
    tmp_path, capsys, timeline
):
    source = FIXTURE(tmp_path, [INVALID, VALID], volume_timestamps=[INVALID, INVALID])
    with pytest.raises(PartialExtractionError) as caught:
        prefetch2json(str(source), timeline_mode=timeline)
    error = caught.value
    assert len(error.records) == 1
    assert [item["stage"] for item in error.diagnostics] == [
        "last_run_time",
        "volume_creation_time",
        "volume_creation_time",
    ]
    assert all(item["raw"] == INVALID for item in error.diagnostics)
    assert all(item["source_file"] == str(source) for item in error.diagnostics)
    assert all(
        volume["creation_time"] is None
        for volume in volumes(error.records[0], timeline)
    )
    stderr = capsys.readouterr().err
    assert "timestamp[0]" in stderr
    assert "volume[0].creation_time" in stderr
    assert "volume[1].creation_time" in stderr


@pytest.mark.parametrize("timeline", [False, True])
@pytest.mark.parametrize("output_format", ["json", "jsonl"])
def test_native_cli_publishes_volume_recovery_and_reports_failure(
    tmp_path, monkeypatch, capsys, timeline, output_format
):
    source = FIXTURE(
        tmp_path / "input", [VALID, VALID + 10000000], volume_timestamps=[INVALID]
    )
    original = source.read_bytes()
    output = tmp_path / "output.json"
    output.write_bytes(b"previous output")
    view = importlib.import_module("prefetch2es.views.Prefetch2jsonView")
    monkeypatch.setattr(
        "sys.argv",
        [
            "prefetch2json",
            str(source),
            "--format",
            output_format,
            "--timeline" if timeline else "--no-timeline",
            "-o",
            str(output),
            "-q",
        ],
    )
    with pytest.raises(SystemExit) as caught:
        view.entry_point()
    assert caught.value.code == 1
    records = (
        orjson.loads(output.read_bytes())
        if output_format == "json"
        else [orjson.loads(line) for line in output.read_bytes().splitlines()]
    )
    assert len(records) == (2 if timeline else 1)
    assert all(
        volumes(record, timeline)[0]["creation_time"] is None for record in records
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "volume[0].creation_time" in captured.err and "ValueError" in captured.err
    assert not list(tmp_path.glob(".output.json.*.tmp"))
    assert source.read_bytes() == original


@pytest.mark.parametrize("timeline", [False, True])
def test_zero_volume_creation_time_keeps_existing_native_representation(
    tmp_path, timeline
):
    source = FIXTURE(tmp_path, [VALID], volume_timestamps=[0, VALID])
    records = prefetch2json(str(source), timeline_mode=timeline)
    assert [volume["creation_time"] for volume in volumes(records[0], timeline)] == [
        "1601-01-01T00:00:00Z",
        TIMES[0],
    ]


def test_volume_metadata_io_failure_is_not_hidden():
    class Volume:
        def get_creation_time(self):
            raise OSError("unreadable volume")

    class Parser:
        volumes = [Volume()]

    diagnostics = []
    with pytest.raises(OSError, match="unreadable volume"):
        model._prepare_volumes(Parser(), diagnostics, "sample.pf")
    assert diagnostics == []
