"""Suspensão duplo-A 3D (V3.8): invariantes rígidos, redução ao 2D, simetria, caster/KPI analíticos e limites."""
import math

import numpy as np
import pytest

from modules import suspension as s2d, suspension3d as S, vehicle_combined as vc


def _plano():
    """Versão plana (todos os pontos simétricos em x) da geometria do exemplo 2D; barra de direção longa na direção x (quase perpendicular ao plano)."""
    return S.DuploA3D(LF=(0.15, 0.20, 0.14), LR=(-0.15, 0.20, 0.14), B=(0, 0.60, 0.12), UF=(0.12, 0.25, 0.30), UR=(-0.12, 0.25, 0.30), D=(0, 0.56, 0.32),
                      T=(-0.9, 0.22, 0.16), Tj=(-0.3, 0.58, 0.15), W=(0, 0.63, 0.24), P=(0, 0.63, 0))


def test_projeto_reproduz_geometria_e_caster_kpi_analiticos():
    s = S.exemplo_ilustrativo(); r = S.resolver_3d(s)
    assert r["camber_graus"] == pytest.approx(0, abs=1e-9) and r["toe_in_graus"] == pytest.approx(0, abs=1e-9) and r["delta_bitola_m"] == pytest.approx(0, abs=1e-12)
    pm = vc.pino_mestre_3d(s.B, s.D, s.P)
    assert r["caster_graus"] == pytest.approx(pm["caster_graus"]) and r["kpi_graus"] == pytest.approx(pm["kpi_graus"])
    assert r["caster_graus"] == pytest.approx(math.degrees(math.atan2(0.02, 0.20)), abs=1e-9)      # D 2 cm atrás de B, 20 cm acima
    assert r["trail_m"] > 0                                                                       # topo para trás ⇒ trail positivo


def test_comprimentos_rigidos_conservados_em_qualquer_pose():
    s = S.exemplo_ilustrativo()
    pts = {n: np.array(getattr(s, n)) for n in ("LF", "LR", "B", "UF", "UR", "D", "T", "Tj")}
    for h, rk in ((0.03, 0.0), (-0.03, 0.0), (0.0, 0.015), (0.02, -0.01)):
        r = S.resolver_3d(s, h, rk)
        B, D, Tj, W = map(np.array, (r["B"], r["D"], r["Tj"], r["W"]))
        T = pts["T"] + [0, rk, 0]
        assert np.linalg.norm(B - pts["LF"]) == pytest.approx(np.linalg.norm(pts["B"] - pts["LF"]), abs=1e-9)
        assert np.linalg.norm(B - pts["LR"]) == pytest.approx(np.linalg.norm(pts["B"] - pts["LR"]), abs=1e-9)
        assert np.linalg.norm(D - pts["UF"]) == pytest.approx(np.linalg.norm(pts["D"] - pts["UF"]), abs=1e-9)
        assert np.linalg.norm(D - pts["UR"]) == pytest.approx(np.linalg.norm(pts["D"] - pts["UR"]), abs=1e-9)
        assert np.linalg.norm(Tj - T) == pytest.approx(np.linalg.norm(pts["Tj"] - pts["T"]), abs=1e-9)
        assert np.linalg.norm(B - D) == pytest.approx(np.linalg.norm(pts["B"] - pts["D"]), abs=1e-9)      # manga rígida
        assert W[2] - s.W[2] == pytest.approx(h, abs=1e-9)


def test_reducao_ao_2d_camber_e_bitola():
    p, q = _plano(), s2d.exemplo_ilustrativo()
    for h in (-0.03, -0.01, 0.02, 0.03):
        a, b = S.resolver_3d(p, h), s2d.resolver(q, h)
        assert a["camber_graus"] == pytest.approx(b["camber_graus"], abs=2e-5)
        assert a["delta_bitola_m"] == pytest.approx(b["delta_bitola_m"], abs=1e-7)
        assert abs(a["toe_in_graus"]) < 0.1            # barra quase perpendicular ao plano: toe residual pequeno (2ª ordem)


def test_simetria_espelhada_em_x_nao_gera_toe_nem_caster_com_barra_no_plano():
    p = _plano()
    r = S.resolver_3d(p, 0.0)
    assert r["caster_graus"] == pytest.approx(0, abs=1e-9) and r["trail_m"] == pytest.approx(0, abs=1e-12)


