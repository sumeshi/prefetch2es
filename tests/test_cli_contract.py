"""Offline command line validation contracts."""
import importlib
import sys

import pytest


@pytest.fixture(autouse=True)
def prepare_prefetch():
    yield


@pytest.mark.parametrize("command", ["Prefetch2jsonView", "Prefetch2esView"])
@pytest.mark.parametrize("args", [["--size", "0"], ["--size", "-2"], ["--qui"]])
def test_cli_rejects_invalid_options(monkeypatch, command, args):
    module = importlib.import_module("prefetch2es.views." + command)
    monkeypatch.setattr(sys, "argv", [command, "input.pf", *args])
    with pytest.raises(SystemExit) as error:
        getattr(module, command)()
    assert error.value.code == 2


@pytest.mark.parametrize("output_format", ["json", "jsonl", "ndjson"])
def test_cli_forwards_output_format(tmp_path, monkeypatch, output_format):
    module = importlib.import_module("prefetch2es.views.Prefetch2jsonView")
    source = tmp_path / "input.pf"
    source.touch()
    captured = {}

    class Presenter:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def export_json(self):
            pass

    monkeypatch.setattr(module, "Prefetch2jsonPresenter", Presenter)
    monkeypatch.setattr(sys, "argv", ["prefetch2json", str(source), "--format", output_format])
    module.entry_point()
    assert captured["output_format"] == output_format


@pytest.mark.parametrize("command", ["Prefetch2jsonView", "Prefetch2esView"])
@pytest.mark.parametrize("kind", ["missing", "empty"])
def test_cli_invalid_input_is_usage_error(tmp_path, monkeypatch, capsys, command, kind):
    source = tmp_path / "missing.pf" if kind == "missing" else tmp_path
    module = importlib.import_module("prefetch2es.views." + command)
    monkeypatch.setattr(sys, "argv", [command, str(source)])
    with pytest.raises(SystemExit) as error:
        module.entry_point()
    assert error.value.code == 2
    assert "completed" not in capsys.readouterr().out


@pytest.mark.parametrize("command", ["Prefetch2jsonView", "Prefetch2esView"])
def test_cli_runtime_error_is_nonzero(tmp_path, monkeypatch, capsys, command):
    module = importlib.import_module("prefetch2es.views." + command)
    source = tmp_path / "bad.pf"
    source.write_bytes(b"bad")
    monkeypatch.setattr(sys, "argv", [command, str(source), "--quiet"])

    class Presenter:
        def __init__(self, **kwargs):
            pass

        def export_json(self):
            raise RuntimeError("output failed")

        bulk_import = export_json

    monkeypatch.setattr(module, command.replace("View", "Presenter"), Presenter)
    with pytest.raises(SystemExit) as error:
        module.entry_point()
    assert error.value.code == 1
    captured = capsys.readouterr()
    assert "output failed" in captured.err
    assert "Converted" not in captured.out
    assert "completed" not in captured.out
