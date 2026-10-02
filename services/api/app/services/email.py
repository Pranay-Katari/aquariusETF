"""Transactional delivery for completed backtest reports."""

from __future__ import annotations

import base64
from html import escape

import httpx


class EmailDeliveryError(RuntimeError):
    """A provider-safe error that can be shown to an API caller."""


def _percent(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.2f}%"


def report_html(name: str, artifact: dict) -> str:
    metrics = artifact["metrics"]
    config = artifact["metadata"]["config"]
    safe_name = escape(name)
    return f"""<!doctype html>
<html><body style="margin:0;background:#08111f;color:#e8effc;font-family:Arial,sans-serif">
  <main style="max-width:620px;margin:0 auto;padding:36px 24px">
    <p style="margin:0 0 12px;color:#35d7c9;font-size:12px;font-weight:700;letter-spacing:1px">AQUARIUS BASKETS</p>
    <h1 style="margin:0 0 8px;font-size:28px">{safe_name} backtest report</h1>
    <p style="margin:0 0 28px;color:#aebed7">Historical simulation summary · not investment advice</p>
    <table role="presentation" width="100%" style="border-collapse:separate;border-spacing:8px 0"><tr>
      <td style="padding:16px;background:#12213a;border-radius:10px"><small style="color:#aebed7">Ending value</small><br><strong>${metrics['ending_value']:,.0f}</strong></td>
      <td style="padding:16px;background:#12213a;border-radius:10px"><small style="color:#aebed7">CAGR</small><br><strong>{_percent(metrics.get('cagr'))}</strong></td>
      <td style="padding:16px;background:#12213a;border-radius:10px"><small style="color:#aebed7">Max drawdown</small><br><strong>{_percent(metrics.get('max_drawdown'))}</strong></td>
    </tr></table>
    <p style="margin:28px 0 0;color:#aebed7;font-size:14px">Benchmark: {escape(config['benchmark'])} · Rebalance: {escape(config['rebalance_frequency'])}</p>
    <p style="margin:18px 0 0;color:#8092b0;font-size:12px;line-height:1.5">The attached tear sheet contains the allocation and backtest metrics. Hypothetical results include assumed costs and do not predict future performance.</p>
  </main>
</body></html>"""


def send_backtest_report(*, api_key: str, sender: str, recipient: str, name: str, artifact: dict, pdf: bytes, idempotency_key: str) -> str:
    if not api_key or not sender or not recipient:
        raise EmailDeliveryError("Email delivery is not configured")
    payload = {
        "from": sender,
        "to": [recipient],
        "subject": f"Aquarius Baskets · {name} backtest report",
        "html": report_html(name, artifact),
        "attachments": [{"filename": "aquarius-backtest-tear-sheet.pdf", "content": base64.b64encode(pdf).decode("ascii")}],
    }
    try:
        response = httpx.post("https://api.resend.com/emails", headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "Idempotency-Key": idempotency_key}, json=payload, timeout=20)
    except httpx.HTTPError as exc:
        raise EmailDeliveryError("Email provider is unavailable. Try again shortly.") from exc
    if response.status_code >= 400:
        raise EmailDeliveryError("Email provider rejected the delivery. Verify the sending domain and recipient.")
    provider_id = response.json().get("id")
    if not provider_id:
        raise EmailDeliveryError("Email provider returned an invalid delivery response")
    return provider_id
