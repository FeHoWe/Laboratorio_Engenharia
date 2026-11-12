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


@pytest.mark.parametrize("lang,trecho", [("en", "ENGINEERING ESTIMATE"), ("es", "ESTIMACIÓN DE INGENIERÍA"), ("de", "INGENIEURSMÄSSIGE ABSCHÄTZUNG"),
                                         ("fr", "ESTIMATION D'INGÉNIERIE")])
def test_laudo_traduzido_mantem_classe_e_numeros(tmp_path, lang, trecho):
    from core import i18n
    a = TracedResult("Barra", "ANALITICO", "σ=F/A", {"sigma_MPa": 12.5}, {"F_N": 100.0})
    b = TracedResult("CFD", "NAO_EXECUTADO", "x", limitacoes=["OpenFOAM NÃO INSTALADO"])
    antes = i18n.idioma(); i18n.definir_idioma(lang, salvar=False)
    try:
        p = RR.gerar([a, b], tmp_path / "r.pdf", versao="3.9", laudo=True, peca="S-1")
    finally:
        i18n.definir_idioma(antes, salvar=False)
    t = _txt(p)
    if t:
        assert trecho in t and "ANALITICO" in t and "NAO_EXECUTADO" in t and "12.5" in t and "S-1" in t   # classe e número NÃO são traduzidos
        assert "ESTIMATIVA DE ENGENHARIA" not in t


def test_laudo_chines_gera_pdf(tmp_path):
    from core import i18n
    a = TracedResult("Barra", "ANALITICO", "σ=F/A", {"sigma_MPa": 12.5}, {"F_N": 100.0})
    antes = i18n.idioma(); i18n.definir_idioma("zh", salvar=False)
    try:
        p = RR.gerar([a], tmp_path / "z.pdf", laudo=True, peca="S-1")
    finally:
        i18n.definir_idioma(antes, salvar=False)
    b = p.read_bytes()
    assert b.startswith(b"%PDF") and (b"STSong-Light" in b or b"/FontFile2" in b)    # CID padrão ou TrueType embutida
    t = _txt(p)
    assert not t or "NEXUS 结果报告" in t
