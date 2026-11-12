import math, pytest
from modules import cfd_case as C

def test_levels():
    r = C.nivel1(0.8, 1.225, 30); assert abs(r.valores["forca_N"] - 0.5*1.225*900*0.8) < 1e-9
    r2 = C.nivel2(0.3, 2.0, 10.0, 4.0, 1.225, 30)
    assert r2.classe == "ANALITICO" and abs(r2.valores["arrasto_total_N"] - r2.valores["arrasto_atrito_N"] - r2.valores["arrasto_forma_N"]) < 1e-9
    with pytest.raises(ValueError): C.nivel1(0, 1.2, 1)

def test_case_files(tmp_path):
    p = C.gerar_caso_openfoam(tmp_path/"c", "carro.stl", 30, 4.0, 2.0)
    for f in ["system/blockMeshDict", "system/controlDict", "system/fvSchemes", "system/fvSolution", "system/snappyHexMeshDict",
              "constant/momentumTransport", "0/U", "0/p", "0/k", "0/omega", "0/nut", "Allrun"]:
        assert (p/f).exists(), f
    assert "magUInf 30" in (p/"system/controlDict").read_text()

def test_execute_without_openfoam_has_no_numbers(tmp_path):
    from modules import solver_registry as sr
    if sr.detect("OpenFOAM").instalado: pytest.skip("OpenFOAM presente")
    r = C.executar_openfoam(tmp_path)
    assert r.classe == "NAO_EXECUTADO" and r.valores == {}


# ------------------------------------------------------------------ integração de pressão (geometria sintética de solução conhecida)
def _cubo_polymesh(raiz, pvals):
    """Corpo cúbico [0,1]³: 6 faces com normais voltadas PARA DENTRO do corpo (= para fora do domínio fluido), como no OpenFOAM."""
    pm = raiz / "constant/polyMesh"; pm.mkdir(parents=True)
    pts = [(x, y, z) for z in (0, 1) for y in (0, 1) for x in (0, 1)]          # 8 pontos: idx = x + 2y + 4z
    H = "FoamFile { version 2.0; format ascii; class %s; object %s; }\n"
    (pm / "points").write_text(H % ("vectorField", "points") + f"{len(pts)}\n(\n" + "\n".join(f"({a} {b} {c})" for a, b, c in pts) + "\n)\n")
    f = [(0, 4, 6, 2), (1, 3, 7, 5), (0, 1, 5, 4), (2, 6, 7, 3), (0, 2, 3, 1), (4, 5, 7, 6)]   # x0,x1,y0,y1,z0,z1 (orientação definida abaixo)
    # normais para dentro: x0 → +x, x1 → −x, etc.; a regra da mão direita decide a ordem dos vértices
    f = [(0, 2, 6, 4), (1, 5, 7, 3), (0, 4, 5, 1), (2, 3, 7, 6), (0, 1, 3, 2), (4, 6, 7, 5)]
    (pm / "faces").write_text(H % ("faceList", "faces") + f"{len(f)}\n(\n" + "\n".join(f"4({a} {b} {c} {d})" for a, b, c, d in f) + "\n)\n")
    (pm / "owner").write_text(H % ("labelList", "owner") + "6\n(\n0\n0\n0\n0\n0\n0\n)\n")
    (pm / "boundary").write_text(H % ("polyBoundaryMesh", "boundary") + "1\n(\n    body\n    {\n        type wall;\n        nFaces 6;\n        startFace 0;\n    }\n)\n")
    t = raiz / "1"; t.mkdir()
    (t / "p").write_text(H % ("volScalarField", "p") + "dimensions [0 2 -2 0 0 0 0];\ninternalField uniform 0;\nboundaryField\n{\n    body\n    {\n        type fixedValue;\n"
                         f"        value nonuniform List<scalar>\n6\n(\n" + "\n".join(str(v) for v in pvals) + "\n)\n;\n    }\n}\n")


def test_pressure_force_uniform_pressure_is_zero_and_gradient_matches_analytic(tmp_path):
    _cubo_polymesh(tmp_path / "u", [5.0] * 6)
    r = C.forcas_pressao(tmp_path / "u", "body", rho=1.0, v_inf=1.0, a_ref=1.0)
    assert all(abs(x) < 1e-12 for x in r["forca_N"]) and abs(r["area_patch_m2"] - 6.0) < 1e-12      # superfície fechada, p uniforme → F = 0
    # p = a·x: x0 → 0, x1 → a, demais faces → a/2 (centro). F = −ρ·a·V·x̂ (normal para dentro)
    a, rho = 40.0, 1.225
    _cubo_polymesh(tmp_path / "g", [0.0, a, a / 2, a / 2, a / 2, a / 2])
    r = C.forcas_pressao(tmp_path / "g", "body", rho=rho, v_inf=10.0, a_ref=2.0, drag_dir=(-1, 0, 0))
    assert r["forca_N"][0] == pytest.approx(-rho * a, rel=1e-12) and abs(r["forca_N"][1]) < 1e-12 and abs(r["forca_N"][2]) < 1e-12
    assert r["cd_pressao"] == pytest.approx(rho * a / (0.5 * rho * 100 * 2.0), rel=1e-12)
    assert "sem atrito" in r["obs"]
    with pytest.raises(KeyError):
        C.forcas_pressao(tmp_path / "g", "inexistente")


def test_log_parser_convergence_flags():
    ok = "Time = 10\nSolving for Ux, Initial residual = 1e-06, Final\nSIMPLE solution converged in 10 iterations\n"
    r = C.ler_log_simplefoam(ok)
    assert r["convergiu"] and r["iteracoes"] == 1 and r["residuos_iniciais_finais"]["Ux"] == 1e-6 and not r["erro_fatal"]
    assert not C.ler_log_simplefoam("Time = 1\n")["convergiu"]
    assert C.ler_log_simplefoam("--> FOAM FATAL ERROR")["erro_fatal"]


def test_openfoam_real_sphere_run_is_honest(tmp_path):
    """Execução REAL (pula sem OpenFOAM/trimesh). Não é validação: só prova que gera malha, resolve e reporta sem inventar."""
    import numpy as np
    from modules import solver_registry as sr
    trimesh = pytest.importorskip("trimesh")
    if not sr.detect("OpenFOAM").instalado:
        pytest.skip("OpenFOAM não instalado")
    p = C.gerar_caso_openfoam(tmp_path / "e", "esfera.stl", 20.0, 1.0, np.pi / 4, iteracoes=120, celulas=(40, 16, 12))
    m = trimesh.creation.icosphere(subdivisions=3, radius=0.5); m.apply_translation([0, 0, 1.5]); m.export(p / "constant/triSurface/esfera.stl")
    r = C.executar_openfoam(p, timeout=600)
    assert r.classe == "SIMULACAO_NUMERICA" and r.solver == "OpenFOAM" and r.valores["iteracoes"] == 120 and not r.valores["erro_fatal"]
    assert r.classe != "VALIDADO" and any("não validado" in x for x in r.limitacoes) and any("NÃO CONVERGIU" in x for x in r.limitacoes)
    assert all(np.isfinite(v) for v in r.valores["residuos_iniciais_finais"].values())
    if "cd_pressao" in r.valores:                                    # integração própria só existe quando as funções-objeto falham
        fp = C.forcas_pressao(p, "body", 1.225, 20.0, np.pi / 4)
        assert abs(fp["area_patch_m2"] - np.pi * 1.0) / (np.pi * 1.0) < 0.05          # malha de superfície ≈ esfera de D = 1 m
        assert fp["forca_N"][0] > 0                                                   # o arrasto de pressão empurra a favor do escoamento
