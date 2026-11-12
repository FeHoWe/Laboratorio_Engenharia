import numpy as np
from core.cad_engine import RawNode
from core.geometry import translation_matrix
from modules.importer import ProjectImporter
from modules.interference_sweep import sweep, to_csv
from modules.kinematics import Link, Mechanism
from samples import geo as g


def _components(engine, tmp_path):
    L = lambda n, s: RawNode(n, shape=s, local_matrix=translation_matrix([0, 0, 0]))
    root = RawNode("t", children=[L("Fixa", g.box(0, 20, 0, 20, 0, 20)), L("Movel", g.box(40, 60, 0, 20, 0, 20)), L("Longe", g.box(200, 220, 0, 20, 0, 20))])
    p = tmp_path / "m.step"
    engine.write_step([root], p)
    from core.project_manager import ProjectManager
    project = ProjectManager(engine).new_project("t")
    project.set_root(ProjectImporter(engine, project.ids).import_file(str(p)).root)
    return project.components


def test_sweep_detects_collision_only_during_motion(engine, tmp_path):
    comps = _components(engine, tmp_path)
    mov = next(l for l in comps.leaves() if l.name == "Movel")
    # desliza em −x: 90° → x=10..30 (sobreposição 10·20·20 = 4000 mm³); 120° → x=0..20 (8000 mm³)
    def pose(theta):
        m = np.eye(4)
        m[0, 3] = -30.0 * theta / 90.0
        return m
    mech = Mechanism("teste", "θ", 360.0, links=[Link([mov.id], pose)])
    rows = sweep(comps, mech, [0, 30, 60, 90, 120], min_volume=1.0)
    assert len(rows) == 1
    r = rows[0]
    assert {r.a_name, r.b_name} == {"Fixa", "Movel"}
    assert r.base_volume == 0.0 and abs(r.max_volume - 8000.0) < 1.0
    assert r.theta_at_max == 120.0 and r.first_theta == 90.0          # 60°: x=10..30? não: 60° → x=20..40 (só toca, volume 0)
    assert "Fixa" in to_csv(rows)


def test_sweep_ignores_static_overlaps(engine, tmp_path):
    comps = _components(engine, tmp_path)
    mov = next(l for l in comps.leaves() if l.name == "Longe")
    mech = Mechanism("parado", "θ", 360.0, links=[Link([mov.id], lambda th: np.eye(4))])
    assert sweep(comps, mech, [0, 90, 180]) == []
