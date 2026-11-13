"""V4.4 — verificação de consistência do projeto (regras determinísticas, sem números inventados)."""
import pytest
from modules.intelligence import ATENCAO, CRITICO, INFO, verificar_projeto


def test_projeto_vazio():
    from core.project_manager import ProjectManager
    from core.cad_engine import CadEngine
    p = ProjectManager(CadEngine()).new_project("x")
    pr = verificar_projeto(p)
    assert pr.pior() == INFO and "não tem peças" in pr.resumo


def test_sem_material_massa_parcial_e_nao_atribui(motor_project):
    p = motor_project
    folhas = p.components.leaves()
    assert folhas and all(not c.material for c in folhas)
    pr = verificar_projeto(p)
    txt = pr.texto()
    assert pr.pior() == ATENCAO and "sem material" in txt and "PARCIAL" in txt
    assert "NÃO foram verificadas" in txt and "NAO_EXECUTADO" in txt                # interferência não rodou: dito explicitamente
    assert all(not c.material for c in p.components.leaves())                       # a verificação NÃO atribuiu nada
    assert "não é IA generativa" in txt


def test_material_inexistente_e_critico_e_massa_completa(motor_project):
    p = motor_project
    folhas = p.components.leaves()
    folhas[0].material = "Unobtainium"
    assert verificar_projeto(p).pior() == CRITICO
    nome = p.materials.names()[0]
    for c in folhas:
        c.material = nome
    pr = verificar_projeto(p, clashes=[])
    assert not any(a.nivel == CRITICO for a in pr.achados)
    assert any("Massa total calculada de todas" in a.texto for a in pr.achados)
    assert any("Nenhuma interferência" in a.texto for a in pr.achados)
    p.dirty = True
    assert any("não salvas" in a.texto for a in verificar_projeto(p, clashes=[1, 2]).achados)
    assert any("2 interferência" in a.texto for a in verificar_projeto(p, clashes=[1, 2]).achados)
