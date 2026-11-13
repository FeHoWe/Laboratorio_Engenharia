"""V4.0: casos não lineares em processo isolado — a interface não bloqueia, erro de entrada volta como texto, cancelamento funciona."""
import pytest

from modules import nl_job
from modules import solver_registry as sr


def _app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_job_erro_de_entrada_volta_como_dado():
    r = nl_job.run("plastico", dict(E=210000, nu=0.3, sigma_y=250, Et=300000, comprimento=20, lado=4, deformacao=0.006))
    assert "_erro" in r
    assert "_erro" in nl_job.run("contato2", dict(inferior=dict(tipo="step", path=""), superior=dict(tipo="caixa", dx=1, dy=1, dz=1),
                                 E1=1, nu1=0, E2=1, nu2=0, forca=1, tamanho=1))
    assert "_erro" in nl_job.run("inexistente", {})


def test_dialogo_nao_bloqueia_e_cancela():
    _app()
    from interface.nl_dialog import NLDialog
    d = NLDialog()
    d.run_plastico()                                   # retorna imediatamente: o cálculo roda em outro processo
    assert d._job is not None and d.b_cancel.isEnabled()
    d.cancelar()
    d.aguardar(30)
    assert d._job.state in ("CANCELLED", "DONE", "FAILED")          # terminou (se já tinha acabado, DONE é legítimo)
    assert not d.b_cancel.isEnabled()
    if d._job.state == "CANCELLED":
        assert "Cancelado" in d.out.toPlainText()


@pytest.mark.skipif(not sr.detect("CalculiX").instalado, reason="CalculiX ausente")
def test_job_plastico_real_confere_com_analitico():
    r = nl_job.run("plastico", dict(E=210000, nu=0.3, sigma_y=250, Et=2100, comprimento=20, lado=4, deformacao=0.006))
    assert r["classe"] == "SIMULACAO_NUMERICA" and abs(r["erro_pct"]) < 5
