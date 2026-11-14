"""Scenario Monte Carlo for Algeria and five competing exporters.

Design (manuscript Sections 3.3-3.7):
* N parameter draws are shared by all countries and scenarios (common random
  numbers), so GRP(s) = C(s) - C(S0) isolates the scenario shock and
  GRP(S0) = 0 by construction.
* Scenario shocks are drawn comonotonically by default: one uniform variate for
  the WACC uplift and one for the war-risk premiums, mapped through every
  scenario's inverse CDF. ``independent=True`` draws them independently
  (dependence sensitivity).
* Channel contributions are accounting (two-factor Shapley) decompositions of
  the deterministic cost model, not causal estimates.
"""
from __future__ import annotations

import numpy as np

from . import cost_model as cm
from .params import load_countries, load_production, load_yaml, sample_production

AREAS = ("red_sea", "gulf")


def _tri_ppf(u, lo, mo, hi):
    if hi == lo:
        return np.full_like(u, lo, dtype=float)
    c = (mo - lo) / (hi - lo)
    left = lo + np.sqrt(u * (hi - lo) * (mo - lo))
    right = hi - np.sqrt((1.0 - u) * (hi - lo) * (hi - mo))
    return np.where(u < c, left, right)


def _ppf(spec, u):
    if isinstance(spec, (int, float)):
        return np.full_like(u, float(spec), dtype=float)
    d = spec.get("dist", "fixed")
    if d == "fixed":
        return np.full_like(u, float(spec["value"]), dtype=float)
    if d == "triangular":
        return _tri_ppf(u, float(spec["low"]), float(spec["mode"]), float(spec["high"]))
    raise ValueError(spec)


def scenario_shocks(cfg: dict, n: int, rng, independent: bool = False) -> dict:
    """WACC uplift for Algeria (pp) and war-risk AP by area, per scenario."""
    spread = float(cfg.get("wacc_uplift_spread", 0.0))
    u_w, u_a = rng.uniform(size=n), rng.uniform(size=n)
    out = {}
    for name, s in cfg["scenarios"].items():
        uw = rng.uniform(size=n) if independent else u_w
        ua = rng.uniform(size=n) if independent else u_a
        w = s["wacc_uplift_pp"]
        if isinstance(w, dict):
            wd = _ppf(w, uw)
        else:
            m = float(w)
            wd = _tri_ppf(uw, m * (1 - spread), m, m * (1 + spread)) if m > 0 else np.zeros(n)
        ap = {a: _ppf(s["war_risk"][a], ua if not independent else rng.uniform(size=n)) for a in AREAS}
        out[name] = {"w": wd, "ap": ap, "gpr": float(s["gpr_change"]), "label": s["label"]}
    return out


def country_wacc(c: dict, wacc_ref, debt_share: float):
    return wacc_ref + debt_share * c["default_spread"] + (1 - debt_share) * c["crp"]


def country_betas(cdefs: dict, rule: str, alt: dict | None = None) -> dict:
    ds_dz = cdefs["Algeria"]["default_spread"]
    if rule == "spread_proportional":
        return {k: v["default_spread"] / ds_dz for k, v in cdefs.items()}
    if rule == "alternative":
        b = {"Algeria": 1.0}
        b.update(alt or {})
        return b
    if rule == "uniform":
        return {k: 1.0 for k in cdefs}
    raise ValueError(rule)


def tail_stats(x, alpha=0.95) -> dict:
    x = np.asarray(x, dtype=float)
    var = float(np.quantile(x, alpha))
    es = float(x[x >= var].mean())
    return {"mean": float(x.mean()), "sd": float(x.std(ddof=1)), "p05": float(np.quantile(x, 0.05)),
            "p50": float(np.median(x)), "p95": var, "ES95": es}


class Model:
    """Evaluates delivered costs for every exporter, mode and shock set."""

    def __init__(self, p: dict, ccfg: dict, wacc_ref, betas: dict, oman_port: str = "Duqm"):
        self.p, self.ccfg, self.betas = p, ccfg, betas
        self.c = {k: dict(v) for k, v in ccfg["countries"].items()}
        if oman_port == "Sohar":
            self.c["Oman"]["routes"] = ccfg["oman_sohar_variant"]["routes"]
        self.debt = float(ccfg["debt_share"])
        self.wacc = {k: country_wacc(v, wacc_ref, self.debt) for k, v in self.c.items()}
        self.yld = {k: v["pv_yield_kwh_per_kwp_yr"] * p["pv_yield_factor"] for k, v in self.c.items()}

    def cost(self, country: str, mode: str, w_dz, ap: dict) -> dict:
        wacc = self.wacc[country] + self.betas[country] * np.asarray(w_dz) / 100.0
        return cm.delivered_cost(self.p, wacc, self.yld[country], mode, ap, self.c[country]["routes"])

    def cost_fixed_wacc(self, country: str, mode: str, wacc, yld, ap: dict) -> dict:
        return cm.delivered_cost(self.p, wacc, yld, mode, ap, self.c[country]["routes"])


