"""Produtos NEXUS (mapa honesto) e NEXUS INTELLIGENCE (regras auditáveis)."""
import pytest
from PySide6.QtWidgets import QApplication

from core import products as P
from modules import intelligence as I
from modules.result_trace import TracedResult as _TR


def TracedResult(*a, **k):
    if (a[1] if len(a) > 1 else k.get("classe")) == "SIMULACAO_NUMERICA":
        k.setdefault("solver", "s"); k.setdefault("solver_versao", "1")
    return _TR(*a, **k)

app = QApplication.instance() or QApplication([])


def test_five_products_and_actions_exist_in_main_window():
    from interface.main_window import MainWindow
    assert [p.nome for p in P.PRODUTOS] == ["NEXUS CAD", "NEXUS STRUCTURAL", "NEXUS AERODYNAMICS", "NEXUS VEHICLE", "NEXUS INTELLIGENCE"]
    mw = MainWindow()
    for p in P.PRODUTOS:
        for c in p.capacidades:
            assert c.estado in (P.PRONTO, P.PARCIAL, P.PLANEJADO)
            if c.estado != P.PLANEJADO:
                assert c.acao in mw.actions_by_key, (p.nome, c.rotulo, c.acao)        # nada "pronto" sem função real atrás
            else:
                assert c.acao is None
    assert all(p.lacunas for p in P.PRODUTOS)                                        # todo produto declara limites


def test_hub_dialog_lists_and_blocks_planned():
    from interface import hub_dialog
    from interface.main_window import MainWindow
    mw = MainWindow(); d = hub_dialog.HubDialog(mw)
    assert d.lista.count() == 5
    d.lista.setCurrentRow(0); assert d.caps.count() == len(P.PRODUTOS[0].capacidades)
    msgs = []
    hub_dialog.QMessageBox.information = lambda *a, **k: msgs.append(a[2])
    d.caps.setCurrentRow(len(P.PRODUTOS[0].capacidades) - 1)        # última é PLANEJADA
    d.abrir()
    assert msgs and "PLANEJADO" in msgs[0]


def test_interpret_not_executed_has_no_numbers():
    r = TracedResult("CFD", "NAO_EXECUTADO", "x", limitacoes=["OpenFOAM NÃO INSTALADO"])
    p = I.interpretar(r)
    assert p.pior() == I.CRITICO and "NÃO foi executada" in p.texto() and not any(c.isdigit() for c in p.resumo)


def test_interpret_fea_safety_factor_levels():
    def res(fs):
        return TracedResult("FEA", "SIMULACAO_NUMERICA", "m", {"vm_max_MPa": 300.0, "vm_max_tipo": "nodal", "fator_seguranca_escoamento_ref": fs},
                            {"malhador": "gmsh", "ordem": 2})
    assert I.interpretar(res(0.8)).pior() == I.CRITICO
    assert I.interpretar(res(1.2)).pior() == I.ATENCAO
    assert I.interpretar(res(2.5)).pior() == I.INFO
    t = I.interpretar(res(0.8)).texto()
    assert "0.80" in t and "valores.fator_seguranca_escoamento_ref" in t and "não é IA generativa" in t


def test_interpret_cfd_flags():
    r = TracedResult("CFD", "SIMULACAO_NUMERICA", "m", {"convergiu": False, "iteracoes": 100, "cd_total_estimado": 0.5, "cl_total_estimado": 0.4},
                     {"bloqueio_pct": 8.0, "a_ref_origem": "caixa envolvente frontal"})
    t = I.interpretar(r).texto()
    assert "NÃO convergiu" in t and "Bloqueio do domínio 8.0" in t and "CAIXA" in t and "Sustentação" in t and "VALIDADO" in t
    assert not any("VALIDADO" in a.texto and a.nivel == I.INFO and "validada" in a.texto for a in I.interpretar(r).achados)


def test_review_project_and_compare_and_glossary():
    proj = {"name": "P", "parts": [{"name": "eixo", "material": None}, {"name": "pino", "material": "aço"}],
            "results": [{"nome": "a", "classe": "SIMULACAO_NUMERICA", "status_geometria": "OBSOLETO"}, {"nome": "b", "classe": "NAO_EXECUTADO"}]}
    p = I.revisar_projeto(proj)
    assert p.pior() == I.CRITICO and "1 peça(s) sem material" in p.texto() and "OBSOLETO" in p.texto() and "NÃO executada" in p.texto()
    assert "sem pendências" in I.revisar_projeto({"name": "ok", "parts": [{"name": "x", "material": "m"}],
                                                 "results": [{"nome": "v", "classe": "VALIDADO", "status_geometria": "VIGENTE"}]}).resumo
    c = I.comparar({"nome": "A", "classe": "ANALITICO", "valores": {"f": 10.0, "t": "x"}}, {"nome": "B", "classe": "ANALITICO", "valores": {"f": 12.0}})
    assert "10 → 12 (+20.0 %)" in c.texto()
    assert "von Mises" in I.explicar("Von Mises") or "von mises" in I.explicar("von mises")
    assert "não está no glossário" in I.explicar("xyzzy")


def test_intelligence_dialog_runs_on_project(tmp_path):
    from interface.hub_dialog import IntelligenceDialog
    from interface.main_window import MainWindow
    from modules.workspace import ProjectStore
    st = ProjectStore(tmp_path); pr = st.create("demo")
    st.attach_result(pr, TracedResult("FEA", "SIMULACAO_NUMERICA", "m", {"vm_max_MPa": 100.0, "fator_seguranca_escoamento_ref": 3.0}))
    st.attach_result(pr, TracedResult("FEA2", "SIMULACAO_NUMERICA", "m", {"vm_max_MPa": 120.0}))
    d = IntelligenceDialog(MainWindow(), st)
    d.revisar(); assert "Revisão — demo" in d.out.toPlainText()
    d.interpretar(); assert "Parecer — FEA2" in d.out.toPlainText()
    d.comparar(); assert "100 → 120 (+20.0 %)" in d.out.toPlainText()


def test_dialog_ask_ai_paths(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from interface import hub_dialog
    from interface.main_window import MainWindow
    from modules.workspace import ProjectStore
    st = ProjectStore(tmp_path); pr = st.create("d")
    st.attach_result(pr, TracedResult("FEA", "SIMULACAO_NUMERICA", "m", {"vm_max_MPa": 100.0, "fator_seguranca_escoamento_ref": 3.0}))
    d = hub_dialog.IntelligenceDialog(MainWindow(), st)
    monkeypatch.setattr(hub_dialog.QInputDialog, "getText", lambda *a, **k: ("posso usar?", True))
    monkeypatch.setattr(hub_dialog.IntelligenceDialog, "confirmar_envio", staticmethod(lambda w: False))
    d.perguntar(); assert "Nada foi enviado" in d.out.toPlainText()
    monkeypatch.setattr(hub_dialog.IntelligenceDialog, "confirmar_envio", staticmethod(lambda w: True))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    d.perguntar(); assert "indisponível" in d.out.toPlainText()
    d.cliente_ia = SimpleNamespace(messages=SimpleNamespace(create=lambda **k: SimpleNamespace(content=[SimpleNamespace(text="FS 3.0 (valores.fator_seguranca_escoamento_ref), margem ok; mas 99 MPa de fadiga.")])))
    d.perguntar(); t = d.out.toPlainText(); assert "⚠" in t and "99" in t
