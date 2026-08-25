"""FastAPI backend for the dashboard. Grows via dashboard/tasks.
Run: uv run uvicorn dashboard.backend.main:app --reload --port 8000
"""
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from tradinglab.data_feed import DataFeed

app = FastAPI(title="Younit-style trading dashboard")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

feed = DataFeed.from_dir("data/egx", symbols=["COMI", "HRHO", "TMGH", "SWDY", "FWRY"])


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/universe")
def universe():
    return feed.symbols


@app.get("/prices/{symbol}")
def prices(symbol: str):
    if symbol not in feed.symbols:
        raise HTTPException(status_code=404, detail="Unknown symbol")

    symbol_index = feed.symbols.index(symbol)
    return {
        "dates": [date.strftime("%Y-%m-%d") for date in feed.dates],
        "close": feed.close[:, symbol_index].tolist(),
    }
