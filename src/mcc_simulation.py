"""Run the full scenario Monte Carlo and write every output table and figure.

Usage:
    python src/mcc_simulation.py              # 10,000 draws, default seed
    python src/mcc_simulation.py --n 50000 --seed 1

Outputs (outputs/):
    table_S5_lcoh_by_scenario.csv      distribution of delivered cost (manuscript Table 12)
    table_S6_grp_decomposition.csv     GRP and its accounting decomposition (Tables 11, 4.1.2)
    table_S7_competitors.csv           cost gaps and break-even GPR (Table 13)
    table_S8_security_value.csv        indicative security value bound (Table 14)
    convergence_S3.csv / fig_S1_convergence.png
    sensitivity.csv / fig_S2_tornado.png
    run_log.json                       seed, n, versions, parameter-file hash, timestamp
"""
from __future__ import annotations

import argparse
import csv
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from h2risk import __version__  # noqa: E402
from h2risk import cost_model as cm  # noqa: E402
from h2risk import params as P  # noqa: E402
from h2risk.params import (ROOT, central, load_yaml, params_hash)  # noqa: E402
from h2risk.simulation import run  # noqa: E402

OUT = ROOT / "outputs"  # replaced by outputs/<calibration>/ in main()
ANNUAL_EXPORT_KG = 100_000 * 1000   # 100,000 t/yr (manuscript Table 14 basis)


def write_csv(path: Path, header: list, rows: list) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


def r3(x):
    return None if x is None else round(float(x), 3)


def tables(res: dict) -> None:
    rows5, rows6 = [], []
    for (route, s), d in res["scenarios"].items():
        L, G = d["lcoh"], d["grp"]
        rows5.append([route, s, d["label"], d["gpr_change"], d["probability"], r3(L["mean"]), r3(L["sd"]),
                      r3(L["p05"]), r3(L["p50"]), r3(L["VaR95"]), r3(L["ES95"])])
        rows6.append([route, s, r3(G["mean"]), r3(G["p05"]), r3(G["VaR95"]),
                      round(100 * d["grp_share_of_baseline_mean"], 2),
                      r3(d["financing_contrib"]), r3(d["insurance_contrib"]), r3(d["interaction"])])
    write_csv(OUT / "table_S5_lcoh_by_scenario.csv",
              ["route", "scenario", "label", "gpr_change", "probability", "mean_usd_kg", "sd", "p05", "median",
               "VaR95", "ES95"], rows5)
    write_csv(OUT / "table_S6_grp_decomposition.csv",
              ["route", "scenario", "grp_mean_usd_kg", "grp_p05", "grp_p95", "grp_pct_of_S0_mean",
               "financing_contrib", "insurance_contrib", "interaction"], rows6)

    rows9 = []
    for key, lab in (("competitors", "1.0"), ("competitors_beta_dz_0.5", "0.5")):
        for comp, d in res[key].items():
            rows9.append([lab, comp, round(d["already_cheaper_at_S0_share"], 3),
                          round(d["breakeven_share_within_range"], 3), r3(d["breakeven_median"]),
                          r3(d["breakeven_p05"]), r3(d["breakeven_p95"])])
    write_csv(OUT / "table_S9_breakeven_sensitivity.csv",
              ["algeria_wacc_beta", "competitor", "share_algeria_cheaper_at_S0", "share_breakeven_within_S0_S3",
               "breakeven_gpr_median", "p05", "p95"], rows9)

    rows7, rows8 = [], []
    for comp, d in res["competitors"].items():
        for s, v in d["scenarios"].items():
            rows7.append([comp, s, r3(v["gap"]["mean"]), r3(v["gap"]["p05"]), r3(v["gap"]["VaR95"]),
                          round(v["share_algeria_cheaper"], 3)])
            rel = v["relative_change"]["mean"]
            rows8.append([comp, s, r3(rel), r3(rel * ANNUAL_EXPORT_KG / 1e6)])
        rows7.append([comp, "breakeven_gpr", r3(d["breakeven_median"]), r3(d["breakeven_p05"]),
                      r3(d["breakeven_p95"]), round(d["breakeven_share_within_range"], 3)])
    write_csv(OUT / "table_S7_competitors.csv",
              ["competitor", "scenario", "gap_mean_usd_kg(+ = Algeria cheaper)", "p05", "p95",
               "share_draws_algeria_cheaper"], rows7)
    write_csv(OUT / "table_S8_security_value.csv",
              ["competitor", "scenario", "relative_cost_change_usd_kg", "annual_value_musd_100kt"], rows8)


