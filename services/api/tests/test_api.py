from fastapi.testclient import TestClient
import pytest
from services.api.app.main import app
from services.api.app.auth import current_user, _hits


@pytest.fixture
def client():
    _hits.clear()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def portfolio(client):
    response = client.post(
        "/v1/etfs",
        json={
            "name": "Test basket",
            "holdings": [{"ticker": "SPY", "target_weight": 1}],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def request(p):
    return {
        "etf_id": p["id"],
        "portfolio_version": p["version"],
        "start_date": "2024-01-02",
        "end_date": "2024-03-28",
    }


def test_create_edit_version_and_immutable_result(client):
    p = portfolio(client)
    r = client.post("/v1/backtests", json=request(p))
    assert r.status_code == 202, r.text
    id = r.json()["id"]
    before = client.get(f"/v1/backtests/{id}/artifact").json()
    assert before["metrics"]["beta"] == pytest.approx(1)
    edited = client.patch(
        f"/v1/etfs/{p['id']}",
        json={
            "name": "Changed",
            "expected_version": 1,
            "holdings": [{"ticker": "QQQ", "target_weight": 1}],
        },
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["version"] == 2
    assert client.get(f"/v1/backtests/{id}/artifact").json() == before
    assert client.post("/v1/backtests", json=request(p)).status_code == 409
    assert (
        client.patch(
            f"/v1/etfs/{p['id']}",
            json={"name": "Overwrite", "expected_version": 1, "holdings": []},
        ).status_code
        == 409
    )


def test_validation(client):
    for holdings in [
        [{"ticker": "SPY", "target_weight": 0.5}],
        [{"ticker": "SPY", "target_weight": -0.1}],
        [
            {"ticker": "SPY", "target_weight": 0.5},
            {"ticker": "SPY", "target_weight": 0.5},
        ],
        [{"ticker": "INVALID", "target_weight": 1}],
    ]:
        assert (
            client.post(
                "/v1/etfs", json={"name": "Invalid", "holdings": holdings}
            ).status_code
            == 422
        )
    p = portfolio(client)
    assert (
        client.post(
            "/v1/backtests", json={**request(p), "end_date": "2099-01-01"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/v1/backtests", json={**request(p), "dividend_mode": "cash"}
        ).status_code
        == 422
    )


def test_ownership(client):
    p = portfolio(client)
    app.dependency_overrides[current_user] = lambda: "different-user"
    assert client.get(f"/v1/etfs/{p['id']}").status_code == 404
    assert client.get("/v1/etfs").json() == []
    assert client.post("/v1/backtests", json=request(p)).status_code == 404


def test_research_and_constraints(client):
    r = client.post(
        "/v1/etfs/generate",
        json={
            "prompt": "AI data center infrastructure",
            "max_holdings": 5,
            "max_weight": 0.2,
        },
    )
    assert r.status_code == 201, r.text
    assert len(r.json()["etf"]["holdings"]) == 5
    assert all(h["sources"] for h in r.json()["etf"]["holdings"])
    assert (
        client.post(
            "/v1/etfs/generate",
            json={"prompt": "AI infrastructure", "max_holdings": 5, "max_weight": 0.1},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/v1/etfs/generate", json={"prompt": "AI infrastructure excluding cloud"}
        ).status_code
        == 422
    )


def test_preview_and_submission_disabled(client):
    p = portfolio(client)
    r = client.post(
        "/v1/orders/preview",
        json={"etf_id": p["id"], "portfolio_version": 1, "investment": 1234.56},
    )
    assert r.status_code == 201, r.text
    assert r.json()["orders"][0]["notional"] == "1234.56"
    assert r.json()["broker_validated"] is False
    assert (
        client.post(
            "/v1/orders/paper", json={"preview_id": r.json()["id"], "confirmed": True}
        ).status_code
        == 403
    )


def test_series_range_and_artifact_checksum(client):
    p = portfolio(client)
    r = client.post("/v1/backtests", json=request(p)).json()
    data = client.get(f"/v1/backtests/{r['id']}/series?range=5D").json()
    assert len(data["portfolio"]) == 5
    assert data["portfolio"] == data["benchmark"]
    assert (
        client.get(f"/v1/backtests/{r['id']}/series?resolution=1m").status_code == 422
    )
    assert len(client.get(f"/v1/backtests/{r['id']}").json()["checksum"]) == 64
