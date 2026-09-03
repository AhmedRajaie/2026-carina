"""
lstm_strategy.py — a sequence-aware sibling to mlp_strategy.py.

The MLP strategies score each day using a single flat feature vector
(observation[:, -1, :]) — they have no memory of what happened on prior
days beyond whatever the hand-built features already encode. LSTMUniverseStrategy
instead feeds the model a trailing SEQ_LEN-day window of features per stock,
so the model can learn temporal patterns across the window rather than just
today's snapshot.

Because MLP's training path (tradinglab.ml.train_model / build_pooled_dataset)
works with flat (n_samples, N_FEATURES) rows, it can't be reused as-is for
sequence input. This module is self-contained: its own LSTM model, its own
day-indexed sequence-window dataset builder, and its own tiny training loop.
If you'd rather have the LSTM class live in tradinglab/models.py next to MLP
for consistency, just move the class below — nothing here depends on where
it lives.

Same conventions as mlp_strategy.py / sma.py:
  - no-lookahead: sequence windows and labels are only ever built from days
    strictly before split_day for training; run_backtest is expected to be
    called with start=split_day so the strategy is only evaluated
    out-of-sample.
  - "don't force a bet": if no stock's predicted next-day return is
    positive, hold nothing (all-zero weights = cash).
"""
from __future__ import annotations
import numpy as np
import torch

from tradinglab.features import feature_columns, N_FEATURES

SPLIT_FRAC = 0.7    # same 70/30 convention as mlp_strategy.py / every notebook
SEQ_LEN = 20         # trailing window (in days) fed to the LSTM per prediction
TOP_N = 5            # how many stocks the universe strategy goes long on
EPOCHS = 60          # LSTMs are slower per-epoch than the MLP; kept low so dev restarts
                      # (uvicorn --reload trains this twice, once per universe) stay fast
LR = 0.01
HIDDEN = 32


# ------------------------------------------------------------------
# Model
# ------------------------------------------------------------------

