import pytest
from modules import casos_nl as CN, solver_registry as sr

pytestmark = pytest.mark.skipif(not sr.detect("CalculiX").instalado, reason="CalculiX não instalado")


def test_casos_vs_analitico():
    r = CN.barra_plastica(210000, 0.3, 250, 2100, 20, 4, 0.006); assert abs(r["erro_pct"]) < 2 and r["plastificou"]
    r = CN.serie_materiais(210000, 70000, 0.0, 20, 4, 1000); assert abs(r["erro_pct"]) < 3
    r = CN.blocos_contato(210000, 0.0, 10, 4, 800); assert abs(r["erro_pct"]) < 3


def test_validacao():
    with pytest.raises(ValueError): CN.barra_plastica(210000, 0.3, 250, 300000, 20, 4, 0.006)
    with pytest.raises(ValueError): CN.blocos_contato(1, 0, 0, 4, 1)


def test_dialogo():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from interface.nl_dialog import NLDialog
    d = NLDialog(); d.run_plastico(); assert "erro_pct" in d.out.toPlainText()
    d.p["Et"].setValue(300000); d.run_plastico(); assert "ERRO" in d.out.toPlainText()


# ---------------------------------------------------------------- V3.8: contato entre duas peças (OCP/STEP) na interface
def _ccx():
    from modules import solver_registry as sr
    return sr.detect("CalculiX").instalado


@pytest.mark.skipif(not _ccx(), reason="CalculiX ausente")
def test_contato_duas_pecas_caixas_equilibrio_e_rigidez_serie():
    from modules import casos_nl as CN
    a = CN.peca_de_especificacao(dict(tipo="caixa", dx=10, dy=10, dz=10)); b = CN.peca_de_especificacao(dict(tipo="caixa", dx=10, dy=10, dz=10))
    r = CN.contato_duas_pecas(a, b, 210000, 0.0, 210000, 0.0, 800, 3.0)
    assert r["classe"] == "SIMULACAO_NUMERICA" and abs(r["erro_equilibrio_pct"]) < 0.1
    ref = 800 * 20 / (210000 * 100)
    assert r["u_topo_mm"] == pytest.approx(ref, rel=0.08) and r["nos_escravo"] > 0


@pytest.mark.skipif(not _ccx(), reason="CalculiX ausente")
def test_contato_duas_pecas_cilindro_sobre_caixa_e_step(tmp_path):
    from modules import casos_nl as CN
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
    cil = BRepPrimAPI_MakeCylinder(4.0, 8.0).Shape(); p = tmp_path / "cil.step"
    w = STEPControl_Writer(); w.Transfer(cil, STEPControl_AsIs); w.Write(str(p))
    base = CN.peca_de_especificacao(dict(tipo="caixa", dx=14, dy=14, dz=6)); sup = CN.peca_de_especificacao(dict(tipo="step", path=str(p)))
    r = CN.contato_duas_pecas(base, sup, 210000, 0.0, 70000, 0.0, 500, 2.5)
    assert r["classe"] == "SIMULACAO_NUMERICA" and abs(r["erro_equilibrio_pct"]) < 0.5 and r["u_topo_mm"] > 0
    # peça superior mais mole ⇒ menor rigidez que com a mesma peça em aço
    r2 = CN.contato_duas_pecas(base, sup, 210000, 0.0, 210000, 0.0, 500, 2.5)
    assert r["rigidez_N_por_mm"] < r2["rigidez_N_por_mm"]


def test_contato_duas_pecas_erros_nao_inventam_numeros(tmp_path):
    from modules import casos_nl as CN
    with pytest.raises(ValueError): CN.peca_de_especificacao(dict(tipo="step", path=str(tmp_path / "nao_existe.step")))
    with pytest.raises(ValueError): CN.peca_de_especificacao(dict(tipo="esfera"))
    with pytest.raises(ValueError): CN.peca_de_especificacao(dict(tipo="caixa", dx=0, dy=1, dz=1))
    a = CN.peca_de_especificacao(dict(tipo="caixa", dx=5, dy=5, dz=5))
    with pytest.raises(ValueError): CN.contato_duas_pecas(a, a, -1, 0.3, 1, 0.3, 10, 2)


@pytest.mark.skipif(not _ccx(), reason="CalculiX ausente")
def test_dialogo_contato_duas_pecas():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from interface.nl_dialog import NLDialog
    d = NLDialog(); d.run_contato2(); t = d.out.toPlainText()
    assert "SIMULACAO_NUMERICA" in t and "erro_equilibrio_pct" in t
    d.pc["sup"]["tipo"].setCurrentText("step"); d.run_contato2()                 # sem caminho → erro tratado
    assert "ERRO" in d.out.toPlainText()
