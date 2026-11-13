"""V5.0 — NEXUS HOME: resumo do projeto, atalhos dos ambientes e verificação de consistência."""
import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture()
def janela(engine, tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_RECOVERY_DIR", str(tmp_path / "rec"))
    QApplication.instance() or QApplication([])
    from interface.main_window import MainWindow
    w = MainWindow(config={}, engine=engine)
    yield w
    w.project.dirty = False
    w.close()


def test_home_e_primeira_aba_e_resumo_acompanha_o_projeto(janela):
    w = janela
    assert w.central_tabs.tabText(0) == "NEXUS HOME" and w.central_tabs.widget(0) is w.home_tab
    assert "0 peça(s)" in w.home_tab.resumo.text()
    w.open_sample_engine(background=False)
    t = w.home_tab.resumo.text()
    assert "180 peça(s)" in t and "Materiais atribuídos: 0 de 180" in t and "PARCIAL" in t
    assert "(ainda não salvo)" in t


def test_home_atalhos_existem_na_janela_e_verificacao(janela):
    w = janela
    for metodo in w.home_tab.botoes:
        assert callable(getattr(w, metodo)), metodo
    w.open_sample_engine(background=False)
    txt = w.home_tab.verificar()
    assert "sem material" in txt and txt == w.home_tab.saida.toPlainText()
    w.mostrar_home()
    assert w.central_tabs.currentWidget() is w.home_tab


def test_home_mostra_versoes_e_alteracoes_nao_salvas(janela, tmp_path):
    w = janela
    w.open_sample_engine(background=False)
    assert w.save_project_as(str(tmp_path / "p.nexus"))
    assert w.registrar_versao("v1")
    w.project.dirty = True
    w.home_tab.atualizar()
    t = w.home_tab.resumo.text()
    assert "Versões registradas: 1" in t and "NÃO salvas" in t


def test_home_recentes_e_atividade(janela, tmp_path):
    from core import atividade
    w = janela
    w.project.components  # janela com projeto novo
    assert not w.home_tab.b_recente.isEnabled() and "sem atividade" in w.home_tab.atividade.toPlainText()
    from modules import importer  # noqa: F401
    arq = tmp_path / "p.nexus"
    w.save_project_as(str(arq))
    w.home_tab.atualizar()
    assert str(arq) in [w.home_tab.recentes.itemData(i) for i in range(w.home_tab.recentes.count())] and w.home_tab.b_recente.isEnabled()
    assert "Salvou" in w.home_tab.atividade.toPlainText()
    assert w.home_tab.abrir_recente() is True
    assert atividade.ultimos(1)[0]["texto"].startswith("Abriu")


def test_home_diagnostico_cinco_blocos(janela):
    w = janela
    w.open_sample_engine(background=False)
    t = w.home_tab.diagnosticar()
    assert all(f"== {b} ==" in t for b in ("CALCULADO", "INTERPRETACAO", "HIPOTESE", "RECOMENDACAO", "INDISPONIVEL")) and "sem IA generativa" in t
    assert "massa total" in t and w.home_tab.saida.toPlainText() == t
    folha = list(w.project.components.leaves())[0]
    w.project.components.set_material(folha.id, "Aço carbono", recursive=False)
    w.estudos_diagnostico = [{"nome": "X", "classe": "SIMULACAO_NUMERICA", "valores": {"a": 1.0}, "componentes": [folha.id]}]
    t2 = w.home_tab.diagnosticar()
    assert "Refazer os estudos afetados" in t2 and "NÃO validado" in t2
