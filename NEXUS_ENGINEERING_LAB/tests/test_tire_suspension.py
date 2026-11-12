import math

import pytest

from modules import suspension as S
from modules import tire_combined as T
from modules import vehicle_lateral as VL

C_A, C_K, MU, FZ = 60000.0, 80000.0, 1.5, 4000.0


def test_reduces_to_pure_lateral_brush_exactly():
    for al in (-0.2, -0.05, 0.01, 0.08, 0.3, 1.0):
        fx, fy = T.forca_combinada(0.0, al, FZ, C_A, C_K, MU)
        assert abs(fx) < 1e-12 and abs(fy - VL.pneu_fy(al, FZ, C_A, MU)) < 1e-9


def test_friction_circle_never_exceeded_and_symmetry():
    for k in (-0.9, -0.3, -0.05, 0.02, 0.2, 0.8, 5.0):
        for al in (-0.4, -0.1, 0.0, 0.05, 0.2, 0.5):
            fx, fy = T.forca_combinada(k, al, FZ, C_A, C_K, MU)
            assert math.hypot(fx, fy) <= MU * FZ * (1 + 1e-12)
    a = T.forca_combinada(0.1, 0.05, FZ, C_A, C_K, MU); b = T.forca_combinada(0.1, -0.05, FZ, C_A, C_K, MU)
    assert abs(a[0] - b[0]) < 1e-9 and abs(a[1] + b[1]) < 1e-9


def test_traction_and_braking_reduce_available_lateral_force():
    base = T.fy_disponivel(0.0, 0.12, FZ, C_A, C_K, MU)
    assert T.fy_disponivel(0.15, 0.12, FZ, C_A, C_K, MU) < base
    assert T.fy_disponivel(-0.15, 0.12, FZ, C_A, C_K, MU) < base
    assert T.fy_disponivel(0.5, 0.12, FZ, C_A, C_K, MU) < T.fy_disponivel(0.15, 0.12, FZ, C_A, C_K, MU)


def test_pure_longitudinal_and_lifted_and_locked():
    fx, fy = T.forca_combinada(0.05, 0.0, FZ, C_A, C_K, MU)
    assert fx > 0 and abs(fy) < 1e-12
    assert T.forca_combinada(0.1, 0.1, 0.0, C_A, C_K, MU) == (0.0, 0.0)
    fx, fy = T.forca_combinada(-1.0, 0.1, FZ, C_A, C_A, MU)                       # roda travada (rigidezes iguais = isotrópico): desliza na direção da velocidade
    assert fx < 0 and abs(math.hypot(fx, fy) - MU * FZ) < 1e-6 and abs(fy / fx + math.tan(0.1)) < 1e-2


def test_envelope_is_inside_circle():
    assert all(math.hypot(x, y) <= MU * FZ * (1 + 1e-9) for x, y in T.envelope_fx_fy(FZ, C_A, C_K, MU))


def test_parallel_equal_arms_keep_camber_zero():
    s = S.DuploA(A=(0.2, 0.15), B=(0.6, 0.15), C=(0.2, 0.35), D=(0.6, 0.35), W=(0.6, 0.25), P=(0.6, 0.0))
    for h in (-0.03, 0.0, 0.03):
        r = S.resolver(s, h)
        assert abs(r["camber_graus"]) < 1e-6 and r["IC"] is None


def test_camber_gain_matches_one_over_fvsa():
    s = S.exemplo_ilustrativo()
    r0 = S.resolver(s, 0.0)
    dh = 0.002
    g = (S.resolver(s, dh)["camber_graus"] - S.resolver(s, -dh)["camber_graus"]) / (2 * dh)           # graus/m
    fvsa = r0["FVSA_m"]
    assert g < 0 and abs(abs(math.radians(g)) - 1.0 / fvsa) / (1.0 / fvsa) < 0.06        # |ganho| ≈ 1/FVSA (±6 %) e NEGATIVO em bump (IC interno)


def test_rigid_lengths_preserved_and_rc_and_range_errors():
    s = S.exemplo_ilustrativo()
    for r in S.curva_heave(s):
        assert abs(S._d(r["B"], r["D"]) - S._d(s.B, s.D)) < 1e-9 and abs(S._d(s.A, r["B"]) - S._d(s.A, s.B)) < 1e-9 and abs(S._d(s.C, r["D"]) - S._d(s.C, s.D)) < 1e-9
    assert S.resolver(s, 0.0)["RC_altura_m"] is not None and abs(S.resolver(s, 0.0)["camber_graus"]) < 1e-6
    with pytest.raises(ValueError):
        S.resolver(s, 0.5)
    with pytest.raises(ValueError):
        S.DuploA(A=(0, 0), B=(0, 0), C=(0, 1), D=(1, 1), W=(1, 0), P=(1, 0)).validar()


def test_vehicle_geo_dialog():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from interface.vehicle_geo_dialog import VehicleGeoDialog
    d = VehicleGeoDialog(); d.calc_tire(); d.calc_susp()
    assert "Fx =" in d.out_t.toPlainText() and "uso do círculo" in d.out_t.toPlainText()
    assert "camber" in d.out_s.toPlainText() and "ERRO" not in d.out_s.toPlainText()
    d.tab.item(1, 0).setText("abc"); d.calc_susp(); assert "ERRO" in d.out_s.toPlainText()     # entrada inválida é reportada, não mascarada
