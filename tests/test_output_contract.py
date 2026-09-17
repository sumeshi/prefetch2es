"""Offline output and reliability contracts (no forensic fixture download)."""
import importlib
import json

import pytest

from prefetch2es.presenters.Prefetch2jsonPresenter import Prefetch2jsonPresenter

json_module = importlib.import_module("prefetch2es.presenters.Prefetch2jsonPresenter")


@pytest.fixture(autouse=True)
def prepare_prefetch():
    """Override legacy network setup for this focused unit module."""
    yield


@pytest.mark.parametrize("output_format", ["jsonl", "ndjson"])
@pytest.mark.parametrize("timeline", [False, True])
def test_jsonl_streams_utf8_records(tmp_path, monkeypatch, output_format, timeline):
    source = tmp_path / "input.pf"
    source.write_bytes(b"evidence")
    records = [{"message": "日本語\nnext"}, {"count": 2}]
    closed = []

    class Model:
        def __init__(self, path):
            pass

        def gen_records(self, **kwargs):
            try:
                yield records[:1]
                yield records[1:]
            finally:
                closed.append(True)

        gen_timeline_records = gen_records

    monkeypatch.setattr(json_module, "Prefetch2es", Model)
    presenter = Prefetch2jsonPresenter(source, "", is_quiet=True,
                                     timeline_mode=timeline, output_format=output_format)
    presenter.export_json()
    assert presenter.output_path == source.with_suffix(".jsonl")
    content = presenter.output_path.read_bytes()
    assert content == b''.join(json.dumps(r, ensure_ascii=False, separators=(",", ":")).encode() + b"\n" for r in records)
    assert closed == [True]


@pytest.mark.parametrize("alias", ["same", "symlink", "hardlink", "directory-source"])
def test_output_cannot_alias_evidence(tmp_path, alias):
    source = tmp_path / "input.pf"
    source.write_bytes(b"evidence")
    output = source
    if alias in ("symlink", "hardlink"):
        output = tmp_path / "output.jsonl"
        if alias == "symlink":
            output.symlink_to(source)
        else:
            output.hardlink_to(source)
    with pytest.raises(ValueError, match="[Oo]utput"):
        Prefetch2jsonPresenter(tmp_path if alias == "directory-source" else source,
                               str(output), output_format="jsonl").export_json()
    assert source.read_bytes() == b"evidence"


def test_default_output_does_not_collide_with_directory(tmp_path):
    source = tmp_path / "evidence.jsonl"
    source.mkdir()
    presenter = Prefetch2jsonPresenter(source, "", output_format="jsonl")
    assert presenter.output_path == source.parent / "evidence.jsonl.jsonl"


def test_invalid_output_format_rejected(tmp_path):
    with pytest.raises(ValueError, match="format"):
        Prefetch2jsonPresenter(tmp_path, "", output_format="yaml")
