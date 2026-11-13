"""V4.3 — comparação A/B e varredura de parâmetro (mesmo solver, diferença aritmética)."""
import pytest
from modules import lapsim
from modules.comparacao import comparar_voltas, texto, varrer_parametro

A = lapsim.Carro(800, 500e3, 1.0, 3.0, 1.6, p_ers=300e3, e_ers=4e6)


def test_a_igual_a_b_da_delta_zero():
    c = comparar_voltas(A, A, ds=4.0)
    assert all(abs(d["delta"]) < 1e-12 and d["melhor"] is None for d in c["campos"].values())
    assert max(abs(x) for x in c["delta_tempo_ao_longo_da_pista"]["delta_s"]) < 1e-12
    assert c["parametros_diferentes"] == {}


def test_mais_potencia_e_mais_rapido_e_delta_fecha_com_o_tempo_de_volta():
    from dataclasses import replace
    B = replace(A, p_ice=600e3)
    c = comparar_voltas(A, B, ds=4.0)
    t = c["campos"]["tempo_s"]
    assert t["B"] < t["A"] and t["melhor"] == "B" and c["parametros_diferentes"] == {"p_ice": {"A": 500e3, "B": 600e3}}
    dt = c["delta_tempo_ao_longo_da_pista"]["delta_s"]
    ds = 4.0
    # o último ponto acumulado + o último trecho = diferença total de tempo de volta
    assert dt[-1] <= 0 and c["maior_ganho_de_B"]["delta_s"] <= dt[-1] + 1e-9
    assert abs(t["delta"]) >= abs(dt[-1]) - 1e-9 and abs(t["delta"] - dt[-1]) < 0.2     # só falta o último trecho de ds
    assert "A/B" in texto(c) and "⚠" in texto(c)


def test_mais_massa_mais_lento_e_resultados_rastreaveis():
    from dataclasses import replace
    c = comparar_voltas(A, replace(A, massa=900), ds=4.0)
    assert c["campos"]["tempo_s"]["melhor"] == "A"
    assert c["resultado_A"].classe == "SIMULACAO_NUMERICA" and c["resultado_B"].solver
    assert any("não prevê" in x for x in c["limitacoes"])


def test_varredura_monotonica_em_potencia_e_erros():
    r = varrer_parametro(A, "p_ice", [400e3, 500e3, 600e3, 700e3])
    ts = [x["tempo_s"] for x in r]
    assert ts == sorted(ts, reverse=True) and r[0]["delta_vs_primeiro_s"] == 0
    with pytest.raises(ValueError): varrer_parametro(A, "inexistente", [1])
    with pytest.raises(ValueError): varrer_parametro(A, "massa", [])
    with pytest.raises(ValueError): varrer_parametro(A, "massa", [-5])


def test_aba_ab_no_dialogo_f1():
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from interface.main_window import MainWindow
    from core.cad_engine import CadEngine
    from interface.f1_dialog import F1Dialog
    w = MainWindow(config={}, engine=CadEngine())
    d = F1Dialog(w)
    d.ab["p_ice"].setText("600")
    d.run_ab()
    t = d.ab_out.toPlainText()
    assert "Comparação A/B" in t and "p_ice: 500000 → 600000" in t
    d.sw_vals.setText("400, 600"); d.run_sweep()
    assert "Varredura de p_ice" in d.ab_out.toPlainText() and "400" in d.ab_out.toPlainText()
    d.sw_campo.setText("xyz"); d.run_sweep(); assert "Não foi possível" in d.ab_out.toPlainText()
    w.project.dirty = False; w.close()
