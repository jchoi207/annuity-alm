"""Scenarios: reinvestment rates (level, slope) and longevity shocks. Synthetic, not fitted to history."""

import numpy as np


def rate_scenarios(r0: float, n: int, horizon: int, level_sd=0.01, slope_sd=0.01, seed: int = 0) -> np.ndarray:
    """(n, horizon) reinvestment rates: r0 plus a parallel shift plus a tilt that builds over the horizon, floored at 0."""
    rng = np.random.default_rng(seed)
    level = rng.normal(0, level_sd, (n, 1))
    slope = rng.normal(0, slope_sd, (n, 1))
    return np.maximum(r0 + level + slope * np.linspace(0, 1, horizon), 0)


def longevity_scenarios(n: int, sigma: float, seed: int = 0) -> np.ndarray:
    """(n,) multiplicative shocks to mortality, lognormal with median 1 (below 1 means people live longer)."""
    return np.exp(np.random.default_rng(seed).normal(0, sigma, n))
