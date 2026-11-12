import numpy as np, pytest
from modules import fea3d as F, fea_voxel as V
from samples.library import PARTS

E, NU = 210000.0, 0.3

def test_box_part_volume_exact():
    s = PARTS["tubo_retangular"].make(length=100, w=40, h=40, t=4)
    m, info = V.mesh_from_shape(s, 2.0)
    assert abs(info["erro_volume_pct"]) < 1e-6      # paredes alinhadas à grade → voxels exatos

def test_round_tube_volume_error_reported():
    s = PARTS["tubo_redondo"].make(length=60, od=40, t=5)
    m, info = V.mesh_from_shape(s, 1.5)
    assert abs(info["erro_volume_pct"]) < 8 and info["tetraedros"] > 1000

def test_tube_cantilever_vs_beam_theory():
    L, w, hh, t, P = 200.0, 40.0, 40.0, 4.0, 200.0
    s = PARTS["tubo_retangular"].make(length=L, w=w, h=hh, t=t)
    m, info = V.mesh_from_shape(s, 2.0)
    x0 = m.nodes[:, 0].min()
    fixed = {i: (0, 1, 2) for i, p in enumerate(m.nodes) if p[0] < x0 + 1e-6}
    tip = [i for i, p in enumerate(m.nodes) if p[0] > m.nodes[:, 0].max() - 1e-6]
    u, vm, R, vol = F.solve(m, E, NU, fixed, F.surface_load(m, tip, (0, 0, -P)))
    I = (w*hh**3 - (w-2*t)*(hh-2*t)**3) / 12
    G = E/(2*(1+NU)); exact = P*L**3/(3*E*I) + P*L/(G*2*t*hh)   # Timoshenko: flexão + cisalhamento (área das almas)
    ratio = abs(u[tip, 2].mean()) / exact
    assert 0.85 < ratio < 1.15, ratio              # Tet4 + voxels vs Timoshenko: ±15% documentado
    assert abs(R[[3*i+2 for i in fixed]].sum() - P) / P < 1e-6   # equilíbrio de reações

def test_limits():
    s = PARTS["tubo_retangular"].make()
    with pytest.raises(ValueError): V.mesh_from_shape(s, 0.1)
    with pytest.raises(ValueError): V.mesh_from_shape(s, -1)
