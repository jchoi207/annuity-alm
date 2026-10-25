"""Pull bond data from WRDS into data/ (gitignored). Set WRDS_USERNAME in the environment."""

import os
from pathlib import Path

import pandas as pd
import wrds
from dotenv import load_dotenv

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def connect() -> wrds.Connection:
    """Credentials from .env (WRDS_USERNAME, WRDS_PASSWORD) or an existing ~/.pgpass entry."""
    load_dotenv()
    if os.environ.get("WRDS_PASSWORD"):
        os.environ["PGPASSWORD"] = os.environ["WRDS_PASSWORD"]  # libpq reads this
    return wrds.Connection(wrds_username=os.environ["WRDS_USERNAME"])


def cached(path: Path, fn) -> pd.DataFrame:
    """Read `path` if it exists, otherwise call fn() (a WRDS pull) and save the result there."""
    if path.exists():
        return pd.read_csv(path)
    df = fn()
    path.parent.mkdir(exist_ok=True)
    df.to_csv(path, index=False)
    return df


def pull_treasuries(db: wrds.Connection, date: str) -> pd.DataFrame:
    """CRSP nominal notes and bonds on one day. ytm annualized, duration in years, prices per 100 par."""
    return db.raw_sql(f"""
        select i.tcusip as cusip, i.itype, i.tcouprt as coupon, i.tmatdt as maturity,
               d.tdnomprc as price, d.tdaccint as accrued,
               d.tdyld * 365 as ytm, d.tdduratn / 365 as duration
        from crsp.tfz_dly d join crsp.tfz_iss i on d.kycrspid = i.kycrspid
        where d.caldt = '{date}' and i.itype in (1, 2)
          and d.tdyld is not null and d.tdnomprc is not null
    """)


def pull_bondret(
    db: wrds.Connection, month_end: str, min_outstanding: float = 300_000
) -> pd.DataFrame:
    """One month of wrdsapps_bondret. Investment grade, semiannual fixed coupon, non-convertible, 1 to 30y.

    Units: coupon in percent, ytm in decimals, price_eom per 100 par, amount_outstanding in $000.
    """
    return db.raw_sql(f"""
        select cusip, company_symbol as issuer, coupon, "yield" as ytm, price_eom, coupacc,
               tmt as maturity, duration, amount_outstanding, r_sp, rating_num
        from wrdsapps_bondret.bondret
        where date = '{month_end}' and rating_num <= 10 and conv = 0
          and coalesce(defaulted, 'N') <> 'Y' and ncoups = 2 and coupon > 0
          and tmt between 1 and 30 and price_eom is not null
          and "yield" between 0 and 0.2 and duration between 0 and 40
          and amount_outstanding >= {min_outstanding}
    """)
