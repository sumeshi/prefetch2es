import importlib
from pathlib import Path
from unittest.mock import MagicMock
import pytest

@pytest.mark.parametrize("failure", ["partial", "transport"])
def test_bulk_failures_propagate_and_close(monkeypatch, failure):
    module = importlib.import_module("prefetch2es.presenters.Prefetch2esPresenter")
    presenter = module.Prefetch2esPresenter(Path("input"), is_quiet=True)
    state = []
    def chunks():
        try:
            yield [{"id": 1}]
            pytest.fail("continued after failed batch")
        finally:
            state.append("closed")
    monkeypatch.setattr(presenter, "prefetch2es", chunks)
    client = MagicMock()
    if failure == "partial":
        client.bulk_indice.return_value = (0, [{"error": "rejected"}])
    else:
        client.bulk_indice.side_effect = RuntimeError("transport failed")
    monkeypatch.setattr(module, "ElasticsearchUtils", lambda **kwargs: client)
    with pytest.raises(RuntimeError):
        presenter.bulk_import()
    client.close.assert_called_once()
    assert state == ["closed"]


def test_bulk_failure_reports_bounded_details_and_total_success(monkeypatch):
    module = importlib.import_module("prefetch2es.presenters.Prefetch2esPresenter")
    logger = MagicMock()
    presenter = module.Prefetch2esPresenter(
        Path("input"), index="events", pipeline="normalize", logger=logger
    )
    state = []
    first_batch = [{"id": 1}, {"id": 2}]
    second_batch = [{"id": number} for number in range(3, 8)]

    def chunks():
        try:
            yield first_batch
            yield second_batch
            pytest.fail("continued after partially failed batch")
        finally:
            state.append("closed")

    failures = [
        {
            "index": {
                "_id": f"failed-{number}",
                "status": 400,
                "error": {
                    "type": "document_parsing_exception",
                    "reason": f"field-{number}: " + "x" * 500 + "hidden-tail",
                },
            }
        }
        for number in range(1, 5)
    ]
    client = MagicMock()
    client.bulk_indice.side_effect = [(2, []), (1, failures)]
    monkeypatch.setattr(presenter, "prefetch2es", chunks)
    monkeypatch.setattr(module, "ElasticsearchUtils", lambda **kwargs: client)

    with pytest.raises(RuntimeError) as caught:
        presenter.bulk_import()

    message = str(caught.value)
    assert "failed to index 4 document(s); 3 indexed before stopping." in message
    for number, failure in enumerate(failures[:3], start=1):
        reason = failure["index"]["error"]["reason"]
        assert (
            f"index id=failed-{number} status=400 document_parsing_exception: "
            + reason[:500]
        ) in message
        assert reason[:501] not in message
    assert "failed-4" not in message
    assert "field-4" not in message
    assert "hidden-tail" not in message
    assert client.bulk_indice.call_count == 2
    assert client.bulk_indice.call_args_list[0].args == (
        first_batch, "events", "normalize"
    )
    assert client.bulk_indice.call_args_list[1].args == (
        second_batch, "events", "normalize"
    )
    client.close.assert_called_once()
    assert state == ["closed"]
    logger.assert_not_called()


@pytest.mark.parametrize(
    ("failure", "detail"),
    [
        ({"index": {"error": "rejected"}}, "index id=? status=? error: rejected"),
        ({"create": {}}, "create id=? status=? error: unknown"),
        ({"index": "rejected"}, ""),
    ],
)
def test_bulk_failure_keeps_summary_when_details_are_incomplete(
    monkeypatch, failure, detail
):
    module = importlib.import_module("prefetch2es.presenters.Prefetch2esPresenter")
    presenter = module.Prefetch2esPresenter(Path("input"), is_quiet=True)
    client = MagicMock()
    client.bulk_indice.return_value = (0, [failure])
    monkeypatch.setattr(presenter, "prefetch2es", lambda: iter([[{"id": 1}]]))
    monkeypatch.setattr(module, "ElasticsearchUtils", lambda **kwargs: client)

    with pytest.raises(RuntimeError) as caught:
        presenter.bulk_import()

    assert str(caught.value) == (
        "Elasticsearch failed to index 1 document(s); "
        "0 indexed before stopping. " + detail
    )
    client.close.assert_called_once()


def test_cli_passes_tls_options(tmp_path, monkeypatch):
    module = importlib.import_module("prefetch2es.views.Prefetch2esView")
    source = tmp_path / "sample.pf"
    source.write_bytes(b"regf" + b"\0" * 4096)
    client = MagicMock()
    monkeypatch.setattr(module, "Prefetch2esPresenter", client)
    monkeypatch.setattr("sys.argv", ["prefetch2es", str(source), "--ca-certs", "ca.pem", "--no-verify-certs"])
    module.Prefetch2esView().run()
    assert client.call_args.kwargs["ca_certs"] == "ca.pem"
    assert client.call_args.kwargs["verify_certs"] is False

def test_tls_options(monkeypatch):
    module = importlib.import_module("prefetch2es.models.ElasticsearchUtils")
    client = MagicMock()
    monkeypatch.setattr(module, "Elasticsearch", client)
    module.ElasticsearchUtils("localhost", 9200, "https", "user", "", ca_certs="ca.pem")
    assert client.call_args.kwargs["verify_certs"] is True
    assert client.call_args.kwargs["ca_certs"] == "ca.pem"
    assert client.call_args.kwargs["basic_auth"] == ("user", "")
