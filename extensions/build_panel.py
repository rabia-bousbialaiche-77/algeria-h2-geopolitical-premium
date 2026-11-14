"""Build the monthly estimation panel and the quarterly synthetic cost index.

    python src/build_panel.py            -> data/processed/panel_monthly.csv
                                            data/processed/lcoh_export_quarterly.csv

Sample: 2015M01-2025M06 (data cut-off June 2025): 126 monthly and 42 quarterly
observations. Missing optional inputs are reported, not imputed.

IMPORTANT (Supplementary S2.3): the synthetic LCOH_Export index is computed with
the cost model, so its movements are driven mechanically by the financing proxy
and the war-risk premium. Regressions of LCOH_Export on these inputs recover the
model's own accounting structure; causal claims must rest on the regressions of
the observable market variables (spread proxy, war-risk quotes, oil volatility)
on GPR, whose estimated elasticities are then mapped into USD/kg by the model.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from h2risk import cost_model as cm  # noqa: E402
from h2risk.params import central_production  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW, PROC = ROOT / "data" / "raw", ROOT / "data" / "processed"
START, END = "2015-01-01", "2025-06-30"
# Country GPR series available for MENA in data_gpr_export.xls (no Algeria-specific series exists).
# AUTHOR TO CONFIRM the selection.
MENA_GPR_COLUMNS: list[str] = ["GPRC_EGY", "GPRC_ISR", "GPRC_SAU", "GPRC_TUN"]


def monthly_index() -> pd.DatetimeIndex:
    return pd.date_range(START, END, freq="MS")


def load_fred(name: str) -> pd.Series:
    df = pd.read_csv(RAW / name)
    df.columns = ["date", "value"]
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.set_index("date")["value"]


def gpr_series() -> pd.DataFrame:
    f = RAW / "gpr_export.xls"
    if not f.exists():
        return pd.DataFrame(index=monthly_index())
    df = pd.read_excel(f)
    df["month"] = pd.to_datetime(df["month"])
    df = df.set_index("month")
    out = pd.DataFrame({"GPR": df["GPR"]})
    if MENA_GPR_COLUMNS:
        out["GPR_MENA"] = df[MENA_GPR_COLUMNS].mean(axis=1)
    return out


def war_risk_monthly(idx: pd.DatetimeIndex) -> pd.Series:
    q = pd.read_csv(RAW / "war_risk_quotes.csv", parse_dates=["date"])
    q = q.sort_values("date").groupby("date")["ap_pct_hull_value"].min()   # keep the lower quote on a tie
    month_end = idx + pd.offsets.MonthEnd(0)                                 # value prevailing at month end
    s = q.reindex(q.index.union(month_end)).ffill().reindex(month_end)
    s.index = idx
    return s.fillna(q.iloc[0]) / 100.0                                       # share of hull value


def build() -> tuple[pd.DataFrame, pd.DataFrame]:
    idx = monthly_index()
    panel = pd.DataFrame(index=idx)
    panel = panel.join(gpr_series(), how="left")
    if (RAW / "fred_GEPUCURRENT.csv").exists():
        panel["EPU"] = load_fred("fred_GEPUCURRENT.csv").resample("MS").mean()
    if (RAW / "fred_DCOILBRENTEU.csv").exists():
        brent = load_fred("fred_DCOILBRENTEU.csv").dropna()
        r = np.log(brent).diff()
        panel["Oil_Vol"] = r.rolling(30, min_periods=20).std().resample("MS").mean()
    for fname, col in (("eu_ets.csv", "EU_ETS"), ("financing_proxy.csv", "Spread_bp"), ("cri.csv", "CRI")):
        f = RAW / fname
        if f.exists():
            d = pd.read_csv(f, parse_dates=["date"]).set_index("date").iloc[:, 0]
            panel[col] = d.resample("MS").mean().reindex(idx).ffill()
    panel["Ins_Prem"] = war_risk_monthly(idx)
    panel["SoutH2_Decl"] = (idx >= "2025-01-01").astype(int)
    panel["EU_Div"] = (idx >= "2022-05-01").astype(int) + (idx >= "2023-03-01").astype(int)  # AUTHOR TO CONFIRM

    # quarterly synthetic cost index (central parameters, time-varying WACC and war-risk premium)
    p = central_production()
    spread = panel["Spread_bp"] if "Spread_bp" in panel else pd.Series(0.0, index=idx)
    dw_pp = (spread - spread.mean()) / 100.0                       # deviation in percentage points
    pipe = cm.delivered_cost(p, "pipeline", dw_pp.fillna(0).to_numpy(), panel["Ins_Prem"].to_numpy())["total"]
    ship = cm.delivered_cost(p, "ship", dw_pp.fillna(0).to_numpy(), panel["Ins_Prem"].to_numpy(),
                             periods=0.0, spillover=0.0)["total"]
    panel["LCOH_pipeline"] = pipe
    panel["LCOH_ship"] = ship
    quarterly = panel[["LCOH_pipeline", "LCOH_ship"]].resample("QS").mean()
    quarterly.index.name = "quarter"
    return panel, quarterly


def main() -> None:
    PROC.mkdir(parents=True, exist_ok=True)
    panel, q = build()
    panel.to_csv(PROC / "panel_monthly.csv", index_label="month")
    q.to_csv(PROC / "lcoh_export_quarterly.csv")
    print(f"monthly panel: {len(panel)} rows ({panel.index[0]:%Y-%m} to {panel.index[-1]:%Y-%m})")
    print(f"quarterly index: {len(q)} rows")
    missing = [c for c in ("GPR", "EPU", "Oil_Vol", "EU_ETS", "Spread_bp", "CRI") if c not in panel]
    if missing:
        print("missing inputs (see params/data_dictionary.csv):", ", ".join(missing))


if __name__ == "__main__":
    main()
