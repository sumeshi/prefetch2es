"""Offline CLI batching, real spawn, discovery and partial-output regressions."""

import importlib
import json
import os
from unittest.mock import MagicMock

import pytest

from prefetch2es import PartialExtractionError, prefetch2json

model = importlib.import_module("prefetch2es.models.Prefetch2es")
es_presenter = importlib.import_module("prefetch2es.presenters.Prefetch2esPresenter")
json_presenter = importlib.import_module(
    "prefetch2es.presenters.Prefetch2jsonPresenter"
)


def synthetic_task(filepath, tags="", timeline_mode=False):
    """Importable worker for an actual spawn pool, without forensic evidence."""
    if filepath.name.startswith("bad"):
        return filepath, [], OSError("invalid synthetic Prefetch")
    count = 0 if filepath.name.startswith("empty") else (3 if timeline_mode else 1)
    return (
        filepath,
        [
            {"source_file": str(filepath), "ordinal": i, "worker_pid": os.getpid()}
            for i in range(count)
        ],
        None,
    )


def make_inputs(tmp_path, names):
    files = [tmp_path / name for name in names]
    for path in files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"synthetic test input")
    return files


@pytest.mark.parametrize("multiprocess", [False, True])
@pytest.mark.parametrize("timeline", [False, True])
def test_es_cli_shares_client_and_batches_across_files(
    tmp_path,
    monkeypatch,
    multiprocess,
    timeline,
):
    files = make_inputs(tmp_path, ["one.pf", "nested/deep/two.PF", "three.pf"])
    client = MagicMock()
    client.bulk_indice.side_effect = lambda records, *args: (len(records), [])
    factory = MagicMock(return_value=client)
    monkeypatch.setattr(es_presenter, "ElasticsearchUtils", factory)
    monkeypatch.setattr(model, "process_prefetch_task", synthetic_task)
    module = importlib.import_module("prefetch2es.views.Prefetch2esView")
    argv = ["prefetch2es", str(tmp_path), str(files[0]), "--size", "2", "--quiet"]
    if multiprocess:
        argv.append("--multiprocess")
    if timeline:
        argv.append("--timeline")
    monkeypatch.setattr("sys.argv", argv)
    module.entry_point()

    factory.assert_called_once()
    client.close.assert_called_once()
    chunks = [call.args[0] for call in client.bulk_indice.call_args_list]
    assert [len(chunk) for chunk in chunks] == ([2, 2, 2, 2, 1] if timeline else [2, 1])
    records = [record for chunk in chunks for record in chunk]
    assert {record["source_file"] for record in records} == {
        str(path) for path in files
    }
    assert all(
        (record["worker_pid"] != os.getpid()) == multiprocess for record in records
    )
    if not timeline:
        assert len({r["source_file"] for r in chunks[0]}) == 2


def test_pool_uses_one_task_per_file_and_caps_workers(tmp_path, monkeypatch):
    files = make_inputs(tmp_path, ["one.pf", "two.pf", "three.pf"])
    pool = MagicMock()
    pool.__enter__.return_value = pool

    def apply_async(process, args):
        assert len(args) == 1
        result = MagicMock()
        result.get.return_value = process(*args)
        return result

    pool.apply_async.side_effect = apply_async
    context = MagicMock()
    context.Pool.return_value = pool
    monkeypatch.setattr(model, "process_prefetch_task", synthetic_task)
    monkeypatch.setattr(model.Prefetch2es, "get_cpu_count", lambda self: 64)
    monkeypatch.setattr(
        model.Prefetch2es, "get_multiprocessing_context", lambda self: context
    )
    assert [
        len(chunk)
        for chunk in model.Prefetch2es(files).gen_records(
            multiprocess=True,
            chunk_size=500,
        )
    ] == [3]
    assert [call.args[1][0] for call in pool.apply_async.call_args_list] == files
    context.Pool.assert_called_once_with(3)
    pool.__exit__.assert_called_once()


