import importlib
import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

from prefetch2es.models.Prefetch2es import Prefetch2es, normalize_tags
from prefetch2es import prefetch2json


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, ["prefetch"]),
        (" prefetch, host01, ,case01,host01 ", ["prefetch", "host01", "case01"]),
        (("host01", " prefetch ", "host01", "", " "), ["prefetch", "host01"]),
        (["one", "two", "one"], ["prefetch", "one", "two"]),
    ],
)
def test_normalize_tags(value, expected):
    assert normalize_tags(value) == expected


@pytest.mark.parametrize("command", ["Prefetch2esView", "Prefetch2jsonView"])
def test_cli_keeps_comma_separated_tags(monkeypatch, command):
    module = importlib.import_module("prefetch2es.views." + command)
    monkeypatch.setattr(
        sys, "argv", [command, "input.pf", "--tags", "prefetch, host01,,case01"]
    )
    view = getattr(module, command)()
    assert view.args.tags == "prefetch, host01,,case01"


@pytest.mark.parametrize("mode", ["standard", "timeline"])
@pytest.mark.parametrize(
    ("tags", "expected"),
    [
        (" prefetch, host01,,case01,host01 ", ["prefetch", "host01", "case01"]),
        (("host01", "prefetch", "host01"), ["prefetch", "host01"]),
        ("", ["prefetch"]),
    ],
)
def test_model_modes_apply_tags(tmp_path, monkeypatch, mode, tags, expected):
    module = importlib.import_module("prefetch2es.models.Prefetch2es")
    monkeypatch.setattr(
        Prefetch2es, "_get_prefetch_files", lambda self: [Path("one.pf")]
    )
    if mode == "standard":
        monkeypatch.setattr(
            module,
            "process_prefetch_file",
            lambda filepath, value: {"tags": normalize_tags(value)},
        )
        records = list(Prefetch2es(tmp_path).gen_records(tags=tags))[0]
    else:
        monkeypatch.setattr(
            module,
            "process_prefetch_file_timeline",
            lambda filepath, value: [{"tags": normalize_tags(value)}],
        )
        records = list(Prefetch2es(tmp_path).gen_timeline_records(tags=tags))[0]
    assert records == [{"tags": expected}]


@pytest.mark.parametrize("timeline", [False, True])
def test_json_and_jsonl_schema_matches_for_same_mode(
    tmp_path, monkeypatch, timeline, fake_prefetch
):
    module = importlib.import_module("prefetch2es.presenters.Prefetch2jsonPresenter")
    model = importlib.import_module("prefetch2es.models.Prefetch2es")
    if timeline:
        record = model.process_prefetch_file_timeline(fake_prefetch, "host01,prefetch")[
            0
        ]
    else:
        record = model.process_prefetch_file(fake_prefetch, "host01,prefetch")

    class Model:
        def __init__(self, input_path):
            pass

        def gen_records(self, **kwargs):
            assert kwargs["tags"] == "host01,prefetch"
            yield [record]

        gen_timeline_records = gen_records

    monkeypatch.setattr(module, "Prefetch2es", Model)
    outputs = {}
    for output_format in ("json", "jsonl"):
        presenter = module.Prefetch2jsonPresenter(
            str(tmp_path / "input.pf"),
            str(tmp_path / f"output.{output_format}"),
            is_quiet=True,
            timeline_mode=timeline,
            tags="host01,prefetch",
            output_format=output_format,
        )
        presenter.export_json()
        data = presenter.output_path.read_text()
        outputs[output_format] = (
            json.loads(data) if output_format == "json" else [json.loads(data)]
        )
    assert outputs["json"] == outputs["jsonl"] == [record]


@pytest.mark.parametrize("timeline", [False, True])
@pytest.mark.parametrize(
    ("tags", "expected"),
    [
        ("prefetch, host01", ["prefetch", "host01"]),
        (["host01", "prefetch", "host01"], ["prefetch", "host01"]),
        (("host01", "", "prefetch", " "), ["prefetch", "host01"]),
    ],
)
def test_public_json_api_formats_tags_in_both_modes(
    timeline, tags, expected, fake_prefetch
):
    records = prefetch2json(str(fake_prefetch), timeline_mode=timeline, tags=tags)

    assert records
    assert records[0]["tags"] == expected
    if timeline:
        assert records[0]["event"]["dataset"] == "windows.prefetch"
    else:
        assert records[0]["name"] == "SAMPLE.EXE"


@pytest.fixture
def fake_prefetch(tmp_path, monkeypatch):
    module = importlib.import_module("prefetch2es.models.Prefetch2es")
    source = tmp_path / "sample.pf"
    source.write_bytes(b"fixture")

    class FakePrefetch:
        executable_filename = "SAMPLE.EXE"
        filenames = ["\\WINDOWS\\SYSTEM32\\SAMPLE.EXE", "日本語.txt"]
        run_count = 2
        format_version = 30
        prefetch_hash = 0x1234
        number_of_volumes = 0
        number_of_filenames = 2
        number_of_file_metrics_entries = 0
        file_metrics_entries = []
        volumes = []

        def open_file_object(self, file_object):
            pass

        def get_last_run_time(self, index):
            if index == 0:
                return datetime(2020, 1, 2, 3, 4, 5)
            return None

        def close(self):
            pass

    monkeypatch.setattr(module.pyscca, "file", FakePrefetch)
    return source
