"""Execução REAL do CalculiX (pula se `ccx` ou Gmsh não estiverem instalados). FEA: NEXUS-Tet10 × ccx × Timoshenko."""
import sys
import numpy as np
import pytest
from modules import calculix_io as C, fea_gmsh as G, fea_study as S, fea_tet10 as Q, solver_registry as sr
from samples.library import PARTS

pytestmark = pytest.mark.skipif(not (sr.detect("CalculiX").instalado and G.available()), reason="CalculiX/Gmsh não instalados")
E, NU = 210000.0, 0.3


@pytest.fixture(scope="module")
def caso(tmp_path_factory):
    s = PARTS["tubo_redondo"].make(length=100, od=40, t=5)
    m, _ = G.mesh_from_shape(s, 8, 2)
    fx = {k: (0, 1, 2) for k in S.face_nodes(m, "xmin")}
    loads = Q.surface_load10(m, S.face_nodes(m, "xmax"), (0, 0, -100))
    u, vm, R, vol = Q.solve(m, E, NU, fx, loads)
    d = tmp_path_factory.mktemp("ccx")
    C.write_inp(m, E, NU, fx, loads, d / "t.inp")
    return m, u, d


def test_ccx_matches_nexus_tet10_and_timoshenko(caso):
    m, u, d = caso
    r = C.run(d / "t.inp")
    assert r.classe == "SIMULACAO_NUMERICA" and r.solver == "CalculiX" and "2." in r.solver_versao
    um = float(np.linalg.norm(u.reshape(-1, 3), axis=1).max())
    assert C.compare(um, r, tol_pct=1.0)["status"] == "CONCORDA"            # mesma formulação: devem coincidir
    I = np.pi / 64 * (40 ** 4 - 30 ** 4); G_ = E / 2.6; A = np.pi / 4 * (40 ** 2 - 30 ** 2)
    tim = 100 * 100 ** 3 / (3 * E * I) + 100 * 100 / (G_ * 0.53 * A)
    assert abs(r.valores["u_max_mm"] / tim - 1) < 0.08                      # referência analítica de viga (Timoshenko)


def test_ccx_runs_through_isolated_job_queue(caso):
    from core.jobs import JobManager
    _, _, d = caso
    j = JobManager().submit_cmd("ccx isolado", [sr.detect("CalculiX").caminho, "t"], cwd=str(d), timeout=120)
    assert j.wait(130) and j.state == "DONE" and (d / "t.dat").exists()
    # solver com arquivo de entrada inexistente: falha real é reportada, não mascarada
    k = JobManager().submit_cmd("ccx inexistente", [sr.detect("CalculiX").caminho, "nao_existe"], cwd=str(d), timeout=60)
    assert k.wait(70) and k.state == "FAILED"
