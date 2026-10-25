"""Bond universe: net yield and cash-flow matrix."""

import numpy as np
import pandas as pd

# Toy assumptions, not LICAT/RBC. Annual default probability and capital factor by rating bucket.
DEFAULT_PROB = {"UST": 0.0, "AAA": 0.0001, "AA": 0.0003, "A": 0.0008, "BBB": 0.002}
CAPITAL_FACTOR = {"UST": 0.0, "AAA": 0.005, "AA": 0.01, "A": 0.02, "BBB": 0.04}
LGD = 0.40

SPREAD = {"AAA": 0.004, "AA": 0.006, "A": 0.009, "BBB": 0.015}


def synthetic_universe(
    treasury_maturities=range(1, 31), corp_maturities=(2, 3, 5, 7, 10, 15, 20, 30)
) -> pd.DataFrame:
    """Par bonds with annual coupons off a made-up upward-sloping curve. For testing the formulation."""
    rows = [(f"UST{m}", "UST", m, 0.0) for m in treasury_maturities]
    rows += [(f"{r}{m}", r, m, s) for r, s in SPREAD.items() for m in corp_maturities]
    df = pd.DataFrame(rows, columns=["name", "rating", "maturity", "spread"])
    df["ytm"] = 0.035 + 0.0015 * np.sqrt(df.maturity) * 3 + df.spread
    df["coupon"] = df.ytm
    df["price"] = 1.0
    df["mod_dur"] = (1 - (1 + df.ytm) ** -df.maturity.astype(float)) / df.ytm
    return df.drop(columns="spread")


def build_universe(
    bondret: pd.DataFrame, treasuries: pd.DataFrame, asof: str
) -> pd.DataFrame:
    """Treasuries plus IG corporates in the same columns as synthetic_universe, plus issuer.

    Prices are dirty (clean plus accrued) per unit of par. Duration is treated as Macaulay and converted to modified.
    """
    corp = pd.DataFrame(
        {
            "name": bondret.cusip,
            "issuer": bondret.issuer.fillna(bondret.cusip.str[:6]),
            "rating": pd.cut(
                bondret.rating_num, [0, 1, 4, 7, 10], labels=["AAA", "AA", "A", "BBB"]
            ).astype(str),
            "maturity": bondret.maturity,
            "coupon": bondret.coupon / 100,
            "price": (bondret.price_eom + bondret.coupacc.fillna(0)) / 100,
            "ytm": bondret.ytm,
            "mod_dur": bondret.duration / (1 + bondret.ytm / 2),
        }
    )
    years = (pd.to_datetime(treasuries.maturity) - pd.Timestamp(asof)).dt.days / 365.25
    tsy = pd.DataFrame(
        {
            "name": treasuries.cusip,
            "issuer": "UST",
            "rating": "UST",
            "maturity": years,
            "coupon": treasuries.coupon / 100,
            "price": (treasuries.price + treasuries.accrued.fillna(0)) / 100,
            "ytm": treasuries.ytm,
            "mod_dur": treasuries.duration / (1 + treasuries.ytm / 2),
        }
    )[years.between(1, 30)]
    return pd.concat([tsy, corp], ignore_index=True)


def curve(universe: pd.DataFrame):
    """Treasury yield at a given maturity (linear interpolation across the Treasury issues)."""
    t = universe[universe.rating == "UST"].sort_values("maturity")
    return lambda m: np.interp(m, t.maturity, t.ytm)


def default_loss(universe: pd.DataFrame) -> pd.Series:
    return universe.rating.map(DEFAULT_PROB) * LGD


def capital_factor(universe: pd.DataFrame) -> pd.Series:
    return universe.rating.map(CAPITAL_FACTOR)


def net_yield(universe: pd.DataFrame) -> pd.Series:
    """ytm - expected default loss. Capital is limited by a cap in the LP, not charged for here."""
    return universe.ytm - default_loss(universe)


def cashflow_matrix(universe: pd.DataFrame, horizon: int) -> np.ndarray:
    """C[t-1, i] = coupon plus principal of bond i in year t, per unit of par. Maturities rounded to whole years."""
    mat = universe.maturity.round().astype(int).to_numpy()
    cpn = universe.coupon.to_numpy()
    t = np.arange(1, horizon + 1)[:, None]
    return np.where(t <= mat, cpn, 0.0) + (t == mat)
