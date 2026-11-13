"""Scenario Monte Carlo, GRP decomposition, competitor break-even points.

Design (Supplementary Section S8):
* N parameter draws are shared by all scenarios (common random numbers), so the
  geopolitical risk premium GRP_s = LCOH_exp(s) - LCOH_exp(S0) isolates the
  scenario shock for an identical techno-economic draw.
* Scenario shocks (WACC uplift, war-risk premium) are drawn comonotonically:
  one uniform variate per draw is mapped through each scenario's inverse CDF,
  so shocks are ordered consistently across scenarios within a draw.
* The decomposition of GRP into financing and insurance contributions is an
  accounting (Shapley two-factor) decomposition of the cost model, not a
  causal estimate.
"""
from __future__ import annotations

import numpy as np

from . import cost_model as cm
from .params import load_competitors, load_production, load_yaml, sample_production


def _tri_ppf(u: np.ndarray, lo: float, mo: float, hi: float) -> np.ndarray:
    """Inverse CDF of the triangular distribution."""
    if hi == lo:
        return np.full_like(u, lo, dtype=float)
    c = (mo - lo) / (hi - lo)
    left = lo + np.sqrt(u * (hi - lo) * (mo - lo))
    right = hi - np.sqrt((1.0 - u) * (hi - lo) * (hi - mo))
    return np.where(u < c, left, right)


def _spec_ppf(spec: dict, u: np.ndarray) -> np.ndarray:
    if spec.get("dist", "fixed") == "fixed":
        return np.full_like(u, float(spec["value"]), dtype=float)
    if spec["dist"] == "triangular":
        return _tri_ppf(u, float(spec["low"]), float(spec["mode"]), float(spec["high"]))
    if spec["dist"] == "uniform":
        return float(spec["low"]) + u * (float(spec["high"]) - float(spec["low"]))
    raise ValueError(spec)


def scenario_shocks(scen_cfg: dict, n: int, rng: np.random.Generator) -> dict:
    """Comonotonic draws of WACC uplift and war-risk rates for each scenario."""
    u_w = rng.uniform(size=n)
    u_a = rng.uniform(size=n)
    spread = float(scen_cfg.get("wacc_uplift_spread", 0.0))
    out = {}
    for name, s in scen_cfg["scenarios"].items():
        m = float(s["wacc_uplift_pp"])
        w = _tri_ppf(u_w, m * (1 - spread), m, m * (1 + spread)) if m > 0 else np.zeros(n)
        a = _spec_ppf(s["war_risk_rate"], u_a)
        out[name] = {"wacc_uplift_pp": w, "war_risk_rate": a, "gpr_change": float(s["gpr_change"]),
                     "probability": float(s["probability"]), "label": s["label"]}
    return out


def tail_stats(x: np.ndarray, alpha: float = 0.95) -> dict:
    var = float(np.quantile(x, alpha))
    es = float(x[x >= var].mean())
    return {"mean": float(x.mean()), "sd": float(x.std(ddof=1)), "p05": float(np.quantile(x, 0.05)),
            "p50": float(np.median(x)), "VaR95": var, "ES95": es}


def run(n: int = 10_000, seed: int = 20251113) -> dict:
    rng = np.random.default_rng(seed)
    prod_cfg = load_production()
    scen_cfg = load_yaml("scenarios.yaml")
    routes = scen_cfg["algeria_routes"]
    p = sample_production(n, rng, prod_cfg)
    shocks = scenario_shocks(scen_cfg, n, rng)
    base = shocks["S0"]

    results = {"n": n, "seed": seed, "scenarios": {}, "draws": {}}
    for route, rc in routes.items():
        per, spill = float(rc["listed_periods"]), float(rc["spillover_share"])
        f00 = cm.delivered_cost(p, route, base["wacc_uplift_pp"], base["war_risk_rate"], per, spill)
        results["draws"][(route, "S0")] = f00["total"]
        for name, sh in shocks.items():
            fwa = cm.delivered_cost(p, route, sh["wacc_uplift_pp"], sh["war_risk_rate"], per, spill)
            fw0 = cm.delivered_cost(p, route, sh["wacc_uplift_pp"], base["war_risk_rate"], per, spill)
            f0a = cm.delivered_cost(p, route, base["wacc_uplift_pp"], sh["war_risk_rate"], per, spill)
            grp = fwa["total"] - f00["total"]
            d_fin = 0.5 * ((fw0["total"] - f00["total"]) + (fwa["total"] - f0a["total"]))
            d_ins = grp - d_fin
            inter = fwa["total"] - fw0["total"] - f0a["total"] + f00["total"]
            results["draws"][(route, name)] = fwa["total"]
            results["scenarios"][(route, name)] = {
                "label": sh["label"], "probability": sh["probability"], "gpr_change": sh["gpr_change"],
                "lcoh": tail_stats(fwa["total"]),
                "grp": tail_stats(grp),
                "grp_share_of_baseline_mean": float(grp.mean() / f00["total"].mean()),
                "financing_contrib": float(d_fin.mean()),
                "insurance_contrib": float(d_ins.mean()),
                "interaction": float(inter.mean()),
                "components_mean": {k: float(np.mean(v)) for k, v in fwa.items()},
            }
    results["competitors"] = competitor_analysis(p, shocks)
    results["competitors_beta_dz_0.5"] = competitor_analysis(p, shocks, beta_algeria=0.5)
    results["_p"] = p
    results["_shocks"] = shocks
    return results


