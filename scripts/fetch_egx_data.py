"""
fetch_egx_data.py — one-off generator for the committed sample data.
Run locally to (re)generate data/egx/*.csv. The repo never calls Yahoo at
runtime. Set auto_adjust=True to get adjusted OHLC directly in the columns.

    uv run --with yfinance python scripts/fetch_egx_data.py
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd
import yfinance as yf

# A broad universe of liquid EGX names for the "pick k of N" RL task.
# NOTE: EGX30 membership changes ~twice a year. This is a FIXED historical
# universe, so it carries mild survivorship bias — teach that as a lesson, don't
# hide it. Verify/trim tickers before a real run; some may delist or rename.
SYMBOLS = {
    "COMI": "COMI.CA",  # CIB
    "HRHO": "HRHO.CA",  # EFG Holding
    "TMGH": "TMGH.CA",  # Talaat Moustafa
    "SWDY": "SWDY.CA",  # Elsewedy Electric
    "FWRY": "FWRY.CA",  # Fawry
    "EAST": "EAST.CA",  # Eastern Company
    "ABUK": "ABUK.CA",  # Abu Qir Fertilizers
    "MFPC": "MFPC.CA",  # Misr Fertilizers (MOPCO)
    "SKPC": "SKPC.CA",  # Sidi Kerir Petrochemicals
    "EFIH": "EFIH.CA",  # e-finance
    "CIEB": "CIEB.CA",  # Credit Agricole Egypt
    "ADIB": "ADIB.CA",  # Abu Dhabi Islamic Bank Egypt
    "SAUD": "SAUD.CA",  # Saudi Egyptian Investment
    "HELI": "HELI.CA",  # Heliopolis Housing
    "MNHD": "MNHD.CA",  # Madinet Nasr Housing
    "PHDC": "PHDC.CA",  # Palm Hills Developments
    "ORWE": "ORWE.CA",  # Oriental Weavers
    "JUFO": "JUFO.CA",  # Juhayna Food
    "DOMTY": "DOMT.CA",  # Domty
    "AMOC": "AMOC.CA",  # Alexandria Mineral Oils
    "SUGR": "SUGR.CA",  # Delta Sugar
    "ISPH": "ISPH.CA",  # Ibnsina Pharma
    "RMDA": "RMDA.CA",  # Tenth of Ramadan Pharma (Rameda)
    "CCAP": "CCAP.CA",  # Qalaa Holdings
    "GBCO": "GBCO.CA",  # GB Corp (GB Auto)
    "BTFH": "BTFH.CA",  # Beltone Financial
    "ALCN": "ALCN.CA",  # Alexandria Container
    "ETEL": "ETEL.CA",   # Telecom Egypt
    "RAYA": "RAYA.CA",   # Raya Holding
    "MCQE": "MCQE.CA",   # Misr Cement (Qena)
    "EGAL": "EGAL.CA",   # Egypt Aluminum
    "OHOD": "OHOD.CA",   # Orascom Hotels & Development
    "ARCC": "ARCC.CA",   # Arabian Cement Co
    "EMFD": "EMFD.CA",   # Emaar Misr for Development
    "EFID": "EFID.CA",   # Edita Food Industries
    "OTMT": "OTMT.CA",   # Orascom Investment Holding (Telecom Media Technology)
    "ORAS": "ORAS.CA",   # Orascom Construction — CAUTION: also lists in London (OC.L); confirm this is the EGX line
    "KIMA": "KIMA.CA",   # Kima — Egypt Chemical Industries — CAUTION: ticker least certain of this batch

    # "EGX30": "^CASE30",  # index (benchmark)
}
START, END = "2015-01-01", None
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "egx"
COLS = ["open", "high", "low", "close", "volume"]

def fetch_one(sym: str) -> pd.DataFrame:
    raw = yf.download(sym, start=START, end=END, interval="1d",
                      auto_adjust=False, progress=False)   # adjusted OHLC
    if raw is None or raw.empty:
        raise RuntimeError(f"no data for {sym}")
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    raw = raw.rename(columns=str.lower)
    df = raw[[c for c in COLS if c in raw.columns]].copy()
    df.index.name = "date"; df = df.reset_index()
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    return df.dropna(subset=["close"]).reset_index(drop=True)

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, ysym in SYMBOLS.items():
        try:
            df = fetch_one(ysym)
        except Exception as exc:
            print(f"{name}: FAILED {exc}"); continue
        df.to_csv(OUT_DIR / f"{name}.csv", index=False)
        print(f"{name}: {len(df)} rows")

if __name__ == "__main__":
    main()
