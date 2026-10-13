"""Offline chunking and parser resource contracts."""
import importlib

import pytest

model = importlib.import_module("prefetch2es.models.Prefetch2es")



@pytest.mark.parametrize("size", [0, -1, 0.5, 1.5, True, "2"])
@pytest.mark.parametrize("method", ["gen_records", "gen_timeline_records"])
def test_model_rejects_invalid_size(tmp_path, size, method):
    with pytest.raises(ValueError, match="greater than zero"):
        list(getattr(model.Prefetch2es(tmp_path), method)(chunk_size=size))
