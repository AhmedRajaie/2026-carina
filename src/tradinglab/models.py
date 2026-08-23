"""
models.py — WEEK 2. Minimal PyTorch models. You EXTEND these, you don't derive them.

These ship COMPLETE and working — the exercise is to modify them: add a layer,
change the width, add dropout, swap the loss, retrain, and see if the TEST error
improves. That's real ML engineering, no math required.
"""
from __future__ import annotations
import torch
import torch.nn as nn


class MLP(nn.Module):
    """Fully-connected return predictor.

    EXTEND ME: add another `nn.Linear(hidden, hidden)` + `nn.ReLU()` before the
    final layer, or try `nn.Dropout(0.2)`. Then retrain and compare test loss.
    """
    def __init__(self, n_features: int, hidden: int = 32):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(n_features, hidden),
            nn.ReLU(),
            # <-- add more layers here to extend the model
            nn.Linear(hidden, 1),
        )

    def forward(self, x):
        return self.net(x).squeeze(-1)


class LSTMRegressor(nn.Module):
    """Sequence return predictor. Input shape: (batch, seq_len, n_features).

    EXTEND ME: try `num_layers=2`, or a larger `hidden`, or add a dropout before
    the head.
    """
    def __init__(self, n_features: int, hidden: int = 32):
        super().__init__()
        self.lstm = nn.LSTM(n_features, hidden, batch_first=True)
        self.head = nn.Linear(hidden, 1)

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.head(out[:, -1, :]).squeeze(-1)


class DeepMLP(nn.Module):
    """Same idea as MLP, but with as many hidden layers as YOU choose to stack.

    EXERCISE: build the layer stack yourself. Given n_hidden_layers, alternate
    Linear -> ReLU that many times, then end with a single Linear(hidden, 1) to
    produce the prediction. Try 2, 4, 8 layers -- does test loss actually
    improve, or does it just overfit faster (watch the gap)?
    """
    def __init__(self, n_features: int, hidden: int = 32, n_hidden_layers: int = 2):
        super().__init__()
        # ---8<--- solution
        layers = [nn.Linear(n_features, hidden), nn.ReLU()]
        for _ in range(n_hidden_layers - 1):
            layers += [nn.Linear(hidden, hidden), nn.ReLU()]
        layers.append(nn.Linear(hidden, 1))
        self.net = nn.Sequential(*layers)
        # ---8<--- end

    def forward(self, x):
        return self.net(x).squeeze(-1)


class GRURegressor(nn.Module):
    """Same job as LSTMRegressor (sequence return predictor), different gating
    mechanism -- GRU has fewer parameters and no separate cell state. Same
    input/output shape: (batch, seq_len, n_features) -> one prediction per row.
    """
    def __init__(self, n_features: int, hidden: int = 32):
        super().__init__()
        self.gru = nn.GRU(n_features, hidden, batch_first=True)
        self.head = nn.Linear(hidden, 1)

    def forward(self, x):
        out, _ = self.gru(x)
        return self.head(out[:, -1, :]).squeeze(-1)