def test_camber_gain_negativo_em_bump_e_bump_steer_e_razao_de_esterco():
    s = S.exemplo_ilustrativo(); d = S.derivadas(s)
    assert d["camber_gain_graus_por_m"] < 0                    # geometria de exemplo: bump → camber negativo (igual ao 2D)
    assert d["razao_esterco_graus_por_mm"] > 0                 # cremalheira para fora aumenta o toe-in: sinal consistente com a convenção documentada
    # bump steer realmente calculado (≠ 0 numérico) e coerente com diferença finita de passo maior
    a, b = S.resolver_3d(s, -0.01), S.resolver_3d(s, 0.01)
    assert (b["toe_in_graus"] - a["toe_in_graus"]) / 0.02 == pytest.approx(d["bump_steer_graus_por_m"], rel=0.1)


def test_esterco_move_toe_e_altera_nada_em_z_da_roda():
    s = S.exemplo_ilustrativo()
    r = S.resolver_3d(s, 0.0, 0.02)
    assert abs(r["toe_in_graus"]) > 1.0 and abs(r["W"][2] - s.W[2]) < 1e-9
    assert S.resolver_3d(s, 0.0, -0.02)["toe_in_graus"] == pytest.approx(-r["toe_in_graus"], rel=0.15)   # quase antissimétrico para curso pequeno


def test_elastocinematica_linear_e_padrao_zero():
    s = S.exemplo_ilustrativo()
    base = S.resolver_3d(s, 0.01)
    z = S.com_elastocinematica(s, 0.01, 0.0, 3000.0, 1000.0, S.CoefElasto())
    assert z["toe_in_graus"] == base["toe_in_graus"] and z["elastocinematica_aplicada"] is False
    k = S.CoefElasto(toe_fy=-0.05, toe_fx=0.02, camber_fy=0.1)
    e = S.com_elastocinematica(s, 0.01, 0.0, 3000.0, 1000.0, k)
    assert e["toe_in_graus"] - base["toe_in_graus"] == pytest.approx(-0.05 * 3 + 0.02 * 1)
    assert e["camber_graus"] - base["camber_graus"] == pytest.approx(0.1 * 3) and e["elastocinematica_aplicada"] is True


def test_camber_e_toe_estaticos_deslocam_a_leitura():
    s = S.exemplo_ilustrativo(); s.camber_estatico_graus = -1.5; s.toe_estatico_graus = 0.2
    r = S.resolver_3d(s)
    assert r["camber_graus"] == pytest.approx(-1.5, abs=1e-9) and r["toe_in_graus"] == pytest.approx(0.2, abs=1e-9)


def test_fora_da_faixa_e_validacoes():
    s = S.exemplo_ilustrativo()
    with pytest.raises(ValueError):
        S.resolver_3d(s, 0.5)
    bad = S.exemplo_ilustrativo(); bad.D = (0.0, 0.56, 0.05)
    with pytest.raises(ValueError):
        S.resolver_3d(bad)
    bad2 = S.exemplo_ilustrativo(); bad2.T = bad2.Tj
    with pytest.raises(ValueError):
        S.resolver_3d(bad2)
    with pytest.raises(ValueError):
        S.curva_heave_3d(s, n=1)


def test_resultado_rastreavel():
    r = S.analisar(S.exemplo_ilustrativo(), ilustrativo=True)
    assert r.classe == "ANALITICO" and "caster_graus" in r.valores and any("ILUSTRATIVA" in p for p in r.premissas) and r.limitacoes


def test_dialogo_suspensao_3d():
    from PySide6.QtWidgets import QApplication, QTableWidgetItem
    app = QApplication.instance() or QApplication([])
    from interface.vehicle_geo_dialog import VehicleGeoDialog
    d = VehicleGeoDialog(); d.calc_susp3d(); t = d.out_s3.toPlainText()
    assert "caster" in t and "Bump steer" in t and "ERRO" not in t
    d.tab3.setItem(5, 2, QTableWidgetItem("0.01")); d.calc_susp3d()          # D abaixo de B → erro tratado
    assert "ERRO" in d.out_s3.toPlainText()
