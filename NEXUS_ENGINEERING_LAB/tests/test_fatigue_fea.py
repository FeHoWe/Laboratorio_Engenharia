import math, pytest
from modules import fatigue as fa, fatigue_fea as ff
from modules.result_trace import TracedResult

MAT = fa.FatigueMaterial("usuario", su=600.0, sy=400.0, se_prime=250.0)


def _r(vm, classe="SIMULACAO_NUMERICA"):
    return TracedResult("FEA", classe, "m", {"vm_max_MPa": vm}, solver="x", solver_versao="1") if classe == "SIMULACAO_NUMERICA" else TracedResult("FEA", classe, "m", limitacoes=["x"])


def test_reverso_puro_goodman():
    r = ff.avaliar(_r(200.0), -1.0, MAT, 200.0)
    assert r["sigma_a_MPa"] == 200 and r["sigma_m_MPa"] == 0 and r["coef_seguranca"]["Goodman"] == pytest.approx(1.0) and r["vida_infinita"] is False or r["ciclos"] >= 1e6


def test_abaixo_do_limite_vida_infinita_e_acima_finita():
    assert ff.avaliar(_r(150.0), -1.0, MAT, 200.0)["vida_infinita"]
    r = ff.avaliar(_r(260.0), -1.0, MAT, 200.0); assert not r["vida_infinita"] and 1e3 < r["ciclos"] < 1e7


def test_media_reduz_seguranca():
    a = ff.avaliar(_r(200.0), -1.0, MAT, 200.0)["coef_seguranca"]["Goodman"]
    b = ff.avaliar(_r(200.0), 0.0, MAT, 200.0)["coef_seguranca"]["Goodman"]
    assert b != a and ff.avaliar(_r(200.0), 0.0, MAT, 200.0)["sigma_m_MPa"] == 100


def test_recusa():
    with pytest.raises(ValueError): ff.avaliar(_r(1, "NAO_EXECUTADO"), -1, MAT, 200)
    with pytest.raises(ValueError): ff.avaliar(_r(200.0), 1.0, MAT, 200)
    with pytest.raises(ValueError): ff.avaliar(_r(0.0), -1, MAT, 200)
