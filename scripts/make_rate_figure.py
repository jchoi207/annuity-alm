"""Sample rate paths from the scenario generator, for the report."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from alm.scenarios import rate_scenarios

R0, T = 0.0359, 40
paths = rate_scenarios(R0, 30, T, seed=0) * 100
yrs = np.arange(1, T + 1)

fig, ax = plt.subplots(figsize=(7, 3.2))
ax.plot(yrs, paths.T, color="C0", alpha=0.35, lw=1)
ax.axhline(R0 * 100, color="C1", ls="--", lw=1.5, label="r = 3.59%")
ax.set(title="Sample cash-rate paths (30 of 200)", xlabel="year", ylabel="cash rate (%)")
ax.legend(loc="upper left")
fig.tight_layout()
out = Path(__file__).resolve().parents[1] / "report" / "rate_paths.png"
fig.savefig(out, dpi=200)
