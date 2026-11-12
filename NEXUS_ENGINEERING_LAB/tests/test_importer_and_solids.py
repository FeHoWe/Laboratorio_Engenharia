"""Importação (STEP/STL/OBJ/FCStd), identificação e separação de sólidos."""
import zipfile

import numpy as np
import pytest

from core.model import ComponentKind, GeometryKind, IdGenerator
from modules.importer import ImportFailure, ProjectImporter, parse_obj
from modules.solid_analyzer import (analyze_tree, can_split, classify, mesh_body_labels,
                                    split_into_solids, undo_split)
from tests.conftest import find


@pytest.fixture
def importer(engine):
    return ProjectImporter(engine, IdGenerator())


def names(root):
    return [n.name for n in root.walk()]


# ------------------------------------------------------------------------ STEP
def test_step_builds_real_hierarchy(importer, step_file):
    r = importer.import_file(step_file)
    assert r.format == "STEP" and r.preserves_hierarchy
    motor = r.root.children[0]
    assert motor.name == "Motor" and motor.kind == ComponentKind.ASSEMBLY
    assert [c.name for c in motor.children] == ["Bloco", "Pistoes", "Virabrequim", "Eixo composto"]
    pistons = motor.children[1]
    assert pistons.kind == ComponentKind.ASSEMBLY
    assert [c.name for c in pistons.children] == ["Pistao", "Pistao #2", "Pistao #3", "Pistao #4"]


def test_step_instances_have_distinct_geometry_and_placement(importer, engine, step_file):
    r = importer.import_file(step_file)
    pistons = [n for n in r.root.walk() if n.name.startswith("Pistao")]
    xs = sorted(round(engine.bbox(p.shape).center[0]) for p in pistons)
    assert xs == [20, 40, 60, 80]
    assert sorted(round(p.placement[0, 3]) for p in pistons) == [20, 40, 60, 80]
    assert len({p.id for p in r.root.walk()}) == len(names(r.root))  # ids únicos


def test_step_report_distinguishes_solid_kinds(importer, step_file):
    r = importer.import_file(step_file)
    rep = r.report
    assert len(rep.multi_solid) == 1                       # só o "Eixo composto"
    assert len(rep.single_solid) == 6                      # bloco, 4 pistões, virabrequim
    assert len(rep.assemblies) == 2 and rep.has_splittable  # raiz do projeto não conta
    eixo = next(n for n in r.root.walk() if n.name == "Eixo composto")
    assert eixo.geometry_kind == GeometryKind.MULTI_SOLID and can_split(eixo)


# ------------------------------------------------------------------------- STL
def test_stl_is_one_object_but_bodies_are_identified(importer, stl_file):
    r = importer.import_file(stl_file)
    assert r.format == "STL" and not r.preserves_hierarchy
    parts = list(r.root.leaves())
    assert len(parts) == 1 and parts[0].geometry_kind == GeometryKind.MESH_MULTI
    assert r.report.has_splittable
    assert r.warnings  # explica a limitação do formato


def test_mesh_body_labels_counts_components(importer, stl_file):
    part = next(importer.import_file(stl_file).root.leaves())
    labels = mesh_body_labels(part.mesh)
    assert sorted(set(labels.tolist())) == [0, 1]


# ------------------------------------------------------------------------- OBJ
def test_obj_objects_quads_and_negative_indices(importer, obj_file):
    r = importer.import_file(obj_file)
    assert r.preserves_hierarchy
    bloco, eixo = r.root.children
    assert (bloco.name, eixo.name) == ("Bloco", "Eixo")
    assert len(bloco.mesh.faces) == 6            # 3 quads -> 6 triângulos
    assert len(eixo.mesh.faces) == 2 and len(eixo.mesh.vertices) == 4
    assert bloco.geometry_kind == GeometryKind.MESH and eixo.geometry_kind == GeometryKind.MESH


def test_obj_invalid_reference(tmp_path):
    bad = tmp_path / "ruim.obj"
    bad.write_text("o X\nv 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 9\n", encoding="utf-8")
    with pytest.raises(ImportFailure, match="inexistentes"):
        parse_obj(bad)
    bad.write_text("o X\nv 0 abc 0\n", encoding="utf-8")
    with pytest.raises(ImportFailure, match="inválido"):
        parse_obj(bad)


# ----------------------------------------------------------------------- FCStd
def test_fcstd_groups_parts_placement_visibility(importer, engine, fcstd_file):
    r = importer.import_file(fcstd_file)
    assert r.format == "FCStd" and r.preserves_hierarchy
    top = {c.name: c for c in r.root.children}
    assert set(top) == {"Grupo Um", "Parte Montada", "Base oculta"}   # esboço ignorado
    assert top["Grupo Um"].kind == ComponentKind.GROUP
    assert [c.name for c in top["Grupo Um"].children] == ["Caixa", "Cilindro"]
    assert top["Parte Montada"].kind == ComponentKind.ASSEMBLY
    wedge = top["Parte Montada"].children[0]
    assert engine.bbox(wedge.shape).min[0] == pytest.approx(500.0)     # Placement do App::Part aplicado
    assert not top["Base oculta"].visible                               # GuiDocument.xml respeitado
    assert top["Grupo Um"].children[0].parametric                       # Part::Box
    assert not wedge.parametric                                         # Part::Feature
    assert any("paramétricos" in w for w in r.warnings)


