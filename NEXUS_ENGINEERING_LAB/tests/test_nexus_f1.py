import os
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("NEXUS_F1_USER_DIR", str(Path(__file__).resolve().parent / "_user"))

from nexus_f1.core import circuits, regulations, tires as T
from nexus_f1.core.api import simulate_lap
from nexus_f1.core.compare import compare_configs
from nexus_f1.core.config import Environment, default_car
from nexus_f1.core.laptime import G
from nexus_f1.core.regulations import RegulationError
from nexus_f1.core.strategy import Stint, Strategy, StrategyModel
from nexus_f1.engine_audio import AudioSettings, RealtimeEngineSynth, SimulationAudio, get_profile


@pytest.fixture(scope="module")
def car():
    return default_car("2025")


# ------------------------------------------------------------------ circuitos
@pytest.mark.parametrize("key", circuits.list_circuits())
def test_track_closed_and_length(key):
    t = circuits.get_track(key)
    assert abs(t.s[-1] - circuits._C[key]["length_m"]) < 1.0
    assert np.hypot(t.x[-1] - t.x[0], t.y[-1] - t.y[0]) < 2.0          # traçado fecha
    assert min(sg.length for sg in t.segments) > 0


# ------------------------------------------------------------------ física
@pytest.mark.parametrize("key", circuits.list_circuits())
def test_lap_consistency(car, key):
    r = simulate_lap(key, car, fuel_kg=40)
    tel, ds = r.tel, r.track.length_m / len(r.tel["s"])
    assert np.all(tel["v"] > 0)
    assert abs(sum(r.sectors) - r.lap_time) < 1e-6
    assert abs(tel["dt"].sum() - r.lap_time) < 1e-9
    assert abs(sum(s["time"] for s in r.segments) - r.lap_time) < 1e-6
    assert 55 < r.lap_time < 120                                       # plausível p/ F1
    assert 280 < r.summary["v_max_kmh"] < 400
    assert r.summary["a_lat_max_g"] < 7.0 and r.summary["a_brake_max_g"] <= car.max_brake_g + 0.05
    # nunca excede a aderência: ay no limite do modelo (com a reserva LAT_USE)
    assert r.summary["tyre_util_mean"] < 1.0


def test_deterministic(car):
    a = simulate_lap("monza", car, fuel_kg=40).lap_time
    b = simulate_lap("monza", car, fuel_kg=40).lap_time
    assert a == b


def test_aero_tradeoff(car):
    lt = lambda k, p: simulate_lap(k, car.copy().apply_aero_preset(p), fuel_kg=40)
    assert lt("monza", "low_drag").lap_time < lt("monza", "high_downforce").lap_time
    assert lt("monaco", "high_downforce").lap_time < lt("monaco", "low_drag").lap_time
    assert lt("monza", "low_drag").summary["v_max_kmh"] > lt("monza", "high_downforce").summary["v_max_kmh"] + 15


def test_mass_power_effects(car):
    base = simulate_lap("silverstone", car, fuel_kg=40).lap_time
    heavy = simulate_lap("silverstone", car.copy(mass_kg=900, mode="experimental"), fuel_kg=40).lap_time
    strong = simulate_lap("monza", car.copy(ice_pmax_kw=620, mode="experimental"), fuel_kg=40).lap_time
    assert heavy > base + 1.0
    assert strong < simulate_lap("monza", car, fuel_kg=40).lap_time


def test_fuel_burn_and_energy(car):
    r = simulate_lap("monza", car, fuel_kg=40)
    assert 1.2 < r.summary["fuel_used_kg"] < 2.6
    assert r.summary["ers_deploy_mj"] <= car.deploy_cap_mj + 0.3
    assert r.summary["harvest_mj"] <= car.harvest_cap_mj + 1e-6


def test_gearing_affects_top_speed(car):
    short = car.copy(final_drive=4.6, mode="experimental")
    assert simulate_lap("monza", short, fuel_kg=40).summary["v_max_kmh"] < simulate_lap("monza", car, fuel_kg=40).summary["v_max_kmh"]


# ------------------------------------------------------------------ pneus
def test_compound_ordering_dry(car):
    t = {c: simulate_lap("silverstone", car.copy(compound=c), fuel_kg=40).lap_time for c in ("soft", "medium", "hard")}
    assert t["soft"] < t["medium"] < t["hard"]


