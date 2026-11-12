import math
import numpy as np
import pytest
from modules import frame_fem as ff

E, I, A, L = 210000.0, 1.0e6, 1000.0, 1000.0


def beam_text(extra, nodes):
    return nodes + f"BEAM b A B {A} {I} {I} 2e6 {E} 80000\n" + extra


def test_cantilever_closed_form():
    f = ff.parse(beam_text("LOAD B 0 0 -1000\n", "NODE A 0 0 0 fix=xyzXYZ\nNODE B 1000 0 0\n"))
    r = ff.solve(f)
    assert r.displacement["B"][2] == pytest.approx(-1000 * L ** 3 / (3 * E * I), rel=1e-9)
    assert r.displacement["B"][4] == pytest.approx(1000 * L ** 2 / (2 * E * I), rel=1e-9)
    assert r.equilibrium_error < 1e-12
    assert ff.moment_at(f, r, "b", 0)[0] == pytest.approx(-1e6)
    assert ff.moment_at(f, r, "b", 1)[0] == pytest.approx(0, abs=1e-6)


def test_simply_supported_udl():
    w = 5.0
    f = ff.parse(beam_text(f"DLOAD b 0 0 {-w}\n", "NODE A 0 0 0 fix=xyzX\nNODE B 1000 0 0 fix=yz\n"))
    r = ff.solve(f)
    # momento no meio = wL²/8 (módulo); flecha no meio via nó extra
    my_mid = ff.moment_at(f, r, "b", 0.5)[0]
    assert abs(my_mid) == pytest.approx(w * L ** 2 / 8, rel=1e-9)
    assert ff.moment_at(f, r, "b", 1)[0] == pytest.approx(-r.end_forces["b"][10], abs=1e-6)
    assert r.reactions["A"][2] == pytest.approx(w * L / 2)
    assert r.equilibrium_error < 1e-12


def test_midspan_deflection_with_split_beam():
    w = 5.0
    t = ("NODE A 0 0 0 fix=xyzX\nNODE M 500 0 0\nNODE B 1000 0 0 fix=yz\n"
         f"BEAM b1 A M {A} {I} {I} 2e6 {E} 80000\nBEAM b2 M B {A} {I} {I} 2e6 {E} 80000\nDLOAD b1 0 0 {-w}\nDLOAD b2 0 0 {-w}\n")
    r = ff.solve(ff.parse(t))
    assert r.displacement["M"][2] == pytest.approx(-5 * w * L ** 4 / (384 * E * I), rel=1e-9)


def test_portal_frame_equilibrium_and_symmetry():
    t = ("NODE A 0 0 0 fix=xyzXYZ\nNODE B 0 0 3000\nNODE C 4000 0 3000\nNODE D 4000 0 0 fix=xyzXYZ\n"
         f"BEAM c1 A B {A} {I} {I} 2e6 {E} 80000\nBEAM v B C {A} {I} {I} 2e6 {E} 80000\nBEAM c2 C D {A} {I} {I} 2e6 {E} 80000\n"
         "DLOAD v 0 0 -10\n")
    r = ff.solve(ff.parse(t))
    assert r.equilibrium_error < 1e-12
    assert r.reactions["A"][2] == pytest.approx(r.reactions["D"][2]) and r.reactions["A"][2] == pytest.approx(20000)
    assert r.displacement["B"][0] == pytest.approx(-r.displacement["C"][0])      # simetria


def test_torsion_out_of_plane_L_frame():
    # braço em y carregado em z na ponta de um balanço em x: gera torção T = P·a no balanço
    t = ("NODE A 0 0 0 fix=xyzXYZ\nNODE B 1000 0 0\nNODE C 1000 500 0\n"
         f"BEAM b1 A B {A} {I} {I} 2e6 {E} 80000\nBEAM b2 B C {A} {I} {I} 2e6 {E} 80000\nLOAD C 0 0 -100\n")
    f = ff.parse(t)
    r = ff.solve(f)
    assert abs(r.end_forces["b1"][3]) == pytest.approx(100 * 500, rel=1e-9)
    assert r.equilibrium_error < 1e-12


def test_mechanism_and_errors():
    with pytest.raises(ff.FrameError, match="hipostática"):
        ff.solve(ff.parse("NODE A 0 0 0 fix=xyz\nNODE B 1000 0 0\nBEAM b A B 1000 1e6 1e6 2e6 210000 80000\nLOAD B 0 0 -1\n"))
    with pytest.raises(ff.FrameError, match="Linha 2"):
        ff.parse("NODE A 0 0 0\nBEAM b A X 1 1 1 1 1 1\n")
    with pytest.raises(ff.FrameError):
        ff.parse("NODE A 0 0 0\nNODE B 1 0 0\nBEAM b A B 0 1 1 1 1 1\n")


