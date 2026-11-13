"""V60 — modelo de bicicleta."""
import math
import pytest
from dataclasses import replace
from modules import lapsim, lapsim_bicicleta as B

G = 9.80665


def carro(**kw):
    d = dict(massa=800, a=1.6, b=1.7, h=0.30, p_ice=500e3, cda=1.0, cla=3.0, mu_f=1.6, mu_r=1.6, bal_aero=0.45, tracao="traseira")
    d.update(kw)
    return B.CarroB(**d)


def T(c, ds=3.0):
    return B.volta(c, None, ds).valores["tempo_s"]


def test_reduz_ao_ponto_material_quando_h0_mesmos_mu_e_tracao_integral():
    c = carro(h=0.0, tracao="integral", bal_aero=0.5, a=1.65, b=1.65)
    pm = lapsim.volta(lapsim.Carro(800, 500e3, 1.0, 3.0, 1.6), None, 3.0).valores
    bi = B.volta(c, None, 3.0).valores
    assert bi["tempo_s"] == pytest.approx(pm["tempo_s"], rel=0.02)                   # mesma física global; diferença só pelo limite por eixo/ellipse
    assert bi["v_max_kmh"] == pytest.approx(pm["v_max_kmh"], rel=0.03)


def test_inversao_com_cg_alto_e_tracao_traseira_mais_lenta_que_integral():
    assert T(carro(tracao="integral")) < T(carro(tracao="traseira"))
    # artefato DOCUMENTADO: sem transferência lateral, CG mais alto ajuda a tração traseira (e o modelo avisa que não serve para otimizar h)
    assert T(carro(h=0.5)) < T(carro(h=0.2))
    assert any("NÃO serve para otimizar a altura do CG" in x for x in B.volta(carro(), None, 3.0).limitacoes)


def test_forca_de_tracao_traseira_bate_forma_fechada_para_k0():
    c = carro(k_carga=0.0, cla=0.0, cda=0.0, crr=0.0, p_ice=1e9)
    v = 20.0
    a = B._a_acel(c, v, 0.0, 1e9)
    Nr0 = c.massa * G * c.a / c.L
    F = c.mu_r * Nr0 / (1 - c.mu_r * c.h / c.L)                                       # F = μ(N_r0 + F·h/L)
    assert a * c.massa == pytest.approx(F, rel=1e-6)


def test_frenagem_ideal_mu_igual_da_mu_g_e_divisao_fixa_ruim_freia_menos():
    c = carro(cla=0.0, cda=0.0, crr=0.0)
    assert B._a_freio(c, 30.0, 0.0) == pytest.approx(c.mu_f * G, rel=1e-6)           # ideal: μ·g sem aero
    ruim = replace(c, freio_diant=0.9)
    assert B._a_freio(ruim, 30.0, 0.0) < B._a_freio(c, 30.0, 0.0)


def test_balanco_aero_muda_sub_sobreesterco():
    frente = B.volta(replace(carro(), bal_aero=0.85), None, 3.0).valores
    tras = B.volta(replace(carro(), bal_aero=0.15), None, 3.0).valores
    assert tras["pct_curvas_limite_traseiro"] <= frente["pct_curvas_limite_traseiro"] + 1e-9 or tras["pct_curvas_limite_dianteiro"] >= frente["pct_curvas_limite_dianteiro"]
    # com muito downforce atrás, o eixo dianteiro satura primeiro (subesterço)
    assert tras["pct_curvas_limite_dianteiro"] >= 50 and frente["pct_curvas_limite_traseiro"] >= 50


def test_sensibilidade_de_carga_k_piora_o_tempo_com_downforce():
    assert T(carro(k_carga=0.3)) > T(carro(k_carga=0.0))


def test_curva_limite_respeita_os_dois_eixos_e_e_continua():
    c = carro()
    for r in (25, 60, 120):
        v, eixo = B._v_curva(c, r)
        assert eixo in ("dianteiro", "traseiro")
        assert v * v / r == pytest.approx(B._ay_max(c, v)[0], rel=1e-6)
        assert (v + 0.3) ** 2 / r > B._ay_max(c, v + 0.3)[0]                         # acima do limite não é viável


def test_rastreabilidade_e_erros():
    r = B.volta(carro(), None, 3.0)
    assert r.classe == "SIMULACAO_NUMERICA" and r.solver == "NEXUS-LapSim-Bicicleta" and any("SINTÉTICA" in x for x in r.limitacoes) and "bicicleta" in B.texto(r)
    for kw in (dict(massa=0), dict(a=0), dict(bal_aero=1.5), dict(k_carga=1.0), dict(tracao="x"), dict(freio_diant=1.0), dict(h=-1)):
        with pytest.raises(ValueError): B.volta(carro(**kw))
    with pytest.raises(ValueError): B.volta(carro(), None, 0)
    assert any("empinar" in x for x in B.volta(carro(mu_r=6.0, h=1.0), None, 4.0).limitacoes)
