"""Deterministic delivered-cost model (manuscript Section 3.2, Eqs. 1-4).

All costs are in constant 2023 USD per kg of hydrogen delivered in Europe.

(1)  CRF(r, n)        = r (1+r)^n / ((1+r)^n - 1)
(2)  LCOE_PV          = (CAPEX_PV CRF(r, n_PV) + OM_PV) / Y_PV
(3)  FLH              = Y_PV (1 - clip) / k
(4)  LCOH_prod        = CAPEX_el (CRF(r, n_el) + om_el) SEC / FLH + SEC LCOE_PV + w c_desal
(5)  T_pipe           = tau_pipe LHV / 1000 fx
(6)  T_ship(d)        = [V (CRF(r_s, n_s) + om_s)] / (N_voy(d) M_H2) + 2 phi (d/5000) LCOH_prod + tariff
(7)  T_NH3(d)         = (C_10k - T_ship(10,000 km)) + T_ship(d)       conversion + shipping + reconversion
(8)  I(s)             = sum_areas AP_a(s) x n_transits x V / M_H2       war-risk insurance
(9)  C(s)             = LCOH_prod(r + dr(s)) + T + I(s) + C_carbon      delivered cost
     GRP(s)           = C(s) - C(S0)                                    same parameter draw, so GRP(S0) = 0
"""
from __future__ import annotations

import numpy as np

NM_TO_KM = 1.852


def crf(r, n):
    r = np.asarray(r, dtype=float)
    n = np.asarray(n, dtype=float)
    f = (1.0 + r) ** n
    return r * f / (f - 1.0)


def pv_lcoe(p: dict, wacc, pv_yield):
    annual = p["pv_capex_usd_per_kw"] * crf(wacc, p["pv_lifetime_yr"]) + p["pv_fixed_om_usd_per_kw_yr"]
    return annual / pv_yield


def full_load_hours(p: dict, pv_yield):
    return pv_yield * (1.0 - p["clipping_loss"]) / p["el_to_pv_ratio"]


def lcoh_production(p: dict, wacc, pv_yield, detail: bool = False):
    """Plant-gate production cost, USD/kg (Eq. 4)."""
    flh = full_load_hours(p, pv_yield)
    kg_per_kw_yr = flh / p["el_sec_kwh_per_kg"]
    capex_term = p["el_capex_usd_per_kw"] * (crf(wacc, p["el_lifetime_yr"]) + p["el_fixed_om_share"]) / kg_per_kw_yr
    elec_term = p["el_sec_kwh_per_kg"] * pv_lcoe(p, wacc, pv_yield)
    water_term = p["water_m3_per_kg"] * p["desal_cost_usd_per_m3"]
    total = capex_term + elec_term + water_term
    if detail:
        return total, {"electrolyser": capex_term, "electricity": elec_term, "water": water_term}
    return total


def transport_pipeline(p: dict):
    """Pipeline transport, USD/kg (Eq. 5)."""
    return p["pipeline_transport_eur_per_mwh"] * p["lhv_kwh_per_kg"] / 1000.0 * p["eur_usd"]


def h2_cargo_kg(p: dict):
    """Hydrogen contained in one ammonia cargo, kg."""
    return p["cargo_m3"] * p["nh3_density_t_per_m3"] * 1000.0 * p["cargo_fill"] * p["h2_mass_fraction_nh3"]


def roundtrip_days(p: dict, nm):
    return 2.0 * nm / (p["ship_speed_kn"] * 24.0) + 2.0 * p["ship_port_days_per_call"]


def shipping_cost(p: dict, nm, cargo_value, canal: bool = False):
    """Distance-dependent shipping cost, USD/kg (Eq. 6): vessel capital and O&M,
    fuel taken from the cargo, and the canal tariff."""
    voyages = p["ship_operating_days_yr"] / roundtrip_days(p, nm)
    annual = p["hull_value_usd"] * (crf(p["ship_wacc"], p["ship_life_yr"]) + p["ship_om_share"])
    vessel = annual / (voyages * h2_cargo_kg(p))
    fuel = 2.0 * p["ship_fuel_share_per_5000km"] * (nm * NM_TO_KM / 5000.0) * cargo_value
    tariff = p["canal_tariff_usd_per_kg"] if canal else 0.0
    return vessel + fuel + tariff


def nh3_fixed_cost(p: dict, cargo_value):
    """Distance-independent part of the ammonia chain (synthesis, storage, cracking), USD/kg."""
    nm_10k = 10_000.0 / NM_TO_KM
    return p["nh3_chain_10k_usd_per_kg"] - shipping_cost(p, nm_10k, cargo_value, canal=False)


def insurance_cost(p: dict, ap_by_area: dict, areas):
    """War-risk additional premium converted to USD/kg (Eq. 8)."""
    total = 0.0
    for a in areas:
        total = total + ap_by_area[a] * p["listed_transits_per_roundtrip"] * p["hull_value_usd"] / h2_cargo_kg(p)
    return total


def carbon_cost(p: dict):
    return p["embedded_emissions_kgco2_per_kg"] * p["ets_price_eur_per_t"] * p["eur_usd"] / 1000.0


def route_cost(p: dict, route: dict, ap_by_area: dict, cargo_value):
    """Shipping, tariff and insurance on one route, USD/kg."""
    ship = shipping_cost(p, route["nm"], cargo_value, canal=route.get("canal", "none") != "none")
    ins = insurance_cost(p, ap_by_area, route.get("areas", []))
    return ship, ins


def delivered_cost(p: dict, wacc, pv_yield, mode: str, ap_by_area: dict, routes=None) -> dict:
    """Delivered cost and its components (Eq. 9).

    mode = "pipeline" or "ship". For "ship", the cheapest route in ``routes`` is
    chosen element-wise (rerouting), given the war-risk premiums.
    """
    prod = lcoh_production(p, wacc, pv_yield)
    zero = 0.0 * prod
    if mode == "pipeline":
        transport = transport_pipeline(p) + zero
        ins = zero
        route_idx = zero
    elif mode == "ship":
        fixed = nh3_fixed_cost(p, prod)
        best = None
        for k, r in enumerate(routes):
            ship, ins_r = route_cost(p, r, ap_by_area, prod)
            tot = ship + ins_r + zero
            if best is None:
                best = (tot, ship + zero, ins_r + zero, np.full_like(prod, k))
            else:
                better = tot < best[0]
                best = (np.where(better, tot, best[0]), np.where(better, ship, best[1]),
                        np.where(better, ins_r, best[2]), np.where(better, k, best[3]))
        transport = fixed + best[1]
        ins = best[2]
        route_idx = best[3]
    else:
        raise ValueError(mode)
    carb = carbon_cost(p) + zero
    total = prod + transport + ins + carb
    return {"total": total, "production": prod, "transport": transport, "insurance": ins,
            "carbon": carb, "route": route_idx}
