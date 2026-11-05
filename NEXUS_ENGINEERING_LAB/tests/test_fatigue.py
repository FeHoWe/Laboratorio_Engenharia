"""Fadiga (V2.0): fórmulas de livro-texto, coerência S-N/Goodman/Miner, molas e erros de entrada."""
import math

import pytest

from modules import fatigue as ft


def mat(**kw):
    d = dict(name="Aço teste", su=690.0, sy=580.0, se_prime=345.0)
    d.update(kw)
    return ft.FatigueMaterial(**d)


def test_marin_factors_match_textbook_values():
    assert ft.surface_factor("Usinado ou laminado a frio", 690) == pytest.approx(0.797, abs=0.005)
    assert ft.size_factor(32.0) == pytest.approx(0.857, abs=0.003)
    assert ft.size_factor(60.0) == pytest.approx(1.51 * 60 ** -0.157)
    assert ft.size_factor(40.0, axial=True) == 1.0
    assert ft.reliability_factor(99.0) == 0.814
    assert 0.753 < ft.reliability_factor(99.5) < 0.814
    with pytest.raises(ValueError):
        ft.reliability_factor(30.0)
    assert ft.fatigue_fraction(400) == 0.9 and ft.fatigue_fraction(1400) == 0.77


def test_se_requires_user_data_or_explicit_estimate():
    m = ft.FatigueMaterial("x", su=600, sy=400)
    with pytest.raises(ValueError):
        ft.endurance_limit(m, ft.MarinInputs())
    m.estimate_se = True
    r = ft.endurance_limit(m, ft.MarinInputs())
    assert r["estimated"] and r["se_prime"] == 300 and any("ESTIMADO" in w for w in r["warnings"])
    with pytest.raises(ValueError):
        ft.FatigueMaterial("x", su=300, sy=400).validate()


def test_section_properties_and_stress():
    s = ft.Section("Círculo cheio", d=20.0)
    p = s.props()
    assert p["A"] == pytest.approx(math.pi * 100) and p["I"] == pytest.approx(math.pi * 20 ** 4 / 64)
    # flexão alternada pura: M = ±100 N·m → σa = 32 M / (π d³)
    st = ft.nominal_stresses(s, ft.LoadRange(bending=(-1e5, 1e5)), ft.Concentration())
    assert st["sigma_a"] == pytest.approx(32 * 1e5 / (math.pi * 8000), rel=1e-9) and st["sigma_m"] == 0
    # torção pura → von Mises √3·τ
    st = ft.nominal_stresses(s, ft.LoadRange(torsion=(0, 2e5)), ft.Concentration())
    tau = 16 * 1e5 / (math.pi * 8000)
    assert st["sigma_a"] == pytest.approx(math.sqrt(3) * tau) and st["sigma_m"] == pytest.approx(math.sqrt(3) * tau)
    with pytest.raises(ValueError):
        ft.nominal_stresses(ft.Section("Retângulo", b=10, h=20), ft.LoadRange(torsion=(0, 1)), ft.Concentration())
    t = ft.Section("Tubo", d=30, di=20).props()
    assert t["A"] == pytest.approx(math.pi * (900 - 400) / 4)


def test_concentration_and_notch_sensitivity():
    c = ft.Concentration(kt_bending=2.0, q_bending=0.8)
    assert c.kf("bending") == pytest.approx(1.8)
    assert ft.Concentration(kf_axial=1.5).kf("axial") == 1.5
    with pytest.raises(ValueError):
        ft.Concentration(kt_bending=0.5).kf("bending")
    with pytest.raises(ValueError):
        ft.Concentration(q_bending=1.5).kf("bending")


def test_safety_factor_criteria_ordering_and_limits():
    f = ft.safety_factors(100.0, 100.0, 250.0, 690.0, 580.0)
    assert f["Goodman"] == pytest.approx(1 / (100 / 250 + 100 / 690))
    assert f["Soderberg"] < f["Goodman"] < f["Gerber"]
    assert f["ASME-elíptico"] > f["Soderberg"]
    # só alternada: todos reduzem a Se/σa (exceto escoamento)
    g = ft.safety_factors(100.0, 0.0, 250.0, 690.0, 580.0)
    assert g["Goodman"] == g["Gerber"] == pytest.approx(2.5)
    assert g["Escoamento (Langer)"] == pytest.approx(5.8)
    assert all(math.isinf(v) for v in ft.safety_factors(0, 0, 250, 690, 580).values())
    # na linha de Goodman, n = 1
    assert ft.safety_factors(125.0, 345.0, 250.0, 690.0, 580.0)["Goodman"] == pytest.approx(1.0)


