# Task 07 — Train/test loss panel (Week 2, Day 2)

**Goal:** show overfitting as a picture — train vs test loss over epochs.

**Context:** the day-2 notebook saved `dashboard/data/mlp_loss.json` with `train`
and `test` arrays.

**Prompt (backend):**
> Add `/loss` that returns the contents of `dashboard/data/mlp_loss.json`.

**Prompt (frontend):**
> Add a Chart.js line panel plotting train loss and test loss vs epoch. Title it
> "Training vs Test loss (mind the gap)".

**Verify:** two curves. When they diverge, that gap is overfitting — on your own
dashboard.
