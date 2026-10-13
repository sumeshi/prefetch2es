# coding: utf-8
from hashlib import md5, sha256
import json
from pathlib import Path
from shutil import copytree

import pytest
from prefetch2es.views.Prefetch2esView import entry_point as p2e
from prefetch2es.views.Prefetch2jsonView import entry_point as p2j

# utils
def calc_md5(path: Path) -> str:
    if path.is_dir():
        return ''
    else:
        return md5(path.read_bytes()).hexdigest()


def assert_content(path: str, count: int, digest: str, timeline: bool = False) -> None:
    # Verified against the committed presenter with the MD5-checked samples.
    # JSON object key order is not part of the record contract.
    records = json.loads(Path(path).read_bytes())
    assert len(records) == count
    # Evidence directories depend on the checkout or temporary test directory.
    for record in records:
        if timeline:
            record['log']['file']['path'] = Path(record['log']['file']['path']).name
        else:
            record['source_file'] = Path(record['source_file']).name
    canonical = json.dumps(
        sorted(records, key=lambda record: json.dumps(record, sort_keys=True)),
        sort_keys=True, separators=(',', ':'), ensure_ascii=False,
    ).encode()
    assert sha256(canonical).hexdigest() == digest


NORMAL_DIGEST = '5c390eaede713c89f0fed925dd183ea19c8bf12258dde4d6a653d6fc8f04c615'
TIMELINE_DIGEST = 'd7c73eb02fba664788359215d0700ab98a687c0e83a270a968d9b1e485f32696'


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


def test_version_is_defined_in_about_module():
    from prefetch2es import __version__
    from prefetch2es.__about__ import __version__ as about_version

    assert __version__ == about_version


# behavior test cases 
@pytest.mark.usefixtures("prepare_prefetch")
def test__prefetch2json_convert(monkeypatch, tmp_path):
    input_path = copytree('tests/cache', tmp_path / 'cache')
    path = str(tmp_path / 'prefetches.json')
    argv = ["prefetch2json", "-o", path, str(input_path)]
    with monkeypatch.context() as m:
        m.setattr("sys.argv", argv)
        p2j()
    assert_content(path, 6, NORMAL_DIGEST)

@pytest.mark.usefixtures("prepare_prefetch")
def test__prefetch2json_convert_multiprocessing(monkeypatch):
    path = 'tests/cache/prefetches-m.json'
    argv = ["prefetch2json", "-o", path, "-m", "tests/cache/"]
    with monkeypatch.context() as m:
        m.setattr("sys.argv", argv)
        p2j()
    assert_content(path, 6, NORMAL_DIGEST)

@pytest.mark.usefixtures("prepare_prefetch")
def test__prefetch2json_timeline_convert(monkeypatch):
    path = 'tests/cache/prefetches-t.json'
    argv = ["prefetch2json", "--timeline", "-o", path, "tests/cache/"]
    with monkeypatch.context() as m:
        m.setattr("sys.argv", argv)
        p2j()
    assert_content(path, 29, TIMELINE_DIGEST, timeline=True)

@pytest.mark.usefixtures("prepare_prefetch")
def test__prefetch2json_timeline_convert_multiprocessing(monkeypatch):
    path = 'tests/cache/prefetches-t-m.json'
    argv = ["prefetch2json", "--timeline", "-o", path, "-m", "tests/cache/"]
    with monkeypatch.context() as m:
        m.setattr("sys.argv", argv)
        p2j()
    assert_content(path, 29, TIMELINE_DIGEST, timeline=True)