def test_sn_curve_passes_through_anchor_points_and_inverts():
    m = mat(f=0.9)
    se = 200.0
    c = ft.build_sn(m, se)
    assert c.stress_at(1e3) == pytest.approx(0.9 * 690)
    assert c.stress_at(1e6) == pytest.approx(se, rel=1e-9)
    assert c.life(0.9 * 690) == pytest.approx(1e3, rel=1e-9)
    assert c.life(se * 1.0001) == pytest.approx(1e6, rel=0.01)
    assert math.isinf(c.life(se)) and math.isinf(c.life(0.0)) and c.life(math.inf) == 0
    # mais tensão → menos ciclos
    assert c.life(400) < c.life(300) < c.life(250)
    with pytest.raises(ValueError):
        ft.build_sn(m, 700.0)
    nk = ft.build_sn(mat(has_knee=False, nk=5e8), 100.0)
    assert not math.isinf(nk.life(90.0))                      # sem joelho → sempre finita


def test_equivalent_reversed_rules():
    assert ft.equivalent_reversed(100, 0, 690) == 100
    assert ft.equivalent_reversed(100, 345, 690) == pytest.approx(200.0)
    assert ft.equivalent_reversed(100, 345, 690, "Gerber") == pytest.approx(100 / (1 - 0.25))
    assert ft.equivalent_reversed(100, 300, 690, "SWT") == pytest.approx(math.sqrt(400 * 100))
    assert math.isinf(ft.equivalent_reversed(100, 700, 690))


def test_analyze_full_flow_finite_and_infinite_life():
    m = mat()
    mar = ft.MarinInputs(d_eq=20.0, load_type="Flexão", reliability_pct=99.0)
    sec = ft.Section("Círculo cheio", d=20.0)
    r_inf = ft.analyze(m, mar, sec, ft.LoadRange(bending=(-4e4, 4e4)), ft.Concentration())
    assert r_inf.infinite and r_inf.factors["Goodman"] > 1
    r_fin = ft.analyze(m, mar, sec, ft.LoadRange(bending=(-1.8e5, 1.8e5)), ft.Concentration())
    assert not r_fin.infinite and 1e3 < r_fin.cycles < 1e7 and r_fin.factors["Goodman"] < 1
    assert "ciclos" in r_fin.summary()
    big = ft.analyze(m, mar, sec, ft.LoadRange(bending=(-5e5, 5e5)), ft.Concentration())
    assert big.low_cycle and any("baixo ciclo" in w for w in big.warnings)
    assert any("Sy" in w for w in big.warnings)


def test_miner_damage_and_repetitions():
    m = mat()
    c = ft.build_sn(m, 200.0)
    n1 = c.life(300.0)
    res = ft.miner([ft.Block("A", 300.0, 0.0, n1 / 2), ft.Block("B", 300.0, 0.0, n1 / 4)], m, c)
    assert res["damage"] == pytest.approx(0.75) and res["repetitions"] == pytest.approx(1 / 0.75)
    assert res["cycles_to_failure"] == pytest.approx(res["repetitions"] * (n1 * 0.75))
    sub = ft.miner([ft.Block("baixo", 100.0, 0.0, 1e9)], m, c)
    assert sub["damage"] == 0 and math.isinf(sub["repetitions"])
    with pytest.raises(ValueError):
        ft.miner([ft.Block("x", 100, 0, -1)], m, c)
    assert ft.life_hours(3600 * 10, 10.0) == pytest.approx(1.0)
    with pytest.raises(ValueError):
        ft.life_hours(1, 0)
    pts = ft.sn_points(c)
    assert pts[0][1] == pytest.approx(c.sf1e3) and pts[-1][1] == c.se


def _spring(**kw):
    d = dict(wire_d=3.0, coil_d=15.0, active_coils=6.0, total_coils=6.0, installed_len=30.0, lift=7.7, preload_force=100.0,
             g_mpa=79300.0, density_g_cm3=7.85, su=1800.0, sse=450.0)
    d.update(kw)
    return ft.SpringInputs(**d)


def test_spring_rate_stress_and_checks():
    r = ft.spring_analysis(_spring())
    assert r["k"] == pytest.approx(79300 * 81 / (8 * 3375 * 6))                # N/mm (G d⁴ / 8 D³ Na)
    assert r["f_max"] == pytest.approx(100 + r["k"] * 7.7) and r["C"] == pytest.approx(5.0)
    kb = (4 * 5 + 2) / (4 * 5 - 3)
    fa = r["k"] * 7.7 / 2
    assert r["tau_a"] == pytest.approx(kb * 8 * 15 * fa / (math.pi * 27))
    assert r["solid_len"] == 18.0 and r["clearance_to_solid"] == pytest.approx(30 - 7.7 - 18)
    assert r["ssu"] == pytest.approx(0.67 * 1800)
    assert r["mass_kg"] == pytest.approx(7.85e-3 * (math.pi * 9 / 4) * (math.pi * 15 * 6) * 1e-3, rel=1e-9)
    assert 100 < r["fn_hz"] < 3000 and r["max_rpm_13x"] == pytest.approx(r["fn_hz"] / 13 * 120)
    assert r["n_f"] > 0
    assert any("sólida" in w for w in ft.spring_analysis(_spring(lift=15.0))["warnings"])
    assert any("C =" in w for w in ft.spring_analysis(_spring(coil_d=45.0))["warnings"])
    with pytest.raises(ValueError):
        ft.spring_analysis(_spring(sse=0))


