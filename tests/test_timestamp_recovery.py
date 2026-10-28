"""Native timestamp failures retain later slots and remain partial failures."""

from datetime import datetime
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


def test_timestamp_recovery_keeps_unsupported_slot_boundary():
    calls = []

    class Parser:
        def get_last_run_time(self, index):
            calls.append(index)
            if index == 0:
                raise ValueError("invalid datetime")
            if index == 1:
                return datetime(2024, 1, 1)
            if index == 2:
                raise OverflowError("datetime out of range")
            if index == 3:
                return model.FILETIME_ZERO
            if index == 4:
                raise OSError("unsupported slot")
            pytest.fail("read beyond supported slots")

    diagnostics = []
    assert model.safe_last_run_times(Parser(), diagnostics) == ["2024-01-01T00:00:00Z"]
    assert calls == [0, 1, 2, 3, 4]
    assert [item["timestamp_index"] for item in diagnostics] == [0, 2]
    with pytest.raises(ValueError, match="invalid datetime"):
        model.safe_last_run_times(Parser())


@pytest.mark.parametrize("timeline", [False, True])
@pytest.mark.parametrize("invalid_index", [0, 1])
def test_native_direct_processor_exposes_recovered_records_and_raw_time(
    tmp_path, timeline, invalid_index
):
    times = [VALID, VALID + 10000000]
    times[invalid_index] = INVALID
    source = FIXTURE(tmp_path, times)
    process = (
        model.process_prefetch_file_timeline
        if timeline
        else model.process_prefetch_file
    )

    with pytest.raises(PartialExtractionError) as caught:
        process(source, "native")

    error = caught.value
    assert len(error.records) == 1
    actual = (
        [error.records[0]["@timestamp"]]
        if timeline
        else error.records[0]["last_exec_times"]
    )
    expected_second = "2016-01-10T02:12:34.809541Z"
    expected_first = "2016-01-10T02:12:33.809541Z"
    assert actual == [expected_second if invalid_index == 0 else expected_first]
    assert error.diagnostics == [
        {
            "source_file": str(source),
            "stage": "last_run_time",
            "timestamp_index": invalid_index,
            "raw": INVALID,
            "error": "ValueError: year 60056 is out of range",
        }
    ]
    transported = pickle.loads(pickle.dumps(error))
    assert transported.records == error.records
    assert transported.diagnostics == error.diagnostics
    assert str(transported) == str(error)


@pytest.mark.parametrize("timeline", [False, True])
@pytest.mark.parametrize("multiprocess", [False, True])
def test_native_task_and_api_retain_partial_and_healthy_files(
    tmp_path, monkeypatch, timeline, multiprocess
):
    bad = FIXTURE(tmp_path / "bad", [INVALID, VALID])
    good = FIXTURE(tmp_path / "good", [VALID, VALID + 10000000])
    monkeypatch.setattr(model.Prefetch2es, "get_cpu_count", lambda self: 2)
    filepath, recovered, error = model.process_prefetch_task(
        bad, timeline_mode=timeline
    )
    assert filepath == bad and len(recovered) == 1
    assert isinstance(error, PartialExtractionError)
    assert recovered is error.records

    reader = model.Prefetch2es([bad, good])
    generate = reader.gen_timeline_records if timeline else reader.gen_records
    records = []
    with pytest.raises(PartialExtractionError) as caught:
        for chunk in generate(multiprocess=multiprocess, chunk_size=1):
            assert len(chunk) == 1
            records.extend(chunk)
    assert len(records) == (3 if timeline else 2)
    assert reader.successful_files == 1
    assert reader.generated_records == len(records)
    assert reader.diagnostics == error.diagnostics == caught.value.diagnostics
    assert str(caught.value).startswith("Partial extraction: 1 failure(s)")

    with pytest.raises(PartialExtractionError) as api:
        prefetch2json(str(tmp_path), timeline_mode=timeline, multiprocess=multiprocess)
    # Directory enumeration order need not match the explicit input sequence.
    assert sorted(orjson.dumps(record) for record in api.value.records) == sorted(
        orjson.dumps(record) for record in records
    )
    assert api.value.diagnostics == error.diagnostics


@pytest.mark.parametrize("timeline", [False, True])
@pytest.mark.parametrize("output_format", ["json", "jsonl"])
def test_native_json_cli_publishes_recovery_with_failure_exit(
    tmp_path, monkeypatch, capsys, timeline, output_format
):
    source = FIXTURE(tmp_path / "input", [INVALID, VALID])
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
    if output_format == "json":
        records = orjson.loads(output.read_bytes())
    else:
        records = [orjson.loads(line) for line in output.read_bytes().splitlines()]
    assert len(records) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "timestamp[0]" in captured.err and "ValueError" in captured.err
    assert not list(tmp_path.glob(".output.json.*.tmp"))


@pytest.mark.parametrize("timeline", [False, True])
def test_all_invalid_times_are_not_reported_as_success(tmp_path, timeline):
    source = FIXTURE(tmp_path / "input", [INVALID, INVALID])
    reader = model.Prefetch2es(source)
    generate = reader.gen_timeline_records if timeline else reader.gen_records
    records = []
    with pytest.raises(PartialExtractionError) as caught:
        for chunk in generate():
            records.extend(chunk)
    # Standard retains the file's useful metadata even without execution times.
    assert len(records) == (0 if timeline else 1)
    assert reader.successful_files == 0
    assert len(caught.value.diagnostics) == 2
    if not timeline:
        assert records[0]["last_exec_times"] == []
        assert records[0]["metrics"][0]["filename"] == "TEST.DLL"
    else:
        presenter = importlib.import_module(
            "prefetch2es.presenters.Prefetch2jsonPresenter"
        )
        output = tmp_path / "output.json"
        output.write_bytes(b"previous output")
        with pytest.raises(PartialExtractionError):
            presenter.Prefetch2jsonPresenter(
                source, str(output), is_quiet=True
            ).export_json()
        assert output.read_bytes() == b"previous output"
