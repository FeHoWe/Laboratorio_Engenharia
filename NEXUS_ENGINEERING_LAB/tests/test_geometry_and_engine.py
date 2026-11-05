"""Testes de core/geometry.py (NumPy) e core/cad_engine.py (OpenCascade)."""
import math

import numpy as np
import pytest
import trimesh

from core.cad_engine import CadEngine, CadEngineError, RawNode, ascii_fold, fix_text
from core.geometry import (BoundingBox, euler_from_matrix, identity, mesh_area, normalize,
                           smooth_vertex_normals, translation_matrix)
from tests import fixtures


# ------------------------------------------------------------------ geometry.py
def test_normalize_and_fallback():
    assert np.allclose(normalize([0, 3, 4]), [0, 0.6, 0.8])
    assert np.allclose(normalize([0, 0, 0], fallback=[1, 0, 0]), [1, 0, 0])
    assert np.allclose(normalize([0, 0, 0]), [0, 0, 0])


def test_bounding_box_properties_and_union():
    a = BoundingBox(np.array([0, 0, 0.0]), np.array([10, 20, 30.0]))
    b = a.translated([100, 0, 0])
    assert np.allclose(a.center, [5, 10, 15])
    assert np.allclose(a.size, [10, 20, 30])
    assert a.diagonal == pytest.approx(math.sqrt(100 + 400 + 900))
    u = BoundingBox.union([a, b, None])
    assert np.allclose(u.min, [0, 0, 0]) and np.allclose(u.max, [110, 20, 30])
    assert BoundingBox.union([None, None]) is None
    with pytest.raises(ValueError):
        BoundingBox.from_points(np.empty((0, 3)))


@pytest.mark.parametrize("rx,ry,rz", [(0, 0, 90), (30, 20, 10), (-45, 60, 170), (90, 0, 0)])
def test_euler_roundtrip(rx, ry, rz):
    a, b, c = (math.radians(v) for v in (rx, ry, rz))
    Rx = np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]])
    Ry = np.array([[math.cos(b), 0, math.sin(b)], [0, 1, 0], [-math.sin(b), 0, math.cos(b)]])
    Rz = np.array([[math.cos(c), -math.sin(c), 0], [math.sin(c), math.cos(c), 0], [0, 0, 1]])
    m = identity()
    m[:3, :3] = Rz @ Ry @ Rx
    assert euler_from_matrix(m) == pytest.approx((rx, ry, rz), abs=1e-6)


def test_euler_gimbal_lock_and_identity():
    assert euler_from_matrix(identity()) == pytest.approx((0, 0, 0))
    m = identity()
    m[:3, :3] = [[0, 0, 1], [0, 1, 0], [-1, 0, 0]]  # ry = 90°
    rx, ry, rz = euler_from_matrix(m)
    assert ry == pytest.approx(90.0)


def test_mesh_area_and_normals():
    v = np.array([[0, 0, 0], [2, 0, 0], [0, 2, 0.0]])
    f = np.array([[0, 1, 2]])
    assert mesh_area(v, f) == pytest.approx(2.0)
    n = smooth_vertex_normals(v, f)
    assert np.allclose(n, [[0, 0, 1]] * 3)
    assert smooth_vertex_normals(v, np.empty((0, 3), dtype=int)).shape == (3, 3)


# ---------------------------------------------------------------- cad_engine.py
def test_box_properties_exact(engine):
    shape = fixtures.box(10, 20, 30)
    p = engine.properties(shape)
    assert p.volume == pytest.approx(6000.0)
    assert p.area == pytest.approx(2200.0)
    assert np.allclose(p.centroid, [5, 10, 15])
    assert p.centroid_kind == "volume"
    bb = engine.bbox(shape)
    assert np.allclose(bb.size, [10, 20, 30])


def test_cylinder_volume_matches_formula(engine):
    shape = fixtures.cylinder(5, 40)
    assert engine.properties(shape).volume == pytest.approx(math.pi * 25 * 40, rel=1e-9)


def test_counts_on_compound(engine):
    comp = fixtures.compound(fixtures.box(1, 1, 1), fixtures.box(1, 1, 1, at=(5, 0, 0)))
    assert engine.count_solids(comp) == 2
    assert engine.count_faces(comp) == 12
    assert len(engine.solids(comp)) == 2


def test_face_only_shape_has_no_volume(engine):
    from OCP.TopAbs import TopAbs_FACE
    face = engine._unique_subshapes(fixtures.box(10, 10, 10), TopAbs_FACE)[0]
    p = engine.properties(face)
    assert p.volume is None and p.centroid_kind == "area"
    assert p.area == pytest.approx(100.0)


def test_tessellation_is_faithful(engine):
    box_mesh = engine.tessellate(fixtures.box(10, 20, 30))
    assert mesh_area(box_mesh.vertices, box_mesh.faces) == pytest.approx(2200.0)
    tm = trimesh.Trimesh(box_mesh.vertices, box_mesh.faces, process=True)
    assert tm.is_watertight and tm.volume == pytest.approx(6000.0)  # orientação correta (volume > 0)

    cyl_mesh = engine.tessellate(fixtures.cylinder(5, 40))
    tm = trimesh.Trimesh(cyl_mesh.vertices, cyl_mesh.faces, process=True)
    assert tm.volume == pytest.approx(math.pi * 25 * 40, rel=0.01)
    assert cyl_mesh.normals.shape == cyl_mesh.vertices.shape


def test_step_roundtrip_preserves_hierarchy_and_positions(engine, step_file):
    roots = engine.read_step(step_file)
    assert len(roots) == 1 and roots[0].name == "Motor"
    names = [c.name for c in roots[0].children]
    assert names == ["Bloco", "Pistoes", "Virabrequim", "Eixo composto"]
    pistons = roots[0].children[1]
    assert pistons.is_assembly and len(pistons.children) == 4
    xs = sorted(round(engine.bbox(p.shape).center[0]) for p in pistons.children)
    assert xs == [20, 40, 60, 80]  # cada instância na sua posição
    # a matriz acumulada da instância guarda a translação real
    assert sorted(round(p.world_matrix[0, 3]) for p in pistons.children) == [20, 40, 60, 80]


def test_shape_binary_roundtrip(engine, tmp_path):
    shape = fixtures.cylinder(3, 9)
    engine.write_shape_bin(shape, tmp_path / "s.bin")
    again = engine.read_shape_bin(tmp_path / "s.bin")
    assert engine.properties(again).volume == pytest.approx(engine.properties(shape).volume)


def test_transform_moves_geometry(engine):
    moved = engine.transform(fixtures.box(10, 10, 10), translation_matrix([100, 0, 0]))
    assert np.allclose(engine.bbox(moved).min, [100, 0, 0])


def test_read_errors_are_clear(engine, tmp_path):
    with pytest.raises(CadEngineError, match="não encontrado"):
        engine.read_step(tmp_path / "nao_existe.step")
    bad = tmp_path / "lixo.step"
    bad.write_text("isto não é um arquivo STEP", encoding="utf-8")
    with pytest.raises(CadEngineError):
        engine.read_step(bad)
    with pytest.raises(CadEngineError):
        engine.read_brep_file(bad)


def test_text_helpers():
    assert fix_text("Cilindro Ã§") == "Cilindro ç"      # UTF-8 lido como Latin-1
    assert fix_text("Pistão") == "Pistão"               # texto correto não é alterado
    assert fix_text(None) is None and fix_text("") == ""
    assert ascii_fold("Pistão de Alumínio") == "Pistao de Aluminio"
    assert ascii_fold("日本") == "peca"                  # nunca devolve nome vazio
