"""Bottom-up delivered cost of Algerian green hydrogen (Supplementary Section S3).

Equations (numbering follows the Supplementary Material):

(S1)  CRF(r, n)      = r (1+r)^n / ((1+r)^n - 1)
(S2)  LCOE_PV        = (CAPEX_PV * CRF(r, n_PV) + OM_PV) / Y_PV
(S3)  FLH_el         = Y_PV (1 - clip) / k
(S4)  LCOH_prod      = (CAPEX_el (CRF(r, n_el) + om_el)) * SEC / FLH_el
                       + SEC * LCOE_PV + w * c_desal
(S5)  T_pipe         = tau_pipe[EUR/MWh] * LHV/1000 * fx
(S6)  T_ship         = tau_ship[EUR/kg] * fx
(S7)  I_route        = AP * (periods + spillover) * V_hull / M_H2,cargo
(S8)  C_carbon       = e_emb * P_ETS * fx / 1000
(S9)  LCOH_exp,route = LCOH_prod + T_route + I_route + C_carbon
(S10) GRP_s          = LCOH_exp(s) - LCOH_exp(S0)   (same parameter draw)

All costs are in USD per kg H2 (2023 prices).
"""
from __future__ import annotations

import numpy as np


def crf(r: np.ndarray, n: np.ndarray) -> np.ndarray:
    """Capital recovery factor (S1)."""
    r = np.asarray(r, dtype=float)
    n = np.asarray(n, dtype=float)
    f = (1.0 + r) ** n
    return r * f / (f - 1.0)


def pv_lcoe(p: dict, wacc: np.ndarray) -> np.ndarray:
    """Levelised cost of PV electricity, USD/kWh (S2)."""
    annual = p["pv_capex_usd_per_kw"] * crf(wacc, p["pv_lifetime_yr"]) + p["pv_fixed_om_usd_per_kw_yr"]
    return annual / p["pv_yield_kwh_per_kwp_yr"]


def full_load_hours(p: dict) -> np.ndarray:
    """Electrolyser full-load hours (S3)."""
    return p["pv_yield_kwh_per_kwp_yr"] * (1.0 - p["clipping_loss"]) / p["el_to_pv_ratio"]


def lcoh_production(p: dict, wacc: np.ndarray, detail: bool = False):
    """Production cost of hydrogen at the plant gate, USD/kg (S4)."""
    flh = full_load_hours(p)
    kg_per_kw_yr = flh / p["el_sec_kwh_per_kg"]
    capex_term = p["el_capex_usd_per_kw"] * (crf(wacc, p["el_lifetime_yr"]) + p["el_fixed_om_share"]) / kg_per_kw_yr
    elec_term = p["el_sec_kwh_per_kg"] * pv_lcoe(p, wacc)
    water_term = p["water_m3_per_kg"] * p["desal_cost_usd_per_m3"]
    total = capex_term + elec_term + water_term
    if detail:
        return total, {"electrolyser": capex_term, "electricity": elec_term, "water": water_term}
    return total


def transport_pipeline(p: dict) -> np.ndarray:
    """Pipeline transport, USD/kg (S5)."""
    return p["pipeline_transport_eur_per_mwh"] * p["lhv_kwh_per_kg"] / 1000.0 * p["eur_usd"]


def transport_ship(p: dict) -> np.ndarray:
    """Ammonia chain (synthesis, shipping, cracking), USD/kg (S6)."""
    return p["ship_chain_eur_per_kg"] * p["eur_usd"]


def h2_cargo_kg(p: dict) -> np.ndarray:
    """Hydrogen-equivalent cargo of one ammonia voyage, kg."""
    return p["cargo_m3"] * p["nh3_density_t_per_m3"] * 1000.0 * p["cargo_fill"] * p["h2_mass_fraction_nh3"]


def war_risk_cost(p: dict, ap_rate: np.ndarray, periods: float, spillover: float) -> np.ndarray:
    """War-risk insurance converted to USD/kg H2 (S7)."""
    exposure = periods + spillover
    return ap_rate * exposure * p["hull_value_usd"] / h2_cargo_kg(p)


def carbon_cost(p: dict) -> np.ndarray:
    """Carbon term, USD/kg (S8)."""
    return p["embedded_emissions_kgco2_per_kg"] * p["ets_price_eur_per_t"] * p["eur_usd"] / 1000.0


def delivered_cost(p: dict, route: str, wacc_uplift_pp: np.ndarray, ap_rate: np.ndarray,
                   periods: float = 0.0, spillover: float = 0.0) -> dict:
    """Delivered export cost by route (S9), returned with its components."""
    wacc = p["wacc_base"] + np.asarray(wacc_uplift_pp) / 100.0
    prod = lcoh_production(p, wacc)
    if route == "pipeline":
        transport = transport_pipeline(p)
    elif route == "ship":
        transport = transport_ship(p)
    else:
        raise ValueError(route)
    ins = war_risk_cost(p, ap_rate, periods, spillover) if route == "ship" else np.zeros_like(prod)
    carb = carbon_cost(p)
    total = prod + transport + ins + carb
    return {"total": total, "production": prod, "transport": transport + 0 * prod,
            "insurance": ins, "carbon": carb + 0 * prod}