def competitor_analysis(p: dict, shocks: dict, beta_algeria: float | None = None) -> dict:
    """Scenario-implied cost gaps and break-even GPR levels (manuscript Tables 13-14)."""
    comps = load_competitors()
    n = len(p["wacc_base"])
    rng = np.random.default_rng(7)
    names = list(shocks)
    order = np.argsort([shocks[s]["gpr_change"] for s in names])
    names = [names[i] for i in order]
    gpr = np.array([shocks[s]["gpr_change"] for s in names])
    a0 = shocks["S0"]["war_risk_rate"]

    beta_dz = float(load_yaml("scenarios.yaml").get("algeria_wacc_beta", 1.0)) if beta_algeria is None else beta_algeria
    prod0 = cm.lcoh_production(p, p["wacc_base"])
    d_dz = {s: cm.lcoh_production(p, p["wacc_base"] + beta_dz * shocks[s]["wacc_uplift_pp"] / 100.0) - prod0
            for s in names}

    out = {}
    for c in comps:
        gap0 = rng.triangular(c["s0_gap_low"], c["s0_gap_mode"], c["s0_gap_high"], size=n) \
            if c["s0_gap_low"] != c["s0_gap_high"] else np.full(n, c["s0_gap_mode"])
        rows, gaps = {}, []
        for s in names:
            sh = shocks[s]
            d_prod = cm.lcoh_production(p, p["wacc_base"] + c["wacc_beta"] * sh["wacc_uplift_pp"] / 100.0) - prod0
            d_ins = cm.war_risk_cost(p, sh["war_risk_rate"], c["listed_periods"], 0.0) - \
                cm.war_risk_cost(p, a0, c["listed_periods"], 0.0)
            rel = d_prod + d_ins - d_dz[s]          # change in competitor's cost relative to Algeria
            gap = gap0 + rel                          # >0: Algeria cheaper
            gaps.append(gap)
            rows[s] = {"gap": tail_stats(gap), "relative_change": tail_stats(rel),
                       "share_algeria_cheaper": float((gap > 0).mean())}
        G = np.vstack(gaps)                           # scenarios x draws
        be = np.full(n, np.nan)
        for i in range(n):
            g = G[:, i]
            if g[0] > 0:
                be[i] = 0.0
                continue
            idx = np.where((g[:-1] <= 0) & (g[1:] > 0))[0]
            if idx.size:
                k = idx[0]
                be[i] = gpr[k] + (0 - g[k]) * (gpr[k + 1] - gpr[k]) / (g[k + 1] - g[k])
        crossed = ~np.isnan(be)
        out[c["competitor"]] = {
            "scenarios": rows,
            "already_cheaper_at_S0_share": float((G[0] > 0).mean()),
            "breakeven_share_within_range": float(crossed.mean()),
            "breakeven_median": float(np.nanmedian(be)) if crossed.any() else None,
            "breakeven_p05": float(np.nanquantile(be, 0.05)) if crossed.any() else None,
            "breakeven_p95": float(np.nanquantile(be, 0.95)) if crossed.any() else None,
            "listed_periods": c["listed_periods"], "wacc_beta": c["wacc_beta"],
        }
    return out
