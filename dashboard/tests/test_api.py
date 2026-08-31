import asyncio

import httpx

from dashboard.backend.main import app


EXPECTED_SYMBOLS = ["COMI", "HRHO", "TMGH", "SWDY", "FWRY"]


def request(method: str, path: str):
    async def send():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path)

    return asyncio.run(send())


def test_health_is_ok():
    response = request("GET", "/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_universe_is_the_canonical_five_symbols():
    response = request("GET", "/universe")
    assert response.status_code == 200
    assert response.json() == EXPECTED_SYMBOLS


def test_prices_returns_parallel_json_safe_series():
    response = request("GET", "/prices/COMI")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"dates", "close"}
    assert len(body["dates"]) == len(body["close"]) > 1000
    assert body["dates"][0] == "2019-08-14"
    assert body["dates"][-1] == "2026-07-30"
    assert all(isinstance(value, float) for value in body["close"])


def test_prices_rejects_unknown_symbol():
    response = request("GET", "/prices/NOPE")
    assert response.status_code == 404
    assert response.json() == {"detail": "Unknown symbol: NOPE"}


def test_indicators_returns_default_twenty_day_sma_with_json_nulls():
    response = request("GET", "/indicators/COMI")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"dates", "sma"}
    assert len(body["dates"]) == len(body["sma"]) == 1693
    assert body["sma"][:19] == [None] * 19
    assert isinstance(body["sma"][19], float)


def test_indicators_accepts_a_valid_window():
    body = request("GET", "/indicators/COMI?window=5").json()
    assert body["sma"][:4] == [None] * 4
    assert isinstance(body["sma"][4], float)


def test_indicators_rejects_invalid_windows_and_unknown_symbols():
    assert request("GET", "/indicators/COMI?window=0").status_code == 422
    assert request("GET", "/indicators/COMI?window=1694").status_code == 422
    assert request("GET", "/indicators/NOPE").status_code == 404


def test_backtest_returns_real_dates_and_egp_curves():
    response = request("GET", "/backtest")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"dates", "portfolio", "benchmark"}
    assert len(body["dates"]) == len(body["portfolio"]) == len(body["benchmark"]) == 1662
    assert body["dates"][0] == "2019-09-26"
    assert body["dates"][-1] == "2026-07-30"
    assert body["portfolio"][0] == 1000.0
    assert 900.0 < body["benchmark"][0] < 1100.0
    assert all(isinstance(value, float) for value in body["portfolio"])
    assert all(isinstance(value, float) for value in body["benchmark"])


def test_metrics_are_rounded_results_of_portfolio_returns():
    response = request("GET", "/metrics")
    assert response.status_code == 200
    assert response.json() == {
        "total_return": 4.18,
        "sharpe": 0.993,
        "max_drawdown": 0.397,
    }
