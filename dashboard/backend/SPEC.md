# Dashboard backend — SPEC (vibe-coding contract)

FastAPI app that serves data to the frontend. Imports `tradinglab`.

## Endpoints
- `GET /universe` -> list of symbols
- `GET /prices/{symbol}` -> [{date, open, high, low, close, volume}]
- `GET /backtest/{strategy}` -> {dates, portfolio, benchmark}

## Run
`uv run uvicorn dashboard.backend.main:app --reload --port 8000`

## Verify
Frontend fetches from these three endpoints and renders without error.
