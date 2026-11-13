"""V70 — dinâmica lateral linear."""
import math
import numpy as np
import pytest
from modules import dinamica_lateral as D

P = D.ParamsLat(massa=800, a=1.6, b=1.7, iz=900, cf=120e3, cr=140e3)        # valores de teste, não de um carro real


def test_gradiente_de_subesterco_e_ganho_de_regime_formula_fechada():
    g = D.ganhos(P, 30.0)
    K = P.massa / P.L * (P.b / P.cf - P.a / P.cr)
    assert g["gradiente_subesterco_rad_por_ms2"] == pytest.approx(K) and g["ganho_guinada_1_por_s"] == pytest.approx(30.0 / (P.L + K * 900))
    assert g["classe"] == "ANALITICO" and g["tipo"] in ("subesterçante", "sobreesterçante", "neutro")


def test_neutro_ganho_e_U_sobre_L():
    n = D.ParamsLat(800, 1.6, 1.7, 900, 100e3, 100e3 * 1.6 / 1.7)               # b/Cf = a/Cr → K = 0
    g = D.ganhos(n, 25.0)
    assert g["tipo"] == "neutro" and g["ganho_guinada_1_por_s"] == pytest.approx(25.0 / n.L, rel=1e-9)


def test_subesterco_tem_velocidade_caracteristica_e_estabilidade_sempre():
    sub = D.ParamsLat(800, 1.6, 1.7, 900, 90e3, 160e3)
    assert D.ganhos(sub, 20)["tipo"] == "subesterçante"
    vc = D.ganhos(sub, 20)["velocidade_caracteristica_ms"]
    assert D.ganhos(sub, vc)["ganho_guinada_1_por_s"] == pytest.approx(0.5 * vc / sub.L, rel=1e-9)     # na característica o ganho cai à metade do neutro
    assert all(g["estavel"] for g in D.varredura_velocidade(sub, [5, 20, 50, 90]))


def test_sobreesterco_fica_instavel_acima_da_velocidade_critica():
    sob = D.ParamsLat(800, 1.6, 1.7, 900, 160e3, 90e3)
    g = D.ganhos(sob, 20)
    assert g["tipo"] == "sobreesterçante" and g["velocidade_critica_ms"] > 0
    vcr = g["velocidade_critica_ms"]
    assert D.ganhos(sob, 0.9 * vcr)["estavel"] and not D.ganhos(sob, 1.1 * vcr)["estavel"]
    d = D.degrau(sob, 1.1 * vcr)
    assert any("INSTÁVEL" in x for x in d["limitacoes"]) and d["sobressinal_pct"] is None


def test_degrau_converge_ao_regime_e_confere_com_integracao_independente():
    d = D.degrau(P, 30.0, delta=0.02, t_fim=6.0, dt=0.005)
    assert d["r_rad_s"][-1] == pytest.approx(d["r_regime_rad_s"], rel=2e-3)
    assert d["ay_ms2"][-1] == pytest.approx(d["ay_regime_ms2"], rel=5e-3)
    # integração Euler independente com passo pequeno
    A, B = D.matrizes(P, 30.0)
    x = np.zeros(2)
    for _ in range(int(6.0 / 1e-4)):
        x = x + 1e-4 * (A @ x + B * 0.02)
    assert d["r_rad_s"][-1] == pytest.approx(x[1], rel=1e-3) and d["beta_rad"][-1] == pytest.approx(x[0], rel=2e-3)
    assert d["t63_s"] is not None and 0 < d["t63_s"] < 1.5 and d["tempo_acomodacao_2pct_s"] >= d["t63_s"]
    assert "sobressinal" in D.texto(d)


def test_autovalores_e_amortecimento_coerentes():
    g = D.ganhos(P, 30.0)
    A, _ = D.matrizes(P, 30.0)
    assert sorted((complex(*z) for z in g["autovalores"]), key=lambda z: (z.real, z.imag)) == pytest.approx(sorted(np.linalg.eigvals(A), key=lambda z: (z.real, z.imag)))
    if g["wn_rad_s"]:
        assert 0 < g["zeta"] and g["wn_rad_s"] ** 2 == pytest.approx(abs(np.linalg.det(A)))


def test_erros():
    for bad in (dict(massa=0), dict(iz=-1), dict(cf=0)):
        kw = dict(massa=800, a=1.6, b=1.7, iz=900, cf=1e5, cr=1e5); kw.update(bad)
        with pytest.raises(ValueError): D.ganhos(D.ParamsLat(**kw), 20)
    with pytest.raises(ValueError, match="0,5"): D.ganhos(P, 0.1)
    with pytest.raises(ValueError): D.degrau(P, 30, t_fim=100)
    with pytest.raises(ValueError): D.degrau(P, 30, t_fim=1, dt=0.5)


def test_resposta_lenta_nao_acomoda_na_janela_e_avisa():
    lenta = D.ParamsLat(5.0, 0.1, 0.1, 5.0, 1000, 1200)
    d = D.degrau(lenta, 30.0, 0.02, 3.0)
    assert d["acomodou_na_janela"] is False and d["sobressinal_pct"] == 0.0 and any("não se acomodou" in x for x in d["limitacoes"])
    assert "não acomodou" in D.texto(d)