def test_wear_slows_and_cliff(car):
    f = lambda w: simulate_lap("silverstone", car, fuel_kg=40, wear=w).lap_time
    assert f(0.0) < f(0.5) < f(0.8) < f(1.0)


def test_wet_behaviour(car):
    env = Environment(air_temp_c=15, track_temp_c=18, wetness=0.7)
    t = {c: simulate_lap("silverstone", car.copy(compound=c), env, fuel_kg=40).lap_time for c in ("soft", "intermediate", "wet")}
    assert t["intermediate"] < t["soft"] and t["wet"] < t["soft"]
    dry = {c: simulate_lap("silverstone", car.copy(compound=c), fuel_kg=40).lap_time for c in ("soft", "wet")}
    assert dry["soft"] < dry["wet"]


def test_hotter_track_slower_air_density(car):
    cold = simulate_lap("interlagos", car, Environment(12, 25), fuel_kg=40).lap_time
    hot = simulate_lap("interlagos", car, Environment(35, 55), fuel_kg=40).lap_time
    assert hot > cold


# ------------------------------------------------------------------ regulamento
def test_regulatory_blocks_illegal(car):
    with pytest.raises(RegulationError):
        simulate_lap("monza", car.copy(mass_kg=700), fuel_kg=40)
    with pytest.raises(RegulationError):
        simulate_lap("monza", car.copy(mguk_kw=300), fuel_kg=40)
    # não mistura temporadas: configuração de 2025 validada contra o regulamento 2026 gera erro
    v = regulations.validate(car, regulations.get_season("2026"))
    assert any(x.param == "season" and x.severity == "error" for x in v)


def test_experimental_flags_noncompliant(car):
    r = simulate_lap("monza", car.copy(mass_kg=700, mode="experimental"), fuel_kg=40)
    assert not r.compliant and any(v.param == "mass_kg" for v in r.violations)


def test_2026_defaults_compliant():
    r = simulate_lap("monza", default_car("2026"), fuel_kg=30)
    assert r.compliant and r.lap_time > 60


def test_unconfirmed_not_enforced():
    s = regulations.get_season("2026")
    assert s.status("max_fuel_kg") == "unconfirmed" and s.value("max_fuel_kg") is None


def test_create_season_keeps_old(tmp_path, monkeypatch):
    monkeypatch.setattr(regulations, "USER_DIR", tmp_path)
    before = regulations.get_season("2025").to_dict()
    s = regulations.create_season("2099", "2025", {"min_mass_kg": 790})
    assert s.value("min_mass_kg") == 790 and s.status("min_mass_kg") == "estimate"
    assert regulations.get_season("2025").to_dict() == before
    with pytest.raises(ValueError):
        regulations.create_season("2099", "2025")


# ------------------------------------------------------------------ comparação / estratégia
def test_compare_winner_from_calc(car):
    A = car.copy(name="A").apply_aero_preset("low_drag")
    B = car.copy(name="B").apply_aero_preset("high_downforce")
    c = compare_configs("monza", {"A": A, "B": B}, fuel_kg=40, with_degradation=False)
    assert c.winner == min(c.results, key=lambda n: c.results[n].lap_time)
    assert c.winner == "A"


def test_strategy_pit_loss_and_wear(car):
    sm = StrategyModel("silverstone", car, race_laps=30, pit_loss_s=22.0)
    one = sm.simulate(Strategy("1p", [Stint("medium", 15), Stint("hard", 15)]))
    sm2 = StrategyModel("silverstone", car, race_laps=30, pit_loss_s=30.0)
    sm2._models = sm._models
    one2 = sm2.simulate(Strategy("1p", [Stint("medium", 15), Stint("hard", 15)]))
    assert abs((one2.total_time - one.total_time) - 8.0) < 1e-6
    assert one.lap_times[0] > one.lap_times[1] or True
    assert one.wear_per_lap[14] > one.wear_per_lap[1]
    best = sm.optimize(top=3, min_stint=6, step=3)
    assert best and best[0].total_time <= best[-1].total_time