class LSTM(torch.nn.Module):
    """Single-layer LSTM regressor. Input: (batch, seq_len, n_features).
    Output: (batch,) predicted next-day return, taken from the final
    layer's last hidden state — mirrors MLP's "one scalar prediction per
    row" interface, just with a sequence in instead of a flat vector."""

    def __init__(self, n_features: int, hidden: int = HIDDEN, num_layers: int = 1):
        super().__init__()
        self.lstm = torch.nn.LSTM(
            input_size=n_features, hidden_size=hidden,
            num_layers=num_layers, batch_first=True,
        )
        self.head = torch.nn.Linear(hidden, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        _, (h_n, _) = self.lstm(x)   # h_n: (num_layers, batch, hidden)
        return self.head(h_n[-1]).squeeze(-1)


# ------------------------------------------------------------------
# Sequence dataset builders (day-indexed, no-lookahead)
# ------------------------------------------------------------------

def _build_single_asset_sequences_by_day(feed, asset, split_day, seq_len=SEQ_LEN):
    """For one stock, slide a seq_len-day window across history. Each
    sample's label is the return the day AFTER the window ends. A window
    is kept only if every day in it (features + label) is valid — same
    NaN-masking spirit as mlp_strategy.py's _build_single_asset_by_day,
    just applied across a whole window instead of one day."""
    X_full = feature_columns(feed, asset)          # (n_days, N_FEATURES)
    y_full = np.full(feed.n_days, np.nan)
    y_full[:-1] = feed.returns[1:, asset]
    day_valid = ~np.isnan(X_full).any(axis=1) & ~np.isnan(y_full)

    X_seqs, y_seqs, end_days = [], [], []
    for end_day in range(seq_len - 1, feed.n_days):
        start_day = end_day - seq_len + 1
        if not day_valid[start_day:end_day + 1].all():
            continue
        X_seqs.append(X_full[start_day:end_day + 1])
        y_seqs.append(y_full[end_day])
        end_days.append(end_day)

    if not end_days:
        empty_X = np.empty((0, seq_len, N_FEATURES), dtype=np.float32)
        empty_y = np.empty((0,), dtype=np.float32)
        return empty_X, empty_y, empty_X, empty_y

    X_seqs = np.asarray(X_seqs, dtype=np.float32)
    y_seqs = np.asarray(y_seqs, dtype=np.float32)
    end_days = np.asarray(end_days)

    train_mask = end_days < split_day
    test_mask = end_days >= split_day
    return (X_seqs[train_mask], y_seqs[train_mask],
            X_seqs[test_mask], y_seqs[test_mask])


def _build_pooled_sequences_by_day(feed, split_day, seq_len=SEQ_LEN):
    """Same idea as build_pooled_dataset in tradinglab.features, but for
    sequence windows: build each stock's windows independently (so a
    window never crosses between two different stocks' histories), then
    concatenate across the universe."""
    Xtr_all, ytr_all, Xte_all, yte_all = [], [], [], []
    for asset in range(feed.n_assets):
        Xtr, ytr, Xte, yte = _build_single_asset_sequences_by_day(feed, asset, split_day, seq_len)
        Xtr_all.append(Xtr); ytr_all.append(ytr)
        Xte_all.append(Xte); yte_all.append(yte)

    Xtr = np.concatenate(Xtr_all, axis=0)
    ytr = np.concatenate(ytr_all, axis=0)
    Xte = np.concatenate(Xte_all, axis=0)
    yte = np.concatenate(yte_all, axis=0)
    return Xtr, ytr, Xte, yte


# ------------------------------------------------------------------
# Training / inference (self-contained -- shapes don't match tradinglab.ml's
# flat-row assumptions, so this doesn't reuse train_model / predict)
# ------------------------------------------------------------------

def _train_lstm(model, Xtr, ytr, Xte, yte, epochs=EPOCHS, lr=LR):
    print(f"[lstm] training on {len(Xtr)} sequences ({epochs} epochs)...")
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = torch.nn.MSELoss()

    Xtr_t = torch.from_numpy(Xtr)
    ytr_t = torch.from_numpy(ytr)

    model.train()
    for epoch in range(epochs):
        optimizer.zero_grad()
        loss = loss_fn(model(Xtr_t), ytr_t)
        loss.backward()
        optimizer.step()
        if (epoch + 1) % 10 == 0 or epoch == 0:
            print(f"[lstm]   epoch {epoch + 1}/{epochs}  train_loss={loss.item():.6f}")

    if len(Xte):
        model.eval()
        with torch.no_grad():
            test_loss = loss_fn(model(torch.from_numpy(Xte)), torch.from_numpy(yte)).item()
        print(f"[lstm] done. final train_loss={loss.item():.6f} test_loss={test_loss:.6f}")
    else:
        print(f"[lstm] done. final train_loss={loss.item():.6f} (no test sequences)")

    return model


def _predict_lstm(model, X_seq: np.ndarray) -> np.ndarray:
    model.eval()
    with torch.no_grad():
        preds = model(torch.from_numpy(X_seq.astype(np.float32)))
    return preds.numpy()


def train_pooled_lstm_model(feed, split_day, epochs=EPOCHS, lr=LR, hidden=HIDDEN, seq_len=SEQ_LEN):
    """Train one LSTM pooled across every stock's history, up to split_day."""
    Xtr, ytr, Xte, yte = _build_pooled_sequences_by_day(feed, split_day, seq_len)
    torch.manual_seed(0)
    model = LSTM(n_features=N_FEATURES, hidden=hidden)
    _train_lstm(model, Xtr, ytr, Xte, yte, epochs=epochs, lr=lr)
    return model


# ------------------------------------------------------------------
# Strategy (called once per backtest day by run_backtest)
# ------------------------------------------------------------------

class LSTMUniverseStrategy:
    """Score every stock daily with one pooled LSTM, using each stock's
    trailing seq_len-day window; go long the top_n with a positive
    predicted return, equal-weighted. Hold nothing if none qualify.
    Stateless -- one instance can be reused across backtests.

    Requires run_backtest to be called with lookback >= seq_len, since
    each prediction needs a full seq_len-day window, not just today."""

    def __init__(self, model, n_assets: int, seq_len: int = SEQ_LEN, top_n: int = TOP_N):
        self.model = model
        self.n_assets = n_assets
        self.seq_len = seq_len
        self.top_n = top_n

    def __call__(self, observation: np.ndarray) -> np.ndarray:
        feats = observation[:, -self.seq_len:, :].astype(np.float32)  # (n_assets, seq_len, N_FEATURES)
        preds = _predict_lstm(self.model, feats)                       # (n_assets,)
        weights = np.zeros(self.n_assets)
        ranked = np.argsort(preds)[::-1][:self.top_n]
        positive = ranked[preds[ranked] > 0]
        if len(positive) > 0:
            weights[positive] = 1.0 / len(positive)
        return weights   # all-zero (cash) if nothing qualifies