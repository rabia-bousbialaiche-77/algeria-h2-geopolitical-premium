"""Run the route-explicit scenario model and write every table and figure.

Usage:
    python src/run_model.py                       # 2023 calibration, 10,000 draws
    python src/run_model.py --calibration 2030
    python src/run_model.py --n 50000 --seed 1

Outputs go to outputs/calibration_<year>/ (tables as CSV, figures as PNG at
300 dpi and as PDF). Every number in the manuscript is read from these files;
tests/test_manuscript_numbers.py checks them.
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
from h2risk import params as P  # noqa: E402
from h2risk.params import ROOT, load_countries, load_yaml, params_hash  # noqa: E402
from h2risk.simulation import run, tail_stats  # noqa: E402

SCEN_ORDER = ["S0", "S1", "S1a", "S2", "S3", "H26"]
COMP = ["Morocco", "Egypt", "Oman", "Australia", "Chile"]
PAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
INK, MUTED, GRID = "#1f2328", "#59636e", "#d0d7de"
OUT = ROOT / "outputs"


def r3(x):
    return None if x is None else round(float(x), 3)


def write_csv(name, header, rows):
    with open(OUT / name, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


# ---------------------------------------------------------------- tables
def tables(res, variants, sob, conv):
    scen = load_yaml("scenarios.yaml")["scenarios"]
    rows = []
    for mode in ("pipeline", "ship"):
        for s in SCEN_ORDER:
            c, g = res["costs"][("Algeria", mode, s)]["total"], res["grp"][("Algeria", mode, s)]
            sh = res["shocks_summary"][s]
            rows.append([mode, s, scen[s]["label"], sh["gpr"], r3(sh["w"]["p50"]),
                         r3(100 * sh["ap"]["red_sea"]["p50"]), r3(100 * sh["ap"]["gulf"]["p50"]),
                         r3(c["mean"]), r3(c["p05"]), r3(c["p50"]), r3(c["p95"]), r3(c["ES95"]),
                         r3(g["grp"]["mean"]), r3(g["grp"]["p05"]), r3(g["grp"]["p50"]), r3(g["grp"]["p95"]),
                         r3(g["grp"]["ES95"]), round(100 * g["pct_of_S0_mean"], 2), r3(g["financing"]), r3(g["insurance"])])
    write_csv("table_algeria_scenarios.csv",
              ["mode", "scenario", "label", "gpr_change", "wacc_uplift_pp_p50", "ap_red_sea_pct_p50", "ap_gulf_pct_p50",
               "cost_mean", "cost_p05", "cost_p50", "cost_p95", "cost_ES95", "grp_mean", "grp_p05", "grp_p50", "grp_p95",
               "grp_ES95", "grp_pct_of_S0_mean", "grp_financing", "grp_insurance"], rows)

    rows = []
    for ctry in COMP:
        for s in SCEN_ORDER:
            c = res["costs"][(ctry, "ship", s)]
            row = [ctry, s, r3(c["total"]["p50"]), r3(c["total"]["p05"]), r3(c["total"]["p95"]),
                   "; ".join(f"{k}: {v:.2f}" for k, v in c["route_share"].items())]
            for ref in ("pipeline", "ship"):
                g = res["gaps"][(ctry, ref)][s]
                row += [r3(g["gap"]["p50"]), r3(g["gap"]["p05"]), r3(g["gap"]["p95"]), round(g["share_algeria_cheaper"], 3),
                        r3(g["change_vs_S0"]["mean"]), r3(g["financing"]), r3(g["insurance_rerouting"]),
                        r3(g["security_premium_mean"]), r3(g["security_premium_ES95"])]
            rows.append(row)
    hdr = ["competitor", "scenario", "cost_p50", "cost_p05", "cost_p95", "route_shares"]
    for ref in ("vsDZpipe", "vsDZnh3"):
        hdr += [f"gap_p50_{ref}", f"gap_p05_{ref}", f"gap_p95_{ref}", f"share_DZ_cheaper_{ref}", f"gap_change_vs_S0_{ref}",
                f"chg_financing_{ref}", f"chg_insurance_rerouting_{ref}", f"SP_mean_{ref}", f"SP_ES95_{ref}"]
    write_csv("table_competitors.csv", hdr, rows)

    rows = []
    for ctry in COMP:
        for ref in ("pipeline", "ship"):
            d = res["gaps"][(ctry, ref)]["S0_components"]
            tot = res["gaps"][(ctry, ref)]["S0"]["gap"]["mean"]
            rows.append([ctry, ref, r3(d["resource"]), r3(d["cost_of_capital"]), r3(d["transport"]), r3(d["insurance"]), r3(tot)])
    write_csv("table_baseline_gap_components.csv",
              ["competitor", "algeria_mode", "resource", "cost_of_capital", "transport", "insurance", "total_gap_mean"], rows)

    rows = []
    for ctry in COMP:
        for ref in ("pipeline", "ship"):
            b = res["breakeven"][(ctry, ref)]
            rows.append([ctry, ref, round(b["already_cheaper_share"], 3), round(b["cross_within_S3_share"], 3),
                         round(b["never_share"], 3), r3(b["median_if_crossed"]), r3(b["p05_if_crossed"]), r3(b["p95_if_crossed"]),
                         round(b["lose_within_S3_share"], 3), r3(b["median_if_lost"]), r3(b["p05_if_lost"]), r3(b["p95_if_lost"])])
    write_csv("table_breakeven.csv", ["competitor", "algeria_mode", "share_DZ_cheaper_at_S0", "share_gain_S0_S3",
                                      "share_never_cheaper", "gain_gpr_median", "gain_p05", "gain_p95",
                                      "share_lose_S0_S3", "lose_gpr_median", "lose_p05", "lose_p95"], rows)

    cc = load_countries()["countries"]
    rows = []
    for ctry, v in cc.items():
        for rt in v["routes"]:
            days = 2 * rt["nm"] / (15 * 24) + 4
            rows.append([ctry, v["site"], v["pv_yield_kwh_per_kwp_yr"], r3(100 * res["wacc"][ctry]["p50"]),
                         r3(res["betas"][ctry]), v["port"], rt["name"], rt["nm"], round(days, 1), rt["canal"],
                         "; ".join(rt["areas"]) or "none", "pipeline + ammonia" if v.get("pipeline") else "ammonia"])
    write_csv("table_route_inputs.csv", ["country", "site", "pvout_kwh_kwp", "wacc_pct_p50", "beta", "port", "route",
                                         "distance_nm", "roundtrip_days_at_15kn", "canal", "listed_areas", "carrier"], rows)

    rows = []
    for out, d in sob["indices"].items():
        for k, v in sorted(d.items(), key=lambda kv: -kv[1]["ST"]):
            rows.append([out, k, r3(v["S1"]), r3(v["S1_conf"]), r3(v["ST"]), r3(v["ST_conf"]),
                         v["status"]])
    write_csv("table_sobol.csv", ["output", "input", "S1", "S1_conf95", "ST", "ST_conf95", "status"], rows)

    rows = []
    for name, r in variants.items():
        g3 = r["grp"][("Algeria", "pipeline", "S3")]
        gh = r["grp"][("Algeria", "pipeline", "H26")]
        a3 = r["grp"][("Algeria", "ship", "S3")]
        ch = r["gaps"][("Chile", "pipeline")]["S3"]
        rows.append([name, r3(r["costs"][("Algeria", "pipeline", "S0")]["total"]["p50"]), r3(g3["grp"]["p50"]),
                     r3(g3["grp"]["p05"]), r3(g3["grp"]["p95"]), round(100 * g3["pct_of_S0_mean"], 2), r3(gh["grp"]["p50"]),
                     r3(r["costs"][("Algeria", "ship", "S0")]["total"]["p50"]), r3(a3["grp"]["p50"]),
                     round(100 * a3["pct_of_S0_mean"], 2),
                     r3(r["gaps"][("Oman", "ship")]["S3"]["gap"]["p50"]), round(r["breakeven"][("Oman", "ship")]["cross_within_S3_share"], 3),
                     r3(r["breakeven"][("Oman", "ship")]["median_if_crossed"]),
                     r3(r["gaps"][("Australia", "ship")]["S3"]["gap"]["p50"]),
                     round(r["breakeven"][("Australia", "ship")]["cross_within_S3_share"], 3),
                     r3(ch["gap"]["p05"]), r3(ch["gap"]["p50"]), r3(ch["gap"]["p95"]), round(ch["share_algeria_cheaper"], 3),
                     r3(r["costs"][("Oman", "ship", "S3")]["total"]["p50"]),
                     r3(r["costs"][("Egypt", "ship", "S3")]["total"]["p50"])])
    write_csv("table_variants.csv", ["variant", "DZpipe_S0_cost_p50", "DZpipe_GRP_S3_p50", "p05", "p95", "pct_of_S0",
                                     "DZpipe_GRP_H26_p50", "DZnh3_S0_cost_p50", "DZnh3_GRP_S3_p50", "DZnh3_pct_of_S0",
                                     "Oman_gap_vsDZnh3_S3_p50", "Oman_share_crossing",
                                     "Oman_breakeven_median", "Australia_gap_vsDZnh3_S3_p50", "Australia_share_crossing",
                                     "Chile_gap_vsDZpipe_S3_p05", "Chile_gap_vsDZpipe_S3_p50", "Chile_gap_vsDZpipe_S3_p95",
                                     "Chile_share_DZpipe_cheaper_S3", "Oman_cost_S3_p50", "Egypt_cost_S3_p50"], rows)
    write_csv("convergence.csv", ["n", "running_mean_grp_S3_pipe", "mcse_mean", "running_ES95", "mcse_ES95_batch"], conv)


def _plain(o):
    """Results dictionary with tuple keys and numpy scalars made JSON-serialisable."""
    if isinstance(o, dict):
        return {("|".join(k) if isinstance(k, tuple) else str(k)): _plain(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_plain(v) for v in o]
    if isinstance(o, np.ndarray):
        return None
    if isinstance(o, (np.floating, np.integer)):
        return float(o)
    return o


def full_results(variants, sob):
    """Unrounded statistics behind the tables (outputs/.../results_full.json); the numbers quoted in
    the article are formatted from this file, which avoids rounding a rounded value."""
    keep = ("costs", "grp", "gaps", "breakeven", "shocks_summary", "wacc", "betas", "central")
    out = {"variants": {name: {k: _plain(r[k]) for k in keep} for name, r in variants.items()},
           "sobol": {"n_base": sob["n_base"], "n_eval": sob["n_eval"], "n_inputs": sob["n_inputs"],
                     "inputs": sob["inputs"], "indices": sob["indices"]}}
    (OUT / "results_full.json").write_text(json.dumps(out, indent=1))


def convergence(res):
    x = res["delta"][("Algeria", "pipeline", "S3")]
    ns = np.unique(np.linspace(200, len(x), 50).astype(int))
    rows = []
    for k in ns:
        xs = x[:k]
        es = tail_stats(xs)["ES95"]
        b = np.array_split(xs, 20)
        es_b = np.array([tail_stats(bb)["ES95"] for bb in b if len(bb) > 20])
        rows.append([int(k), r3(xs.mean()), round(float(xs.std(ddof=1) / np.sqrt(k)), 5), r3(es),
                     round(float(es_b.std(ddof=1) / np.sqrt(len(es_b))), 5)])
    return rows


def validation_table(res):
    """Ex-ante scenario values against the observations in data/raw/observed_2026.csv."""
    sc = res["shocks_summary"]
    scen = load_yaml("scenarios.yaml")["scenarios"]
    h26 = scen["H26"]["wacc_uplift_pp"]
    anchor = float(h26["mode"])                          # Algerian equivalent of Egypt's +44 bp (pp)
    w2, w3 = sc["S2"]["w"]["p50"], sc["S3"]["w"]["p50"]
    g = {s: 100 * (1 + sc[s]["gpr"]) for s in ("S1", "S2", "S3")}
    band = lambda s, a: f"{100*sc[s]['ap'][a]['p05']:.1f}-{100*sc[s]['ap'][a]['p95']:.1f}"
    rows = [
        ["GPR (1985-2019 mean = 100; % above mean in brackets)",
         f"S2: {g['S2']:.0f} (+{100*sc['S2']['gpr']:.0f}%); S3: {g['S3']:.0f} (+{100*sc['S3']['gpr']:.0f}%)",
         "Mar 2026: 330; Apr: 253; May: 204; Jun-Oct: 126-178",
         "Above S3 in March-April; near S2 from June", "Caldara and Iacoviello (2022), data to Oct 2026"],
        ["War-risk AP, Strait of Hormuz (% hull per transit)",
         f"S2: {band('S2', 'gulf')}; S3: {band('S3', 'gulf')}",
         "Pre-war 0.20-0.25; early Mar 1.0-3.0; 30 Mar 5.0-7.5; 10 Apr ~3 (withdrawn); mid-Jun ~5 then ~2; late Jul 7.5-10",
         "Reached the S3 band within a week; above it in late March, mid-June and July",
         "Insurance Business; Trans.info; Datamar; Argus Media; S&P Global (2026)"],
        ["War-risk AP, Red Sea / Bab el-Mandeb (% hull per transit)",
         f"S2: {band('S2', 'red_sea')}; S3: {band('S3', 'red_sea')}",
         "Late Mar ~0.6 to 0.65-0.75; 13 Apr 0.75; mid-Jul 0.3; 21-23 Jul 0.5-0.75, then above 1",
         "Below the S2 band until late July (design applied one AP to all listed areas)",
         "Argus Media; S&P Global; Reuters via Insurance Journal (2026)"],
        ["Financing shock (WACC / sovereign spreads)",
         f"Algeria WACC +{w2:.1f} pp (S2), +{w3:.1f} pp (S3)",
         f"EMBI GD +17 to +25 bp; Egypt +44 bp (Mar 2026); Algerian equivalent {anchor:.2f} pp (Egypt / beta)",
         f"S2 and S3 uplifts are {w2/anchor:.0f} and {w3/anchor:.0f} times the {anchor:.2f}-pp Algerian equivalent "
         f"({100*w2/25:.0f}-{100*w3/17:.0f} times the raw EMBI move)",
         "Reuters (2026)"],
        ["Hydrogen-derivative prices", "Not a cost item for green hydrogen (channel C4)", "Urea price doubled Jan-Apr 2026",
         "Consistent with C4 raising grey-ammonia costs", "IEA (2026)"],
    ]
    write_csv("table_validation_2026.csv", ["variable", "ex_ante_assumption", "observed_2026", "assessment", "source"], rows)


# ---------------------------------------------------------------- figures
def _style(ax):
    ax.spines[["top", "right"]].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.yaxis.grid(True, color=GRID, lw=0.5)
    ax.set_axisbelow(True)


def figures(res, sob):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8.5, "axes.labelcolor": INK, "text.color": INK})

    def save(fig, name):
        fig.savefig(OUT / f"{name}.png", dpi=300, bbox_inches="tight")
        fig.savefig(OUT / f"{name}.pdf", bbox_inches="tight")
        plt.close(fig)

    # Fig. 1 - framework diagram (notation as in Eqs. 1-7 of the article)
    fig, ax = plt.subplots(figsize=(7.2, 3.7))
    ax.set_xlim(0, 10); ax.set_ylim(0, 5); ax.axis("off")
    def box(x, y, w, h, txt, fc, ec, bold=False, fs=7):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08", fc=fc, ec=ec, lw=1))
        ax.text(x + w / 2, y + h / 2, txt, ha="center", va="center", fontsize=fs, weight="bold" if bold else "normal",
                linespacing=1.35)
    def arrow(p, q, col=MUTED, lw=0.8):
        ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=9, color=col, lw=lw, shrinkA=0, shrinkB=0))
    box(0.05, 1.8, 2.4, 1.4, "Geopolitical scenario $s$\nGPR level,\nWACC uplift,\nwar-risk premiums\nof listed areas", "#eef4fc", PAL[0], True, fs=6.6)
    chans = [("C1 Financing\n" + r"$r_i(s)=r_i(S0)+\beta_i\,\Delta r_{DZ}(s)$", 3.95, True),
             ("C2 Insurance and rerouting\n" + r"$I_k(s)=2\,V\,\Sigma_a AP_a(s)\,/\,Q$", 2.8, True),
             ("C3 Buyer preferences\n(contract terms)", 1.65, False),
             ("C4 Fossil input prices\n(grey H$_2$ / NH$_3$)", 0.5, False)]
    for t, y, priced in chans:
        box(3.05, y, 2.85, 0.85, t, "#fdf0e9" if priced else "#f4f5f7", PAL[1] if priced else GRID)
        arrow((2.49, 2.5), (3.03, y + 0.42))
    box(6.6, 2.75, 3.3, 1.75, "Route-explicit delivered cost\n" + r"$C_{i,m}(s)=LCOH^{prod}_i(r_i(s))$" + "\n"
        + r"$+\,T_{i,m}(s)+I_{i,m}(s)+K_i$" + "\n(cheapest route in every draw)", "#eaf7f1", PAL[2], True)
    box(6.6, 0.5, 3.3, 1.6, "Outputs\n" + r"$GRP_{i,m}(s)=C_{i,m}(s)-C_{i,m}(S0)$" + "\nShapley split into C1 and C2\nbreak-even GPR; security premium",
        "#fff6e0", PAL[3])
    arrow((5.92, 4.37), (6.58, 3.95), PAL[1], 1.0)
    arrow((5.92, 3.22), (6.58, 3.35), PAL[1], 1.0)
    arrow((8.25, 2.73), (8.25, 2.14))
    ax.text(4.47, 0.14, "C3 and C4 are discussed but not priced.", ha="center", fontsize=6.5, color=MUTED)
    save(fig, "fig1_framework")

    # Fig. 2 - violin plots of delivered cost (Algeria)
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.2), sharey=False)
    for ax, mode, title, col in zip(axes, ("pipeline", "ship"), ("(a) Algeria, SoutH2 pipeline", "(b) Algeria, ammonia ship"), (PAL[0], PAL[1])):
        data = [res["draws"][("Algeria", mode, s)] for s in SCEN_ORDER]
        vp = ax.violinplot(data, showmedians=False, showextrema=False, widths=0.8)
        for b in vp["bodies"]:
            b.set_facecolor(col); b.set_edgecolor(col); b.set_alpha(0.35)
        for i, d in enumerate(data, start=1):
            q05, q50, q95 = np.quantile(d, [0.05, 0.5, 0.95])
            ax.vlines(i, q05, q95, color=INK, lw=0.9); ax.plot(i, q50, "o", ms=3, color=INK)
        ax.set_xticks(range(1, len(SCEN_ORDER) + 1), SCEN_ORDER)
        ax.set_title(title, fontsize=8.5, loc="left"); _style(ax)
    axes[0].set_ylabel("Delivered cost (USD/kg H2, 2023 prices)")
    fig.text(0.5, -0.02, "Dots: median; lines: 5th-95th percentile; 10,000 draws per scenario.", ha="center", fontsize=7, color=MUTED)
    fig.tight_layout(); save(fig, "fig2_cost_distributions")

    # Fig. 3 - change in delivered cost by channel, S3 and H26
    units = [("Algeria", "pipeline", "DZ pipe"), ("Algeria", "ship", "DZ NH3")] + \
            [(c, "ship", c) for c in COMP]
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.0), sharey=False)
    for ax, s, title in zip(axes, ("S3", "H26"), ("(a) S3, full blockade (ex ante)", "(b) H26, Hormuz 2026 as observed")):
        x = np.arange(len(units))
        fin = [res["grp"][(c, m, s)]["financing_p50"] for c, m, _ in units]
        ins = [res["grp"][(c, m, s)]["insurance_p50"] for c, m, _ in units]
        ax.bar(x, fin, 0.62, color=PAL[0], label="Financing (C1)", edgecolor="white", lw=0.8)
        ax.bar(x, ins, 0.62, bottom=fin, color=PAL[1], label="Insurance and rerouting (C2)", edgecolor="white", lw=0.8)
        ax.set_xticks(x, [u[2] for u in units], fontsize=7, rotation=35, ha="right"); ax.set_title(title, fontsize=8.5, loc="left"); _style(ax)
        ax.axhline(0, color=MUTED, lw=0.6); ax.set_ylim(0, 1.15 * max(np.add(fin, ins)))
    axes[0].set_ylabel("Change in delivered cost vs S0 (USD/kg)")
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, frameon=False, fontsize=7, loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.01))
    fig.text(0.5, -0.045, "The vertical scales of the two panels differ by about a factor of ten.", ha="center", fontsize=7, color=MUTED)
    fig.tight_layout(rect=(0, 0.06, 1, 1)); save(fig, "fig3_channel_decomposition")

    # Fig. 4 - cost differential vs GPR
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.3), sharex=True)
    for ax, ref, title in zip(axes, ("pipeline", "ship"), ("(a) Competitor minus Algeria (pipeline)", "(b) Competitor minus Algeria (ammonia)")):
        for i, c in enumerate(COMP):
            cv = res["curves"][(c, ref)]
            gx = 100 * cv["grid"]
            ax.fill_between(gx, cv["p05"], cv["p95"], color=PAL[i], alpha=0.12, lw=0)
            ax.plot(gx, cv["p50"], color=PAL[i], lw=1.6, label=c)
        ax.axhline(0, color=INK, lw=0.8, ls="--")
        ax.set_title(title, fontsize=8.5, loc="left"); _style(ax)
    axes[0].set_ylabel("Cost differential (USD/kg); > 0: Algeria cheaper")
    fig.supxlabel("GPR, % above the 1985-2019 mean (Hormuz path S0-S1-S2-S3); lines: median, bands: 5th-95th percentile", fontsize=7.5, color=INK)
    axes[1].legend(frameon=False, fontsize=7, ncol=1, loc="upper left", bbox_to_anchor=(1.0, 1.0))
    fig.tight_layout(); save(fig, "fig4_competitor_differentials")

    # Fig. 5 - 2026 validation
    import pandas as pd
    gpr_file = ROOT / "data" / "raw" / "gpr_export.xls"
    obs = pd.read_csv(ROOT / "data" / "raw" / "observed_2026.csv", parse_dates=["date"])
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.2))
    ax = axes[0]
    if gpr_file.exists():
        g = pd.read_excel(gpr_file, engine="calamine")[["month", "GPR"]]
        g = g[g.month >= "2025-01-01"]
        ax.plot(g.month, g.GPR, color=INK, lw=1.4, label="GPR (monthly)")
    for s, col in (("S1", PAL[3]), ("S2", PAL[1]), ("S3", PAL[4])):
        lev = 100 * (1 + res["shocks_summary"][s]["gpr"])
        ax.axhline(lev, color=col, lw=1, ls="--")
        ax.text(pd.Timestamp("2025-07-20"), lev + 5, f"{s} ({lev:.0f})", fontsize=7, color=col,
                bbox=dict(fc="white", ec="none", pad=0.6, alpha=0.85))
    ax.set_title("(a) Geopolitical Risk Index, 2025-2026", fontsize=8.5, loc="left"); _style(ax)
    ax.set_ylabel("Index (1985-2019 = 100)")
    ax.tick_params(axis="x", labelrotation=30)
    ax = axes[1]
    sc = res["shocks_summary"]
    t0, t1 = pd.Timestamp("2026-02-15"), pd.Timestamp("2026-08-15")
    for s, col in (("S2", PAL[1]), ("S3", PAL[4])):
        lo, hi = 100 * sc[s]["ap"]["gulf"]["p05"], 100 * sc[s]["ap"]["gulf"]["p95"]
        ax.fill_between([t0, t1], lo, hi, color=col, alpha=0.15, lw=0); ax.text(t1, hi * 1.04, f"{s} band ", fontsize=7, color=col, ha="right")
    w = obs[obs.variable == "war_risk_ap"].sort_values("date")
    for area, col, mk in (("Strait of Hormuz", PAL[0], "o"), ("Bab el-Mandeb / Red Sea", PAL[2], "s")):
        d = w[w.area == area]
        mid = (d.value_low + d.value_high) / 2
        ax.plot(d.date, mid, "-", color=col, lw=0.8, alpha=0.6)            # path between dated quotes
        ax.vlines(d.date, d.value_low, d.value_high, color=col, lw=1.5)
        ax.plot(d.date, mid, mk, color=col, ms=3.5, label=area)
    ax.set_yscale("log"); ax.set_ylim(0.1, 15)
    ax.set_xlim(t0, t1)
    ax.set_ylabel("War-risk additional premium (% of hull value)")
    ax.set_title("(b) Observed premiums vs ex-ante S2/S3", fontsize=8.5, loc="left"); _style(ax)
    ax.legend(frameon=False, fontsize=7, loc="lower left", bbox_to_anchor=(0.18, 0.0)); ax.tick_params(axis="x", labelrotation=30)
    fig.tight_layout(); save(fig, "fig5_validation_2026")

    # Fig. S - Sobol indices
    from h2risk.sensitivity import LABELS
    keys = list(sob["indices"])
    fig, axes = plt.subplots(1, len(keys), figsize=(7.2, 3.0), sharey=False)
    for ax, k in zip(axes, keys):
        d = sorted(sob["indices"][k].items(), key=lambda kv: kv[1]["ST"])[-7:]
        y = np.arange(len(d))
        ax.barh(y - 0.18, [v["S1"] for _, v in d], 0.34, color=PAL[0], label="First order")
        ax.barh(y + 0.18, [v["ST"] for _, v in d], 0.34, color=PAL[1], label="Total")
        ax.set_yticks(y, [LABELS.get(n, n) for n, _ in d], fontsize=7); ax.set_xlim(0, 1)
        ax.set_title(k, fontsize=7.5, loc="left"); _style(ax); ax.xaxis.grid(True, color=GRID, lw=0.5); ax.yaxis.grid(False)
    axes[0].legend(frameon=False, fontsize=7, loc="lower right")
    fig.tight_layout(); save(fig, "figS_sobol")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10_000)
    ap.add_argument("--seed", type=int, default=20251113)
    ap.add_argument("--calibration", choices=["2023", "2030"], default="2023")
    ap.add_argument("--no-figures", action="store_true")
    a = ap.parse_args()
    global OUT
    P.set_production_file("production.yaml" if a.calibration == "2023" else "production_2030.yaml")
    OUT = ROOT / "outputs" / f"calibration_{a.calibration}"
    OUT.mkdir(parents=True, exist_ok=True)
    res = run(a.n, a.seed, keep_draws=False)
    variants = {"baseline (spread-proportional beta, Duqm)": res,
                "author betas (earlier version)": run(a.n, a.seed, beta_rule="alternative"),
                "Algeria beta = 0.5": run(a.n, a.seed, algeria_beta=0.5),
                "Oman exports from Sohar": run(a.n, a.seed, oman_port="Sohar"),
                "independent scenario shocks": run(a.n, a.seed, independent=True),
                "midstream capital exposed to exporter WACC (upper bound)": run(a.n, a.seed, midstream=True),
                "fuel valued at production cost + 1 USD/kg": run(a.n, a.seed, fuel_adder=True),
                "independent PV yield factor per site": run(a.n, a.seed, independent_yield=True)}
    from h2risk.sensitivity import run_sobol
    sob = run_sobol(2048, a.seed, "S3")
    conv = convergence(res)
    tables(res, variants, sob, conv)
    validation_table(res)
    full_results(variants, sob)
    if not a.no_figures:
        figures(res, sob)
    summary = {
        "betas": res["betas"], "wacc_p50": {k: v["p50"] for k, v in res["wacc"].items()},
        "pv_yield_mean": res["pv_yield"], "sobol_n_eval": sob["n_eval"], "sobol_n_inputs": sob["n_inputs"],
        "sobol_inputs": sob["inputs"],
        # Algerian production cost at the modal parameters (worked example, Section 3.3) and
        # the back-of-the-envelope bound for wind-solar hybrid supply (Section 5.3)
        "central": res["central"],
        "algeria_pipeline_S0": {"mean": res["costs"][("Algeria", "pipeline", "S0")]["total"]["mean"],
                                "p50": res["costs"][("Algeria", "pipeline", "S0")]["total"]["p50"],
                                "modal_sum": res["central"]["central"]["total"] + res["central"]["pipeline_transport"]},
        "shapley_interaction_mean": {f"{c}|{m}|{sc}": v["interaction"] for (c, m, sc), v in res["grp"].items()
                                     if abs(v["interaction"]) > 1e-9},
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))
    log = {"model_version": __version__, "calibration": a.calibration, "production_file": P.PRODUCTION_FILE,
           "n_draws": a.n, "seed": a.seed, "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "python": platform.python_version(), "numpy": np.__version__, "parameter_files_sha256": params_hash(),
           "gpr_workbook_present": (ROOT / "data" / "raw" / "gpr_export.xls").exists()}
    (OUT / "run_log.json").write_text(json.dumps(log, indent=2))
    print(json.dumps(log, indent=2))


if __name__ == "__main__":
    main()