def test_discovery_resolves_filters_and_deduplicates(tmp_path):
    files = make_inputs(tmp_path, ["top.pf", "nested/deep/upper.PF", "ignore.txt"])
    (tmp_path / "directory.pf").mkdir()
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    alias = tmp_path / "alias.pf"
    alias.symlink_to(files[0])
    assert set(model.get_prefetch_files([tmp_path, files[0], alias])) == set(files[:2])
    assert model.get_prefetch_files([tmp_path / "directory.pf"]) == []
    diagnostics = []
    assert model.get_prefetch_files(
        [files[0], tmp_path / "missing", empty_dir], diagnostics
    ) == [files[0]]
    assert [entry["source_file"] for entry in diagnostics] == [
        str((tmp_path / "missing").resolve()),
        str(empty_dir.resolve()),
    ]


@pytest.mark.parametrize("directory_mode", [0, 0o400])
def test_unreadable_subdirectory_keeps_good_records_and_reports_partial_failure(
    tmp_path, monkeypatch, capsys, directory_mode
):
    if os.name != "posix":
        pytest.skip("Requires POSIX directory permissions")
    source = tmp_path / "source"
    files = make_inputs(source, ["good.pf", "blocked/hidden.pf", "blocked/deep/hidden.pf"])
    blocked = files[1].parent
    blocked.chmod(directory_mode)
    try:
        if os.access(blocked, os.R_OK | os.X_OK):
            pytest.skip("Directory permissions cannot restrict this user")
        monkeypatch.setattr(model, "process_prefetch_task", synthetic_task)
        module = importlib.import_module("prefetch2es.views.Prefetch2jsonView")
        output = tmp_path / "output.jsonl"
        monkeypatch.setattr(
            "sys.argv",
            ["prefetch2json", str(source), "--format", "jsonl", "-o", str(output), "-q"],
        )
        with pytest.raises(SystemExit) as exited:
            module.entry_point()
        assert exited.value.code == 1
        assert [json.loads(line)["source_file"] for line in output.read_text().splitlines()] == [
            str(files[0])
        ]
        captured = capsys.readouterr()
        assert captured.out == ""
        assert str(blocked) in captured.err
        files[0].unlink()
        diagnostics = []
        assert model.get_prefetch_files([source], diagnostics) == []
        assert len(diagnostics) == (1 if directory_mode == 0 else 2)
        assert all(entry["source_file"].startswith(str(blocked)) for entry in diagnostics)
    finally:
        blocked.chmod(0o700)


@pytest.mark.parametrize("timeline", [False, True])
def test_nested_uppercase_json_cli_matches_es(tmp_path, monkeypatch, timeline):
    source = tmp_path / "source"
    make_inputs(source, ["nested/deep/one.PF", "nested/two.pf"])
    output = tmp_path / "output.jsonl"
    monkeypatch.setattr(model, "process_prefetch_task", synthetic_task)
    json_view = importlib.import_module("prefetch2es.views.Prefetch2jsonView")
    argv = ["prefetch2json", str(source), "--format", "jsonl", "-o", str(output), "-q"]
    if timeline:
        argv.append("--timeline")
    monkeypatch.setattr("sys.argv", argv)
    json_view.entry_point()
    exported = [json.loads(line) for line in output.read_text().splitlines()]
    presenter = es_presenter.Prefetch2esPresenter(source, timeline_mode=timeline)
    assert exported == [record for chunk in presenter.prefetch2es() for record in chunk]


def test_unreadable_writable_directory_still_protects_evidence(tmp_path):
    if os.name != "posix":
        pytest.skip("Requires POSIX directory permissions")
    files = make_inputs(tmp_path, ["good.pf", "blocked/hidden.pf"])
    blocked = files[1].parent
    sentinel = files[1].read_bytes()
    blocked.chmod(0o300)
    try:
        if os.access(blocked, os.R_OK):
            pytest.skip("Directory permissions cannot restrict this user")
        with pytest.raises(ValueError, match="input directory"):
            json_presenter.Prefetch2jsonPresenter(
                tmp_path, str(files[1]), is_quiet=True
            ).export_json()
        assert files[1].read_bytes() == sentinel
    finally:
        blocked.chmod(0o700)


