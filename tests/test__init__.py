# coding: utf-8
from hashlib import md5
from pathlib import Path

import pytest
from prefetch2es.views.Prefetch2esView import entry_point as p2e
from prefetch2es.views.Prefetch2jsonView import entry_point as p2j

# utils
def calc_md5(path: Path) -> str:
    if path.is_dir():
        return ''
    else:
        return md5(path.read_bytes()).hexdigest()


# command-line test cases
def test_prefetch2es_help(monkeypatch):
    argv = ["prefetch2es", "-h"]
    with pytest.raises(SystemExit) as exited:
        with monkeypatch.context() as m:
            m.setattr("sys.argv", argv)
            p2e()
        assert exited.value.code == 0

def test_prefetch2es_version(monkeypatch):
    argv = ["prefetch2es", "-v"]
    with pytest.raises(SystemExit) as exited:
        with monkeypatch.context() as m:
            m.setattr("sys.argv", argv)
            p2e()
        assert exited.value.code == 0

def test_prefetch2json_help(monkeypatch):
    argv = ["prefetch2json", "-h"]
    with pytest.raises(SystemExit) as exited:
        with monkeypatch.context() as m:
            m.setattr("sys.argv", argv)
            p2j()
        assert exited.value.code == 0

def test_prefetch2json_version(monkeypatch):
    argv = ["prefetch2json", "-v"]
    with pytest.raises(SystemExit) as exited:
        with monkeypatch.context() as m:
            m.setattr("sys.argv", argv)
            p2j()
        assert exited.value.code == 0

# behavior test cases 
def test__prefetch2json_convert(monkeypatch):
    path = 'tests/cache/prefetches.json'
    argv = ["prefetch2json", "-o", path, "tests/cache/"]
    with monkeypatch.context() as m:
        m.setattr("sys.argv", argv)
        p2j()
    assert calc_md5(Path(path)) == "c5c63abb890bdbd72f5ed1237a108ab2"

def test__prefetch2json_convert_multiprocessing(monkeypatch):
    path = 'tests/cache/prefetches-m.json'
    argv = ["prefetch2json", "-o", path, "-m", "tests/cache/"]
    with monkeypatch.context() as m:
        m.setattr("sys.argv", argv)
        p2j()
    assert calc_md5(Path(path)) == "c5c63abb890bdbd72f5ed1237a108ab2"

def test__prefetch2json_timeline_convert(monkeypatch):
    path = 'tests/cache/prefetches-t.json'
    argv = ["prefetch2json", "--timeline", "-o", path, "tests/cache/"]
    with monkeypatch.context() as m:
        m.setattr("sys.argv", argv)
        p2j()
    assert calc_md5(Path(path)) == "5ad06fe5ec524c940e8037248ed59e60"

def test__prefetch2json_timeline_convert_multiprocessing(monkeypatch):
    path = 'tests/cache/prefetches-t-m.json'
    argv = ["prefetch2json", "--timeline", "-o", path, "-m", "tests/cache/"]
    with monkeypatch.context() as m:
        m.setattr("sys.argv", argv)
        p2j()
    assert calc_md5(Path(path)) == "5ad06fe5ec524c940e8037248ed59e60"