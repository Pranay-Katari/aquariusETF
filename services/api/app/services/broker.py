"""Paper-only adapter. Live endpoints are deliberately not configurable."""

from decimal import Decimal, ROUND_DOWN
import hashlib
import httpx
from ..config import settings


class PaperBroker:
    base = "https://paper-api.alpaca.markets"

    def request(self, method, path, **kwargs):
        if (
            not settings.paper_trading_enabled
            or not settings.alpaca_api_key
            or not settings.alpaca_api_secret
        ):
            raise ValueError(
                "Paper trading is not configured. Add server-side Alpaca paper credentials and enable PAPER_TRADING_ENABLED."
            )
        with httpx.Client(
            timeout=20,
            headers={
                "APCA-API-KEY-ID": settings.alpaca_api_key,
                "APCA-API-SECRET-KEY": settings.alpaca_api_secret,
            },
        ) as client:
            response = client.request(method, self.base + path, **kwargs)
            if response.status_code >= 400:
                raise ValueError(
                    f"Paper broker rejected the request ({response.status_code}). Check account, buying power and market availability."
                )
            return response.json()

    def account(self):
        return self.request("GET", "/v2/account")

    def asset(self, symbol):
        return self.request("GET", f"/v2/assets/{symbol}")

    def submit(self, order):
        return self.request("POST", "/v2/orders", json=order)

    def lookup(self, client_id):
        return self.request(
            "GET",
            "/v2/orders:by_client_order_id",
            params={"client_order_id": client_id},
        )


broker = PaperBroker()


def size_orders(holdings, investment, preview_id):
    orders = []
    for h in holdings:
        amount = (Decimal(str(investment)) * Decimal(str(h["target_weight"]))).quantize(
            Decimal("0.01"), rounding=ROUND_DOWN
        )
        if amount <= 0:
            continue
        orders.append(
            {
                "symbol": h["ticker"],
                "notional": str(amount),
                "side": "buy",
                "type": "market",
                "time_in_force": "day",
                "client_order_id": "aq-"
                + hashlib.sha256(f"{preview_id}:{h['ticker']}".encode()).hexdigest()[
                    :40
                ],
            }
        )
    residual = Decimal(str(investment)) - sum(
        (Decimal(o["notional"]) for o in orders), Decimal(0)
    )
    return orders, float(residual)