@pytest.mark.parametrize("multiprocess", [False, True])
@pytest.mark.parametrize("timeline", [False, True])
def test_jsonl_cli_good_bad_good_partial_output_and_atomic_publish(
    tmp_path,
    monkeypatch,
    capsys,
    multiprocess,
    timeline,
):
    source = tmp_path / "source"
    files = make_inputs(source, ["good-one.pf", "bad.pf", "good-two.pf"])
    output = tmp_path / "output.jsonl"
    output.write_bytes(b"existing output")
    monkeypatch.setattr(model, "process_prefetch_task", synthetic_task)
    # Keep good/bad/good order explicit, independently of filesystem order.
    module = importlib.import_module("prefetch2es.views.Prefetch2jsonView")
    monkeypatch.setattr(
        module,
        "get_prefetch_files",
        lambda paths, diagnostics=None: files,
    )
    argv = [
        "prefetch2json",
        str(source),
        "-o",
        str(output),
        "--format",
        "jsonl",
        "-q",
        "--size",
        "2",
    ]
    if multiprocess:
        argv.append("--multiprocess")
    if timeline:
        argv.append("--timeline")
    monkeypatch.setattr("sys.argv", argv)
    with pytest.raises(SystemExit) as exited:
        module.entry_point()
    assert exited.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert str(files[1]) in captured.err
    assert "OSError" in captured.err
    assert "file(s) parsed successfully" in captured.err
    records = [json.loads(line) for line in output.read_text().splitlines()]
    assert {record["source_file"] for record in records} == {
        str(files[0]),
        str(files[2]),
    }
    assert len(records) == (6 if timeline else 2)
    assert "Partial extraction" in captured.err
    assert list(tmp_path.glob(".output.jsonl.*.tmp")) == []


@pytest.mark.parametrize("multiprocess", [False, True])
@pytest.mark.parametrize("timeline", [False, True])
def test_es_file_failure_processes_remaining_files_then_exits_nonzero(
    tmp_path,
    monkeypatch,
    capsys,
    multiprocess,
    timeline,
):
    files = make_inputs(tmp_path, ["good-one.pf", "bad.pf", "good-two.pf"])
    missing = tmp_path / "missing.pf"
    client = MagicMock()
    client.bulk_indice.side_effect = lambda records, *args: (len(records), [])
    factory = MagicMock(return_value=client)
    monkeypatch.setattr(es_presenter, "ElasticsearchUtils", factory)
    monkeypatch.setattr(model, "process_prefetch_task", synthetic_task)
    module = importlib.import_module("prefetch2es.views.Prefetch2esView")
    argv = ["prefetch2es", *map(str, files), str(missing), "--quiet", "--size", "1"]
    if multiprocess:
        argv.append("--multiprocess")
    if timeline:
        argv.append("--timeline")
    monkeypatch.setattr("sys.argv", argv)
    with pytest.raises(SystemExit) as exited:
        module.entry_point()
    assert exited.value.code == 1
    records = [
        record for call in client.bulk_indice.call_args_list for record in call.args[0]
    ]
    expected_files = {str(files[0]), str(files[2])}
    assert {record["source_file"] for record in records} == expected_files
    assert len(records) == (3 if timeline else 1) * 2
    factory.assert_called_once()
    client.close.assert_called_once()
    captured = capsys.readouterr().err
    assert str(missing) in captured
    assert "Partial extraction" in captured


def test_es_cli_unreadable_explicit_input_keeps_good_files_and_exits_nonzero(
    tmp_path, monkeypatch, capsys
):
    if os.name != "posix":
        pytest.skip("Requires POSIX directory permissions")
    files = make_inputs(tmp_path, ["good.pf", "blocked/hidden.pf", "good2.pf"])
    blocked = files[1].parent
    blocked.chmod(0)
    try:
        if os.access(blocked, os.R_OK | os.X_OK):
            pytest.skip("Directory permissions cannot restrict this user")
        client = MagicMock()
        client.bulk_indice.side_effect = lambda records, *args: (len(records), [])
        factory = MagicMock(return_value=client)
        monkeypatch.setattr(es_presenter, "ElasticsearchUtils", factory)
        monkeypatch.setattr(model, "process_prefetch_task", synthetic_task)
        module = importlib.import_module("prefetch2es.views.Prefetch2esView")
        monkeypatch.setattr(
            "sys.argv", ["prefetch2es", *map(str, files), "--quiet"]
        )
        with pytest.raises(SystemExit) as exited:
            module.entry_point()
        assert exited.value.code == 1
        records = [
            record
            for call in client.bulk_indice.call_args_list
            for record in call.args[0]
        ]
        assert {record["source_file"] for record in records} == {
            str(files[0]),
            str(files[2]),
        }
        captured = capsys.readouterr()
        assert captured.out == ""
        assert str(files[1]) in captured.err
        assert "Partial extraction" in captured.err
        factory.assert_called_once()
        client.close.assert_called_once()
    finally:
        blocked.chmod(0o700)


