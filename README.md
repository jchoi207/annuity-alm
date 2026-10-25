# alm

Asset-liability matching for an annuity block. A formulation exercise, not a model of any real insurer. Results and assumptions are in [report.md](report.md).

An insurer owes 1,000 annuitants 10k a year while alive. We pick a bond portfolio (Treasuries and investment-grade corporates) that covers the payments and maximizes net yield, subject to cash matching, duration, capital, rating and issuer limits.

1. Deterministic LP on expected payouts.
2. Two-stage stochastic LP over longevity and rate scenarios.
3. Compare both on fresh scenarios: net yield against shortfall.

## Setup

```
uv sync
cp .env.example .env    # add WRDS_USERNAME and WRDS_PASSWORD
uv run python scripts/make_figures.py
```

`notebooks/alm.ipynb` uses synthetic bonds. `notebooks/alm_real.ipynb` uses CRSP Treasuries and WRDS bondret (Nov 2025 snapshot). WRDS data is not redistributable, so it is pulled into `data/` (gitignored) on first run.
