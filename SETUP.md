# Setup — do this BEFORE day 1

You need four things: **VS Code**, **Git**, **uv**, and a **GitHub account**.

Important: **you do NOT need to install Python yourself.** uv downloads the
correct Python for you. Install uv, and it handles the rest.

Node.js is optional (dashboard, week 1). PostgreSQL is optional (only if a later
exercise needs it — we'll tell you).

---

## Windows — from zero

1. **VS Code** — https://code.visualstudio.com → Download for Windows → install.
2. **Git** — https://git-scm.com/download/win → install (accept all defaults).
3. **uv** — open **PowerShell** and paste:
   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```
   Close PowerShell, reopen it, then verify:
   ```powershell
   uv --version
   ```
4. **GitHub** — sign up at https://github.com/signup, then apply for the free
   **Student Developer Pack** (includes Copilot): https://education.github.com/pack
   Do this early — approval can take a few days.

## macOS — from zero

1. **VS Code** — https://code.visualstudio.com → Download for macOS → drag to Applications.
2. **Git** — open **Terminal**, run `git --version`; if prompted, click Install.
3. **uv** — in Terminal, paste:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
   Close Terminal, reopen it, then verify:
   ```bash
   uv --version
   ```
4. **GitHub + Student Pack** — same links as above. Apply early.

---

## First run (both systems)

From a terminal (PowerShell on Windows, Terminal on macOS):

```bash
git clone <REPO_URL>
cd efg-algo-internship
uv sync
```

`uv sync` will:
- download the correct Python (you didn't need to install it),
- create an isolated environment in `.venv/`,
- install every dependency, pinned to the same versions for everyone.

That `.venv/` folder **is** your virtual environment. You never install packages
globally. Prefix commands with `uv run` and they use it automatically.

## Verify everything works

Run these two commands from the terminal, in the project root, to confirm
your environment is set up correctly:

```bash
uv run python -c "from tradinglab.data_feed import DataFeed; print('tradinglab imports correctly')"
uv run python -c "import sys; print(sys.executable)"
```

The first line should print `tradinglab imports correctly` — confirming the
package is installed and working. The second line prints the exact Python
being used — it should end in `.venv\Scripts\python.exe` (Windows) or
`.venv/bin/python` (Mac/Linux), inside **this** project folder. If it points
anywhere else, your kernel or terminal isn't using this project's own
environment — re-run `uv sync` and try again.
## Open in VS Code
```bash
code .
```
When VS Code asks for a Python interpreter, pick the one inside `.venv`.

---

## Recommended — keep your notebook commits clean

Running notebooks fills them with outputs (plots, printed numbers) that git sees
as noise on every commit. `nbstripout` strips outputs automatically before each
commit, so your notebook still shows outputs when you open it, but git history
stays clean. It's already installed as part of `uv sync` — you just need to
register it once per machine:

```bash
uv run nbstripout --install
```

Then create `.gitattributes` at the repo root so git knows to apply it to every
notebook:

**macOS / Linux:**
```bash
echo "*.ipynb filter=nbstripout" > .gitattributes
```

**Windows (PowerShell):**
```powershell
"*.ipynb filter=nbstripout" | Out-File -Encoding utf8 .gitattributes
```

Verify it's active:
```bash
git check-attr filter -- week1/01-setup-and-data/notebook.ipynb
```
Should print `filter: nbstripout`.

## Register the Jupyter kernel (so you don't set it manually every notebook)

Without this, VS Code / Jupyter may not reliably auto-detect the repo's `.venv`,
so you'd pick the interpreter by hand for every new notebook. Registering it once
makes it a named option everywhere:

```bash
uv run python -m ipykernel install --user --name efg-internship --display-name "Python (efg-internship)"
```

After this, "Python (efg-internship)" appears in the kernel picker for any
notebook in this repo — pick it once and VS Code remembers your choice per file.


## Daily git rhythm

**Push your own work first, every time — before you merge anything in.**
`git merge` needs a clean working directory. If you have uncommitted changes
when you try to merge, git will refuse (or worse, tangle your unsaved work
into the merge). Always commit and push what you have *before* pulling in
new material — even if it's not finished. A messy, working commit beats a
blocked merge.

**1. Commit and push your own progress (do this often, independent of
anything I push):**

```bash
git add -A
git commit -m "day 2: implemented sma_crossover_weights"
git push origin group-01
```

This is the habit-building part. Commit and push often — don't wait for a
"finished" moment, and don't wait for us to push anything first.

**2. When new material lands on `main`, bring it into your branch:**

```bash
git checkout group-01
git fetch origin
git merge origin/main
```

If this fails or complains about your working directory, go back to step 1
first — commit your current work, then retry the merge.

**If merging causes a conflict in a `.ipynb` file**, don't try to hand-edit
the JSON. Pick a whole side instead:

```bash
git checkout --theirs path/to/notebook.ipynb   # keep YOUR version (yes, --theirs)
git add path/to/notebook.ipynb
git commit
```

Git's `--ours`/`--theirs` naming is reversed from what you'd expect during a
merge — during a merge, `--theirs` means "the branch I'm merging in," which,
confusingly, is what to use to *keep your own* uncommitted work in most of
our cases. If in doubt, ask, and default to keeping your own version — new
material almost always adds new files rather than editing ones you're
actively working in.

## Common issues
- **`uv: command not found`** — close and reopen the terminal after installing uv.
- **`ModuleNotFoundError: tradinglab`** — run from the repo root, and make sure
  `uv sync` finished without errors.
- **`No such file or directory: data/egx`** — run commands from the repo root,
  not from inside a subfolder.

## Optional — Kaggle (alternative to Colab for RL)
`notebooks/colab_train.ipynb` also runs on Kaggle Notebooks, which give ~30 free
GPU hours/week. Upload the notebook, add the repo as a dataset or clone it in the
first cell, and run. The training code is identical to Colab.
