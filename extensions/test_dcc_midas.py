import numpy as np

from econometrics.dcc_midas_x import beta_weights, fit_dcc_midas_x, simulate


def test_beta_weights_sum_to_one_and_decay():
    w = beta_weights(12, 1.0, 4.0)
    assert np.isclose(w.sum(), 1.0)
    assert np.all(np.diff(w) < 0)


def test_parameter_recovery_on_simulated_data():
    x1, x2, tau, X = simulate(T_low=100, n_per=21, theta=0.5, seed=1)
    res = fit_dcc_midas_x(x1, x2, tau, X, K=12)
    assert res.a + res.b < 1
    assert abs(res.theta[0] - 0.5) < 0.25
    assert np.all(np.abs(res.rho) < 1)
