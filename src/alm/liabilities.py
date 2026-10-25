"""Annuity block: expected payment stream L_t from a mortality table."""

import numpy as np


def gompertz_qx(a: float = 3.46e-5, b: float = 0.09, max_age: int = 120) -> np.ndarray:
    """Synthetic one-year death probabilities by age. Roughly 1.2% at 65 and 7% at 85."""
    ages = np.arange(max_age + 1)
    qx = 1 - np.exp(-a * np.exp(b * ages) * (np.exp(b) - 1) / b)
    qx[-1] = 1.0
    return qx


def survival_curve(qx: np.ndarray, age: int, horizon: int) -> np.ndarray:
    """P(alive at t | alive at `age`) for t = 1..horizon, from one-year death probabilities qx."""
    q = np.append(qx, np.ones(horizon))[age : age + horizon]
    return np.cumprod(1 - q)


def annuity_cashflows(qx: np.ndarray, ages: np.ndarray, payment: float, horizon: int) -> np.ndarray:
    """Expected annual payout L_t (paid at the end of year t) summed over the block."""
    vals, counts = np.unique(ages, return_counts=True)
    return payment * sum(n * survival_curve(qx, int(a), horizon) for a, n in zip(vals, counts))


def scenario_cashflows(qx: np.ndarray, ages: np.ndarray, payment: float, horizon: int, shocks: np.ndarray) -> np.ndarray:
    """(len(shocks), horizon) payouts when mortality is scaled by each shock."""
    scaled = lambda f: np.append(np.minimum(qx[:-1] * f, 1.0), 1.0)
    return np.array([annuity_cashflows(scaled(f), ages, payment, horizon) for f in shocks])


def pv_duration(L: np.ndarray, rate: float) -> tuple[float, float]:
    """Present value and modified duration of the payment stream at a flat annual rate."""
    t = np.arange(1, len(L) + 1)
    pv_t = L / (1 + rate) ** t
    pv = pv_t.sum()
    return pv, (t * pv_t).sum() / pv / (1 + rate)
