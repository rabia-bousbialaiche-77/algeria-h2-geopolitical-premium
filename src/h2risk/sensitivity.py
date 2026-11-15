"""Variance-based global sensitivity analysis (Sobol indices; manuscript Section 3.7).

The D = 13 inputs are the eleven triangular parameters (PV capital cost, PV
fixed O&M, PV yield factor, electrolyser capital cost, electrolyser SEC,
desalination cost, pipeline transport cost, 10,000 km ammonia chain cost, ship
speed, hull value and the reference WACC) and two scenario quantiles: u_w for
the WACC uplift and u_a for the war-risk premium (one quantile for both listed
areas). First-order (S1) and total (ST) indices are estimated with the
Saltelli/Jansen estimators in SALib (Herman and Usher, 2017; Saltelli et al.,
2010), which needs N (D + 2) model evaluations.

Three states are reported for every input and output:
* ``active``: changing the input changes the output in the design;
* ``structurally inactive``: the input does not enter the equations of that
  output (for example the WACC uplift in the S0 cost, or shipping parameters
  in the pipeline cost);
* ``no effect on the sampled support``: the input enters the equations but
  never changes the output over the range sampled (for example the war-risk
  premium in the S3 Oman-Algeria gap: every S3 premium is above the level at
  which Oman reroutes around the Cape, so the premium is never paid).
"""
from __future__ import annotations

import numpy as np
from SALib.analyze import sobol
from SALib.sample import sobol as sobol_sample

from . import cost_model as cm
from .params import central, load_countries, load_production, load_yaml
from .simulation import AREAS, Model, _ppf, _tri_ppf, country_betas

LABELS = {
    "wacc_ref": "Reference WACC", "pv_yield_factor": "PV yield", "pv_capex_usd_per_kw": "PV CAPEX",
    "pv_fixed_om_usd_per_kw_yr": "PV O&M", "el_capex_usd_per_kw": "Electrolyser CAPEX",
    "el_sec_kwh_per_kg": "Electrolyser SEC", "desal_cost_usd_per_m3": "Desalination cost",
    "pipeline_transport_eur_per_mwh": "Pipeline tariff", "nh3_chain_10k_usd_per_kg": "NH3 chain cost",
    "ship_speed_kn": "Ship speed", "hull_value_usd": "Hull value", "u_w": "Scenario WACC uplift",
    "u_a": "Scenario war-risk premium",
}


SHIP_INPUTS = {"nh3_chain_10k_usd_per_kg", "ship_speed_kn", "hull_value_usd", "u_a"}
ADDITIVE = {"pipeline_transport_eur_per_mwh", "desal_cost_usd_per_m3", "pv_fixed_om_usd_per_kw_yr"}
# Inputs that do not enter the equations of each output, or cancel exactly in it
# (keyed by the start of the output name). Additive cost items that do not depend
# on the WACC cancel in a GRP; the chain cost and the water cost cancel in the gap
# between two ammonia suppliers.
STRUCTURALLY_INACTIVE = {
    "Algeria pipeline, S0": SHIP_INPUTS | {"u_w"},
    "Algeria pipeline, GRP": SHIP_INPUTS | ADDITIVE,
    "Oman minus Algeria (ammonia)": {"pipeline_transport_eur_per_mwh", "nh3_chain_10k_usd_per_kg", "desal_cost_usd_per_m3"},
}


def _status(output: str, name: str, changed: bool) -> str:
    if changed:
        return "active"
    for prefix, names in STRUCTURALLY_INACTIVE.items():
        if output.startswith(prefix) and name in names:
            return "structurally inactive"
    return "no effect on the sampled support"


def _problem(prod: dict, ccfg: dict) -> tuple[dict, list]:
    names, bounds, specs = [], [], []
    for k, v in prod.items():
        if v.get("dist") == "triangular":
            names.append(k); bounds.append([0.0, 1.0]); specs.append(v)
    names.append("wacc_ref"); bounds.append([0.0, 1.0]); specs.append(dict(ccfg["wacc_ref"]))
    for k in ("u_w", "u_a"):
        names.append(k); bounds.append([0.0, 1.0]); specs.append(None)
    return {"num_vars": len(names), "names": names, "bounds": bounds}, specs


def outputs(X: np.ndarray, names: list, specs: list, prod: dict, ccfg: dict, scen: dict, scenario: str = "S3",
            oman_port: str = "Duqm") -> dict:
    n = X.shape[0]
    p = {k: np.full(n, central(v)) for k, v in prod.items()}
    wacc_ref = None
    uw = ua = None
    for j, (nm, sp) in enumerate(zip(names, specs)):
        u = X[:, j]
        if nm == "u_w":
            uw = u
        elif nm == "u_a":
            ua = u
        elif nm == "wacc_ref":
            wacc_ref = _tri_ppf(u, float(sp["low"]), float(sp["mode"]), float(sp["high"]))
        else:
            p[nm] = _tri_ppf(u, float(sp["low"]), float(sp["mode"]), float(sp["high"]))
    betas = country_betas(ccfg["countries"], ccfg.get("beta_rule", "spread_proportional"), ccfg.get("beta_alternative"))
    M = Model(p, ccfg, wacc_ref, betas, oman_port=oman_port)
    spread = float(scen.get("wacc_uplift_spread", 0.0))
    s = scen["scenarios"][scenario]
    m = float(s["wacc_uplift_pp"]) if not isinstance(s["wacc_uplift_pp"], dict) else None
    w = _tri_ppf(uw, m * (1 - spread), m, m * (1 + spread)) if m is not None else _ppf(s["wacc_uplift_pp"], uw)
    ap = {a: _ppf(s["war_risk"][a], ua) for a in AREAS}
    s0 = scen["scenarios"]["S0"]
    ap0 = {a: _ppf(s0["war_risk"][a], ua) for a in AREAS}
    w0 = np.zeros(n)
    out = {}
    c_pipe0 = M.cost("Algeria", "pipeline", w0, ap0)["total"]
    out["Algeria pipeline, S0 delivered cost"] = c_pipe0
    out[f"Algeria pipeline, GRP {scenario}"] = M.cost("Algeria", "pipeline", w, ap)["total"] - c_pipe0
    out[f"Oman minus Algeria (ammonia), gap {scenario}"] = (M.cost("Oman", "ship", w, ap)["total"]
                                                          - M.cost("Algeria", "ship", w, ap)["total"])
    return out


def run_sobol(n_base: int = 2048, seed: int = 20251113, scenario: str = "S3") -> dict:
    prod = load_production()
    ccfg = load_countries()
    scen = load_yaml("scenarios.yaml")
    problem, specs = _problem(prod, ccfg)
    X = sobol_sample.sample(problem, n_base, calc_second_order=False, seed=seed)
    Y = outputs(X, problem["names"], specs, prod, ccfg, scen, scenario)
    res = {}
    for key, y in Y.items():
        si = sobol.analyze(problem, y, calc_second_order=False, seed=seed)
        D = problem["num_vars"]
        A = y[0::D + 2]
        res[key] = {}
        for i, nm in enumerate(problem["names"]):
            AB = y[1 + i::D + 2]                           # rows where only input i differs from A
            res[key][nm] = {"S1": float(si["S1"][i]), "S1_conf": float(si["S1_conf"][i]),
                            "ST": float(si["ST"][i]), "ST_conf": float(si["ST_conf"][i]),
                            "status": _status(key, nm, bool(np.any(np.abs(A - AB) > 1e-9)))}
    return {"n_base": n_base, "n_eval": int(X.shape[0]), "scenario": scenario, "n_inputs": problem["num_vars"],
            "inputs": problem["names"], "indices": res}
