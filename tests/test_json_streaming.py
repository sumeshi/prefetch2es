"""JSON array output stays compatible while retaining only the current chunk."""

import importlib

import orjson
import pytest

from prefetch2es.models.Prefetch2es import PartialExtractionError
from prefetch2es.presenters.Prefetch2jsonPresenter import Prefetch2jsonPresenter

MODULE = importlib.import_module(Prefetch2jsonPresenter.__module__)


def _model(monkeypatch, chunks, state, error=None):
    class Model:
        generated_records = 0

        def __init__(self, paths, input_diagnostics=()):
            self.generated_records = 0

        def gen_records(self, **kwargs):
            state["arguments"] = kwargs
            try:
                for chunk in chunks:
                    self.generated_records += len(chunk)
                    yield chunk
                if error is not None:
                    raise error
            finally:
                state["closed"] = True

        gen_timeline_records = gen_records

    monkeypatch.setattr(MODULE, "Prefetch2es", Model)


def _presenter(tmp_path, **kwargs):
    source = tmp_path / "input.pf"
    source.write_bytes(b"evidence")
    return Prefetch2jsonPresenter(
        source, str(tmp_path / "output.json"), input_files=[source], **kwargs
    )


@pytest.mark.parametrize("quiet", [False, True])
@pytest.mark.parametrize("timeline", [False, True])
def test_json_is_written_before_requesting_the_next_chunk(
    tmp_path, monkeypatch, quiet, timeline
):
    first = {"name": "日本語", "nested": {"items": [True, None]}}
    second = {"name": "second"}
    state = {}

    def chunks():
        yield [first]
        temporary = list(tmp_path.glob(".output.json.*.tmp"))
        assert len(temporary) == 1
        assert temporary[0].read_bytes() == orjson.dumps(
            [first], option=orjson.OPT_INDENT_2
        )[:-2]
        assert not (tmp_path / "output.json").exists()
        yield [second]

    _model(monkeypatch, chunks(), state)
    presenter = _presenter(
        tmp_path, is_quiet=quiet, timeline_mode=timeline,
        chunk_size=1, multiprocess=True, tags=["host"],
    )
    presenter.export_json()

    assert presenter.output_path.read_bytes() == orjson.dumps(
        [first, second], option=orjson.OPT_INDENT_2
    )
    assert state == {
        "arguments": {"tags": ["host"], "multiprocess": True, "chunk_size": 1},
        "closed": True,
    }
    assert list(tmp_path.glob(".output.json.*.tmp")) == []


@pytest.mark.parametrize(
    "chunks",
    [
        [],
        [[], []],
        [[{}]],
        [[], [{"name": "日本語", "line": "one\ntwo", "path": "C:\\one"}], []],
        [
            [{"values": [None, True, False, 0, -1, 1.5], "empty": {}}],
            [],
            [{"second": [{"empty": []}, ["a", "b"]]}, {"third": 3}],
        ],
    ],
    ids=["empty", "empty-chunks", "empty-object", "unicode", "nested-multiple"],
)
def test_streamed_array_matches_complete_array_bytes(tmp_path, monkeypatch, chunks):
    state = {}
    _model(monkeypatch, chunks, state)
    presenter = _presenter(tmp_path, is_quiet=True)

    presenter.export_json()

    assert presenter.output_path.read_bytes() == orjson.dumps(
        [record for chunk in chunks for record in chunk], option=orjson.OPT_INDENT_2
    )
    assert state["closed"]
    assert list(tmp_path.glob(".output.json.*.tmp")) == []


@pytest.mark.parametrize("quiet", [False, True])
@pytest.mark.parametrize("failure", ["serialize", "write", "parse"])
def test_late_failure_preserves_existing_output_and_closes_stream(
    tmp_path, monkeypatch, quiet, failure
):
    output = tmp_path / "output.json"
    output.write_bytes(b"previous output")
    state = {}
    chunks = [[{"first": 1}], [{"second": {1, 2} if failure == "serialize" else 2}]]
    terminal_error = RuntimeError("parse failed") if failure == "parse" else None
    _model(monkeypatch, chunks, state, terminal_error)

    if failure == "write":
        original = MODULE.NamedTemporaryFile

        class FailingWriter:
            def __init__(self, *args, **kwargs):
                self.output = original(*args, **kwargs)
                self.name = self.output.name

            def __enter__(self):
                self.output.__enter__()
                return self

            def __exit__(self, *args):
                return self.output.__exit__(*args)

            def write(self, payload):
                if b'"second"' in payload:
                    raise OSError("write failed")
                return self.output.write(payload)

            def flush(self):
                return self.output.flush()

        monkeypatch.setattr(MODULE, "NamedTemporaryFile", FailingWriter)

    error_type = {"serialize": TypeError, "write": OSError, "parse": RuntimeError}[failure]
    with pytest.raises(error_type) as caught:
        _presenter(tmp_path, is_quiet=quiet).export_json()

    # Keep the traceback alive: cleanup must not depend on garbage collection.
    assert caught.value is not None
    assert state["closed"]
    assert output.read_bytes() == b"previous output"
    assert list(tmp_path.glob(".output.json.*.tmp")) == []
    assert (tmp_path / "input.pf").read_bytes() == b"evidence"


@pytest.mark.parametrize("quiet", [False, True])
@pytest.mark.parametrize("recoverable", [False, True])
def test_partial_extraction_publishes_only_recovered_output(
    tmp_path, monkeypatch, quiet, recoverable
):
    output = tmp_path / "output.json"
    output.write_bytes(b"previous output")
    records = [{"recovered": "日本語"}] if recoverable else []
    error = PartialExtractionError([{"source_file": "bad.pf", "error": "unreadable"}])
    state = {}
    _model(monkeypatch, [records], state, error)

    with pytest.raises(PartialExtractionError) as caught:
        _presenter(tmp_path, is_quiet=quiet).export_json()

    assert caught.value is error
    assert output.read_bytes() == (
        orjson.dumps(records, option=orjson.OPT_INDENT_2)
        if recoverable else b"previous output"
    )
    assert state["closed"]
    assert list(tmp_path.glob(".output.json.*.tmp")) == []
