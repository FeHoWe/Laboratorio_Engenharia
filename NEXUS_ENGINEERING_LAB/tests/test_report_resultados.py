import pytest
from modules import report_resultados as RR
from modules.result_trace import TracedResult


def _txt(path):
    import subprocess
    return subprocess.run(["pdftotext", str(path), "-"], capture_output=True, text=True).stdout


def test_pdf_com_classes_e_laudo(tmp_path):
    a = TracedResult("Barra", "ANALITICO", "σ=F/A", {"sigma_MPa": 12.5}, {"F_N": 100.0})
    b = TracedResult("CFD", "NAO_EXECUTADO", "x", limitacoes=["OpenFOAM NÃO INSTALADO"])
    p = RR.gerar([a, b], tmp_path / "r.pdf", versao="3.6", laudo=True, peca="Suporte S-1", responsavel="")
    assert p.exists() and p.stat().st_size > 1500
    t = _txt(p)
    if t:                                                                         # pdftotext pode não existir
        assert "ESTIMATIVA DE ENGENHARIA" in t and "NÃO EXECUTADO" in t and "Suporte S-1" in t and "12.5" in t and "ANALITICO" in t


def test_sem_resultados_recusa(tmp_path):
    with pytest.raises(ValueError): RR.gerar([], tmp_path / "x.pdf")


def test_dialogo_inteligencia_relatorio_e_selos(tmp_path):
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from interface.main_window import MainWindow
    from interface.hub_dialog import IntelligenceDialog
    from modules.workspace import ProjectStore
    st = ProjectStore(tmp_path / "proj"); st.create("p1") if hasattr(st, "create") else None
    d = IntelligenceDialog(MainWindow(), store=st); d.selos()
    assert "CONFERIDO" in d.out.toPlainText() and "NÃO é validação" in d.out.toPlainText()
