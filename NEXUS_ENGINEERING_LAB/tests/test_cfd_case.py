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