def test_fatigue_tab_widget_flow():
    from PySide6.QtWidgets import QApplication
    from interface.fatigue_tab import FatigueTab
    QApplication.instance() or QApplication([])
    t = FatigueTab()
    assert t.result is None and "Su e Sy" in t.out.text()                    # sem dados: pede os valores, não inventa
    t.su.setValue(690); t.sy.setValue(580); t.se_p.setValue(345)
    t.sec_kind.setCurrentText("Círculo cheio"); t.sd.setValue(20); t.d_eq.setValue(20)
    t.load_type.setCurrentText("Flexão")
    t.ld["bending"][0].setValue(-1.8e5); t.ld["bending"][1].setValue(1.8e5)
    assert t.result is not None and not t.result.infinite and "ciclos" in t.out.text()
    assert t.plot.point is not None and not t.plot.grab().toImage().isNull()
    t.add_current_block(); t.m_table.item(0, 2).setText("1e5")
    res = t.calc_miner()
    assert res and res["damage"] > 0 and "Dano por repetição" in t.m_out.text()
    assert t.calc_spring() is None and "densidade" in t.s_out.text()          # sem material do fio: recusa
    t._density = 7.85
    t.spring_preset()
    assert t.sp["wire_d"].value() == 3.0 and t.sp["lift"].value() > 7.0
    assert t.calc_spring() is None                                            # G, Su, Sse não digitados → recusa
    for k, v in (("g_mpa", 79300), ("su", 1800), ("sse", 450), ("preload_force", 100)):
        t.sp[k].setValue(v)
    sr = t.calc_spring()
    assert sr and sr["n_f"] > 0 and "Taxa k" in t.s_out.text()
    assert t.calc_valvetrain() is None and "massa equivalente" in t.s_out.text()      # sem massa: recusa
    t.vt_mass.setValue(60.0)
    t.vt_rpm.setValue(3000)
    r1 = t.calc_valvetrain()
    assert r1 and "Dinâmica da válvula" in t.s_out.text() and r1["f_min"] > 0 and not r1["floats"]
    t.vt_rpm.setValue(30000)
    r2 = t.calc_valvetrain()
    assert r2["f_min"] < r1["f_min"] and "FLUTUA" in t.s_out.text() and t.s_out.text().count("— Dinâmica") == 1
    txt = t.report_text()
    assert "Miner" in txt and "Mola helicoidal" in txt and "não é elementos finitos" in txt


def test_valvetrain_contact_force_and_float_rpm():
    import numpy as np
    from modules import valvetrain as vt
    th = np.arange(0, 721, 1.0)
    lift = np.where((th > 300) & (th < 540), 8.0 * (np.sin(np.pi * (th - 300) / 240)) ** 2, 0.0)       # exemplo suave (C¹)
    f_slow = vt.contact_force(lift, 1.0, 10.0, 0.08, 30.0, 150.0)
    assert len(f_slow) == 720
    assert np.allclose(f_slow, 150.0 + 30.0 * lift[:-1], atol=0.5)                  # rpm→0: só a mola
    assert vt.contact_force(lift, 1.0, 6000.0, 0.08, 30.0, 150.0).min() < f_slow.min()   # inércia reduz a força mínima
    fr = vt.float_rpm(lift, 1.0, 0.08, 30.0, 150.0)
    assert 500 < fr < 40000
    below = vt.contact_force(lift, 1.0, fr * 0.97, 0.08, 30.0, 150.0).min()
    above = vt.contact_force(lift, 1.0, fr * 1.03, 0.08, 30.0, 150.0).min()
    assert below > 0 > above
    assert vt.float_rpm(lift, 1.0, 0.2, 30.0, 150.0) < fr                           # mais massa flutua antes
    assert vt.float_rpm(lift, 1.0, 0.08, 60.0, 150.0) > fr                          # mola mais dura flutua depois
    res = vt.analyze_valvetrain(lift, 1.0, fr * 1.2, 0.08, 30.0, 150.0)
    assert res["floats"] and res["f_min"] < 0 and 300 < res["angle_at_min_deg"] < 540
    with pytest.raises(ValueError):
        vt.contact_force(lift, 1.0, 0.0, 0.08, 30.0, 150.0)