def test_es_transport_errors_still_stop_processing(tmp_path, monkeypatch):
    files = make_inputs(tmp_path, ["good-one.pf", "bad.pf", "good-two.pf"])
    client = MagicMock()
    client.bulk_indice.side_effect = RuntimeError("transport failed")
    monkeypatch.setattr(es_presenter, "ElasticsearchUtils", lambda **kwargs: client)
    monkeypatch.setattr(model, "process_prefetch_task", synthetic_task)
    with pytest.raises(RuntimeError, match="transport failed"):
        es_presenter.Prefetch2esPresenter(files, chunk_size=1).bulk_import()
    client.bulk_indice.assert_called_once()
    client.close.assert_called_once()


@pytest.mark.parametrize("output_format", ["json", "jsonl"])
def test_output_write_failure_preserves_destination(
    tmp_path, monkeypatch, output_format
):
    source = make_inputs(tmp_path, ["one.pf"])[0]
    output = tmp_path / "out.json"
    output.write_bytes(b"existing")
    monkeypatch.setattr(model, "process_prefetch_task", synthetic_task)
    monkeypatch.setattr(
        json_presenter.orjson,
        "dumps",
        lambda *a, **k: (_ for _ in ()).throw(OSError("write failed")),
    )
    with pytest.raises(OSError, match="write failed"):
        json_presenter.Prefetch2jsonPresenter(
            source,
            str(output),
            output_format=output_format,
            is_quiet=True,
        ).export_json()
    assert output.read_bytes() == b"existing"
    assert list(tmp_path.glob(".out.json.*.tmp")) == []


@pytest.mark.parametrize("output_format", ["json", "jsonl"])
@pytest.mark.parametrize("input_kind", ["missing", "corrupt"])
def test_no_recovered_records_preserves_existing_output(
    tmp_path, monkeypatch, capsys, output_format, input_kind
):
    source = tmp_path / "bad.pf"
    if input_kind == "corrupt":
        source.write_bytes(b"invalid Prefetch header")
    output = tmp_path / f"output.{output_format}"
    output.write_bytes(b"existing output")
    module = importlib.import_module("prefetch2es.views.Prefetch2jsonView")
    monkeypatch.setattr(
        "sys.argv",
        ["prefetch2json", str(source), "-o", str(output), "--format", output_format, "-q"],
    )
    with pytest.raises(SystemExit) as exited:
        module.entry_point()
    assert exited.value.code == 1
    assert output.read_bytes() == b"existing output"
    assert not list(tmp_path.glob(f".{output.name}.*.tmp"))
    captured = capsys.readouterr()
    assert captured.out == ""
    assert str(source) in captured.err


def test_partial_python_api_exposes_records_and_diagnostics(tmp_path, monkeypatch):
    files = make_inputs(tmp_path, ["good-one.pf", "bad.pf", "good-two.pf"])
    monkeypatch.setattr(model, "process_prefetch_task", synthetic_task)
    monkeypatch.setattr(model.Prefetch2es, "_get_prefetch_files", lambda self: files)
    with pytest.raises(PartialExtractionError) as partial:
        prefetch2json(str(tmp_path))
    assert [record["source_file"] for record in partial.value.records] == [
        str(files[0]),
        str(files[2]),
    ]
    assert partial.value.diagnostics == [
        {"source_file": str(files[1]), "error": "OSError: invalid synthetic Prefetch"}
    ]


def test_empty_timeline_is_success_not_parse_failure(tmp_path, monkeypatch):
    files = make_inputs(tmp_path, ["empty.pf", "good.pf"])
    monkeypatch.setattr(model, "process_prefetch_task", synthetic_task)
    prefetch = model.Prefetch2es(files)
    assert (
        len([record for chunk in prefetch.gen_timeline_records() for record in chunk])
        == 3
    )
    assert prefetch.successful_files == 2
    assert prefetch.diagnostics == []


