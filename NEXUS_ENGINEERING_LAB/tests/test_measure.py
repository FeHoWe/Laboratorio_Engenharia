import numpy as np
import pytest

from modules.explode_engine import ExplodeParams
from modules.measure_engine import MeasureEngine
from tests.conftest import find


def test_exact_distance_between_boxes(engine):
    from tests.fixtures import box
    from core.model import Component, ComponentKind
    a = Component(id="A", name="A", kind=ComponentKind.PART, shape=box(10, 10, 10))
    b = Component(id="B", name="B", kind=ComponentKind.PART, shape=engine.transform(box(10, 10, 10), np.array(
        [[1, 0, 0, 25], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1.0]])))
    d, pa, pb = engine.min_distance(a.shape, b.shape)
    assert d == pytest.approx(15.0)
    assert abs(pb[0] - pa[0]) == pytest.approx(15.0)


def test_touching_parts_report_contact(engine):
    from tests.fixtures import box
    assert engine.min_distance(box(10, 10, 10), box(10, 10, 10))[0] == pytest.approx(0.0, abs=1e-9)


def test_measure_in_motor_assembly_and_after_explosion(motor_project):
    comps = motor_project.components
    bloco, pistao = find(motor_project, "Bloco"), find(motor_project, "Pistao")
    me = MeasureEngine(comps)
    before = me.measure(bloco, pistao)
    assert before.exact and before.min_distance is not None and before.center_distance > 0
    assert before.original_min_distance is None            # nada deslocado ainda
    motor_project.assembly.apply_offsets(motor_project.assembly.target_explode_all(ExplodeParams(factor=1.0)))
    after = me.measure(bloco, pistao)
    assert after.original_min_distance == pytest.approx(before.min_distance, abs=1e-6)
    assert after.min_distance >= before.min_distance - 1e-6
    assert after.center_distance > before.center_distance
    assert "mm" in after.summary()


def test_measure_rejects_same_and_groups(motor_project):
    me = MeasureEngine(motor_project.components)
    bloco = find(motor_project, "Bloco")
    with pytest.raises(ValueError):
        me.measure(bloco, bloco)
    with pytest.raises(ValueError):
        me.measure(bloco, find(motor_project, "Pistoes"))


def test_mesh_measure_is_marked_approximate(engine, stl_file):
    from core.project_manager import ProjectManager
    from modules.importer import ProjectImporter
    pr = ProjectManager(engine).new_project("m")
    pr.set_root(ProjectImporter(engine, pr.ids).import_file(str(stl_file)).root)
    leaves = pr.components.leaves()
    assert len(leaves) >= 1
    # um corpo de malha contra si mesmo deslocado: usa a mesma malha duas vezes via componentes distintos
    from copy import copy
    a = leaves[0]
    b = copy(a); b.id = "X"; b.name = "cópia"; b.offset = np.array([100.0, 0, 0])
    m = MeasureEngine(pr.components).measure(a, b)
    assert not m.exact and m.min_distance is not None and any("aproximada" in n for n in m.notes)


def test_diameters_and_axes(motor_project):
    from modules.measure_engine import MeasureEngine
    me = MeasureEngine(motor_project.components)
    d = me.diameters(find(motor_project, "Pistao"))
    assert len(d) == 1 and d[0].diameter == pytest.approx(16.0) and d[0].axis_label == "Z"
    v = me.diameters(find(motor_project, "Virabrequim"))
    assert v[0].diameter == pytest.approx(12.0) and v[0].axis_label == "X"
    assert me.diameters(find(motor_project, "Bloco")) == []          # caixa: sem cilindros


def test_angle_between_crank_and_piston_is_90(motor_project):
    from modules.measure_engine import MeasureEngine
    me = MeasureEngine(motor_project.components)
    r = me.angle(find(motor_project, "Virabrequim"), find(motor_project, "Pistao"))
    assert r.angle_deg == pytest.approx(90.0, abs=1e-6) and "cilindro" in r.basis_a
    same = me.angle(find(motor_project, "Pistao"), [l for l in motor_project.components.leaves() if l.name == "Pistao #2"][0])
    assert same.angle_deg == pytest.approx(0.0, abs=1e-6)
    box = me.angle(find(motor_project, "Bloco"), find(motor_project, "Virabrequim"))     # normal de face plana x eixo X
    assert box.angle_deg is not None and 0 <= box.angle_deg <= 90


def test_angle_tilted_cylinder(engine):
    from tests.fixtures import cylinder
    from core.model import Component, ComponentKind
    a = Component(id="A", name="A", kind=ComponentKind.PART, shape=cylinder(5, 20, axis=(0, 0, 1)))
    b = Component(id="B", name="B", kind=ComponentKind.PART, shape=cylinder(5, 20, axis=(0, 1, 1)))
    from core.component_manager import ComponentManager
    r = __import__("modules.measure_engine", fromlist=["x"]).MeasureEngine(ComponentManager(engine)).angle(a, b)
    assert r.angle_deg == pytest.approx(45.0, abs=1e-6)


def test_inspector_reports_diameters(motor_project):
    from modules.component_inspector import ComponentInspector
    rep = ComponentInspector(motor_project.components, motor_project.materials).inspect(find(motor_project, "Pistao"))
    assert rep.diameters and rep.diameters[0][0] == pytest.approx(16.0)
