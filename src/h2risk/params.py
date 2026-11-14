"""Loading and sampling of model parameters.

All numerical inputs live in ``params/*.yaml`` / ``params/*.csv`` so that every
value can be traced to a source (see the ``source`` and ``basis`` fields).
"""
from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[2]
PARAM_DIR = ROOT / "params"


def load_yaml(name: str) -> dict:
    with open(PARAM_DIR / name, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_countries() -> dict:
    """Route-explicit exporter definitions (countries.yaml)."""
    return load_yaml("countries.yaml")


def load_competitors() -> list[dict]:
    with open(PARAM_DIR / "competitors.csv", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        for k in ("s0_gap_low", "s0_gap_mode", "s0_gap_high", "wacc_beta", "listed_periods"):
            r[k] = float(r[k])
    return rows


def params_hash() -> str:
    """SHA-256 of all parameter files, written to the run log."""
    h = hashlib.sha256()
    for p in sorted(PARAM_DIR.glob("*")):
        h.update(p.name.encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def draw(spec: dict, n: int, rng: np.random.Generator) -> np.ndarray:
    """Draw ``n`` values from a parameter specification."""
    dist = spec.get("dist", "fixed")
    if dist == "fixed":
        return np.full(n, float(spec["value"]))
    if dist == "triangular":
        lo, mo, hi = float(spec["low"]), float(spec["mode"]), float(spec["high"])
        if lo == hi:
            return np.full(n, lo)
        return rng.triangular(lo, mo, hi, size=n)
    if dist == "uniform":
        return rng.uniform(float(spec["low"]), float(spec["high"]), size=n)
    raise ValueError(f"unknown distribution: {dist}")


def central(spec: dict) -> float:
    """Central (mode/fixed) value of a specification."""
    dist = spec.get("dist", "fixed")
    if dist == "fixed":
        return float(spec["value"])
    if dist == "triangular":
        return float(spec["mode"])
    if dist == "uniform":
        return 0.5 * (float(spec["low"]) + float(spec["high"]))
    raise ValueError(dist)


PRODUCTION_FILE = "production.yaml"


def set_production_file(name: str) -> None:
    """Select the production parameter file (e.g. production_2030.yaml)."""
    global PRODUCTION_FILE
    PRODUCTION_FILE = name


def load_production() -> dict:
    return load_yaml(PRODUCTION_FILE)


def sample_production(n: int, rng: np.random.Generator, prod: dict | None = None) -> dict:
    """Independent draws for every production/transport parameter."""
    prod = prod or load_production()
    return {k: draw(v, n, rng) for k, v in prod.items()}


def central_production(prod: dict | None = None) -> dict:
    prod = prod or load_production()
    return {k: np.array([central(v)]) for k, v in prod.items()}
