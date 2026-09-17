"""Offline chunking and parser resource contracts."""
import importlib

import pytest

model = importlib.import_module("prefetch2es.models.Prefetch2es")


@pytest.fixture(autouse=True)
def prepare_prefetch():
    yield


@pytest.mark.parametrize("size", [0, -1])
@pytest.mark.parametrize("method", ["gen_records", "gen_timeline_records"])
def test_model_rejects_nonpositive_size(tmp_path, size, method):
    with pytest.raises(ValueError, match="positive"):
        list(getattr(model.Prefetch2es(tmp_path), method)(chunk_size=size))


@pytest.mark.parametrize("size", [0, -1])
def test_chunker_rejects_nonpositive_size(size):
    with pytest.raises(ValueError, match="positive"):
        list(model.generate_chunks(size, []))
