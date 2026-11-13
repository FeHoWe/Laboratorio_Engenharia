"""V110 Fase B — diálogo gráfico de estudos avançados (chama os módulos reais; sem cálculo próprio)."""
import json
import pytest
from PySide6.QtWidgets import QApplication
from interface.estudos_avancados_dialog import EstudosAvancadosDialog, parse_kv, CARRO_EXEMPLO
from modules import lapsim, validacao_dados as VD

QApplication.instance() or QApplication([])


@pytest.fixture
def dlg():
    return EstudosAvancadosDialog(None)


def test_parse_kv_ok_e_erros():
    assert parse_kv("a=1 b=2,5; c=3") == {"a": 1.0, "b": 2.5, "c": 3.0}
    with pytest.raises(ValueError, match="campo=valor"): parse_kv("abc")
    with pytest.raises(ValueError, match="inválido"): parse_kv("a=x")


def test_validacao_igual_ao_modulo(dlg, tmp_path):
    c = lapsim.Carro(**parse_kv(CARRO_EXEMPLO))
    arq = tmp_path / "t.csv"; arq.write_text(VD.para_csv_exemplo(c), encoding="utf-8")
    dlg.v_tol.setText("rmse_kmh=5")
    dlg.run_validacao(str(arq))
    esperado = VD.texto(VD.validar(c, VD.ler_telemetria(arq), None, 3.0, {"rmse_kmh": 5.0}))
    assert dlg.saida.toPlainText() == esperado and "VALIDADO" in esperado


def test_calibracao_freios_lateral(dlg, tmp_path):
    arq = tmp_path / "t.csv"; arq.write_text(VD.para_csv_exemplo(lapsim.Carro(**{**parse_kv(CARRO_EXEMPLO), "mu": 1.5})), encoding="utf-8")
    dlg.run_calibracao(str(arq))
    assert "mu" in dlg.saida.toPlainText() and "Não foi possível" not in dlg.saida.toPlainText()
    dlg.f_voltas.setText("2"); dlg.run_freios()
    assert "Freios" in dlg.saida.toPlainText() and "SIMULACAO_NUMERICA" in dlg.saida.toPlainText()
    dlg.run_lateral()
    assert "Cf e Cr" in dlg.saida.toPlainText() or "subester" in dlg.saida.toPlainText().lower() or "ANALITICO" in dlg.saida.toPlainText()


def test_erros_viram_texto_e_nao_excecao(dlg):
    dlg.carro_txt.setText("massa=abc"); dlg.run_freios()
    assert dlg.saida.toPlainText().startswith("Não foi possível calcular")
    dlg.carro_txt.setText(CARRO_EXEMPLO); dlg.l_par.setText("massa=800"); dlg.run_lateral()
    assert dlg.saida.toPlainText().startswith("Não foi possível calcular")
    dlg.run_projeto(); assert "projeto aberto" in dlg.saida.toPlainText()


def test_dossie_criar_e_verificar(dlg, tmp_path):
    esp = tmp_path / "e.json"; esp.write_text(json.dumps({"tipo": "volta", "parametros": {"carro": parse_kv(CARRO_EXEMPLO)}, "nota": "gui"}))
    out = tmp_path / "x.dossie.json"
    dlg.criar_dossie(str(esp), str(out)); assert out.exists() and "Gravado" in dlg.saida.toPlainText()
    dlg.verificar_dossie(str(out)); assert "reprodução: ok" in dlg.saida.toPlainText()


def test_projeto_para_carro_usa_massa_do_projeto(dlg, motor_project):
    class W: project = motor_project
    dlg.w = W; dlg.p_yd.setText("-50"); dlg.p_yt.setText("150")
    dlg.run_projeto()                                              # sem material: o módulo recusa, a GUI mostra o motivo
    assert "não atribui automaticamente" in dlg.saida.toPlainText()
    motor_project.components.set_material(motor_project.components.root.id, "Aço carbono", recursive=True)
    dlg.run_projeto()
    from modules import carro_do_projeto as CP
    esperado = CP.levantar(motor_project, -50.0, 150.0)["massa_kg"]
    assert parse_kv(dlg.carro_txt.text())["massa"] == pytest.approx(esperado, rel=1e-5) and "ANALITICO" in dlg.saida.toPlainText()


def test_comparar_ab_na_gui(dlg, tmp_path):
    base = parse_kv(CARRO_EXEMPLO)
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    a.write_text(json.dumps({"carro": base})); b.write_text(json.dumps({"carro": {**base, "massa": 780.0}}))
    dlg.comparar_veiculos(str(a), str(b))
    t = dlg.saida.toPlainText()
    assert "Comparação A/B" in t and "tempo_volta_lapsim_s" in t and "NÃO devem ser somados" in t
    b.write_text("{"); dlg.comparar_veiculos(str(a), str(b))
    assert dlg.saida.toPlainText().startswith("Não foi possível calcular")
