"""Train MLP and LSTM models for the dashboard.

Run once to generate saved models:
    python dashboard/backend/train_models.py

Saves:
    dashboard/backend/mlp_model.pt
    dashboard/backend/lstm_model.pt
"""
import sys
import os
from pathlib import Path

# Add src to path
repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo_root / "src"))

import numpy as np
import torch
import torch.nn as nn

from tradinglab.data_feed import DataFeed
from tradinglab.features import build_pooled_dataset, build_pooled_sequences
from tradinglab.models import MLP, LSTMRegressor


def train_mlp(feed, split_day):
    """Train MLP on pooled dataset."""
    print("\n" + "="*60)
    print("TRAINING MLP")
    print("="*60)
    
    X_train, y_train, X_test, y_test = build_pooled_dataset(feed, split_day)
    print(f"Train samples: {X_train.shape[0]}")
    print(f"Test samples:  {X_test.shape[0]}")
    
    n_features = X_train.shape[1]
    model = MLP(n_features, hidden=32)
    
    X_tr = torch.tensor(X_train, dtype=torch.float32)
    y_tr = torch.tensor(y_train, dtype=torch.float32)
    X_te = torch.tensor(X_test, dtype=torch.float32)
    y_te = torch.tensor(y_test, dtype=torch.float32)
    
    opt = torch.optim.Adam(model.parameters(), lr=0.001)
    loss_fn = nn.MSELoss()
    
    epochs = 800
    for epoch in range(epochs):
        opt.zero_grad()
        pred = model(X_tr)
        loss = loss_fn(pred, y_tr)
        loss.backward()
        opt.step()
        
        if (epoch + 1) % 200 == 0:
            with torch.no_grad():
                test_loss = loss_fn(model(X_te), y_te).item()
            print(f"Epoch {epoch+1}/{epochs}  train={loss.item():.6f}  test={test_loss:.6f}")
    
    print(f"\nFinal train loss: {loss.item():.6f}")
    print(f"Final test loss:  {test_loss:.6f}")
    
    return model


def train_lstm(feed, split_day, seq_len=30):
    """Train LSTM on pooled sequences."""
    print("\n" + "="*60)
    print(f"TRAINING LSTM (seq_len={seq_len})")
    print("="*60)
    
    X_train, y_train, X_test, y_test = build_pooled_sequences(feed, split_day, seq_len)
    print(f"Train sequences: {X_train.shape}")
    print(f"Test sequences:  {X_test.shape}")
    
    n_features = X_train.shape[2]
    model = LSTMRegressor(n_features, hidden=32)
    
    X_tr = torch.tensor(X_train, dtype=torch.float32)
    y_tr = torch.tensor(y_train, dtype=torch.float32)
    X_te = torch.tensor(X_test, dtype=torch.float32)
    y_te = torch.tensor(y_test, dtype=torch.float32)
    
    opt = torch.optim.Adam(model.parameters(), lr=0.001)
    loss_fn = nn.MSELoss()
    
    epochs = 600  # Reduced for seq_len=30 (slower)
    for epoch in range(epochs):
        opt.zero_grad()
        pred = model(X_tr)
        loss = loss_fn(pred, y_tr)
        loss.backward()
        opt.step()
        
        if (epoch + 1) % 150 == 0:
            with torch.no_grad():
                test_loss = loss_fn(model(X_te), y_te).item()
            print(f"Epoch {epoch+1}/{epochs}  train={loss.item():.6f}  test={test_loss:.6f}")
    
    print(f"\nFinal train loss: {loss.item():.6f}")
    print(f"Final test loss:  {test_loss:.6f}")
    
    return model


def main():
    print("Loading data...")
    feed = DataFeed.from_dir("data/egx")
    print(f"Universe: {feed.n_assets} assets")
    print(f"Period: {feed.dates[0].date()} → {feed.dates[-1].date()}")
    print(f"Days: {feed.n_days}")
    
    split_day = int(feed.n_days * 0.7)
    print(f"Split day: {split_day} (70% of {feed.n_days})")
    
    # Train MLP
    mlp = train_mlp(feed, split_day)
    
    # Train LSTM with seq_len=30
    lstm = train_lstm(feed, split_day, seq_len=30)
    
    # Save models
    output_dir = Path(__file__).parent
    mlp_path = output_dir / "mlp_model.pt"
    lstm_path = output_dir / "lstm_model.pt"
    
    torch.save(mlp.state_dict(), mlp_path)
    torch.save(lstm.state_dict(), lstm_path)
    
    print("\n" + "="*60)
    print("SAVED MODELS")
    print("="*60)
    print(f"MLP:  {mlp_path}")
    print(f"LSTM: {lstm_path} (seq_len=30)")
    print("\nModels ready for dashboard!")


if __name__ == "__main__":
    main()
