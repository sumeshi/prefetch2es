"""Public chunk-size validation happens before I/O or client creation."""

import importlib
from unittest.mock import MagicMock

import pytest

import prefetch2es as api
from prefetch2es.presenters.Prefetch2esPresenter import Prefetch2esPresenter
from prefetch2es.presenters.Prefetch2jsonPresenter import Prefetch2jsonPresenter

es_presenter = importlib.import_module(
    "prefetch2es.presenters.Prefetch2esPresenter"
)

INVALID_SIZES = [0, -1, 1.5, True, False, None, "1"]


@pytest.mark.parametrize("size", INVALID_SIZES)
def test_python_apis_reject_invalid_size_before_presenter_or_path_io(
    tmp_path, monkeypatch, size
):
    input_path = str(tmp_path / "unused")
    es_factory = MagicMock()
    prefetch_factory = MagicMock()
    resolve = MagicMock(side_effect=AssertionError("resolved path before validation"))
    monkeypatch.setattr(api, "Prefetch2esPresenter", es_factory)
    monkeypatch.setattr(api, "Prefetch2es", prefetch_factory)
    monkeypatch.setattr(type(tmp_path), "resolve", resolve)

    with pytest.raises(ValueError, match="greater than zero"):
        api.prefetch2es("unused", chunk_size=size)
    with pytest.raises(ValueError, match="greater than zero"):
        api.prefetch2json(input_path, chunk_size=size)

    es_factory.assert_not_called()
    prefetch_factory.assert_not_called()
    resolve.assert_not_called()


@pytest.mark.parametrize("size", [0, 1.5])
def test_es_presenter_rejects_invalid_size_before_client_creation(
    monkeypatch, size
):
    client_factory = MagicMock()
    monkeypatch.setattr(es_presenter, "ElasticsearchUtils", client_factory)

    with pytest.raises(ValueError, match="greater than zero"):
        Prefetch2esPresenter("unused", chunk_size=size).bulk_import()

    client_factory.assert_not_called()


@pytest.mark.parametrize("size", [0, 1.5])
def test_json_presenter_rejects_invalid_size_before_output_io(
    tmp_path, monkeypatch, size
):
    source = tmp_path / "input.pf"
    source.write_bytes(b"evidence")
    destination = tmp_path / "output.json"
    destination.write_bytes(b"existing output")
    temp_factory = MagicMock()
    monkeypatch.setattr(
        "prefetch2es.presenters.Prefetch2jsonPresenter.NamedTemporaryFile",
        temp_factory,
    )

    with pytest.raises(ValueError, match="greater than zero"):
        Prefetch2jsonPresenter(source, str(destination), chunk_size=size)

    temp_factory.assert_not_called()
    assert destination.read_bytes() == b"existing output"
