"""Projeto .nexus (salvar/abrir), exportação, seleção, visibilidade e agrupamento."""
import json
import zipfile

import numpy as np
import pytest

from core.model import ComponentKind, GeometryKind
from core.project_manager import FORMAT_VERSION, ProjectError, ProjectManager
from modules.component_inspector import ComponentInspector
from modules.explode_engine import ExplodeParams
from modules.exporter import ExportError, Exporter
from modules.importer import ProjectImporter
from modules.selection_manager import SelectionManager
from modules.solid_analyzer import split_into_solids, undo_split
from tests.conftest import find


def snapshot(project):
    return [(n.id, n.name, n.kind, n.geometry_kind, n.visible, n.material,
             tuple(np.round(n.offset, 9)), n.parent.id if n.parent else None)
            for n in project.components.root.walk()]


# ------------------------------------------------------------------ salvar/abrir
def test_save_open_roundtrip_preserves_everything(engine, motor_project, tmp_path):
    pm = ProjectManager(engine)
    proj = motor_project
    comps, asm = proj.components, proj.assembly
    comps.set_material(find(proj, "Bloco").id, "Aço carbono")
    proj.materials.add_custom("Liga X", 3.3)
    comps.set_material(find(proj, "Virabrequim").id, "Liga X")
    comps.set_visible(find(proj, "Pistao #2").id, False)
    asm.apply_offsets(asm.target_explode_all(ExplodeParams(factor=1.2)))
    proj.log("Explosão", "fator 1,2")
    before = snapshot(proj)
    vol = ComponentInspector(comps, proj.materials).inspect(find(proj, "Bloco")).volume

    saved = pm.save(proj, tmp_path / "motor")           # sem extensão -> .nexus
    assert saved.suffix == ".nexus" and saved.exists() and not proj.dirty
    assert not list(tmp_path.glob("*.tmp"))             # gravação atômica não deixa lixo

    again = pm.open(saved)
    assert snapshot(again) == before                     # árvore, ids, offsets, visibilidade, material
    assert again.name == proj.name and not again.dirty and again.path == saved
    assert again.materials.get("Liga X").density_g_cm3 == pytest.approx(3.3)
    rep = ComponentInspector(again.components, again.materials).inspect(find(again, "Bloco"))
    assert rep.volume == pytest.approx(vol) and rep.mass == pytest.approx(vol / 1000 * 7.85)
    actions = [h.action for h in again.history.entries]
    assert "Explosão" in actions and "Projeto salvo" in actions and actions[-1] == "Projeto aberto"
    # a explosão salva pode ser restaurada exatamente
    again.assembly.restore()
    assert again.assembly.verify_restored()
    # novos ids não colidem com os carregados
    new_id = again.ids.next()
    assert new_id not in {n.id for n in again.components.root.walk()}


def test_save_open_mesh_project_and_split_undo(engine, stl_file, tmp_path):
    pm = ProjectManager(engine)
    proj = pm.new_project("malha")
    res = ProjectImporter(engine, proj.ids).import_file(stl_file)
    proj.set_root(res.root)
    part = next(res.root.leaves())
    n_faces = len(part.mesh.faces)
    split_into_solids(part, engine, proj.ids)
    proj.components.reindex()

    again = pm.open(pm.save(proj, tmp_path / "malha.nexus"))
    group = next(n for n in again.components.root.walk() if n.metadata.get("split_from_composite"))
    assert group.kind == ComponentKind.GROUP and len(group.children) == 2
    assert sum(len(c.mesh.faces) for c in group.children) == n_faces
    undo_split(group)                                    # backup sobreviveu ao salvamento
    assert len(group.mesh.faces) == n_faces and group.geometry_kind == GeometryKind.MESH_MULTI


def test_save_without_path_and_dirty_tracking(engine):
    pm = ProjectManager(engine)
    proj = pm.new_project("vazio")
    with pytest.raises(ProjectError, match="Salvar como"):
        pm.save(proj)
    assert proj.dirty and proj.title.endswith("•")       # criado = não salvo ainda


def test_save_as_creates_new_file_and_keeps_old(engine, motor_project, tmp_path):
    pm = ProjectManager(engine)
    a = pm.save(motor_project, tmp_path / "a.nexus")
    find(motor_project, "Bloco").name = "Bloco B"
    b = pm.save(motor_project, tmp_path / "b.nexus")     # "Salvar como"
    assert a != b and motor_project.path == b
    assert any(n.name == "Bloco" for n in pm.open(a).components.all())
    assert any(n.name == "Bloco B" for n in pm.open(b).components.all())


