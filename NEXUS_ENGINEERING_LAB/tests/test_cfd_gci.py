import math

import pytest

from modules.cfd_gci import gci3


def test_gci_recovers_known_second_order():
    f_exact, C, p = 1.0, 0.8, 2.0
    h = (0.1, 0.2, 0.4)
    f = tuple(f_exact + C * x ** p for x in h)
    r = gci3(h, f)
    assert r["aplicavel"] and abs(r["ordem_aparente"] - 2.0) < 1e-6 and abs(r["valor_extrapolado"] - 1.0) < 1e-6
    assert r["gci_fino"] > 0


def test_gci_nonuniform_ratio():
    f = tuple(2.0 + 0.5 * x ** 1.5 for x in (0.1, 0.17, 0.33))
    r = gci3((0.1, 0.17, 0.33), f)
    assert r["aplicavel"] and abs(r["ordem_aparente"] - 1.5) < 1e-6 and abs(r["valor_extrapolado"] - 2.0) < 1e-6


def test_gci_refuses_oscillatory_sequence_like_sphere_study():
    r = gci3((1.0, 1.5, 2.25), (0.507, 0.544, 0.461))        # fina, média, grossa do estudo anterior
    assert not r["aplicavel"] and "NÃO monotônica" in r["motivo"]


def test_gci_input_validation_and_zero_diff():
    with pytest.raises(ValueError):
        gci3((2, 1, 3), (1, 2, 3))
    assert not gci3((1, 2, 4), (1.0, 1.0, 1.2))["aplicavel"]


def _log(vals_p, vals_u=None):
    vals_u = vals_u or vals_p
    return "".join(f"Time = {i+1}\nsmoothSolver:  Solving for Ux, Initial residual = {u:.3e}, Final residual = 1e-9, No Iterations 1\n"
                   f"GAMG:  Solving for p, Initial residual = {p:.3e}, Final residual = 1e-9, No Iterations 1\n" for i, (p, u) in enumerate(zip(vals_p, vals_u)))


def test_criterio_de_residuo_classes():
    from modules import cfd_case as C
    import numpy as np
    n = 120
    assert C.classificar_residuos(_log(np.logspace(-1, -3, n)))["estado"] == "DECAINDO"
    assert C.classificar_residuos(_log([1e-2] * n))["estado"] == "ESTAGNADO"
    assert C.classificar_residuos(_log(np.logspace(-3, -1, n)))["estado"] == "DIVERGINDO"
    assert C.classificar_residuos(_log([1e-2] * 10))["estado"] == "INSUFICIENTE"
    assert C.classificar_residuos(_log([1e-2] * 50) + "SIMPLE solution converged in 50 iterations")["estado"] == "CONVERGIDO"
    assert C.ler_log_simplefoam(_log([1e-2] * n))["criterio_residuo"]["estado"] == "ESTAGNADO"
