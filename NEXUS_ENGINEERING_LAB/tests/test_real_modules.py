import math, pytest
from modules.result_trace import TracedResult
from modules import solver_registry as sr
from modules.vehicle_dynamics import Veiculo, simular, resumo, G

def test_trace_rules():
    with pytest.raises(ValueError): TracedResult("x","VALIDADO","m")
    with pytest.raises(ValueError): TracedResult("x","SIMULACAO_NUMERICA","m")
    with pytest.raises(ValueError): TracedResult("x","NAO_EXECUTADO","m",valores={"a":1})
    assert "ANALITICO" in TracedResult("x","ANALITICO","m").to_json()

def test_solver_missing_is_explicit():
    s = sr.detect("CalculiX")
    if not s.instalado:
        assert s.estado == "NÃO INSTALADO"
        with pytest.raises(RuntimeError): sr.require("CalculiX")
    assert set(sr.detect_all()) == {"CalculiX","OpenFOAM","Gmsh"}

def test_terminal_velocity_matches_closed_form():
    v = Veiculo(massa=800, cd=1.0, area=1.5, crr=0.0, forca_motriz=3000, potencia=1e9, mu=10)
    h = simular(v, 200, 0.02)
    vt = math.sqrt(2*3000/(1.225*1.0*1.5))
    assert abs(h[-1][2]-vt)/vt < 1e-3

def test_grip_limited_launch():
    v = Veiculo(massa=1000, cd=0.0, area=1, crr=0.0, forca_motriz=1e6, potencia=1e9, mu=0.8)
    h = simular(v, 1.0, 0.001)
    assert abs(h[-1][2]-0.8*G) < 1e-3
    assert resumo(v,h).classe == "ANALITICO"

def test_braking_stops():
    v = Veiculo(massa=1000, cd=0, area=1, crr=0, forca_motriz=5000, potencia=1e9, mu=1)
    h = simular(v, 20, 0.01, v0=20, frear_em=0, forca_freio=5000)
    assert h[-1][2] == 0 and abs(h[-1][1]-40.0) < 0.5