def units(country: str) -> list[str]:
    return ["pipeline", "ship"] if country == "Algeria" else ["ship"]


def shapley_two(f00, fw0, f0a, fwa):
    """Two-factor Shapley split of fwa - f00 into financing (w) and insurance (a)."""
    d_fin = 0.5 * ((fw0 - f00) + (fwa - f0a))
    d_ins = (fwa - f00) - d_fin
    return d_fin, d_ins


def run(n: int = 10_000, seed: int = 20251113, independent: bool = False, beta_rule: str | None = None,
        oman_port: str = "Duqm", algeria_beta: float = 1.0, keep_draws: bool = False) -> dict:
    rng = np.random.default_rng(seed)
    prod_cfg = load_production()
    scen_cfg = load_yaml("scenarios.yaml")
    ccfg = load_countries()
    p = sample_production(n, rng, prod_cfg)
    wr = ccfg["wacc_ref"]
    wacc_ref = rng.triangular(float(wr["low"]), float(wr["mode"]), float(wr["high"]), size=n)
    shocks = scenario_shocks(scen_cfg, n, rng, independent=independent)
    rule = beta_rule or ccfg.get("beta_rule", "spread_proportional")
    betas = country_betas(ccfg["countries"], rule, ccfg.get("beta_alternative"))
    betas["Algeria"] = float(algeria_beta)
    M = Model(p, ccfg, wacc_ref, betas, oman_port=oman_port)
    s0 = shocks["S0"]

    res = {"n": n, "seed": seed, "independent": independent, "beta_rule": rule, "oman_port": oman_port,
           "algeria_beta": float(algeria_beta),
           "betas": betas, "wacc": {k: tail_stats(v) for k, v in M.wacc.items()},
           "pv_yield": {k: float(np.mean(v)) for k, v in M.yld.items()},
           "costs": {}, "grp": {}, "delta": {}, "draws": {}}

    # Delivered cost, GRP and Shapley split for every exporter and mode -------
    for ctry in M.c:
        for mode in units(ctry):
            f00 = M.cost(ctry, mode, s0["w"], s0["ap"])
            res["draws"][(ctry, mode, "S0")] = f00["total"]
            for s, sh in shocks.items():
                fwa = M.cost(ctry, mode, sh["w"], sh["ap"])
                fw0 = M.cost(ctry, mode, sh["w"], s0["ap"])
                f0a = M.cost(ctry, mode, s0["w"], sh["ap"])
                grp = fwa["total"] - f00["total"]
                d_fin, d_ins = shapley_two(f00["total"], fw0["total"], f0a["total"], fwa["total"])
                res["draws"][(ctry, mode, s)] = fwa["total"]
                res["delta"][(ctry, mode, s)] = grp
                res["costs"][(ctry, mode, s)] = {
                    "total": tail_stats(fwa["total"]),
                    "components": {k: float(np.mean(v)) for k, v in fwa.items() if k != "route"},
                    "route_share": {r["name"]: float(np.mean(fwa["route"] == i))
                                    for i, r in enumerate(M.c[ctry]["routes"])} if mode == "ship" else {},
                }
                res["grp"][(ctry, mode, s)] = {
                    "grp": tail_stats(grp), "pct_of_S0_mean": float(grp.mean() / f00["total"].mean()),
                    "financing": float(d_fin.mean()), "insurance": float(d_ins.mean()),
                    "financing_share": float(d_fin.mean() / grp.mean()) if abs(grp.mean()) > 1e-12 else None,
                }

    # Competitor gaps, decomposition, security premium --------------------------
    res["gaps"] = {}
    dz = {m: {s: res["draws"][("Algeria", m, s)] for s in shocks} for m in ("pipeline", "ship")}
    dz_y = M.yld["Algeria"]
    dz_w = M.wacc["Algeria"]
    for ctry in M.c:
        if ctry == "Algeria":
            continue
        for ref in ("ship", "pipeline"):
            out = {}
            for s in shocks:
                gap = res["draws"][(ctry, "ship", s)] - dz[ref][s]          # > 0: Algeria cheaper
                d_gap = gap - (res["draws"][(ctry, "ship", "S0")] - dz[ref]["S0"])
                es_c = tail_stats(res["delta"][(ctry, "ship", s)])["ES95"]
                es_d = tail_stats(res["delta"][("Algeria", ref, s)])["ES95"]
                out[s] = {"gap": tail_stats(gap), "share_algeria_cheaper": float((gap > 0).mean()),
                          "change_vs_S0": tail_stats(d_gap),
                          "financing": res["grp"][(ctry, "ship", s)]["financing"] - res["grp"][("Algeria", ref, s)]["financing"],
                          "insurance_rerouting": res["grp"][(ctry, "ship", s)]["insurance"] - res["grp"][("Algeria", ref, s)]["insurance"],
                          "security_premium_ES95": es_c - es_d,
                          "security_premium_mean": float(res["delta"][(ctry, "ship", s)].mean() - res["delta"][("Algeria", ref, s)].mean())}
            # Baseline gap by channel (S0)
            fc = M.cost(ctry, "ship", s0["w"], s0["ap"])
            fd = M.cost("Algeria", ref, s0["w"], s0["ap"])
            prod_res = cm.lcoh_production(p, dz_w, M.yld[ctry]) - cm.lcoh_production(p, dz_w, dz_y)
            prod_wacc = fc["production"] - cm.lcoh_production(p, dz_w, M.yld[ctry])
            out["S0_components"] = {"resource": float(prod_res.mean()), "cost_of_capital": float(prod_wacc.mean()),
                                    "transport": float((fc["transport"] - fd["transport"]).mean()),
                                    "insurance": float((fc["insurance"] - fd["insurance"]).mean())}
            res["gaps"][(ctry, ref)] = out

    # Continuous gap curves and break-even GPR on the Hormuz path ---------------
    path = scen_cfg.get("hormuz_path", ["S0", "S1", "S2", "S3"])
    g_anchor = np.array([shocks[s]["gpr"] for s in path])
    grid = np.round(np.arange(0.0, g_anchor[-1] + 1e-9, 0.02), 4)
    W = np.vstack([shocks[s]["w"] for s in path])
    A = {a: np.vstack([shocks[s]["ap"][a] for s in path]) for a in AREAS}

    def interp(mat, g):
        k = int(np.clip(np.searchsorted(g_anchor, g, side="right") - 1, 0, len(g_anchor) - 2))
        t = (g - g_anchor[k]) / (g_anchor[k + 1] - g_anchor[k])
        return mat[k] + t * (mat[k + 1] - mat[k])

    curves = {}
    dz_curve = {m: [] for m in ("pipeline", "ship")}
    comp_curve = {c: [] for c in M.c if c != "Algeria"}
    for g in grid:
        w = interp(W, g)
        ap = {a: interp(A[a], g) for a in AREAS}
        for m in ("pipeline", "ship"):
            dz_curve[m].append(M.cost("Algeria", m, w, ap)["total"])
        for c in comp_curve:
            comp_curve[c].append(M.cost(c, "ship", w, ap)["total"])
    res["breakeven"] = {}
    for c, rows in comp_curve.items():
        Cc = np.vstack(rows)
        for ref in ("ship", "pipeline"):
            G = Cc - np.vstack(dz_curve[ref])                 # grid x draws
            be = np.full(n, np.nan)
            pos = G >= 0
            already = pos[0]
            be[already] = 0.0
            first = np.argmax(pos, axis=0)
            crossed = (~already) & pos.any(axis=0)
            be[crossed] = grid[first[crossed]]
            ok = ~np.isnan(be)
            # Loss of an existing Algerian advantage: first grid point where the gap turns negative
            neg = G < 0
            lose = already & neg.any(axis=0)
            bl = np.full(n, np.nan)
            bl[lose] = grid[np.argmax(neg, axis=0)[lose]]
            res["breakeven"][(c, ref)] = {
                "already_cheaper_share": float(already.mean()),
                "cross_within_S3_share": float(crossed.mean()),
                "never_share": float((~ok).mean()),
                "median_if_crossed": float(np.median(be[crossed])) if crossed.any() else None,
                "p05_if_crossed": float(np.quantile(be[crossed], 0.05)) if crossed.any() else None,
                "p95_if_crossed": float(np.quantile(be[crossed], 0.95)) if crossed.any() else None,
                "lose_within_S3_share": float(lose.mean()),
                "median_if_lost": float(np.median(bl[lose])) if lose.any() else None,
                "p05_if_lost": float(np.quantile(bl[lose], 0.05)) if lose.any() else None,
                "p95_if_lost": float(np.quantile(bl[lose], 0.95)) if lose.any() else None,
            }
            curves[(c, ref)] = {"grid": grid, "p05": np.quantile(G, 0.05, axis=1),
                                "p50": np.median(G, axis=1), "p95": np.quantile(G, 0.95, axis=1)}
    res["curves"] = curves
    res["shocks_summary"] = {s: {"gpr": sh["gpr"], "w": tail_stats(sh["w"]),
                                 "ap": {a: tail_stats(sh["ap"][a]) for a in AREAS}} for s, sh in shocks.items()}
    if keep_draws:
        res["_p"], res["_shocks"], res["_model"] = p, shocks, M
    return res