# ------------------------------------------------------------------------ erros
def test_import_errors(importer, tmp_path):
    with pytest.raises(ImportFailure, match="não encontrado"):
        importer.import_file(tmp_path / "x.step")
    other = tmp_path / "modelo.dwg"
    other.write_text("x")
    with pytest.raises(ImportFailure, match="não suportado"):
        importer.import_file(other)
    empty = tmp_path / "vazio.stl"
    empty.write_bytes(b"")
    with pytest.raises(ImportFailure, match="vazio"):
        importer.import_file(empty)
    garbage = tmp_path / "lixo.step"
    garbage.write_text("conteúdo qualquer")
    with pytest.raises(ImportFailure):
        importer.import_file(garbage)
    notzip = tmp_path / "ruim.FCStd"
    notzip.write_text("não sou zip")
    with pytest.raises(ImportFailure, match="corrompido"):
        importer.import_file(notzip)
    nodoc = tmp_path / "semdoc.FCStd"
    with zipfile.ZipFile(nodoc, "w") as zf:
        zf.writestr("outra.txt", "x")
    with pytest.raises(ImportFailure, match="Document.xml"):
        importer.import_file(nodoc)
    emptystl = tmp_path / "sem_triangulos.stl"
    emptystl.write_text("solid vazio\nendsolid vazio\n")
    with pytest.raises(ImportFailure):
        importer.import_file(emptystl)


# --------------------------------------------------------- separação de sólidos
def test_split_brep_preserves_exact_geometry_and_is_reversible(engine, importer, step_file):
    root = importer.import_file(step_file).root
    eixo = next(n for n in root.walk() if n.name == "Eixo composto")
    original_shape = eixo.shape
    vol_before = engine.properties(eixo.shape).volume
    ids = importer.ids

    children = split_into_solids(eixo, engine, ids)
    assert len(children) == 2 and eixo.kind == ComponentKind.GROUP and eixo.shape is None
    assert [c.name for c in children] == ["Eixo composto · sólido 1", "Eixo composto · sólido 2"]
    assert all(c.geometry_kind == GeometryKind.SOLID for c in children)
    assert sum(engine.properties(c.shape).volume for c in children) == pytest.approx(vol_before)
    assert all(c.parent is eixo for c in children)
    assert len({c.id for c in root.walk()}) == len(list(root.walk()))

    removed = undo_split(eixo)
    assert sorted(removed) == sorted(c.id for c in children)
    assert eixo.shape is original_shape and eixo.kind == ComponentKind.PART
    assert eixo.geometry_kind == GeometryKind.MULTI_SOLID and not eixo.children


def test_single_solid_is_never_split(engine, importer, step_file):
    bloco = next(n for n in importer.import_file(step_file).root.walk() if n.name == "Bloco")
    assert not can_split(bloco)
    with pytest.raises(ValueError, match="não contém vários"):
        split_into_solids(bloco, engine, importer.ids)
    with pytest.raises(ValueError, match="nada a desfazer"):
        undo_split(bloco)


def test_split_mesh_bodies(engine, importer, stl_file):
    part = next(importer.import_file(stl_file).root.leaves())
    total_faces = len(part.mesh.faces)
    kids = split_into_solids(part, engine, importer.ids)
    assert len(kids) == 2 and sum(len(k.mesh.faces) for k in kids) == total_faces
    assert all(k.geometry_kind == GeometryKind.MESH for k in kids)
    # corpos separados continuam na posição original (caixa de um centrada na origem)
    boxes = sorted(k.mesh.vertices.min(axis=0)[0] for k in kids)
    assert boxes[0] == pytest.approx(-5.0)
    undo_split(part)
    assert len(part.mesh.faces) == total_faces and part.geometry_kind == GeometryKind.MESH_MULTI


def test_connected_fused_solid_is_not_cut(engine, importer):
    """Dois volumes fundidos viram UM sólido: não pode ser dividido."""
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
    from tests import fixtures
    fused = BRepAlgoAPI_Fuse(fixtures.box(10, 10, 10), fixtures.box(10, 10, 10, at=(5, 0, 0))).Shape()
    from core.model import Component
    comp = Component(id="Cx", name="fundido", shape=fused)
    assert engine.count_solids(fused) == 1
    assert classify(comp, engine) == GeometryKind.SOLID and not can_split(comp)
