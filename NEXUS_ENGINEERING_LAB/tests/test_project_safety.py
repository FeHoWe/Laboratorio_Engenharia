"""V4.0: autosave sem efeito colateral, recuperação após encerramento inesperado, versões e comparação, backup ao salvar."""
import json
import os

import pytest

from core import project_safety as PS
from core.cad_engine import CadEngine
from core.project_manager import ProjectError, ProjectManager


@pytest.fixture()
def pm():
    return ProjectManager(CadEngine())


def _projeto_com_peca(pm, nome="P"):
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from core.model import Component, ComponentKind, GeometryKind
    proj = pm.new_project(nome)
    c = Component(id=proj.ids.next(), name="Bloco", kind=ComponentKind.PART, shape=BRepPrimAPI_MakeBox(10, 20, 30).Shape(), geometry_kind=GeometryKind.SOLID)
    proj.components.root.add_child(c)
    proj.dirty = True
    return proj, c


def test_autosave_nao_altera_o_projeto_aberto(pm, tmp_path):
    proj, _ = _projeto_com_peca(pm)
    h0 = len(proj.history.entries)
    a = PS.AutoSaver(pm, tmp_path / "rec", sessao="t1")
    arq = a.gravar(proj)
    assert arq.is_file() and (tmp_path / "rec" / "t1.json").is_file()
    assert proj.path is None and proj.dirty is True and len(proj.history.entries) == h0
    assert not (tmp_path / "rec" / "backups").exists()
    a.limpar()
    assert not arq.exists() and PS.pendentes(tmp_path / "rec") == []


def test_projeto_vazio_e_limpo_nao_gera_autosave(pm, tmp_path):
    proj = pm.new_project("vazio"); proj.dirty = False
    assert PS.AutoSaver(pm, tmp_path, sessao="v").gravar(proj) is None


def test_recuperacao_apos_encerramento_inesperado(pm, tmp_path):
    proj, _ = _projeto_com_peca(pm, "Perdido")
    rec = tmp_path / "rec"
    a = PS.AutoSaver(pm, rec, sessao="morto")
    a.gravar(proj)
    meta = json.loads(a.meta.read_text()); meta["pid"] = 2 ** 22 + 12345; a.meta.write_text(json.dumps(meta))   # processo que não existe mais
    vivo = PS.AutoSaver(pm, rec, sessao="vivo"); vivo.gravar(proj)                                              # esta sessão (pid atual) NÃO é pendente
    pend = PS.pendentes(rec)
    assert [p.sessao for p in pend] == ["morto"]
    rec_proj = PS.abrir_pendente(pm, pend[0])
    assert rec_proj.dirty and len(rec_proj.components.leaves()) == 1 and rec_proj.components.leaves()[0].name == "Bloco"
    PS.descartar_pendente(pend[0])
    assert PS.pendentes(rec) == []


def test_salvar_cria_backup_da_versao_anterior(pm, tmp_path):
    proj, _ = _projeto_com_peca(pm)
    alvo = tmp_path / "p.nexus"
    pm.save(proj, alvo)
    assert not (tmp_path / "backups").exists()
    pm.save(proj, alvo)
    assert len(list((tmp_path / "backups").glob("p.nexus.*.bak"))) == 1


def test_versoes_listar_comparar_restaurar(pm, tmp_path):
    proj, c = _projeto_com_peca(pm)
    alvo = tmp_path / "p.nexus"
    pm.save(proj, alvo)
    v1 = PS.salvar_versao(alvo, "primeira / versão!")
    c.material = "Aço teste"; c.name = "Bloco B"
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    c.shape = BRepPrimAPI_MakeBox(11, 20, 30).Shape()
    extra = type(c)(id=proj.ids.next(), name="Novo", kind=c.kind, shape=BRepPrimAPI_MakeBox(1, 1, 1).Shape(), geometry_kind=c.geometry_kind)
    proj.components.root.add_child(extra)
    pm.save(proj, alvo)
    v2 = PS.salvar_versao(alvo, "segunda")
    vs = PS.listar_versoes(alvo)
    assert [v["nota"] for v in vs] == ["primeira versão", "segunda"]
    d = PS.comparar(v1, v2)
    assert d["acrescentados"] == ["Novo"] and d["renomeados"] == [("Bloco", "Bloco B")]
    assert d["material"] == [("Bloco B", None, "Aço teste")] and "Bloco B" in d["geometria"] and not d["iguais"]
    assert PS.comparar(v1, v1)["iguais"] is True
    PS.restaurar_versao(alvo, v1)
    assert PS.comparar(alvo, v1)["iguais"] is True
    assert list((tmp_path / "backups").glob("p.nexus.*.bak"))            # o estado anterior à restauração foi guardado


def test_erros_tratados(pm, tmp_path):
    with pytest.raises(ProjectError):
        PS.salvar_versao(tmp_path / "nao_existe.nexus")
    ruim = tmp_path / "x.nexus"; ruim.write_bytes(b"nao e zip")
    with pytest.raises(ProjectError):
        PS.comparar(ruim, ruim)
    with pytest.raises(ProjectError):
        PS.restaurar_versao(tmp_path / "p.nexus", tmp_path / "nada.nexus")