@pytest.mark.parametrize("timeline", [False, True])
def test_parser_closes_after_open_failure(tmp_path, monkeypatch, timeline):
    source = make_inputs(tmp_path, ["bad.pf"])[0]
    parser = MagicMock()
    parser.open_file_object.side_effect = OSError("invalid header")
    monkeypatch.setattr(model.pyscca, "file", lambda: parser)
    process = (
        model.process_prefetch_file_timeline
        if timeline
        else model.process_prefetch_file
    )
    with pytest.raises(OSError, match="invalid header"):
        process(source, "")
    parser.close.assert_called_once()
    filepath, records, error = model.process_prefetch_task(
        source, timeline_mode=timeline
    )
    assert filepath == source
    assert records == []
    assert isinstance(error, OSError)
    assert str(error) == "invalid header"


def test_vanished_snapshot_file_is_handled_per_file(tmp_path, monkeypatch):
    files = make_inputs(tmp_path, ["good.pf", "vanished.pf"])
    snapshot = model.get_prefetch_files(files)
    files[1].unlink()

    def parse(path, tags):
        path.read_bytes()
        return {"source_file": str(path)}

    monkeypatch.setattr(model, "process_prefetch_file", parse)
    chunks = model.Prefetch2es(snapshot).gen_records()
    assert next(chunks) == [{"source_file": str(files[0])}]
    with pytest.raises(PartialExtractionError) as partial:
        next(chunks)
    assert "FileNotFoundError" in partial.value.diagnostics[0]["error"]


def test_publish_rechecks_output_alias(tmp_path, monkeypatch):
    source = make_inputs(tmp_path, ["one.pf"])[0]
    output = tmp_path / "out.jsonl"

    def process(filepath, **kwargs):
        output.hardlink_to(source)
        return synthetic_task(filepath, **kwargs)

    monkeypatch.setattr(model, "process_prefetch_task", process)
    with pytest.raises(ValueError, match="overwrite"):
        json_presenter.Prefetch2jsonPresenter(
            source,
            str(output),
            output_format="jsonl",
            is_quiet=True,
        ).export_json()
    assert source.read_bytes() == b"synthetic test input"
    assert output.read_bytes() == source.read_bytes()
    assert list(tmp_path.glob(".out.jsonl.*.tmp")) == []


@pytest.mark.parametrize("multiprocess", [False, True])
@pytest.mark.parametrize("timeline", [False, True])
def test_native_parser_invalid_header_becomes_partial_api_error(
    tmp_path, multiprocess, timeline
):
    for name in ("bad-one.pf", "bad-two.pf"):
        (tmp_path / name).write_bytes(b"synthetic invalid Prefetch header")

    with pytest.raises(PartialExtractionError) as partial:
        prefetch2json(str(tmp_path), multiprocess=multiprocess, timeline_mode=timeline)
    assert len(partial.value.diagnostics) == 2
    assert all("OSError" in entry["error"] for entry in partial.value.diagnostics)
    assert all("signature" in entry["error"].lower() for entry in partial.value.diagnostics)
    assert partial.value.records == []


@pytest.mark.parametrize("command", ["Prefetch2jsonView", "Prefetch2esView"])
def test_cli_uses_one_discovery_snapshot(tmp_path, monkeypatch, command):
    files = make_inputs(tmp_path / "source", ["deep/one.PF", "two.pf"])
    module = importlib.import_module("prefetch2es.views." + command)
    discover = MagicMock(wraps=model.get_prefetch_files)
    monkeypatch.setattr(module, "get_prefetch_files", discover)
    monkeypatch.setattr(model, "process_prefetch_task", synthetic_task)

    def rediscovery(*args):
        pytest.fail("enumerated inputs were discovered again")

    monkeypatch.setattr(model, "get_prefetch_files", rediscovery)
    monkeypatch.setattr(json_presenter, "get_prefetch_files", rediscovery)
    client = MagicMock()
    client.bulk_indice.side_effect = lambda records, *args: (len(records), [])
    monkeypatch.setattr(es_presenter, "ElasticsearchUtils", lambda **kwargs: client)
    argv = [command, str(files[0].parent.parent), "--quiet"]
    if command == "Prefetch2jsonView":
        argv.extend(["-o", str(tmp_path / "output.jsonl"), "--format", "jsonl"])
    monkeypatch.setattr("sys.argv", argv)
    module.entry_point()
    discover.assert_called_once()
