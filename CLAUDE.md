# annuity-alm

Asset-liability matching for an annuity block: a deterministic LP and a two-stage stochastic LP on synthetic liabilities and real WRDS bond data. A formulation exercise, not a model of any real insurer. `report.md` is the write-up.

## Layout

- `src/alm/`: `liabilities.py` (Gompertz mortality, payouts), `assets.py` (universe, net yield, cash flow matrix, made-up risk table), `optimize.py` (both LPs, `simulate`), `scenarios.py`, `data.py` (WRDS pulls, cached to `data/`).
- `notebooks/alm.ipynb` (synthetic bonds), `notebooks/alm_real.ipynb` (WRDS data).
- `scripts/make_figures.py` rebuilds `figures/` for the report. `scripts/probe_wrds.py` is a read-only schema and coverage probe.
- `report/` is a personal write-up, gitignored.

## Run

```
uv sync
uv run python scripts/make_figures.py
```

## Rules

- Never print, log or commit the WRDS login. It lives in `.env` (gitignored). Do not use `~/.pgpass` unless Jonathan says so.
- WRDS data is not redistributable. Nothing from `data/`, and no WRDS usernames, goes in the repo.
- Pin `wrds==3.5.0`. Older versions fail with `'Connection' object has no attribute 'cursor'`.
- Capstone (mie479) is team and sponsor code. Reuse ideas only, never code.
- Capital factors, default probabilities and the 1.5% cap are made up. Say so wherever they appear.
- Do not enlarge the scope. The aim is to interpret results and poke holes, not add features.
- In `report.md`, amounts are "USD millions" or "10k", with no currency `$` (it clashes with math delimiters). Math uses `$ $` and `$$ $$`.
- Stochastic LP: solve with `cf == C @ x` so per-scenario constraints stay sparse. Putting `C @ x` in every scenario constraint is far too slow.

## Style

- Conciseness first. No em dashes, no emoji, sentence case headers.
- Banned words: delve, leverage, robust, seamless, tapestry, landscape, realm, unlock, elevate, navigate (as metaphor), testament to, boasts, underscore.
- Comments say why, not what. Docstrings are one or two lines.
- Figures: plain matplotlib, tab:blue for the main series, tab:orange for the comparison, same size and title placement.
- No invented numbers. Quote results from a run.

## Commits

`type: summary`, lowercase, short, imperative, no period. No `Co-Authored-By` or other Claude attribution.
