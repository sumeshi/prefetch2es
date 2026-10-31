"""Timeline preparation keeps native evidence and per-event containers intact."""

from collections import Counter
from hashlib import sha256
import importlib
from pathlib import Path

import orjson
import pytest

model = importlib.import_module("prefetch2es.models.Prefetch2es")
FIXTURE = Path(__file__).resolve().parents[1] / ".github/fixtures/calc-win10.bin"


class ObservedNative:
    """Delegate to pyscca while counting or failing one native boundary read."""

    def __init__(self, wrapped, calls, prefix="file", failure=None):
        self.wrapped = wrapped
        self.calls = calls
        self.prefix = prefix
        self.failure = failure
        self.input_handle = None

    def open_file_object(self, handle):
        self.input_handle = handle
        return self.wrapped.open_file_object(handle)

    def __getattr__(self, name):
        key = f"{self.prefix}.{name}"
        self.calls[key] += 1
        if key == self.failure:
            raise OSError(f"unreadable {key}")
        value = getattr(self.wrapped, name)
        if name in ("volumes", "file_metrics_entries"):
            prefix = "volume" if name == "volumes" else "metric"
            return [
                ObservedNative(item, self.calls, prefix, self.failure)
                for item in value
            ]
        return value


def observed_parser(monkeypatch, failure=None):
    calls = Counter()
    parser = ObservedNative(model.pyscca.file(), calls, failure=failure)
    monkeypatch.setattr(model.pyscca, "file", lambda: parser)
    return parser, calls


def test_native_metadata_is_read_once_for_multiple_execution_times(monkeypatch):
    parser, calls = observed_parser(monkeypatch)

    records = model.process_prefetch_file_timeline(FIXTURE, "native")

    assert len(records) == 2
    prefetch = records[0]["windows"]["prefetch"]
    assert len(prefetch["metrics"]) == 63
    assert len(prefetch["volumes"]) == 1
    for name in (
        "executable_filename", "run_count", "prefetch_hash", "format_version",
        "volumes", "file_metrics_entries",
    ):
        assert calls[f"file.{name}"] == 1
    for name in ("filename", "file_reference"):
        assert calls[f"metric.{name}"] == len(prefetch["metrics"])
    for name in ("device_path", "get_creation_time", "serial_number"):
        assert calls[f"volume.{name}"] == len(prefetch["volumes"])
    assert calls["file.close"] == 1
    assert parser.input_handle.closed


@pytest.mark.parametrize(
    "option,expected",
    [
        (0, "900d9e1bfce9ece4a107df869cabe5cd945d67e22129036eff75145ba13e6cc3"),
        (orjson.OPT_INDENT_2, "eadac9e1bedcd9c3ddae848ac82987a82f2321cf7b1484d7adb92a9a7337d5bf"),
        (orjson.OPT_SORT_KEYS, "d0566aa3e730e4c7caa25e59efdb2e8a4cddea88ffb01fc0d06f25a92c1cc957"),
    ],
)
def test_native_timeline_matches_preparation_baseline_bytes(option, expected):
    # Captured from bd0144a before preparation changes, with only the fixture
    # path replaced so the check is independent of checkout location and OS.
    records = model.process_prefetch_file_timeline(
        FIXTURE, ["native", "日本語", "prefetch"]
    )
    assert len(records) == 2
    for record in records:
        record["log"]["file"]["path"] = "<native-prefetch>"
    assert sha256(orjson.dumps(records, option=option)).hexdigest() == expected


def test_native_timeline_events_keep_independent_mutable_containers():
    records = model.process_prefetch_file_timeline(FIXTURE, "native")
    before = orjson.dumps(records[1])

    first = records[0]
    first["event"]["category"].append("changed")
    first["event"]["type"].append("changed")
    first["process"]["name"] = "changed"
    first["log"]["file"]["path"] = "changed"
    prefetch = first["windows"]["prefetch"]
    prefetch["hash"]["prefetch"] = "changed"
    prefetch["metrics"][0]["filename"] = "changed"
    prefetch["volumes"][0]["path"] = "changed"
    prefetch["metrics"].append({"filename": "added"})
    prefetch["volumes"].append({"path": "added"})

    assert orjson.dumps(records[1]) == before
    # Tags already share the per-file normalized list; this change preserves it.
    assert records[0]["tags"] is records[1]["tags"]


@pytest.mark.parametrize("times", ["none", "zero", "unavailable"])
def test_empty_timeline_does_not_read_unused_metadata(tmp_path, monkeypatch, times):
    source = tmp_path / "empty.pf"
    source.write_bytes(b"empty timeline boundary fixture")

    class EmptyTimeline:
        closed = False
        input_handle = None

        def open_file_object(self, handle):
            self.input_handle = handle

        def get_last_run_time(self, index):
            if times == "unavailable":
                raise OSError("no timestamp slot")
            return model.FILETIME_ZERO if times == "zero" else None

        def __getattr__(self, name):
            pytest.fail(f"read unused metadata: {name}")

        def close(self):
            self.closed = True

    parser = EmptyTimeline()
    monkeypatch.setattr(model.pyscca, "file", lambda: parser)

    assert model.process_prefetch_file_timeline(source, "native") == []
    assert parser.closed
    assert parser.input_handle.closed


@pytest.mark.parametrize(
    "failure",
    [
        "file.executable_filename", "file.run_count", "file.prefetch_hash",
        "file.format_version", "file.volumes", "volume.device_path",
        "volume.get_creation_time", "volume.serial_number",
        "file.file_metrics_entries", "metric.filename", "metric.file_reference",
    ],
)
def test_metadata_read_failure_retains_file_failure_and_closes_parser(
    monkeypatch, failure
):
    parser, calls = observed_parser(monkeypatch, failure)

    filepath, records, error = model.process_prefetch_task(
        FIXTURE, "native", timeline_mode=True
    )

    assert filepath == FIXTURE
    assert records == []
    assert isinstance(error, OSError)
    assert str(error) == f"unreadable {failure}"
    assert calls["file.close"] == 1
    assert parser.input_handle.closed
