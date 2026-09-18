"""Reject unverified source before building the bundled library."""

import importlib.util
import io
from pathlib import Path

import pytest


def test_bad_source_checksum_stops_before_install(tmp_path, monkeypatch):
    script = (
        Path(__file__).resolve().parents[1]
        / ".github/prepare_release_sources.py"
    )
    spec = importlib.util.spec_from_file_location(
        "prepare_release_sources", script
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(
        module, "urlopen", lambda *a, **kw: io.BytesIO(b"wrong source")
    )

    def unexpected_install(*args, **kwargs):
        pytest.fail("Unverified source must not be installed")

    monkeypatch.setattr(module.subprocess, "run", unexpected_install)
    output = tmp_path / "sources"
    with pytest.raises(RuntimeError, match="checksum"):
        module.prepare(output)
    assert not output.exists()
