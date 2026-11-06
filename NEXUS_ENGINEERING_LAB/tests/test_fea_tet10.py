import numpy as np, pytest
from modules import fea3d as F, fea_tet10 as Q

E, NU = 210000.0, 0.3

def test_mass_ref_sums_to_one():
    assert abs(Q._MREF.sum() - 1.0) < 1e-12            # ∫ΣΣ NiNj = V

def _cant(nx, ny, nz, L=100., b=10., h=10., P=100.):
    m = Q.to_quadratic(F.box_mesh(L, b, h, nx, ny, nz))
    fixed = {i: (0, 1, 2) for i, p in enumerate(m.nodes) if p[0] < 1e-9}
    tip = [i for i, p in enumerate(m.nodes) if abs(p[0]-L) < 1e-9]
    u, vm, R, vol = Q.solve(m, E, NU, fixed, Q.surface_load10(m, tip, (0, 0, -P)))
    return m, u, vm, R, vol, tip, fixed

def test_cantilever_matches_timoshenko_with_coarse_mesh():
    L, b, h, P = 100., 10., 10., 100.
    I = b*h**3/12; G = E/(2*(1+NU))
    tim = P*L**3/(3*E*I) + P*L/(G*(5/6)*b*h)
    m, u, vm, R, vol, tip, fixed = _cant(6, 1, 1)
    d = abs(u[tip, 2].mean())
    assert abs(d/tim - 1) < 0.05, d/tim              # Tet4 dava ~35% nessa malha
    assert abs(vol - L*b*h) < 1e-6
    assert abs(sum(R[3*i+2] for i in fixed) - P) < 1e-6

def test_patch_tension_exact():
    L, A = 50., 100.
    m = Q.to_quadratic(F.box_mesh(L, 10, 10, 2, 1, 1))
    fixed = {i: (0,) for i, p in enumerate(m.nodes) if p[0] < 1e-9}
    c = lambda x, y, z: [i for i, p in enumerate(m.nodes) if np.allclose(p, (x, y, z))][0]
    fixed[c(0, 0, 0)] = (0, 1, 2); fixed[c(0, 10, 0)] = (0, 2); fixed[c(0, 0, 10)] = (0, 1)
    tip = [i for i, p in enumerate(m.nodes) if abs(p[0]-L) < 1e-9]
    u, vm, R, vol = Q.solve(m, E, NU, fixed, Q.surface_load10(m, tip, (1000., 0, 0)))
    assert abs(u[tip, 0].mean() - 1000*L/(E*A)) / (1000*L/(E*A)) < 1e-9
    assert abs(vm.mean() - 10.0) < 1e-6

def test_modal_close_to_beam_theory():
    L, b, h, rho = 100., 10., 10., 7.85e-9
    m = Q.to_quadratic(F.box_mesh(L, b, h, 8, 1, 1))
    fixed = {i: (0, 1, 2) for i, p in enumerate(m.nodes) if p[0] < 1e-9}
    f = Q.modal(m, E, NU, rho, fixed, 3)
    I = b*h**3/12; A = b*h
    f1 = 1.8751**2/(2*np.pi*L**2)*np.sqrt(E*I/(rho*A))
    assert 0.97*f1 < f[0] < 1.08*f1                     # Tet4 dava +8% com malha 40x4x4
