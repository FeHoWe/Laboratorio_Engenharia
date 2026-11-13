"""V40 — calibração e identificabilidade (telemetria sintética só nos testes)."""
import pytest
from dataclasses import replace
from modules import lapsim, calibracao as K, doe

REAL = lapsim.Carro(800, 500e3, 1.0, 3.0, 1.5, p_ers=300e3, e_ers=4e6)        # “verdade” do teste
BASE = replace(REAL, mu=1.65, cla=3.0)


def tele(c, ruido_pct=0.0, semente=3):
    r = lapsim.volta(c, None, 3.0)
    rnd = doe.mulberry32(semente)
    return {"s_m": list(r.valores["s_m"]), "v_kmh": [v * 3.6 * (1 + ruido_pct / 100 * (2 * rnd() - 1)) for v in r.valores["v_ms"]], "t_s": None}


def test_recupera_parametro_conhecido():
    r = K.calibrar(BASE, {"mu": (1.2, 1.9)}, tele(REAL))
    assert r["parametros_calibrados"]["mu"] == pytest.approx(1.5, abs=2e-3)
    assert r["treino"]["rmse_depois_kmh"] < 0.1 * r["treino"]["rmse_antes_kmh"] and r["convergiu"] and r["classe"] == "SIMULACAO_NUMERICA"
    assert r["tempo_calibrado_s"] == pytest.approx(lapsim.volta(REAL, None, 3.0).valores["tempo_s"], rel=2e-3)
    assert any("EFETIVOS" in x for x in r["limitacoes"]) and any("NÃO equivale a validar" in x for x in r["limitacoes"])


def test_dois_parametros_e_incerteza_com_ruido():
    t = tele(replace(REAL, mu=1.5, cla=3.4), ruido_pct=0.5)
    r = K.calibrar(BASE, {"mu": (1.2, 1.9), "cla": (2.0, 5.0)}, t)
    assert r["parametros_calibrados"]["mu"] == pytest.approx(1.5, abs=0.05) and r["parametros_calibrados"]["cla"] == pytest.approx(3.4, abs=0.4)
    assert set(r["incerteza_aprox"]) == {"mu", "cla"} and all(u > 0 for u in r["incerteza_aprox"].values())
    c = r["correlacoes"][0]["correlacao"]
    assert -1 <= c <= 1 and r["numero_condicao"] >= 1 and len(r["valores_singulares"]) == 2


def test_validacao_por_trecho():
    r = K.calibrar(BASE, {"mu": (1.2, 1.9)}, tele(REAL), frac_treino=0.6)
    assert r["teste"] and r["treino"]["n_pontos"] > r["teste"]["n_pontos"] * 1.2
    assert r["teste"]["rmse_depois_kmh"] < r["teste"]["rmse_antes_kmh"] and r["teste"]["rmse_depois_kmh"] < 0.5


def test_borda_e_pouca_melhora_geram_aviso():
    r = K.calibrar(BASE, {"mu": (1.55, 1.9)}, tele(REAL))              # o verdadeiro (1.5) está fora da faixa
    assert any("borda" in x for x in r["avisos"]) and r["parametros_calibrados"]["mu"] == pytest.approx(1.55, abs=1e-3)
    r2 = K.calibrar(BASE, {"crr": (0.005, 0.03)}, tele(REAL))             # crr quase não explica o erro de μ
    assert any("reduziu pouco" in x or "borda" in x or "condição" in x for x in r2["avisos"])


def test_parametro_sem_efeito_e_singular():
    r = K.calibrar(BASE, {"mu": (1.2, 1.9), "e_ers": (1e6, 8e6)}, tele(REAL))     # e_ers já está no limite útil da volta: pode não ser identificável
    assert "numero_condicao" in r and isinstance(r["avisos"], list)


def test_erros():
    t = tele(REAL)
    for kw in (dict(parametros={}), dict(parametros={"x": (0, 1)}), dict(parametros={"mu": (2, 1)}), dict(parametros={"mu": (1.8, 1.9)}), dict(parametros={"mu": (1.2, 1.9)}, frac_treino=0.1)):
        with pytest.raises(ValueError):
            K.calibrar(BASE, telemetria=t, **kw)
    with pytest.raises(K.TelemetriaError): K.calibrar(BASE, {"mu": (1.2, 1.9)}, {"s_m": [0.0, 5.0, 10.0], "v_kmh": [100.0] * 3, "t_s": None})


def test_texto():
    assert "Calibração" in K.texto(K.calibrar(BASE, {"mu": (1.2, 1.9)}, tele(REAL), frac_treino=0.7))
