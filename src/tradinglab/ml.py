"""
ml.py — WEEK 2. The training loop, given. Same every time you fit a model.

The point of this file is the HABIT baked into it: we track TRAIN and TEST loss
every epoch. If train loss falls while test loss rises, that's OVERFITTING —
memorizing the past instead of learning a pattern that generalizes. You watch
for that on every model, every day.
"""
from __future__ import annotations
import numpy as np
import torch


def train_model(model, X_train, y_train, X_test, y_test, epochs=200, lr=1e-3):
    """Train, returning per-epoch train/test loss so you can SEE overfitting."""
    Xtr = torch.as_tensor(X_train); ytr = torch.as_tensor(y_train)
    Xte = torch.as_tensor(X_test);  yte = torch.as_tensor(y_test)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = torch.nn.MSELoss()

    history = {"train": [], "test": []}
    for _ in range(epochs):
        model.train()
        opt.zero_grad()
        loss = loss_fn(model(Xtr), ytr)
        loss.backward(); opt.step()

        model.eval()
        with torch.no_grad():
            te = loss_fn(model(Xte), yte).item()
        history["train"].append(loss.item())
        history["test"].append(te)
    return history


def predict(model, X):
    model.eval()
    with torch.no_grad():
        return model(torch.as_tensor(X)).numpy()
