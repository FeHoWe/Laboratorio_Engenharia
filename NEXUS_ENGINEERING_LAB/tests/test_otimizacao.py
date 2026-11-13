"""V7.0 — sensibilidade e otimização sobre o lapsim."""
import pytest
from dataclasses import replace
from modules import lapsim, otimizacao as O

BASE = lapsim.Carro(800, 500e3, 1.0, 3.0, 1.6, p_ers=300e3, e_ers=4e6)


def test_tornado_ordenado_e_sinais():
    t = O.tornado(BASE, variacao_pct=5)
    am = [r["amplitude_s"] for r in t["linhas"]]
    assert am == sorted(am, reverse=True) and len(t["linhas"]) == 8
    d = {r["campo"]: r for r in t["linhas"]}
    assert d["massa"]["d_mais_s"] > 0 > d["massa"]["d_menos_s"]          # mais massa → mais lento
    assert d["cla"]["d_mais_s"] < 0 < d["cla"]["d_menos_s"]              # mais downforce → mais rápido (modelo sem custo de arrasto)
    assert d["mu"]["d_mais_s"] < 0
    assert t["tempo_base_s"] == pytest.approx(lapsim.volta(BASE, None, 3.0).valores["tempo_s"])


def test_tornado_confere_com_volta_direta():
    t = O.tornado(BASE, ["massa"], 10)
    assert t["linhas"][0]["t_mais_s"] == pytest.approx(lapsim.volta(replace(BASE, massa=880.0), None, 3.0).valores["tempo_s"])


def test_tornado_erros():
    with pytest.raises(ValueError): O.tornado(BASE, ["xyz"])
    with pytest.raises(ValueError): O.tornado(BASE, variacao_pct=0)
    with pytest.raises(ValueError): O.tornado(BASE, variacao_pct=80)


def test_otimizar_melhora_e_respeita_faixa():
    o = O.otimizar(BASE, {"massa": (760, 800), "mu": (1.5, 1.7)}, max_iter=15)
    assert o["tempo_otimo_s"] <= o["tempo_base_s"] + 1e-9
    assert 760 - 1e-9 <= o["parametros"]["massa"] <= 800 + 1e-9 and 1.5 - 1e-9 <= o["parametros"]["mu"] <= 1.7 + 1e-9
    # modelo monótono: menos massa e mais μ → borda
    assert o["parametros"]["massa"] == pytest.approx(760, abs=0.5) and o["parametros"]["mu"] == pytest.approx(1.7, abs=0.005)
    assert "massa" in o["na_borda"]
    assert any("não é prova de ótimo global" in x for x in o["limitacoes"])
    # o tempo informado é o do solver para o carro devolvido
    assert o["tempo_otimo_s"] == pytest.approx(lapsim.volta(replace(BASE, **{k: o["parametros"][k] for k in o["parametros"]}), None, 3.0).valores["tempo_s"])


def test_otimizar_repetivel():
    a = O.otimizar(BASE, {"cla": (2.0, 4.0)}, max_iter=8, k_cda_por_cla=0.25)
    b = O.otimizar(BASE, {"cla": (2.0, 4.0)}, max_iter=8, k_cda_por_cla=0.25)
    assert a["parametros"] == b["parametros"]


def test_acoplamento_cda_muda_resultado_e_avisa_sem_acoplamento():
    sem = O.otimizar(BASE, {"cla": (2.0, 4.0)}, max_iter=8)
    assert any("SEM acoplamento" in x for x in sem["limitacoes"])
    com = O.otimizar(BASE, {"cla": (2.0, 4.0)}, max_iter=8, k_cda_por_cla=0.3)
    assert com["carro_otimo"]["cda"] == pytest.approx(BASE.cda + 0.3 * (com["parametros"]["cla"] - BASE.cla))
    assert not any("SEM acoplamento" in x for x in com["limitacoes"])
    assert com["tempo_otimo_s"] >= sem["tempo_otimo_s"] - 1e-9            # arrasto extra não pode ajudar


def test_otimizar_erros():
    with pytest.raises(ValueError): O.otimizar(BASE, {"massa": (800, 700)})
    with pytest.raises(ValueError): O.otimizar(BASE, {"abc": (0, 1)})
    with pytest.raises(ValueError): O.otimizar(BASE, {"massa": (700, 800)}, k_cda_por_cla=0.1)


def test_textos():
    assert "amplitude" in O.texto_tornado(O.tornado(BASE, ["massa", "mu"]))
    assert "melhor encontrado" in O.texto_otimizacao(O.otimizar(BASE, {"mu": (1.5, 1.7)}, max_iter=5))


def test_otimizar_1d_interior_e_borda():
    # tempo em função de p_ice é monótono → borda superior; em função de crr também (menor é melhor) → borda inferior
    a = O.otimizar_1d(BASE, "p_ice", 400e3, 600e3)
    assert a["valor_otimo"] == pytest.approx(600e3, rel=1e-4) and a["na_borda"] == ["p_ice"]
    b = O.otimizar_1d(BASE, "crr", 0.008, 0.016)
    assert b["valor_otimo"] == pytest.approx(0.008, abs=1e-5) and b["tempo_otimo_s"] <= b["tempo_base_s"]
    assert any("borda" in x for x in b["limitacoes"])


def test_otimizar_1d_acha_minimo_interior(monkeypatch):
    """Verifica o ALGORITMO com uma função unimodal conhecida (parábola em μ com mínimo em 1,62), substituindo só o cálculo do tempo."""
    monkeypatch.setattr(O, "_tempo", lambda c, pista, ds: 50.0 + (c.mu - 1.62) ** 2)
    r = O.otimizar_1d(BASE, "mu", 1.0, 2.5)
    assert r["valor_otimo"] == pytest.approx(1.62, abs=1e-5) and not r["na_borda"] and r["avaliacoes"] < 60


def test_otimizar_1d_erros():
    with pytest.raises(ValueError): O.otimizar_1d(BASE, "xx", 0, 1)
    with pytest.raises(ValueError): O.otimizar_1d(BASE, "mu", 2, 1)