def test_portal_example_global_equilibrium_and_plane():
    f = ff.parse(ff.portal_example())
    r = ff.solve(f)
    fx = sum(v[0] for v in r.reactions.values())
    fz = sum(v[2] for v in r.reactions.values())
    assert fx == pytest.approx(-10000, rel=1e-9) and fz == pytest.approx(20 * 6000, rel=1e-9)
    # colunas verticais fletem em My (plano x–z global), nunca em Mz
    assert max(abs(ff.moment_at(f, r, "c1", s)[1]) for s in (0, .5, 1)) < 1e-6
    assert "σmáx" in ff.report(f, r, 250)


def test_modal_cantilever_vs_analytic():
    # balanço: f_n = (βL)²/(2π) √(EI/(ρA L⁴)); 20 elementos
    n, Lt = 20, 1000.0
    E_, I_, A_, rho = 210000.0, 8.0e4, 400.0, 7850.0
    lines = ["NODE N0 0 0 0 fix=xyzXYZ"] + [f"NODE N{i} {Lt * i / n} 0 0" for i in range(1, n + 1)]
    lines += [f"BEAM e{i} N{i - 1} N{i} {A_} {I_} {I_} {2 * I_} {E_} 80000 rho={rho}" for i in range(1, n + 1)]
    r = ff.modal(ff.parse("\n".join(lines)), 6)
    assert r.freq_hz[0] == pytest.approx(r.freq_hz[1], rel=1e-9)         # Iy = Iz: modos de flexão duplos (dois planos)
    for got, bl in zip((r.freq_hz[0], r.freq_hz[2]), (1.8751, 4.6941)):
        exp = bl ** 2 / (2 * math.pi) * math.sqrt(E_ * 1e6 * I_ * 1e-12 / (rho * A_ * 1e-6 * (Lt * 1e-3) ** 4))
        assert got == pytest.approx(exp, rel=2e-3)
    assert r.mass_total_kg == pytest.approx(rho * A_ * 1e-6 * Lt * 1e-3, rel=1e-9)


def test_modal_point_mass_and_errors():
    # massa concentrada na ponta de balanço leve: f = (1/2π)√(3EI/L³/m)
    t = ("NODE A 0 0 0 fix=xyzXYZ\nNODE B 1000 0 0\nBEAM b A B 400 8e4 8e4 1.6e5 210000 80000 rho=1\nMASS B 10\n")
    r = ff.modal(ff.parse(t), 2)
    k = 3 * 210000 * 8e4 / 1000 ** 3 * 1000       # N/m
    assert r.freq_hz[0] == pytest.approx(math.sqrt(k / 10.0) / (2 * math.pi), rel=2e-3)
    with pytest.raises(ff.FrameError, match="rho"):
        ff.modal(ff.parse("NODE A 0 0 0 fix=xyzXYZ\nNODE B 1000 0 0\nBEAM b A B 400 8e4 8e4 1.6e5 210000 80000\n"))


def _column(n_el, base_fix, top_fix, E_=210000.0, I_=8.0e4, A_=400.0, Lt=1000.0):
    lines = [f"NODE N0 0 0 0 fix={base_fix}"] + [f"NODE N{i} {Lt * i / n_el} 0 0" + (f" fix={top_fix}" if i == n_el and top_fix else "") for i in range(1, n_el + 1)]
    lines += [f"BEAM e{i} N{i - 1} N{i} {A_} {I_} {I_} {2 * I_} {E_} 80000" for i in range(1, n_el + 1)]
    lines.append(f"LOAD N{n_el} -1 0 0")
    return "\n".join(lines)


def test_buckling_euler_pinned_and_cantilever():
    E_, I_, Lt = 210000.0, 8.0e4, 1000.0
    r = ff.buckling(ff.parse(_column(10, "xyzX", "yz")), 2)
    assert r.factors[0] == pytest.approx(math.pi ** 2 * E_ * I_ / Lt ** 2, rel=2e-3)              # articulada–articulada
    assert r.reference_axial["e1"] == pytest.approx(-1.0)                                            # compressão
    r2 = ff.buckling(ff.parse(_column(10, "xyzXYZ", "")), 2)
    assert r2.factors[0] == pytest.approx(math.pi ** 2 * E_ * I_ / (4 * Lt ** 2), rel=2e-3)       # engastada–livre (K=2)


def test_buckling_tension_has_no_critical_factor():
    t = _column(4, "xyzX", "yz").replace("LOAD N4 -1 0 0", "LOAD N4 1 0 0")
    assert ff.buckling(ff.parse(t), 2).factors == []