def convergence(res: dict) -> None:
    x = res["draws"][("pipeline", "S3")] - res["draws"][("pipeline", "S0")]
    ns = np.unique(np.linspace(100, len(x), 60).astype(int))
    rows = [[k, r3(x[:k].mean()), round(float(x[:k].std(ddof=1) / np.sqrt(k)), 5)] for k in ns]
    write_csv(OUT / "convergence_S3.csv", ["n", "running_mean_grp", "mc_standard_error"], rows)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        m = np.array([r[1] for r in rows]); se = np.array([r[2] for r in rows])
        fig, ax = plt.subplots(figsize=(6.5, 3.4), dpi=200)
        ax.plot(ns, m, color="#1F3864", lw=1.6, label="Running mean")
        ax.fill_between(ns, m - 1.96 * se, m + 1.96 * se, color="#2E75B6", alpha=0.18, lw=0, label="±1.96 MC s.e.")
        ax.set_xlabel("Number of draws"); ax.set_ylabel("GRP, S3, pipeline (USD/kg)")
        ax.spines[["top", "right"]].set_visible(False); ax.legend(frameon=False, fontsize=8)
        fig.tight_layout(); fig.savefig(OUT / "fig_S1_convergence.png"); plt.close(fig)
    except ImportError:
        pass


def sensitivity() -> None:
    """One-at-a-time sensitivity of S0 delivered cost (pipeline) and S3 GRP."""
    prod = P.load_production()
    scen = load_yaml("scenarios.yaml")["scenarios"]
    base = {k: np.array([central(v)]) for k, v in prod.items()}
    w3 = np.array([scen["S3"]["wacc_uplift_pp"]])
    a0 = np.array([scen["S0"]["war_risk_rate"]["value"]])

    def metrics(pp):
        c0 = cm.delivered_cost(pp, "pipeline", np.array([0.0]), a0)["total"][0]
        c3 = cm.delivered_cost(pp, "pipeline", w3, a0)["total"][0]
        return c0, c3 - c0

    b0, bg = metrics(base)
    rows = []
    for k, v in prod.items():
        if v.get("dist") != "triangular" or k in ("ship_chain_eur_per_kg", "hull_value_usd"):
            continue
        out = []
        for bound in ("low", "high"):
            pp = dict(base); pp[k] = np.array([float(v[bound])])
            out.append(metrics(pp))
        rows.append([k, r3(out[0][0] - b0), r3(out[1][0] - b0), r3(out[0][1] - bg), r3(out[1][1] - bg)])
    rows.sort(key=lambda r: -abs(r[2] - r[1]))
    write_csv(OUT / "sensitivity.csv", ["parameter", "dS0cost_low", "dS0cost_high", "dGRP_S3_low", "dGRP_S3_high"],
              rows)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        labels = {"el_capex_usd_per_kw": "Electrolyser CAPEX", "wacc_base": "Baseline WACC",
                  "pv_yield_kwh_per_kwp_yr": "PV specific yield", "pv_capex_usd_per_kw": "PV CAPEX",
                  "el_sec_kwh_per_kg": "Electrolyser SEC", "pipeline_transport_eur_per_mwh": "Pipeline transport",
                  "pv_fixed_om_usd_per_kw_yr": "PV fixed O&M", "desal_cost_usd_per_m3": "Desalination cost"}
        top = rows[:8][::-1]
        fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.6), dpi=200, sharey=True)
        for ax, (i, j, title) in zip(axes, [(1, 2, f"S0 delivered cost (base {b0:.2f} USD/kg)"),
                                            (3, 4, f"S3 GRP (base {bg:.2f} USD/kg)")]):
            y = np.arange(len(top))
            ax.barh(y, [r[i] for r in top], color="#2E75B6", height=0.6, label="Parameter at low bound")
            ax.barh(y, [r[j] for r in top], color="#1F3864", height=0.6, label="Parameter at high bound")
            ax.axvline(0, color="#555", lw=0.8)
            ax.set_yticks(y, [labels.get(r[0], r[0]) for r in top], fontsize=8)
            ax.set_title(title, fontsize=8.5); ax.set_xlabel("Change (USD/kg)", fontsize=8)
            ax.spines[["top", "right"]].set_visible(False); ax.tick_params(axis="x", labelsize=7.5)
        axes[0].legend(frameon=False, fontsize=7, loc="lower right")
        fig.tight_layout(); fig.savefig(OUT / "fig_S2_tornado.png"); plt.close(fig)
    except ImportError:
        pass


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10_000)
    ap.add_argument("--seed", type=int, default=20251113)
    ap.add_argument("--calibration", choices=["2023", "2030"], default="2023",
                    help="2023: current sourced costs (production.yaml); 2030: projection (production_2030.yaml)")
    a = ap.parse_args()
    global OUT
    P.set_production_file("production.yaml" if a.calibration == "2023" else "production_2030.yaml")
    OUT = ROOT / "outputs" / f"calibration_{a.calibration}"
    OUT.mkdir(parents=True, exist_ok=True)
    res = run(a.n, a.seed)
    tables(res)
    convergence(res)
    sensitivity()
    log = {"model_version": __version__, "calibration": a.calibration,
           "production_file": P.PRODUCTION_FILE, "n_draws": a.n, "seed": a.seed,
           "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "python": platform.python_version(), "numpy": np.__version__,
           "parameter_files_sha256": params_hash()}
    (OUT / "run_log.json").write_text(json.dumps(log, indent=2))
    print(json.dumps(log, indent=2))


if __name__ == "__main__":
    main()
