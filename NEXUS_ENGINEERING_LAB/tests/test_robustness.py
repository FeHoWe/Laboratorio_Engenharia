"""Entradas inválidas/extremas devem virar erro explícito (nunca NaN silencioso, travamento ou crash)."""
import math, numpy as np, pytest
from modules import fea3d as F, fea_tet10 as Q, fea_study as S, vehicle_dynamics as VD, cfd_case as C, cad_history as CH
from modules.result_trace import TracedResult
from samples.library import PARTS


def test_fea_rejects_bad_material_and_geometry():
    m = F.box_mesh(10, 10, 10, 1, 1, 1)
    for E, nu in [(0, .3), (-1, .3), (210000, .5), (210000, -1)]:
        with pytest.raises(ValueError): F.solve(m, E, nu, {0: (0, 1, 2)}, {})
    with pytest.raises(ValueError): F.box_mesh(0, 1, 1, 1, 1, 1)
    with pytest.raises(ValueError): F.box_mesh(1, 1, 1, 0, 1, 1)


def test_singular_support_detected():
    m = F.box_mesh(10, 10, 10, 2, 2, 2)
    with pytest.raises(Exception): F.solve(m, 210000, .3, {0: (0,)}, {5: (0, 0, 1.0)})      # mecanismo: não pode devolver número


def test_study_bad_inputs():
    s = PARTS["chapa_furada"].make(length=60, width=30, thickness=6, hole_d=0, nx=0, ny=0)
    with pytest.raises(ValueError): S.run(s, 0, 70000, .3, "xmin", "xmax", (1, 0, 0))
    with pytest.raises(ValueError): S.run(s, -3, 70000, .3, "xmin", "xmax", (1, 0, 0))
    with pytest.raises(KeyError): S.run(s, 3, 70000, .3, "foo", "xmax", (1, 0, 0))


def test_part_parameter_limits():
    with pytest.raises(ValueError): PARTS["flange"].make(od=1)
    with pytest.raises(KeyError): PARTS["flange"].make(xyz=1)


def test_vehicle_and_cfd_bad_inputs():
    with pytest.raises(ValueError): VD.simular(VD.Veiculo(0, 1, 1, 0, 1, 1, 1), 1)
    with pytest.raises(ValueError): C.gerar_caso_openfoam("/tmp/x", "a.stl", 0, 1, 1)
    with pytest.raises(ValueError): C.nivel2(0.3, 0, 1, 1, 1.2, 10)


def test_result_trace_never_validates_without_ref():
    for cls in ("VALIDADO",):
        with pytest.raises(ValueError): TracedResult("x", cls, "m")


def test_cad_history_failure_leaves_state_intact():
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt
    h = CH.CadHistory(BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 10, 10, 10).Shape())
    v0 = h.volume()
    for bad in [("fillet", dict(radius=100, edges="all")), ("hole", dict(x=1, y=1, z=1, dx=0, dy=0, dz=1, diameter=0, depth=1)), ("scale", dict(factor=-1))]:
        with pytest.raises(CH.CadHistoryError): h.add(bad[0], **bad[1])
    assert h.ops == [] and abs(h.volume() - v0) < 1e-9


def test_tet10_dof_guard():
    m = Q.to_quadratic(F.box_mesh(10, 10, 10, 2, 2, 2))
    m.nodes = np.vstack([m.nodes] * 1)           # malha pequena passa
    Q.solve(m, 210000, .3, {i: (0, 1, 2) for i, p in enumerate(m.nodes) if p[0] < 1e-9}, {})
