"""Deterministic delivered-cost model (manuscript Section 3.2, Eqs. 1-6).

All costs are in constant 2023 USD per kg of hydrogen delivered in Europe.

    CRF(r, n)    = r (1+r)^n / ((1+r)^n - 1)
    Y_use        = Y_PV (1 - clip)                    PV output that reaches the electrolyser
    H            = Y_use / k                          electrolyser full-load hours
    LCOH_prod    = c_el (CRF(r, n_el) + om_el) SEC / H
                   + SEC (c_pv CRF(r, n_pv) + o_pv) / Y_use + w p_w            (Eq. 2)
    T_pipe       = t_pipe LHV / 1000 e
    S(d; P)      = V (CRF(r_s, n_s) + om_s) / (N_voy(d) Q) + 2 phi (d / 5000 km) P    (Eq. 3)
    F_i          = tau_10k - S(10,000 km; P_i(S0))    conversion, storage, reconversion
    T_NH3(s)     = F_i + S(d_q; P_i(s)) + kappa_q     q = cheapest route       (Eqs. 4-5)
    I_k(s)       = 2 V sum_a AP_a(s) / Q                                           (Eq. 6)
    C(s)         = LCOH_prod(r(s)) + T(s) + I(s) + K                               (Eq. 1)
    GRP(s)       = C(s) - C(S0)                       same parameter draw      (Eq. 8)

Changes in version 2.1.0 (see CHANGELOG.md):
* The PV electricity cost is divided by the usable yield Y_use (after the 3%
  clipping loss) instead of the gross yield, so that the electricity term and
  the electrolyser full-load hours use the same energy balance.
* The reference shipping cost that is subtracted from the IRENA 10,000 km
  chain cost is valued at the exporter's baseline (S0) production cost, so
  that the distance-independent conversion cost F_i does not move with the
  scenario WACC. It contains no canal toll and no war-risk insurance.
* Optional bounding variants: exposure of midstream capital to the exporter's
  WACC change (``midstream``) and a higher value of the cargo used as fuel
  (``fuel_adder``).
"""
from __future__ import annotations

import numpy as np

NM_TO_KM = 1.852


def crf(r, n):
    r = np.asarray(r, dtype=float)
    n = np.asarray(n, dtype=float)
    f = (1.0 + r) ** n
    return r * f / (f - 1.0)


def usable_yield(p: dict, pv_yield):
    """PV output delivered to the electrolyser, kWh per kWp and year (after clipping)."""
    return pv_yield * (1.0 - p["clipping_loss"])


def pv_lcoe(p: dict, wacc, pv_yield):
    """Cost of the electricity that reaches the electrolyser, USD/kWh.

    The annualised PV cost is divided by the usable yield: the 3% of output
    clipped by the smaller electrolyser is paid for but not used.
    """
    annual = p["pv_capex_usd_per_kw"] * crf(wacc, p["pv_lifetime_yr"]) + p["pv_fixed_om_usd_per_kw_yr"]
    return annual / usable_yield(p, pv_yield)


def full_load_hours(p: dict, pv_yield):
    return usable_yield(p, pv_yield) / p["el_to_pv_ratio"]


def lcoh_production(p: dict, wacc, pv_yield, detail: bool = False):
    """Plant-gate production cost, USD/kg (Eq. 2)."""
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
    """Pipeline transport, USD/kg."""
    return p["pipeline_transport_eur_per_mwh"] * p["lhv_kwh_per_kg"] / 1000.0 * p["eur_usd"]


def h2_cargo_kg(p: dict):
    """Hydrogen contained in one ammonia cargo, kg."""
    return p["cargo_m3"] * p["nh3_density_t_per_m3"] * 1000.0 * p["cargo_fill"] * p["h2_mass_fraction_nh3"]


def roundtrip_days(p: dict, nm):
    return 2.0 * nm / (p["ship_speed_kn"] * 24.0) + 2.0 * p["ship_port_days_per_call"]


def shipping_cost(p: dict, nm, cargo_value, canal: bool = False):
    """Distance-dependent shipping cost, USD/kg: vessel capital and O&M, fuel and
    boil-off taken from the cargo, and the canal tariff.

    Fuel and boil-off are a replacement cost at constant delivered payload Q:
    2 phi (d / 5000 km) of the cargo, valued at ``cargo_value`` (USD/kg H2).
    """
    voyages = p["ship_operating_days_yr"] / roundtrip_days(p, nm)
    annual = p["hull_value_usd"] * (crf(p["ship_wacc"], p["ship_life_yr"]) + p["ship_om_share"])
    vessel = annual / (voyages * h2_cargo_kg(p))
    fuel = 2.0 * p["ship_fuel_share_per_5000km"] * (nm * NM_TO_KM / 5000.0) * cargo_value
    tariff = p["canal_tariff_usd_per_kg"] if canal else 0.0
    return vessel + fuel + tariff


def nh3_fixed_cost(p: dict, cargo_value):
    """Distance-independent part of the ammonia chain (synthesis, storage, cracking), USD/kg.

    ``cargo_value`` must be the exporter's baseline (S0) production cost, so that
    this residual does not change with the scenario. The reference voyage has no
    canal toll and no war-risk insurance.
    """
    nm_10k = 10_000.0 / NM_TO_KM
    return p["nh3_chain_10k_usd_per_kg"] - shipping_cost(p, nm_10k, cargo_value, canal=False)


def insurance_cost(p: dict, ap_by_area: dict, areas):
    """War-risk additional premium converted to USD/kg (Eq. 6)."""
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


def midstream_factor(p: dict, wacc, wacc_base):
    """Multiplier on a midstream cost when its capital share is exposed to the
    exporter's WACC change (bounding variant; equals 1 in the baseline)."""
    n = p["midstream_life_yr"]
    return 1.0 + p["midstream_capital_share"] * (crf(wacc, n) / crf(wacc_base, n) - 1.0)


def delivered_cost(p: dict, wacc, pv_yield, mode: str, ap_by_area: dict, routes=None, wacc_base=None,
                   midstream: bool = False, fuel_adder: float = 0.0) -> dict:
    """Delivered cost and its components (Eq. 1).

    mode = "pipeline" or "ship". For "ship", the cheapest route in ``routes`` is
    chosen element-wise (rerouting), given the war-risk premiums.

    wacc_base  : the exporter's baseline (S0) WACC. It fixes the production cost
                 at which the 10,000 km reference voyage is valued (Eq. 4) and is
                 the reference for the midstream variant. Defaults to ``wacc``.
    midstream  : if True, the capital share of the pipeline tariff and of the
                 distance-independent ammonia cost moves with the exporter's WACC.
    fuel_adder : USD/kg added to the production cost when valuing the cargo used
                 as fuel (ammonia is worth more than the hydrogen it contains).
    """
    if wacc_base is None:
        wacc_base = wacc
    prod = lcoh_production(p, wacc, pv_yield)
    prod_base = lcoh_production(p, wacc_base, pv_yield)
    zero = 0.0 * prod
    mid = midstream_factor(p, wacc, wacc_base) if midstream else 1.0
    if mode == "pipeline":
        transport = transport_pipeline(p) * mid + zero
        ins = zero
        route_idx = zero
    elif mode == "ship":
        fixed = nh3_fixed_cost(p, prod_base + fuel_adder) * mid
        best = None
        for k, r in enumerate(routes):
            ship, ins_r = route_cost(p, r, ap_by_area, prod + fuel_adder)
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