def test_open_errors(engine, tmp_path):
    pm = ProjectManager(engine)
    with pytest.raises(ProjectError, match="não encontrado"):
        pm.open(tmp_path / "x.nexus")
    bad = tmp_path / "ruim.nexus"
    bad.write_text("não é zip")
    with pytest.raises(ProjectError, match="corrompido"):
        pm.open(bad)
    nojson = tmp_path / "semjson.nexus"
    with zipfile.ZipFile(nojson, "w") as zf:
        zf.writestr("x.txt", "x")
    with pytest.raises(ProjectError, match="não é um projeto"):
        pm.open(nojson)
    wrong = tmp_path / "versao.nexus"
    with zipfile.ZipFile(wrong, "w") as zf:
        zf.writestr("project.json", json.dumps({"nexus_format": FORMAT_VERSION + 5}))
    with pytest.raises(ProjectError, match="Versão"):
        pm.open(wrong)
    broken = tmp_path / "quebrado.nexus"
    with zipfile.ZipFile(broken, "w") as zf:
        zf.writestr("project.json", json.dumps({"nexus_format": FORMAT_VERSION, "root": {"id": "C1"}}))
    with pytest.raises(ProjectError):
        pm.open(broken)


# ---------------------------------------------------------------------- exportar
def test_export_step_roundtrip_hierarchy_and_volumes(engine, motor_project, tmp_path):
    ex = Exporter(engine)
    res = ex.export(motor_project, tmp_path / "saida.step")
    assert res.format == "STEP" and res.exported == 7 and not res.skipped
    reimported = ProjectImporter(engine).import_file(res.path)
    names = [n.name for n in reimported.root.walk()]
    for expected in ("Bloco", "Pistoes", "Virabrequim", "Eixo composto", "Pistao", "Pistao #4"):
        assert expected in names
    vol_in = sum(engine.properties(l.shape).volume for l in motor_project.components.leaves())
    vol_out = sum(engine.properties(l.shape).volume for l in reimported.root.leaves())
    assert vol_out == pytest.approx(vol_in)


def test_export_step_exploded_vs_assembled(engine, motor_project, tmp_path):
    asm = motor_project.assembly
    asm.apply_offsets(asm.target_explode_all(ExplodeParams(factor=1.0)))
    ex = Exporter(engine)
    rest = ProjectImporter(engine).import_file(ex.export(motor_project, tmp_path / "montada.step").path)
    boom = ProjectImporter(engine).import_file(
        ex.export(motor_project, tmp_path / "explodida.step", include_explosion=True).path)
    def extent(res):
        boxes = [engine.bbox(l.shape) for l in res.root.leaves()]
        return np.max([b.max for b in boxes], axis=0) - np.min([b.min for b in boxes], axis=0)
    assert np.all(extent(boom) >= extent(rest) - 1e-6) and np.linalg.norm(extent(boom)) > np.linalg.norm(extent(rest)) * 1.05
    # a montagem original do projeto não foi alterada pela exportação
    assert asm.is_exploded()


def test_export_only_visible_and_mesh_limits(engine, motor_project, obj_file, tmp_path):
    ex = Exporter(engine)
    comps = motor_project.components
    comps.set_visible(find(motor_project, "Pistoes").id, False)
    res = ex.export(motor_project, tmp_path / "visiveis.step", only_visible=True)
    assert res.exported == 3                              # bloco, virabrequim, eixo composto
    # malhas não viram STEP: erro claro
    pm = ProjectManager(engine)
    mesh_proj = pm.new_project("malha")
    mesh_proj.set_root(ProjectImporter(engine, mesh_proj.ids).import_file(obj_file).root)
    with pytest.raises(ExportError, match="malhas"):
        ex.export(mesh_proj, tmp_path / "malha.step")


def test_export_stl_and_obj(engine, motor_project, tmp_path):
    ex = Exporter(engine)
    stl = ex.export(motor_project, tmp_path / "t.stl")
    obj = ex.export(motor_project, tmp_path / "t.obj")
    assert stl.exported == obj.exported == 7
    objects = ProjectImporter(engine).import_file(obj.path)
    assert len(objects.root.children) == 7 and {c.name for c in objects.root.children} >= {"Bloco", "Pistao #4"}
    stl_back = ProjectImporter(engine).import_file(stl.path)
    total_tris = sum(len(motor_project.components.render_mesh(l).faces) for l in motor_project.components.leaves())
    assert len(next(stl_back.root.leaves()).mesh.faces) == total_tris
    with pytest.raises(ExportError, match="não suportado"):
        ex.export(motor_project, tmp_path / "t.dwg")


