"""Read-only probe of the WRDS tables we plan to use. Prints schemas, latest dates, coverage and null rates.

uv run python scripts/probe_wrds.py
"""

import pandas as pd

from alm import data

db = data.connect()


def section(title):
    print(f"\n=== {title} ===")


def probe(title, fn):
    section(title)
    try:
        fn()
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")


def schema(library, table):
    print(
        db.describe_table(library=library, table=table)[["name", "type"]].to_string(
            index=False
        )
    )


def latest(library, table, col):
    print(
        db.raw_sql(
            f"select min({col}) as first, max({col}) as last, count(*) as n from {library}.{table}"
        ).to_string(index=False)
    )


# 1. schemas and date ranges
for lib, tab, col in [
    ("wrdsapps_bondret", "bondret", "date"),
    ("crsp", "tfz_dly", "caldt"),
    ("crsp", "tfz_iss", "tmatdt"),
    ("contrib_bond_dickerson", "dickerson_bonds_daily", "trd_exctn_dt"),
]:
    probe(f"{lib}.{tab} schema", lambda lib=lib, tab=tab: schema(lib, tab))
    probe(
        f"{lib}.{tab} range of {col}",
        lambda lib=lib, tab=tab, col=col: latest(lib, tab, col),
    )


# 2. latest bondret month: size, ratings, null rates
def bondret_latest():
    last = db.raw_sql("select max(date) as d from wrdsapps_bondret.bondret").d[0]
    df = db.raw_sql(f"select * from wrdsapps_bondret.bondret where date = '{last}'")
    print(f"month {last}: {len(df)} bonds, {df.cusip.nunique()} cusips")
    print(
        "null share:\n",
        df[
            [
                "yield",
                "t_spread",
                "duration",
                "coupon",
                "tmt",
                "price_eom",
                "r_sp",
                "rating_num",
            ]
        ]
        .isna()
        .mean()
        .round(3)
        .to_string(),
    )
    print("rating_class:\n", df.rating_class.value_counts(dropna=False).to_string())
    print("S&P rating:\n", df.r_sp.value_counts(dropna=False).head(15).to_string())
    print("maturity (tmt) quantiles:\n", df.tmt.describe().round(2).to_string())
    print("bond_type:\n", df.bond_type.value_counts().head(8).to_string())


probe("bondret latest month", bondret_latest)


# 3. Treasuries: latest day, number of issues, yield by maturity bucket
def treasuries_latest():
    last = db.raw_sql("select max(caldt) as d from crsp.tfz_dly").d[0]
    df = db.raw_sql(f"""
        select i.tcusip, i.itype, i.tcouprt, i.tmatdt, d.tdnomprc, d.tdyld, d.tdduratn
        from crsp.tfz_dly d join crsp.tfz_iss i on d.kycrspid = i.kycrspid
        where d.caldt = '{last}'""")
    df["years"] = (pd.to_datetime(df.tmatdt) - pd.Timestamp(last)).dt.days / 365.25
    print(
        f"day {last}: {len(df)} issues; itype counts:\n",
        df.itype.value_counts().to_string(),
    )
    df["bucket"] = pd.cut(df.years, [0, 1, 2, 3, 5, 7, 10, 20, 30, 50])
    print(
        "annualized yield (tdyld*365) by maturity bucket:\n",
        (
            df.assign(y=df.tdyld * 365)
            .groupby("bucket", observed=True)
            .y.agg(["count", "mean"])
            .round(4)
        ).to_string(),
    )


probe("Treasuries latest day", treasuries_latest)
