"""Dinâmica lateral: casos com solução analítica conhecida."""
import math
import pytest
from modules import vehicle_lateral as vl
from modules.vehicle_lateral import VeiculoLateral, G, exemplo_ilustrativo


def _lin(**kw):
    # pneus quase lineares (μ enorme) e sem transferência de carga (h = 0 no limite) para comparar com a fórmula fechada
    d = dict(m=1500.0, iz=2500.0, a=1.2, b=1.4, h=1e-6, tf=1.5, tr=1.5, c_f=40000.0, c_r=50000.0, mu_f=50.0, mu_r=50.0)
    d.update(kw)
    return VeiculoLateral(**d)


def test_understeer_gradient_matches_closed_form():
    v = _lin()
    K = vl.gradiente_subesterco_linear(v)
    assert K > 0
    r = vl.regime_curva(v, 10.0, 200.0)                       # ay pequeno → regime linear
    assert r["k_subesterco"] == pytest.approx(K, rel=2e-3)
    assert r["delta"] == pytest.approx(v.L / 200.0 + K * r["ay_ms2"], rel=2e-3)   # δ = L/R + K·ay
    assert r["comportamento"] == "subesterçante"


def test_neutral_and_oversteer_signs():
    v = _lin(c_f=90000.0, c_r=40000.0)
    assert vl.regime_curva(v, 10.0, 200.0)["comportamento"] == "sobresterçante"
    # neutro: Wf/Cf = Wr/Cr  →  Cf/Cr = b/a
    vn = _lin(c_f=60000.0, c_r=60000.0 * 1.2 / 1.4)   # Cf/Cr = b/a → Wf/Cf = Wr/Cr (Wf ∝ b, Wr ∝ a)
    assert abs(vl.gradiente_subesterco_linear(vn)) < 1e-12


def test_lateral_load_transfer_formula():
    v = _lin(h=0.5, h_rc_f=0.0, h_rc_r=0.0, k_roll_f=50000.0, k_roll_r=50000.0, a=1.3, b=1.3)   # CG no meio, rolagem 50/50
    ay = 0.8 * G
    cg = vl.cargas_eixos(v, 20.0, ay)
    esperado = v.m * ay * v.h / (2 * v.tf) / 1.0 / 1.0                          # ΔFz_f=ΔFz_r = m·ay·h/(2·t)
    assert cg["dzf"] == pytest.approx(esperado, rel=1e-12) and cg["dzr"] == pytest.approx(esperado, rel=1e-12)
    # equilíbrio: a soma das 4 cargas é o peso
    assert sum(cg[k] for k in ("f_int", "f_ext", "r_int", "r_ext")) == pytest.approx(v.m * G, rel=1e-12)


def test_skidpad_limit_without_aero_is_mu_g():
    v = _lin(mu_f=1.3, mu_r=1.3, h=0.4, h_rc_f=0.0, h_rc_r=0.0)
    # carga vertical repartida igualmente entre pneus + saturação: ay_lim ≈ μ·g (transferência não reduz soma com pneu μ constante)
    lim = vl.ay_limite(v, 20.0)
    assert lim["ay_g"] == pytest.approx(1.3, rel=1e-6)
    sp = vl.skidpad(v, 50.0)
    assert sp["v_ms"] == pytest.approx(math.sqrt(1.3 * G * 50.0), rel=1e-6)


def test_downforce_raises_skidpad_speed():
    v0 = exemplo_ilustrativo()
    v1 = VeiculoLateral(**{**v0.__dict__, "cla": 3.0})
    assert vl.skidpad(v1, 80.0)["v_ms"] > vl.skidpad(v0, 80.0)["v_ms"]


def test_limit_axis_identification():
    v = _lin(mu_f=1.0, mu_r=1.6, c_f=60000, c_r=60000)       # frente com menos atrito → satura primeiro
    assert "subesterço" in vl.ay_limite(v, 20.0)["limite"]
    v2 = _lin(mu_f=1.6, mu_r=1.0)
    assert "sobresterço" in vl.ay_limite(v2, 20.0)["limite"]


def test_saturated_corner_reports_no_steering_numbers():
    r = vl.regime_curva(exemplo_ilustrativo(), 60.0, 30.0)    # ay = 12 g: impossível
    assert r["saturado"] and "delta" not in r
    t = vl.resumo_curva(exemplo_ilustrativo(), 60.0, 30.0, ilustrativo=True)
    assert "delta_deg" not in t.valores and t.valores["saturado"] is True


def test_step_steer_converges_to_steady_state():
    v = _lin()
    vel, delta = 20.0, math.radians(0.5)
    hist = vl.degrau_esterco(v, vel, delta, t_final=6.0, dt=0.002)
    K = vl.gradiente_subesterco_linear(v)
    r_ss = vel * delta / (v.L + K * vel * vel)               # ganho de guinada em regime: r = V·δ/(L + K·V²)
    assert hist[-1][2] == pytest.approx(r_ss, rel=5e-3)
    assert hist[0][2] == 0.0 and all(math.isfinite(x) for row in hist for x in row)


def test_validation_and_traced_result():
    with pytest.raises(ValueError):
        VeiculoLateral(**{**exemplo_ilustrativo().__dict__, "m": -1}).validar()
    with pytest.raises(ValueError):
        vl.regime_curva(exemplo_ilustrativo(), 0.0, 50.0)
    t = vl.resumo_curva(exemplo_ilustrativo(), 20.0, 100.0, ilustrativo=True)
    assert t.classe == "ANALITICO" and any("ILUSTRATIVO" in p for p in t.premissas)
    assert t.valores["comportamento"] in ("subesterçante", "neutro", "sobresterçante")


def test_brush_tire_properties():
    fz, c, mu = 4000.0, 50000.0, 1.2
    assert vl.pneu_fy(1e-5, fz, c, mu) == pytest.approx(c * 1e-5, rel=1e-3)          # inclinação inicial = C
    assert vl.pneu_fy(math.radians(30), fz, c, mu) == pytest.approx(mu * fz)          # saturado
    assert vl.pneu_fy(-0.05, fz, c, mu) == -vl.pneu_fy(0.05, fz, c, mu)               # ímpar
    assert vl.pneu_fy(0.05, 0.0, c, mu) == 0.0                                        # pneu levantado




def test_lab_tab_curva_defaults_run_and_saturation_message():
    from interface.lab_tab import calcs
    c = next(x for x in calcs() if x.key == "curva")
    vals = {f.key: f.default for f in c.fields}
    t = c.run(vals)
    assert "Gradiente de subesterço" in t and "ILUSTRATIVOS" in t and "skidpad" in t
    vals.update(v=300.0, R=20.0)                      # impossível: deve avisar e não inventar esterçamento
    t2 = c.run(vals)
    assert "NÃO sustenta" in t2 and "Esterçamento" not in t2
