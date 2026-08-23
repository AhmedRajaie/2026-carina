# dashboard/ — your product, built a little each day

You don't build the dashboard in one go. It grows from **day 2**, one panel at a
time, using the task files in `tasks/`. Each task is a prompt you hand to GitHub
Copilot (Copilot Chat), then verify.

## How to use a task file
1. Open the task file for today (e.g. `tasks/TASK_02_price_chart.md`).
2. Read the **Goal** and **Context**.
3. Paste the **Prompt** into Copilot Chat, or work through the numbered steps.
4. Run the **Verify** step. If it works, commit. If not, iterate with Copilot.

## Order
- Day 2: `TASK_01_scaffold` then `TASK_02_price_chart`
- Day 3: `TASK_03_indicators`
- Day 4: `TASK_04_equity_curve`
- Day 5: `TASK_05_polish`
Later weeks add model diagnostics, agent allocations, and risk panels.

## Run it
```
uv run uvicorn dashboard.backend.main:app --reload --port 8000
```
Then open `dashboard/frontend/index.html` in your browser.
