import numpy as np, pytest
from modules import fea3d as F

E, NU = 210000.0, 0.3

def _cant(L, b, h, nx, ny, nz, P):
    m = F.box_mesh(L, b, h, nx, ny, nz)
    fixed = {i: (0, 1, 2) for i, p in enumerate(m.nodes) if p[0] < 1e-9}
    tip = [i for i, p in enumerate(m.nodes) if abs(p[0]-L) < 1e-9]
    loads = F.surface_load(m, tip, (0, 0, -P))
    u, vm, R, vol = F.solve(m, E, NU, fixed, loads)
    return m, u, vm, vol, tip

def test_patch_tension_exact():
    L, A = 50.0, 10*10
    m = F.box_mesh(L, 10, 10, 5, 2, 2)
    fixed = {i: (0,) for i, p in enumerate(m.nodes) if p[0] < 1e-9}
    fixed[0] = (0, 1, 2)
    j = [i for i, p in enumerate(m.nodes) if p[0] < 1e-9 and p[1] > 9.99 and p[2] < 1e-9][0]; fixed[j] = (0, 2)
    k = [i for i, p in enumerate(m.nodes) if p[0] < 1e-9 and p[1] < 1e-9 and p[2] > 9.99][0]; fixed[k] = (0, 1)
    tip = [i for i, p in enumerate(m.nodes) if abs(p[0]-L) < 1e-9]
    P = 1000.0
    u, vm, R, vol = F.solve(m, E, NU, fixed, F.surface_load(m, tip, (P, 0, 0)))
    assert abs(vol - L*A) < 1e-6
    assert abs(u[tip[0], 0] - P*L/(E*A)) / (P*L/(E*A)) < 1e-6
    assert abs(vm.mean() - P/A) / (P/A) < 1e-6

def test_volume_and_positive():
    m = F.box_mesh(20, 10, 5, 4, 2, 1)
    P = m.nodes[m.tets]
    vol = np.einsum('ij,ij->i', np.cross(P[:,1]-P[:,0], P[:,2]-P[:,0]), P[:,3]-P[:,0]) / 6
    assert (vol > 0).all() and abs(vol.sum() - 1000) < 1e-9

def test_cantilever_converges_and_underestimates():
    L, b, h, P = 100.0, 10.0, 10.0, 100.0
    I = b*h**3/12
    exact = P*L**3/(3*E*I)  # Euler-Bernoulli
    errs = []
    for n in [(10, 1, 1), (20, 2, 2), (40, 4, 4)]:
        m, u, vm, vol, tip = _cant(L, b, h, *n, P)
        d = abs(np.mean(u[tip, 2]))
        errs.append(d / exact)
    assert errs[0] < errs[1] < errs[2] < 1.05     # converge por baixo (travamento Tet4)
    assert errs[2] > 0.75                        # malha refinada: ≤25% abaixo de Euler-Bernoulli (travamento Tet4, documentado)

def test_traced_and_inp(tmp_path):
    m, u, vm, vol, tip = _cant(50, 10, 10, 10, 2, 2, 50)
    r = F.to_traced("cant", m, E, NU, u, vm, vol)
    assert r.classe == "SIMULACAO_NUMERICA" and r.solver == "NEXUS-Tet4"
    F.write_calculix_inp(m, E, NU, {0: (0, 1, 2)}, {tip[0]: (0, 0, -1)}, tmp_path/"a.inp")
    t = (tmp_path/"a.inp").read_text()
    assert "*ELEMENT, TYPE=C3D4" in t and "*ELASTIC" in t

def test_errors():
    m = F.box_mesh(10, 10, 10, 1, 1, 1)
    with pytest.raises(ValueError): F.solve(m, E, NU, {}, {0: (1, 0, 0)})
    with pytest.raises(ValueError): F.solve(m, -1, NU, {0: (0,1,2)}, {})


def test_modal_cantilever_vs_beam_theory():
    L, b, h = 100.0, 10.0, 10.0
    rho = 7.85e-9  # t/mm³
    m = F.box_mesh(L, b, h, 40, 4, 4)
    fixed = {i: (0, 1, 2) for i, p in enumerate(m.nodes) if p[0] < 1e-9}
    f = F.modal(m, E, NU, rho, fixed, 4)
    I = b*h**3/12; A = b*h
    f1 = (1.8751**2) / (2*np.pi*L**2) * np.sqrt(E*I/(rho*A))
    assert 0.9 * f1 < f[0] < 1.3 * f1       # Tet4 é rígido: sobrestima frequência
    assert abs(f[0] - f[1]) / f[0] < 0.12   # y e z ~ iguais (divisão em 6 tets é levemente anisotrópica)
    with pytest.raises(ValueError): F.modal(m, E, NU, 0, fixed)

def test_modal_free_mass_scaling():
    m = F.box_mesh(50, 10, 10, 10, 2, 2); fixed = {i: (0, 1, 2) for i, p in enumerate(m.nodes) if p[0] < 1e-9}
    f1 = F.modal(m, E, NU, 7.85e-9, fixed, 1)[0]; f2 = F.modal(m, E, NU, 4*7.85e-9, fixed, 1)[0]
    assert abs(f1/f2 - 2) < 1e-6          # f ∝ 1/√ρ


def test_export_vtk(tmp_path):
    m, u, vm, vol, tip = _cant(50, 10, 10, 5, 1, 1, 50)
    F.export_vtk(tmp_path/"r.vtk", m, u, vm)
    t = (tmp_path/"r.vtk").read_text().splitlines()
    assert t[3] == "DATASET UNSTRUCTURED_GRID" and f"POINTS {len(m.nodes)} double" in t
    assert t.count("10") == len(m.tets) and "SCALARS von_mises_MPa double 1" in t
