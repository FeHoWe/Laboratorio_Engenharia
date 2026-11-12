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
