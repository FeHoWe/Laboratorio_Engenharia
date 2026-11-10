import os
import sys
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nexus_f1.core import analysis as A  # noqa: E402
from nexus_f1.core.api import simulate_lap  # noqa: E402
from nexus_f1.core.config import default_car  # noqa: E402


@pytest.fixture(scope="module")
def base():
    c = default_car("2025")
    return c, simulate_lap("monza", c, fuel_kg=40, ds=8.0)


def test_delta_time_closes_on_lap_difference(base):
    c, r1 = base
    r2 = simulate_lap("monza", c.copy(mass_kg=c.mass_kg + 30), fuel_kg=40, ds=8.0)
    d = A.delta_time(r1, r2)
    assert abs(d["final"] - (r2.lap_time - r1.lap_time)) < 0.02 and d["final"] > 0 and d["delta"][0] == 0.0
    assert abs(sum(x["dt"] for x in A.segment_deltas(r1, r2)) - (r2.lap_time - r1.lap_time)) < 1e-6
    with pytest.raises(ValueError):
        A.delta_time(r1, simulate_lap("monaco", c, fuel_kg=40, ds=8.0))


def test_math_channel_safe_and_correct(base):
    _, r = base
    assert np.allclose(A.math_channel(r, "v*3.6"), r.tel["v_kmh"])
    assert np.allclose(A.math_channel(r, "hypot(ax_g, ay_g)"), np.hypot(r.tel["ax_g"], r.tel["ay_g"]))
    assert A.math_channel(r, "5").shape == r.tel["s"].shape
    for bad in ("__import__('os').system('x')", "v.sum()", "v[0]", "open('f')", "lambda: 1", "foo*2", "(1).__class__"):
        with pytest.raises((ValueError, SyntaxError)):
            A.math_channel(r, bad)


def test_gg_hist_gear_stats(base):
    _, r = base
    g = A.gg_diagram(r)
    assert np.abs(g["ay"]).max() > 1.0 and g["ax_min"].min() < -1.0
    h = A.histogram(r, "v_kmh", 16)
    assert abs(h["counts_s"].sum() - r.lap_time) < 1e-6 and abs(h["pct"].sum() - 100) < 1e-6
    assert abs(sum(A.gear_usage(r).values()) - r.lap_time) < 1e-6
    st = A.throttle_brake_stats(r)
    assert all(0 <= x <= 100 for x in st.values())


def test_sweep_sensitivity_optimizers(base):
    c, _ = base
    s = A.sweep("monza", c, "ice_pmax_kw", [500, 560, 620], fuel_kg=40)
    assert s["lap_times"][0] > s["lap_times"][1] > s["lap_times"][2]           # mais potência, volta mais rápida
    rows = A.sensitivity("monza", c, ["mass_kg", "ice_pmax_kw"], fuel_kg=40)
    d = {x["param"]: x["d_lap_por_pct"] for x in rows}
    assert d["mass_kg"] > 0 > d["ice_pmax_kw"]
    # Monza (retões) quer pouca asa; Mônaco quer muita
    assert A.optimize_aero("monza", c, fuel_kg=40)["best_level"] < A.optimize_aero("monaco", c, fuel_kg=40)["best_level"]
    o = A.optimize_param("monza", c, "final_drive", 3.0, 5.0, fuel_kg=40)
    assert 3.0 <= o["best_value"] <= 5.0 and o["best_time"] <= A.sweep("monza", c, "final_drive", [5.0], fuel_kg=40)["best_time"]
    with pytest.raises(ValueError):
        A.sweep("monza", c, "name", [1])


def test_analysis_tab_runs_all_modes():
    from PySide6.QtWidgets import QApplication
    from nexus_f1.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    tab = next(w.tabs.widget(i) for i in range(w.tabs.count()) if w.tabs.tabText(i) == "Análise")
    w.slots["A"] = w.current_car().copy(name="A"); w.slots["B"] = w.current_car().copy(name="B", mass_kg=830)
    for i in range(tab.cb.count()):
        tab.cb.setCurrentIndex(i)
        tab.ed.setText("v*3.6")
        tab.run()
        assert not tab.out.text().startswith("⚠"), (i, tab.out.text())
    w.close()


def test_main_window_opens_f1_simulator():
    from PySide6.QtWidgets import QApplication
    from interface.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    assert "f1sim" in w.actions_map if hasattr(w, "actions_map") else True
    w.show_f1sim()
    assert w._f1sim.tabs.count() >= 10 and w._f1sim.isVisible()
    w._f1sim.close()
    w.close()
