"""Timeline defaults and the explicit Standard compatibility path."""

import importlib
import json

import pytest

import prefetch2es as api
from prefetch2es.presenters.Prefetch2esPresenter import Prefetch2esPresenter
from prefetch2es.presenters.Prefetch2jsonPresenter import Prefetch2jsonPresenter
from test_tags_contract import fake_prefetch


@pytest.mark.parametrize(
    "options,timeline",
    [({}, True), ({"timeline_mode": True}, True), ({"timeline_mode": False}, False)],
)
def test_public_json_api_defaults_to_timeline_and_keeps_standard(
    fake_prefetch, options, timeline
):
    records = api.prefetch2json(str(fake_prefetch), **options)
    assert records
    assert all(("event" in record) is timeline for record in records)
    if not timeline:
        assert len(records) == 1
        assert records[0]["name"] == "SAMPLE.EXE"


@pytest.mark.parametrize(
    "options,timeline",
    [({}, True), ({"timeline_mode": True}, True), ({"timeline_mode": False}, False)],
)
def test_public_es_api_passes_default_and_explicit_mode(monkeypatch, options, timeline):
    captured = {}

    class Presenter:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def bulk_import(self):
            pass

    monkeypatch.setattr(api, "Prefetch2esPresenter", Presenter)
    api.prefetch2es("sample.pf", **options)
    assert captured["timeline_mode"] is timeline


@pytest.mark.parametrize("view_name", ["Prefetch2esView", "Prefetch2jsonView"])
@pytest.mark.parametrize(
    "flags,timeline", [([], True), (["--timeline"], True), (["--no-timeline"], False)]
)
def test_cli_forwards_default_and_explicit_mode(
    fake_prefetch, monkeypatch, view_name, flags, timeline
):
    module = importlib.import_module("prefetch2es.views." + view_name)
    captured = {}

    class Presenter:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def bulk_import(self):
            pass

        export_json = bulk_import

    monkeypatch.setattr(module, view_name.replace("View", "Presenter"), Presenter)
    monkeypatch.setattr("sys.argv", [view_name, str(fake_prefetch), "--quiet", *flags])
    getattr(module, view_name)().run()
    assert captured["timeline_mode"] is timeline


@pytest.mark.parametrize(
    "options,timeline", [({}, True), ({"timeline_mode": False}, False)]
)
def test_direct_presenters_match_default_and_standard(
    fake_prefetch, tmp_path, options, timeline
):
    expected = api.prefetch2json(str(fake_prefetch), **options)
    producer = Prefetch2esPresenter(fake_prefetch, is_quiet=True, **options)
    assert [record for chunk in producer.prefetch2es() for record in chunk] == expected
    output = tmp_path / "records.json"
    Prefetch2jsonPresenter(
        fake_prefetch, output, is_quiet=True, **options
    ).export_json()
    assert json.loads(output.read_bytes()) == expected
    assert all(("event" in record) is timeline for record in expected)