# ----------------------------------------------------------------------- seleção
def test_selection_notifies_with_source_and_dedupes():
    sel, events = SelectionManager(), []
    sel.subscribe(lambda ids, src: events.append((ids, src)))
    sel.select("C1", source="tree")
    sel.select("C1", source="tree")                      # igual: sem novo evento
    sel.select(["C2", "C3"], source="viewport", additive=True)
    assert events == [(["C1"], "tree"), (["C1", "C2", "C3"], "viewport")]
    assert sel.primary == "C3"
    sel.toggle("C2", "tree")
    assert sel.selected == ["C1", "C3"]
    sel.prune({"C1"}, "api")
    assert sel.selected == ["C1"]
    sel.clear()
    assert sel.selected == [] and sel.primary is None


# ----------------------------------------------------- visibilidade e agrupamento
def test_visibility_isolate_and_show_all(motor_project):
    comps = motor_project.components
    pist = find(motor_project, "Pistoes")
    comps.set_visible(pist.id, False)                     # recursivo
    assert all(not c.visible for c in pist.walk())
    assert not comps.is_effectively_visible(find(motor_project, "Pistao"))
    comps.isolate([find(motor_project, "Bloco").id])
    bloco = find(motor_project, "Bloco")
    assert comps.is_effectively_visible(bloco)             # contêineres ficam visíveis
    assert [l.name for l in comps.leaves() if comps.is_effectively_visible(l)] == ["Bloco"]
    assert len(comps.show_all()) == len(list(comps.root.walk())) - 3   # raiz + Motor + Bloco já visíveis
    assert comps.counts()["hidden"] == 0
    with pytest.raises(KeyError):
        comps.get("inexistente")


def test_group_and_ungroup_components(motor_project):
    asm, comps = motor_project.assembly, motor_project.components
    bloco, vira = find(motor_project, "Bloco"), find(motor_project, "Virabrequim")
    group = asm.group_components([bloco.id, vira.id], "Bloco + virabrequim")
    assert group.kind == ComponentKind.GROUP and bloco.parent is group and vira.parent is group
    assert comps.get(group.id) is group
    asm.apply_offsets(asm.target_explode_group(group.id, ExplodeParams()))
    with pytest.raises(ValueError, match="Restaure"):
        asm.ungroup(group.id)
    asm.restore()
    asm.ungroup(group.id)
    assert bloco.parent is comps.root.children[0] and comps.find(group.id) is None
    with pytest.raises(ValueError, match="ao menos dois"):
        asm.group_components([bloco.id], "x")
    with pytest.raises(ValueError, match="raiz"):
        asm.group_components([comps.root.id, bloco.id], "x")


def test_isolate_keeps_ancestors_visible(motor_project):
    comps = motor_project.components
    leaf = comps.leaves()[0]
    comps.isolate([leaf.id])
    assert comps.is_effectively_visible(leaf)
    assert sum(comps.is_effectively_visible(l) for l in comps.leaves()) == 1


# ----------------------------------------------------------------- FCStd (escrita)
def test_fcstd_export_roundtrip(motor_project, engine, tmp_path):
    from modules.component_inspector import ComponentInspector
    from modules.importer import ProjectImporter
    from modules.exporter import Exporter
    comps = motor_project.components
    comps.set_visible(find(motor_project, "Bloco").id, False)
    res = Exporter(engine).export(motor_project, tmp_path / "saida.FCStd")
    assert res.format == "FCStd" and res.exported == len(comps.leaves()) and not res.skipped
    again = ProjectImporter(engine, motor_project.ids.__class__()).import_file(str(tmp_path / "saida.FCStd"))
    leaves_a = sorted(l.name for l in again.root.leaves())
    leaves_b = sorted(l.name for l in comps.leaves())
    assert leaves_a == leaves_b                                   # nomes (com acento) e hierarquia de peças
    vol = lambda root, name: engine.properties(next(l for l in root.leaves() if l.name == name).shape).volume  # noqa: E731
    assert vol(again.root, "Pistao") == pytest.approx(vol(comps.root, "Pistao"), rel=1e-6)
    assert not next(l for l in again.root.leaves() if l.name == "Bloco").visible    # visibilidade preservada
    # grupos preservados
    assert [n.name for n in again.root.walk() if not n.has_geometry and n is not again.root]


def test_fcstd_export_rejects_meshes(engine, tmp_path, stl_file):
    from modules.importer import ProjectImporter
    from modules.exporter import Exporter, ExportError
    from core.project_manager import ProjectManager
    pm = ProjectManager(engine)
    proj = pm.new_project("m")
    proj.set_root(ProjectImporter(engine, proj.ids).import_file(str(stl_file)).root)
    with pytest.raises(ExportError, match="malhas"):
        Exporter(engine).export(proj, tmp_path / "x.FCStd")
