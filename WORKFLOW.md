# How we work — git, branches, and groups

This program is run like a small engineering team. The habits here matter as much
as the code. Read this once; it takes ten minutes and saves you all week.

## Groups and roles
You work in groups. Rotate these roles **daily** so everyone does each job:
- **Driver** — types, shares screen.
- **Reviewer** — reads every line before it's committed, asks "why".
- **Data** — checks inputs/outputs are sane (shapes, NaNs, ranges).
- **Presenter** — explains the day's result at the close, and demos on Fridays.

## The daily git rhythm
Your instructor owns `main` and pushes each day's material there. Each group works
on its own branch: `group-01`, `group-02`, and so on.

Every morning:
```bash
git checkout group-XX          # your group's branch
git pull origin main           # get today's material
git merge main                 # bring it into your branch (resolve conflicts together)
```

While you work:
```bash
git add -p                     # stage in small, reviewed chunks
git commit -m "day 3: implement portfolio_return, tests green"
git push origin group-XX       # push often — end of every block, not just end of day
```

End of day, open a **Pull Request** from `group-XX` into a `showcase` branch (which
never merges — it's just where the instructor reviews everyone's diffs in one place).

## Commit like a professional
- Small commits with clear messages. "fix" tells no one anything; "day 4: add
  Sharpe + max_drawdown, tests pass" tells the whole story.
- Never commit broken code to a shared branch. Run the day's tests first:
  `uv run pytest weekN/dayX/tests/`
- Never commit secrets (API keys). They go in environment variables, not files.

## The graduation loop (how code becomes "yours")
1. Build a function in the day's notebook.
2. A quick check passes → move it into `src/tradinglab/...`.
3. Run the formal test: `uv run pytest weekN/dayX/tests/`.
4. Commit and push. Now the whole system runs on your code.

## Vibe-coding the dashboard
The dashboard grows via `dashboard/tasks/TASK_*.md`. Each is a prompt for GitHub
Copilot. Read the task, paste the prompt, run the verify step, commit. The skill
you're practicing is **writing a clear spec** — the code is the easy part.

## Copilot (free for students)
Apply for the GitHub Student Developer Pack early (approval takes days):
https://education.github.com/pack — it includes Copilot at no cost.
