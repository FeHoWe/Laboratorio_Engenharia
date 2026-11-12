import numpy as np, pytest
from modules import fea_gmsh as G, fea_tet10 as Q, fea_study as S
from samples.library import PARTS

pytestmark = pytest.mark.skipif(not G.available(), reason="gmsh indisponível (pip install gmsh; no Linux requer libGLU)")
E, NU = 210000.0, 0.3


def test_conformal_volume_error_small():
    s = PARTS["tubo_redondo"].make(length=100, od=40, t=5)
    m, info = G.mesh_from_shape(s, 6, 2)
    assert m.tets.shape[1] == 10 and abs(info["erro_volume_pct"]) < 0.5      # voxel dá vários %


def test_plate_with_hole_matches_peterson():
    """Kt de placa finita sob tração (Peterson): Kt_net = 3.0039-3.753x+7.90x²-9.18x³+4.04x⁴, x=d/w."""
    w, d, t, L, sg = 100., 20., 5., 300., 100.
    s = PARTS["chapa_furada"].make(length=L, width=w, thickness=t, hole_d=d, nx=1, ny=1, margin=20)
    m, _ = G.mesh_from_shape(s, 12, 2, size_min=2)
    fx = {k: (0, 1, 2) for k in S.face_nodes(m, "xmin")}
    loads = Q.surface_load10(m, S.face_nodes(m, "xmax"), (sg*w*t, 0, 0))
    u, vm, R, vol = Q.solve(m, E, NU, fx, loads)
    sig, vmn = Q.nodal_stress(m, u, E, NU)
    x = d/w; kt = 3.0039 - 3.753*x + 7.90*x**2 - 9.18*x**3 + 4.04*x**4
    ref = kt * sg * w/(w-d)
    assert abs(sig[:, 0].max()/ref - 1) < 0.05, (sig[:, 0].max(), ref)


def test_study_with_gmsh_traced():
    s = PARTS["tubo_redondo"].make(length=100, od=40, t=5)
    r, d = S.run(s, 8.0, E, NU, "xmin", "xmax", (0, 0, -100), sigma_yield=250, mesher="gmsh", order=2)
    I = np.pi/64*(40**4-30**4); G_ = E/2.6; A = np.pi/4*(40**2-30**2)
    tim = 100*100**3/(3*E*I) + 100*100/(G_*0.53*A)
    assert r.solver == "NEXUS-Tet10" and abs(r.valores["u_max_mm"]/tim - 1) < 0.1
    assert r.valores["vm_max_tipo"].startswith("nodal") and r.valores["fator_seguranca_escoamento_ref"] > 0
