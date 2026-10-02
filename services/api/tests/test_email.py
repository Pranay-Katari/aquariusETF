from unittest.mock import Mock, patch

from services.api.app.services.email import send_backtest_report


def test_report_email_uses_server_side_attachment_and_idempotency_key():
    response = Mock(status_code=200)
    response.json.return_value = {"id": "email_123"}
    artifact = {
        "metrics": {"ending_value": 11800, "cagr": 0.12, "max_drawdown": -0.18},
        "metadata": {"config": {"benchmark": "SPY", "rebalance_frequency": "monthly"}},
    }
    with patch("services.api.app.services.email.httpx.post", return_value=response) as post:
        provider_id = send_backtest_report(
            api_key="server-only-key",
            sender="Aquarius <reports@aquariusbaskets.app>",
            recipient="owner@example.com",
            name="Growth basket",
            artifact=artifact,
            pdf=b"%PDF-test",
            idempotency_key="backtest-report/test/checksum",
        )
    assert provider_id == "email_123"
    assert post.call_args.kwargs["headers"]["Idempotency-Key"] == "backtest-report/test/checksum"
    assert post.call_args.kwargs["json"]["attachments"][0]["content"]
