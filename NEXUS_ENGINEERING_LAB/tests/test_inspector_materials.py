"""Component Inspector e biblioteca de materiais."""
import math

import numpy as np
import pytest

from core.model import Component, ComponentKind, GeometryKind, IdGenerator
from modules.component_inspector import ComponentInspector
from modules.importer import ProjectImporter
from modules.material_manager import MaterialLibrary
from modules.explode_engine import ExplodeParams
from tests import fixtures
from tests.conftest import find


@pytest.fixture
def inspector(motor_project):
    return ComponentInspector(motor_project.components, motor_project.materials)


def test_block_properties_come_from_real_geometry(motor_project, inspector):
    rep = inspector.inspect(find(motor_project, "Bloco"))
    assert rep.size == pytest.approx((100, 60, 40))               # comprimento X, largura Y, altura Z
    assert rep.volume == pytest.approx(240000.0)
    assert rep.area == pytest.approx(2 * (100 * 60 + 100 * 40 + 60 * 40))
    assert rep.centroid == pytest.approx((50, 30, 20))
    assert rep.node_kind == "Peça" and rep.geometry_type == "Sólido B-Rep"
    assert (rep.n_solids, rep.n_faces) == (1, 6) and rep.n_triangles == 12
    assert any("sem histórico" in n for n in rep.notes)           # importada, não paramétrica
    assert rep.rotation == pytest.approx((0, 0, 0))


def test_mass_requires_material_and_is_not_invented(motor_project, inspector):
    bloco = find(motor_project, "Bloco")
    rep = inspector.inspect(bloco)
    assert rep.mass is None and "material" in rep.mass_note.lower()
    assert rep.material is None and rep.density is None

    motor_project.components.set_material(bloco.id, "Aço carbono")
    rep = inspector.inspect(bloco)
    assert rep.mass == pytest.approx(240000 / 1000 * 7.85)         # 1884 g
    assert rep.material == "Aço carbono" and rep.density == pytest.approx(7.85)


def test_cylinder_volume_and_instance_position(motor_project, inspector):
    p3 = find(motor_project, "Pistao #3")
    rep = inspector.inspect(p3)
    assert rep.volume == pytest.approx(math.pi * 64 * 30, rel=1e-9)
    assert rep.position == pytest.approx((60, 30, 60))             # centro do pistão #3 no mundo
    assert rep.displacement == (0.0, 0.0, 0.0)
    assert (rep.part_count, rep.child_count) == (1, 0)


def test_position_follows_explosion_but_size_does_not(motor_project, inspector):
    p3 = find(motor_project, "Pistao #3")
    at_rest = inspector.inspect(p3)
    asm = motor_project.assembly
    asm.apply_offsets(asm.target_explode_all(ExplodeParams(factor=1.0)))
    exploded = inspector.inspect(p3)
    assert exploded.size == pytest.approx(at_rest.size)
    assert exploded.volume == pytest.approx(at_rest.volume)
    assert exploded.centroid == pytest.approx(at_rest.centroid)    # centroide = geometria original
    delta = np.array(exploded.position) - np.array(at_rest.position)
    assert np.allclose(delta, exploded.displacement) and np.linalg.norm(delta) > 0
    asm.restore()
    assert inspector.inspect(p3).position == pytest.approx(at_rest.position)


def test_group_aggregates_and_needs_all_materials(motor_project, inspector):
    pistons = find(motor_project, "Pistoes")
    rep = inspector.inspect(pistons)
    assert rep.node_kind == "Montagem" and rep.child_count == 4 and rep.part_count == 4
    assert rep.volume == pytest.approx(4 * math.pi * 64 * 30)
    assert rep.mass is None and "todas as peças" in rep.mass_note
    motor_project.components.set_material(pistons.id, "Alumínio (liga genérica)")
    rep = inspector.inspect(pistons)
    assert rep.mass == pytest.approx(4 * math.pi * 64 * 30 / 1000 * 2.70)
    assert rep.size == pytest.approx((8 * 2 + 60, 16, 30))         # pistões em x=20..80 com raio 8


def test_shell_has_no_volume_and_says_why(engine, motor_project):
    from OCP.TopAbs import TopAbs_FACE
    face = engine._unique_subshapes(fixtures.box(10, 10, 10), TopAbs_FACE)[0]
    comp = Component(id="Cface", name="superfície", shape=face)
    motor_project.components.root.add_child(comp)
    motor_project.components.reindex()
    comp.geometry_kind = GeometryKind.SHELL
    insp = ComponentInspector(motor_project.components, motor_project.materials)
    rep = insp.inspect(comp)
    assert rep.volume is None and rep.area == pytest.approx(100.0)
    assert "superfícies" in " ".join(rep.notes)
    motor_project.components.set_material("Cface", "Cobre")
    assert insp.inspect(comp).mass is None and "indisponível" in insp.inspect(comp).mass_note


def test_mesh_volume_only_when_watertight(engine, stl_file, obj_file):
    # STL: dois corpos fechados -> volume real da malha
    from core.project_manager import ProjectManager
    pm = ProjectManager(engine)
    proj = pm.new_project("m")
    res = ProjectImporter(engine, proj.ids).import_file(stl_file)
    proj.set_root(res.root)
    insp = ComponentInspector(proj.components, proj.materials)
    part = next(res.root.leaves())
    rep = insp.inspect(part)
    assert rep.volume == pytest.approx(1000 + math.pi * 9 * 20, rel=0.02)
    assert rep.geometry_type == "Malha com vários corpos desconexos"
    assert rep.n_solids is None and rep.n_triangles == len(part.mesh.faces)

    # OBJ: 3 quads abertos -> não existe volume nem massa
    proj2 = pm.new_project("o")
    res2 = ProjectImporter(engine, proj2.ids).import_file(obj_file)
    proj2.set_root(res2.root)
    insp2 = ComponentInspector(proj2.components, proj2.materials)
    bloco = res2.root.children[0]
    rep = insp2.inspect(bloco)
    assert rep.volume is None and rep.area == pytest.approx(300.0)
    assert any("não estanque" in n for n in rep.notes)
    proj2.components.set_material(bloco.id, "ABS")
    assert insp2.inspect(bloco).mass is None


def test_inspector_rotation_from_placement(motor_project, inspector):
    bloco = find(motor_project, "Bloco")
    m = np.eye(4)
    m[:3, :3] = [[0, -1, 0], [1, 0, 0], [0, 0, 1]]                 # rotação de 90° em Z
    bloco.placement = m
    assert inspector.inspect(bloco).rotation == pytest.approx((0, 0, 90))


# ------------------------------------------------------------------- materiais
def test_material_library_rules():
    lib = MaterialLibrary()
    assert lib.get("Aço carbono").density_g_cm3 == pytest.approx(7.85)
    assert lib.get(None) is None and lib.get("inexistente") is None
    custom = lib.add_custom("  Liga X  ", 3.3)
    assert custom.name == "Liga X" and not custom.builtin and lib.customs() == [custom]
    assert "Liga X" in lib.names()
    with pytest.raises(ValueError, match="nativo"):
        lib.add_custom("Aço carbono", 1.0)
    with pytest.raises(ValueError, match="maior que zero"):
        lib.add_custom("Ruim", 0)
    with pytest.raises(ValueError, match="nome"):
        lib.add_custom("  ", 1)
    assert MaterialLibrary.mass_g(1000.0, custom) == pytest.approx(3.3)   # 1 cm³ * 3,3 g/cm³
