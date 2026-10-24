"""Bounded result buffering and cleanup through an actual spawn Pool."""

import importlib
import multiprocessing as mp
import os
import time
from types import SimpleNamespace

import pytest

model = importlib.import_module("prefetch2es.models.Prefetch2es")


def payload_task(filepath, tags="", timeline_mode=False):
    """Replace only parsing; each completed file produces a sizable result."""
    records = [
        {"source_file": str(filepath), "ordinal": i, "payload": "x" * (128 * 1024)}
        for i in range(3 if timeline_mode else 1)
    ]
    filepath.with_suffix(".done").touch()
    return filepath, records, None


def gated_task(filepath, tags="", timeline_mode=False):
    if tags == "gate-first" and filepath.stem == "000":
        deadline = time.monotonic() + 10
        while not filepath.with_name("001.done").exists():
            if time.monotonic() >= deadline:
                raise TimeoutError("the second file never completed")
            time.sleep(0.005)
    return payload_task(filepath, timeline_mode=timeline_mode)


def failed_task(filepath, tags="", timeline_mode=False):
    raise RuntimeError("unexpected worker failure")


def pool_fence():
    return os.getpid()


@pytest.fixture
def real_spawn_pool(monkeypatch):
    context = mp.get_context("spawn")
    pools = []
    children = []

    def create_pool(workers):
        pool = context.Pool(workers)
        pools.append(pool)
        children.extend(pool._pool)
        return pool

    monkeypatch.setattr(model.Prefetch2es, "get_cpu_count", lambda self: 2)
    monkeypatch.setattr(
        model.Prefetch2es,
        "get_multiprocessing_context",
        lambda self: SimpleNamespace(Pool=create_pool),
    )
    yield pools, children
    for pool in pools:
        pool.terminate()
        pool.join()


@pytest.mark.parametrize("timeline", [False, True])
def test_stalled_consumer_bounds_completed_files_and_close_reaps_workers(
    tmp_path, monkeypatch, real_spawn_pool, timeline
):
    files = [tmp_path / f"{i:03}.pf" for i in range(128)]
    monkeypatch.setattr(model, "process_prefetch_task", payload_task)
    prefetch = model.Prefetch2es(files)
    method = prefetch.gen_timeline_records if timeline else prefetch.gen_records
    records = method(multiprocess=True, chunk_size=1)
    pools, children = real_spawn_pool
    try:
        first = next(records)
        assert first[0]["source_file"] == str(files[0])
        # These probes sit behind the work already submitted to the real Pool.
        # With imap, its feeder exhausts all 128 inputs before servicing them.
        # Waiting for probes gives that feeder time without consuming output.
        fences = [pools[0].apply_async(pool_fence) for _ in range(2)]
        assert all(fence.get(timeout=15) != os.getpid() for fence in fences)
        completed = list(tmp_path.glob("*.done"))
        assert 1 <= len(completed) <= 4
        assert prefetch.successful_files == 1
        assert prefetch.generated_records == (3 if timeline else 1)
        assert prefetch.diagnostics == []
    finally:
        records.close()
    assert children and all(not child.is_alive() for child in children)
    assert all(child.exitcode is not None for child in children)


@pytest.mark.parametrize("timeline", [False, True])
def test_spawn_results_keep_input_order_and_serial_chunking(
    tmp_path, monkeypatch, real_spawn_pool, timeline
):
    files = [tmp_path / f"{i:03}.pf" for i in range(6)]
    monkeypatch.setattr(model, "process_prefetch_task", gated_task)
    prefetch = model.Prefetch2es(files)
    method = prefetch.gen_timeline_records if timeline else prefetch.gen_records

    parallel = list(method(multiprocess=True, chunk_size=4, tags="gate-first"))
    serial = list(method(multiprocess=False, chunk_size=4))

    assert parallel == serial
    assert all(len(chunk) == 4 for chunk in parallel[:-1])
    assert [record["source_file"] for chunk in parallel for record in chunk] == [
        str(path) for path in files for _ in range(3 if timeline else 1)
    ]
    _, children = real_spawn_pool
    assert all(not child.is_alive() for child in children)


def test_unexpected_worker_exception_reaps_pool(tmp_path, monkeypatch, real_spawn_pool):
    monkeypatch.setattr(model, "process_prefetch_task", failed_task)
    prefetch = model.Prefetch2es([tmp_path / "first.pf", tmp_path / "second.pf"])

    with pytest.raises(RuntimeError, match="unexpected worker failure"):
        list(prefetch.gen_records(multiprocess=True, chunk_size=1))

    _, children = real_spawn_pool
    assert children and all(not child.is_alive() for child in children)
    assert all(child.exitcode is not None for child in children)