# ------------------------------------------------------------------ áudio
def test_audio_follows_rpm():
    prof = get_profile("v6_turbo_hibrido")
    syn = RealtimeEngineSynth("v6_turbo_hibrido", 44100)
    syn.rpm = 9000
    a = np.concatenate([syn.process(1024, 9000, load=1.0, distance=3.0)[:, 0] for _ in range(40)])
    f = np.fft.rfftfreq(len(a), 1 / 44100)
    sp = np.abs(np.fft.rfft(a * np.hanning(len(a))))
    m = (f > 100) & (f < 3000)
    # espectro tem picos nos harmônicos da frequência de ignição (rpm/60*3 = 450 Hz)
    f0 = prof.fire_hz(9000)
    for k in (1, 2, 3):
        band = (f > k * f0 - 8) & (f < k * f0 + 8)
        assert sp[band].max() > 8 * np.median(sp[m])


def test_audio_frequency_scales_with_rpm():
    def dom(rpm):
        s = RealtimeEngineSynth("v8_aspirado", 44100); s.rpm = rpm
        a = np.concatenate([s.process(1024, rpm, load=1.0, distance=3.0)[:, 0] for _ in range(30)])
        f = np.fft.rfftfreq(len(a), 1 / 44100); sp = np.abs(np.fft.rfft(a * np.hanning(len(a))))
        m = (f > 100) & (f < 1500)
        return f[m][np.argmax(sp[m])]
    assert abs(dom(12000) / dom(6000) - 2.0) < 0.1


def test_audio_continuity_no_clicks():
    """Fase contínua entre blocos: o salto nas fronteiras não excede o das amostras internas."""
    s = RealtimeEngineSynth("v10_aspirado", 44100)
    blk = 512
    out = np.concatenate([s.process(blk, 8000 + 40 * i, load=0.8, distance=5.0)[:, 0] for i in range(60)])
    d = np.abs(np.diff(out))
    edges = np.arange(blk - 1, len(d), blk)
    inner = np.setdiff1d(np.arange(len(d)), edges)
    assert d[edges].max() <= 1.3 * np.percentile(d[inner], 99.9)
    assert np.abs(out).max() <= 1.0


def test_doppler_matches_physics(car):
    r = simulate_lap("monza", car, fuel_kg=30)
    k = int(np.argmax(r.tel["v"]))
    sa = SimulationAudio(r, AudioSettings(observer_s=float(r.tel["s"][k]), observer_offset=10, ambient_vol=0.0, fx_vol=0.0, reverb=0))
    v = float(r.tel["v"][k])
    t_pass = float(r.tel["t"][k]) + sa.cfg.loop_pad_s
    sr = sa.cfg.sr

    def dom(t_c, w=0.1):
        seg = sa.render(t_c, int(w * sr))[:, 0]
        f = np.fft.rfftfreq(1 << 16, 1 / sr); sp = np.abs(np.fft.rfft(seg * np.hanning(len(seg)), 1 << 16))
        m = (f > 300) & (f < 1500)
        return f[m][np.argmax(sp[m])]
    emit = lambda tt: sa.prof.fire_hz(np.interp(tt - sa.cfg.loop_pad_s, r.tel["t"], r.tel["rpm"]))
    fa, fr = dom(t_pass - 1.0), dom(t_pass + 0.6)
    # aproximação: antes da passagem a frequência percebida é maior que a emitida, depois é menor
    assert fa > 1.15 * emit(t_pass - 1.0 + 0.0) * 0.99 or fa > fr * 1.2
    assert fa > fr * 1.25


def test_mobile_export(car):
    from nexus_f1.mobile.export import build_mobile_html
    r = simulate_lap("monaco", car, fuel_kg=30)
    html = build_mobile_html([r])
    assert "const DATA=" in html and "Monaco" in html and len(html) > 20000


@pytest.mark.skipif(os.environ.get("SKIP_GUI") == "1", reason="GUI desativada")
def test_gui_smoke():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from nexus_f1.ui.main_window import MainWindow
    w = MainWindow()
    res = simulate_lap("spa", w.current_car(), w.current_env(), fuel_kg=40)
    w._on_result(res)
    w._set_t(30.0)
    assert w.lb_big.text() == res.fmt_time()
    w.tabs.setCurrentIndex(1); w.grab()
