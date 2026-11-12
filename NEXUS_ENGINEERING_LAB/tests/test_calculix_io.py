import numpy as np
from modules import calculix_io as C, fea3d as F, fea_tet10 as Q, solver_registry as sr

DAT = """
 displacements (vx,vy,vz) for set NALL and time  0.1000000E+01

         1  0.000000E+00  0.000000E+00  0.000000E+00
         2  1.000000E-03 -2.000000E-03  3.000000E-03

 stresses (elem, integ.pnt.,sxx,syy,szz,sxy,sxz,syz) for set EALL and time  0.1000000E+01

         1   1  1.000000E+02  0.000000E+00  0.000000E+00  0.000000E+00  0.000000E+00  0.000000E+00
         1   2  1.000000E+02  0.000000E+00  0.000000E+00  0.000000E+00  0.000000E+00  0.000000E+00
"""

def test_parse_dat():
    U, S = C.parse_dat(DAT)
    assert U[2] == [1e-3, -2e-3, 3e-3] and len(S[1]) == 2
    assert abs(C.vm_from_S(S)[1] - 100.0) < 1e-9

def test_write_inp_tet10_and_tet4(tmp_path):
    m = Q.to_quadratic(F.box_mesh(10, 5, 5, 1, 1, 1))
    C.write_inp(m, 210000, 0.3, {0: (0, 1, 2)}, {5: (0, 0, -1.0)}, tmp_path/"a.inp", rho=7.85e-9)
    t = (tmp_path/"a.inp").read_text()
    assert "TYPE=C3D10" in t and "*DENSITY" in t and "*NODE PRINT" in t and "*NSET, NSET=NALL" in t
    m4 = F.box_mesh(10, 5, 5, 1, 1, 1); C.write_inp(m4, 210000, .3, {0: (0, 1, 2)}, {}, tmp_path/"b.inp")
    assert "TYPE=C3D4" in (tmp_path/"b.inp").read_text()

def test_run_and_compare_honest(tmp_path):
    if sr.detect("CalculiX").instalado:
        return
    r = C.run(tmp_path/"x.inp"); assert r.classe == "NAO_EXECUTADO" and r.valores == {}
    assert C.compare(1.0, r)["status"] == "NAO_COMPARADO"
