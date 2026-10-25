"""Deterministic LP and two-stage stochastic LP (cvxpy)."""

from dataclasses import dataclass

import cvxpy as cp
import numpy as np
import pandas as pd
import scipy.sparse as sp


@dataclass
class Result:
    x: np.ndarray            # par held per bond
    net_yield: float         # annual income / A
    duals: dict[str, float]  # income gained per unit the constraint is relaxed
    status: str


def _portfolio_limits(x, price, dur, D_L, A, k, delta, max_weight, rating, rating_caps, capital_cap, issuer):
    """Constraints on the first-stage portfolio, shared by both LPs."""
    n = len(price)
    mv = cp.multiply(price, x)
    cons = {
        "duration_hi": (dur - D_L) @ mv <= delta * A,
        "duration_lo": (dur - D_L) @ mv >= -delta * A,
    }
    if issuer is None:
        cons["issuer"] = mv <= max_weight * A
    else:
        names = np.asarray(issuer)
        capped = np.flatnonzero(names != "UST")
        codes, _ = pd.factorize(names[capped])
        G = sp.csr_matrix((np.ones(len(capped)), (codes, capped)), shape=(codes.max() + 1, n))
        cons["issuer"] = G @ mv <= max_weight * A
    if capital_cap is not None:
        cons["capital"] = (k * price) @ x <= capital_cap
    for g, cap in (rating_caps or {}).items():
        cons[f"rating_{g}"] = cp.sum(mv[np.asarray(rating) == g]) <= cap * A
    return mv, cons


def solve_deterministic(
    y, price, C, L, dur, D_L, A, k, r,
    delta=0.5, max_weight=0.10, rating=None, rating_caps=None, capital_cap=None, issuer=None,
) -> Result:
    """Max net income s.t. cash matching, duration gap, capital, issuer and rating limits.

    s[t] is cash carried from year t to t+1 at rate r. Duration is linearized as
    sum (d_i - D_L) * MV_i within +-delta * A. With `issuer`, the cap applies per issuer
    (Treasuries uncapped), otherwise per bond.
    """
    T, n = C.shape
    x = cp.Variable(n, nonneg=True)
    s = cp.Variable(T + 1, nonneg=True)
    mv, limits = _portfolio_limits(x, price, dur, D_L, A, k, delta, max_weight, rating, rating_caps, capital_cap, issuer)

    cons = {
        "budget": mv.sum() + s[0] == A,
        "cash_matching": C @ x + (1 + r) * s[:-1] - s[1:] == L,
        **limits,
    }
    prob = cp.Problem(cp.Maximize((y * price) @ x), list(cons.values()))
    prob.solve()
    if prob.status != "optimal":
        return Result(np.full(n, np.nan), np.nan, {}, prob.status)
    duals = {name: float(np.sum(c.dual_value)) for name, c in cons.items()}
    return Result(x.value, prob.value / A, duals, prob.status)


def solve_stochastic(
    y, price, C, L_scen, r_scen, dur, D_L, A, k, kappa, iota,
    delta=0.5, max_weight=0.10, rating=None, rating_caps=None, capital_cap=None, issuer=None,
) -> Result:
    """Two-stage LP. First stage: the portfolio (same limits as the deterministic LP).

    Second stage, per scenario w: cash s[w, t] is carried at r_scen[w, t-1]. A shortfall b[w, t] is borrowed
    and accrues at r_scen[w, t-1] + kappa. Objective: net income minus iota times the average borrowed
    balance over scenarios and years, so iota is the price of a shortfall.

    L_scen and r_scen have shape (S, T).
    """
    S, T = L_scen.shape
    n = len(price)
    x = cp.Variable(n, nonneg=True)
    s = cp.Variable((S, T + 1), nonneg=True)
    b = cp.Variable((S, T + 1), nonneg=True)
    mv, limits = _portfolio_limits(x, price, dur, D_L, A, k, delta, max_weight, rating, rating_caps, capital_cap, issuer)

    # one variable for the bond cash flow in each year keeps the per-scenario constraints sparse
    cf = cp.Variable(T)
    inflow = np.ones((S, 1)) @ cp.reshape(cf, (1, T), order="C")
    cons = {
        "bond_cashflow": cf == C @ x,
        "budget": mv.sum() + s[0, 0] == A,
        "no_initial_debt": b[:, 0] == 0,
        "same_initial_cash": s[:, 0] == s[0, 0],
        "cash_matching": s[:, 1:] - b[:, 1:]
        == inflow + cp.multiply(1 + r_scen, s[:, :-1]) - cp.multiply(1 + r_scen + kappa, b[:, :-1]) - L_scen,
        **limits,
    }
    income = (y * price) @ x
    prob = cp.Problem(cp.Maximize(income - iota * cp.sum(b[:, 1:]) / (S * T)), list(cons.values()))
    prob.solve()
    if prob.status != "optimal":
        return Result(np.full(n, np.nan), np.nan, {}, prob.status)
    duals = {name: float(np.sum(c.dual_value)) for name, c in limits.items()}
    return Result(x.value, income.value / A, duals, prob.status)


def simulate(x, price, C, L_scen, r_scen, A, kappa):
    """Run a fixed portfolio through scenarios. Returns debt balances b[w, t] (shape (S, T)).

    Cash earns r_scen, debt costs r_scen + kappa, and a surplus is never held while in debt.
    """
    S, T = L_scen.shape
    inflow = C @ x
    cash = A - float(price @ x)
    s = np.full(S, cash)
    d = np.zeros(S)
    out = np.zeros((S, T))
    for t in range(T):
        z = inflow[t] + (1 + r_scen[:, t]) * s - (1 + r_scen[:, t] + kappa) * d - L_scen[:, t]
        s, d = np.maximum(z, 0), np.maximum(-z, 0)
        out[:, t] = d
    return out
