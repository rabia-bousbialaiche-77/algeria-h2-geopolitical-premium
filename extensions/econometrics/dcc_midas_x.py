"""Bivariate DCC-MIDAS-X (Colacito, Engle & Ghysels, 2011; Hu & Borjigin, 2024).

Two-step quasi-maximum likelihood:

Step 1 - univariate GARCH(1,1) for each high-frequency return series i:
    r_{i,t} = mu_i + e_{i,t},   sigma2_{i,t} = w_i + alpha_i e2_{i,t-1} + beta_i sigma2_{i,t-1}
    xi_{i,t} = e_{i,t} / sigma_{i,t}

Step 2 - dynamic correlation with a MIDAS long-run component driven by
low-frequency exogenous variables X (e.g. monthly GPR, EPU, CRI):
    z_tau     = m + sum_j theta_j sum_{k=1..K} phi_k(w1, w2) X_{j,tau-k}          (manuscript Eq. 4)
    rhobar_tau = (exp(2 z_tau) - 1) / (exp(2 z_tau) + 1) = tanh(z_tau)            (manuscript Eq. 3)
    q_{ij,t}  = rhobar_{ij,tau(t)} (1-a-b) + a xi_{i,t-1} xi_{j,t-1} + b q_{ij,t-1}
    q_{ii,t}  = (1-a-b) + a xi_{i,t-1}^2 + b q_{ii,t-1}
    rho_t     = q_{12,t} / sqrt(q_{11,t} q_{22,t})
    logL      = -1/2 sum_t [ log(1-rho_t^2) + (xi1^2 + xi2^2 - 2 rho xi1 xi2)/(1-rho^2) - (xi1^2 + xi2^2) ]

phi_k is the normalised Beta lag polynomial; w1 = 1 gives the usual
monotonically decaying restriction. Standard errors come from the inverse of a
numerical Hessian (non-robust); bootstrap or sandwich corrections are left to
the user and documented in the Supplementary Material.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize


# ----------------------------------------------------------------------------- GARCH
def _garch_filter(e: np.ndarray, w: float, a: float, b: float) -> np.ndarray:
    s2 = np.empty_like(e)
    s2[0] = e.var()
    for t in range(1, len(e)):
        s2[t] = w + a * e[t - 1] ** 2 + b * s2[t - 1]
    return s2


def fit_garch11(r: np.ndarray) -> dict:
    """Gaussian QML GARCH(1,1) with constant mean."""
    r = np.asarray(r, float)
    v = r.var()

    def unpack(x):
        mu = x[0]
        w = np.exp(x[1])
        a = 1 / (1 + np.exp(-x[2]))
        b = (1 - a) / (1 + np.exp(-x[3]))
        return mu, w, a, b

    def nll(x):
        mu, w, a, b = unpack(x)
        e = r - mu
        s2 = _garch_filter(e, w, a, b)
        return 0.5 * np.sum(np.log(2 * np.pi * s2) + e ** 2 / s2)

    x0 = np.array([r.mean(), np.log(0.05 * v), -2.5, 2.5])
    res = minimize(nll, x0, method="Nelder-Mead", options={"maxiter": 4000, "xatol": 1e-7, "fatol": 1e-7})
    mu, w, a, b = unpack(res.x)
    e = r - mu
    s2 = _garch_filter(e, w, a, b)
    return {"mu": mu, "omega": w, "alpha": a, "beta": b, "xi": e / np.sqrt(s2), "sigma2": s2,
            "loglik": -res.fun, "converged": bool(res.success)}


# ----------------------------------------------------------------------------- MIDAS weights
def beta_weights(K: int, w1: float, w2: float) -> np.ndarray:
    k = np.arange(1, K + 1) / (K + 1)
    phi = k ** (w1 - 1) * (1 - k) ** (w2 - 1)
    return phi / phi.sum()


def midas_lags(X: np.ndarray, K: int) -> np.ndarray:
    """Array L[tau, j, k] = X[tau-k, j] for k = 1..K (NaN where unavailable)."""
    X = np.atleast_2d(np.asarray(X, float))
    if X.shape[0] < X.shape[1]:
        X = X.T
    T, J = X.shape
    L = np.full((T, J, K), np.nan)
    for k in range(1, K + 1):
        L[k:, :, k - 1] = X[:-k, :]
    return L


# ----------------------------------------------------------------------------- DCC-MIDAS-X
@dataclass
class DCCMidasXResult:
    a: float
    b: float
    m: float
    theta: np.ndarray
    w1: float
    w2: float
    loglik: float
    se: dict
    rho: np.ndarray
    rhobar: np.ndarray
    converged: bool


def _corr_path(xi1, xi2, tau_idx, L, params, K, fix_w1):
    a, b, m = params[0], params[1], params[2]
    J = L.shape[1]
    theta = params[3:3 + J]
    w1 = 1.0 if fix_w1 else params[3 + J]
    w2 = params[-1]
    phi = beta_weights(K, w1, w2)
    z = m + np.einsum("tjk,k,j->t", np.nan_to_num(L), phi, theta)
    rhobar_tau = np.tanh(z)
    rb = rhobar_tau[tau_idx]
    T = len(xi1)
    q11 = np.ones(T); q22 = np.ones(T); q12 = np.empty(T)
    q12[0] = rb[0]
    c = 1 - a - b
    for t in range(1, T):
        q11[t] = c + a * xi1[t - 1] ** 2 + b * q11[t - 1]
        q22[t] = c + a * xi2[t - 1] ** 2 + b * q22[t - 1]
        q12[t] = rb[t] * c + a * xi1[t - 1] * xi2[t - 1] + b * q12[t - 1]
    rho = np.clip(q12 / np.sqrt(q11 * q22), -0.999, 0.999)
    return rho, rhobar_tau


def _corr_nll(rho, xi1, xi2, valid):
    r = rho[valid]; x1 = xi1[valid]; x2 = xi2[valid]
    one = 1 - r ** 2
    return 0.5 * np.sum(np.log(one) + (x1 ** 2 + x2 ** 2 - 2 * r * x1 * x2) / one - (x1 ** 2 + x2 ** 2))


def fit_dcc_midas_x(r1, r2, tau_idx, X, K: int = 12, fix_w1: bool = True) -> DCCMidasXResult:
    """Two-step QML estimation.

    r1, r2  : high-frequency returns (length T)
    tau_idx : integer array (length T) mapping each observation to its
              low-frequency period (0..L-1)
    X       : low-frequency regressors, shape (L, J)
    """
    g1, g2 = fit_garch11(r1), fit_garch11(r2)
    xi1, xi2 = g1["xi"], g2["xi"]
    tau_idx = np.asarray(tau_idx, int)
    L = midas_lags(X, K)
    J = L.shape[1]
    valid = tau_idx >= K                      # drop periods without a full lag window

    def unpack(x):
        a = 1 / (1 + np.exp(-x[0]))
        b = (1 - a) / (1 + np.exp(-x[1]))
        m = x[2]
        th = x[3:3 + J]
        rest = [] if fix_w1 else [1 + np.exp(x[3 + J])]
        w2 = 1 + np.exp(x[-1])
        return np.r_[a, b, m, th, rest, w2]

    def obj(x):
        pr = unpack(x)
        rho, _ = _corr_path(xi1, xi2, tau_idx, L, pr, K, fix_w1)
        v = _corr_nll(rho, xi1, xi2, valid)
        return v if np.isfinite(v) else 1e10

    x0 = np.r_[-3.0, 2.0, 0.0, np.zeros(J), ([] if fix_w1 else [0.0]), 1.0]
    res = minimize(obj, x0, method="Nelder-Mead", options={"maxiter": 20000, "xatol": 1e-6, "fatol": 1e-6})
    res = minimize(obj, res.x, method="BFGS")
    pr = unpack(res.x)
    rho, rbar = _corr_path(xi1, xi2, tau_idx, L, pr, K, fix_w1)

    # numerical Hessian on the natural parameters
    names = ["a", "b", "m"] + [f"theta_{j}" for j in range(J)] + ([] if fix_w1 else ["w1"]) + ["w2"]

    def obj_nat(p):
        if p[0] <= 0 or p[1] <= 0 or p[0] + p[1] >= 1 or p[-1] <= 1:
            return 1e10
        rh, _ = _corr_path(xi1, xi2, tau_idx, L, p, K, fix_w1)
        return _corr_nll(rh, xi1, xi2, valid)

    h = 1e-4 * np.maximum(1.0, np.abs(pr))
    n = len(pr)
    H = np.zeros((n, n))
    f0 = obj_nat(pr)
    for i in range(n):
        for j in range(i, n):
            ei = np.zeros(n); ej = np.zeros(n); ei[i] = h[i]; ej[j] = h[j]
            H[i, j] = H[j, i] = (obj_nat(pr + ei + ej) - obj_nat(pr + ei - ej)
                                 - obj_nat(pr - ei + ej) + obj_nat(pr - ei - ej)) / (4 * h[i] * h[j])
    try:
        se_vec = np.sqrt(np.diag(np.linalg.inv(H)))
    except np.linalg.LinAlgError:
        se_vec = np.full(n, np.nan)
    se = dict(zip(names, se_vec))
    return DCCMidasXResult(a=pr[0], b=pr[1], m=pr[2], theta=pr[3:3 + J],
                           w1=1.0 if fix_w1 else pr[3 + J], w2=pr[-1], loglik=-f0, se=se,
                           rho=rho, rhobar=rbar, converged=bool(res.success or np.isfinite(f0)))


def simulate(T_low: int = 120, n_per: int = 21, K: int = 12, a: float = 0.04, b: float = 0.90,
             m: float = 0.2, theta: float = 0.5, w2: float = 4.0, seed: int = 0):
    """Simulate data from the model (used by the unit tests)."""
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(T_low, 1)).cumsum(axis=0) * 0.1
    X = (X - X.mean()) / X.std()
    tau = np.repeat(np.arange(T_low), n_per)
    T = len(tau)
    L = midas_lags(X, K)
    phi = beta_weights(K, 1.0, w2)
    z = m + theta * np.einsum("tjk,k->t", np.nan_to_num(L), phi)
    rb = np.tanh(z)[tau]
    xi = np.zeros((T, 2)); q11 = q22 = 1.0; q12 = rb[0]
    for t in range(T):
        if t:
            q11 = (1 - a - b) + a * xi[t - 1, 0] ** 2 + b * q11
            q22 = (1 - a - b) + a * xi[t - 1, 1] ** 2 + b * q22
            q12 = rb[t] * (1 - a - b) + a * xi[t - 1, 0] * xi[t - 1, 1] + b * q12
        rho = q12 / np.sqrt(q11 * q22)
        C = np.array([[1, rho], [rho, 1]])
        xi[t] = rng.multivariate_normal([0, 0], C)
    return xi[:, 0], xi[:, 1], tau, X
