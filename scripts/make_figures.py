"""Rebuild the figures used in report.md from the cached WRDS data (needs data/ filled by the notebook).

uv run python scripts/make_figures.py
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from alm import assets, data, liabilities, optimize, scenarios

OUT = Path(__file__).resolve().parents[1] / "figures"
OUT.mkdir(exist_ok=True)

# Colors: tab:blue for the main series, tab:orange for the comparison (curve, liabilities, deterministic LP).
MAIN, COMPARE = "tab:blue", "tab:orange"
SIZE = (7, 4)

# ---- same setup as notebooks/alm_real.ipynb
BONDRET_DATE, TSY_DATE = "2025-11-30", "2025-11-28"
corp_raw = data.cached(
    data.DATA_DIR / f"bondret_{BONDRET_DATE}.csv",
    lambda: data.pull_bondret(data.connect(), BONDRET_DATE),
)
tsy_raw = data.cached(
    data.DATA_DIR / f"treasuries_{TSY_DATE}.csv",
    lambda: data.pull_treasuries(data.connect(), TSY_DATE),
)
u = assets.build_universe(corp_raw, tsy_raw, asof=TSY_DATE)
y, k, curve = assets.net_yield(u), assets.capital_factor(u), assets.curve(u)
T = 40
qx = liabilities.gompertz_qx()
ages = np.random.default_rng(0).integers(65, 76, size=1000)
L = liabilities.annuity_cashflows(qx, ages, payment=0.01, horizon=T)
rate = 0.04
for _ in range(3):
    pv, D_L = liabilities.pv_duration(L, rate)
    rate = float(curve(D_L))
C = assets.cashflow_matrix(u, T)
A = 1.02 * pv
limits = dict(
    r=float(curve(1.0)),
    delta=0.5,
    max_weight=0.03,
    rating_caps={"BBB": 0.25},
    capital_cap=0.015 * A,
)
price, dur = u.price.to_numpy(), u.mod_dur.to_numpy()

res = optimize.solve_deterministic(
    y=y.to_numpy(),
    price=price,
    C=C,
    L=L,
    dur=dur,
    D_L=D_L,
    A=A,
    k=k.to_numpy(),
    rating=u.rating.to_numpy(),
    issuer=u.issuer.to_numpy(),
    **limits,
)

KAPPA, SIGMA, r0 = 0.03, 0.15, limits["r"]


def draw(n, seed):
    f = scenarios.longevity_scenarios(n, SIGMA, seed)
    return liabilities.scenario_cashflows(
        qx, ages, 0.01, T, f
    ), scenarios.rate_scenarios(r0, n, T, seed=seed + 1000)


L_fit, r_fit = draw(200, 1)
L_test, r_test = draw(1000, 2)


def peaks(x):
    return optimize.simulate(x, price, C, L_test, r_test, A, KAPPA).max(axis=1)


def solve_sto(iota):
    return optimize.solve_stochastic(
        y=y.to_numpy(),
        price=price,
        C=C,
        L_scen=L_fit,
        r_scen=r_fit,
        dur=dur,
        D_L=D_L,
        A=A,
        k=k.to_numpy(),
        kappa=KAPPA,
        iota=iota,
        delta=limits["delta"],
        max_weight=limits["max_weight"],
        rating=u.rating.to_numpy(),
        rating_caps=limits["rating_caps"],
        capital_cap=limits["capital_cap"],
        issuer=u.issuer.to_numpy(),
    )


IOTAS = [0.0, 0.02, 0.05, 0.1, 0.3, 1.0, 3.0]
sto = {i: solve_sto(i) for i in IOTAS}
income = y.to_numpy() * price


def save(fig, name):
    fig.tight_layout()
    fig.savefig(OUT / name, dpi=200)
    plt.close(fig)


# ---- 1. universe
fig, ax = plt.subplots(figsize=SIZE)
c = u[u.rating != "UST"]
ax.scatter(
    c.maturity,
    c.ytm * 100,
    s=3,
    alpha=0.25,
    color=MAIN,
    linewidths=0,
    label="IG corporates (6,984)",
)
m = np.linspace(1, 30, 120)
ax.plot(m, curve(m) * 100, color=COMPARE, label="Treasury curve")
ax.set(
    title="Bond universe, Nov 2025",
    xlabel="years to maturity",
    ylabel="yield to maturity (%)",
)
ax.legend(loc="upper left")
save(fig, "universe.png")

# ---- 2. weights: rating x modified duration
edges = [0, 2, 4, 6, 8, 10, 12, 14, 16, 30]
labels = [f"{a}-{b}" for a, b in zip(edges[:-1], edges[1:-1])] + [f"{edges[-2]}+"]
order = ["UST", "AAA", "AA", "A", "BBB"]
bucket = pd.cut(u.mod_dur, edges, labels=labels)
w = pd.Series(price * res.x / A * 100, index=u.index)
G = (
    w.groupby([u.rating, bucket], observed=False)
    .sum()
    .unstack()
    .reindex(order)[labels]
    .fillna(0)
)

fig, ax = plt.subplots(figsize=SIZE)
im = ax.imshow(G.values, cmap="Blues", aspect="auto")
ax.set_xticks(range(len(G.columns)), G.columns)
ax.set_yticks(range(len(G.index)), G.index)
for i in range(G.shape[0]):
    for j in range(G.shape[1]):
        v = G.values[i, j]
        if v >= 0.05:
            ax.text(
                j,
                i,
                f"{v:.1f}",
                ha="center",
                va="center",
                color="white" if v > 0.55 * G.values.max() else "black",
            )
fig.colorbar(im, ax=ax, label="share of assets (%)")
ax.set(
    title="Deterministic LP portfolio",
    xlabel="modified duration (years)",
    ylabel="credit rating",
)
save(fig, "weights_heatmap.png")

# ---- 3. cash flow vs liability by year
yrs = np.arange(1, T + 1)
bond_cf = C @ res.x
carried_in, s_prev = np.zeros(T), A - float(
    price @ res.x
)  # cash carried in from last year, with interest
for t in range(T):
    carried_in[t] = (1 + limits["r"]) * s_prev
    s_prev = max(bond_cf[t] + carried_in[t] - L[t], 0.0)

fig, ax = plt.subplots(figsize=SIZE)
ax.bar(yrs, bond_cf, color=MAIN, label="bond cash flow")
ax.plot(yrs, L, color=COMPARE, label="expected payout to annuitants")
ax.set(title="Bond cash flow vs liabilities", xlabel="year", ylabel="USD millions")
ax.legend(loc="upper right")
save(fig, "cashflow.png")

# ---- 4. yield vs safety, by iota
rows = []
for name, x in [("deterministic", res.x)] + [(f"{i:g}", sto[i].x) for i in IOTAS]:
    pk = peaks(x)
    rows.append(
        dict(
            name=name,
            income=income @ x / A * 100,
            p=(pk > 1e-6).mean() * 100,
            cvar=np.sort(pk)[::-1][: int(0.05 * len(pk))].mean(),
        )
    )
F = pd.DataFrame(rows)
S_, d = F[F.name != "deterministic"], F[F.name == "deterministic"].iloc[0]

fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
for ax, col, xlabel, title in [
    (
        axes[0],
        "cvar",
        "95% CVaR of peak shortfall (USD millions)",
        "Net yield vs tail shortfall",
    ),
    (
        axes[1],
        "p",
        "scenarios with any shortfall (%)",
        "Net yield vs share of scenarios with shortfall",
    ),
]:
    ax.plot(
        S_[col], S_.income, "-o", color=MAIN, label="stochastic LP (labelled by iota)"
    )
    for _, r_ in S_.iterrows():
        ax.annotate(
            r_["name"], (r_[col], r_.income), textcoords="offset points", xytext=(4, 5)
        )
    ax.plot(d[col], d.income, "o", color=COMPARE, label="deterministic LP")
    ax.set(title=title, xlabel=xlabel)
axes[0].set_ylabel("net yield (%)")
axes[0].legend(loc="lower right")
save(fig, "frontier.png")

# ---- 5. share of scenarios at or below a given peak shortfall, all iotas
fig, ax = plt.subplots(figsize=SIZE)
shades = plt.cm.Blues(np.linspace(0.3, 1.0, len(IOTAS)))
for i, shade in zip(IOTAS, shades):
    pk = np.sort(peaks(sto[i].x))
    ax.step(
        pk,
        np.arange(1, len(pk) + 1) / len(pk),
        where="post",
        color=shade,
        label=f"iota = {i:g}",
    )
pk = np.sort(peaks(res.x))
ax.step(
    pk,
    np.arange(1, len(pk) + 1) / len(pk),
    where="post",
    color=COMPARE,
    linestyle="--",
    label="deterministic",
)
ax.set_xlim(0, 30)
ax.set(
    title="Peak shortfall across 1,000 fresh scenarios",
    xlabel="peak shortfall (USD millions)",
    ylabel="share of scenarios at or below",
)
ax.legend(loc="lower right")
save(fig, "shortfall_ecdf.png")

print(
    f"cash left after year {T}: {s_prev:.1f}m; bond cash flow {bond_cf.sum():.1f}m vs owed {L.sum():.1f}m"
)
print(F.round(3).to_string(index=False))
