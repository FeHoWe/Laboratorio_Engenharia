"""Testes V2.2: projetos predefinidos, biblioteca de peças, mecanismo da F1, laboratório (aero/estrutural)."""
import math
import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from modules import aero, structural as st  # noqa: E402
from samples import geo as g  # noqa: E402
from samples.library import PARTS  # noqa: E402
from samples.projects import all_projects, get, project_for_name  # noqa: E402


# ------------------------------------------------------------------ aerodinâmica
def test_isa_sea_level_and_tropopause():
    a = aero.isa(0)
    assert a["rho"] == pytest.approx(1.225, abs=1e-3) and a["p"] == pytest.approx(101325) and a["a"] == pytest.approx(340.29, abs=0.05)
    assert aero.isa(11000)["T"] == pytest.approx(216.65, abs=1e-6)
    assert aero.isa(5000)["rho"] == pytest.approx(0.7364, abs=2e-3)
    with pytest.raises(ValueError):
        aero.isa(30000)


def test_lifting_line_elliptic_wing_is_ideal():
    r = aero.lifting_line(10.0, lambda s: math.sqrt(max(1 - s * s, 0.0)), 5.0)
    assert r.e == pytest.approx(1.0, abs=1e-3)
    assert r.cl_alpha == pytest.approx(2 * math.pi / (1 + 2 / r.ar), rel=2e-3)
    assert r.cdi == pytest.approx(r.cl ** 2 / (math.pi * r.ar), rel=1e-3)


def test_rectangular_wing_less_efficient_and_taper_helps():
    rect = aero.lifting_line(10.0, 1.0, 5.0)
    taper = aero.lifting_line(10.0, lambda s: 1.0 * (1 - 0.6 * abs(s)), 5.0)
    assert 0.88 < rect.e < 0.97
    assert taper.e > rect.e


def test_naca2412_alpha_l0_and_ground_effect():
    assert math.degrees(aero.naca4_alpha_l0(0.02, 0.4)) == pytest.approx(-2.07, abs=0.1)
    free = aero.lifting_line(1.6, 0.35, 8.0, -4.0)
    near = aero.lifting_line(1.6, 0.35, 8.0, -4.0, h_ground=0.2)
    assert near.cdi < free.cdi and near.cl == pytest.approx(free.cl)


def test_vehicle_top_speed_and_cornering():
    v = aero.Vehicle(mass=800, cda=1.0, cla=0.0, power=500e3, mu_tyre=1.5, crr=0.0)
    vmax = v.top_speed()
    assert v.power_required(vmax) == pytest.approx(500e3, rel=1e-6)
    assert vmax == pytest.approx((2 * 500e3 / (1.225 * 1.0)) ** (1 / 3), rel=1e-6)          # P = ½ρ CdA V³
    assert v.corner_speed(100) == pytest.approx(math.sqrt(1.5 * 9.80665 * 100), rel=1e-9)   # sem downforce: v=√(μ g R)
    v2 = aero.Vehicle(mass=800, cda=1.0, cla=3.0, power=500e3, mu_tyre=1.5)
    assert v2.corner_speed(100) > v.corner_speed(100)
    assert aero.Vehicle(mass=100, cda=1, cla=10, power=1e5, mu_tyre=2.0).corner_speed(100) == math.inf


# ------------------------------------------------------------------ estrutural
def test_beam_closed_forms():
    sec = st.circle(20)
    r = st.beam("cant_end", 100, 500, 210000, sec, 300)
    assert r["deflection"] == pytest.approx(100 * 500 ** 3 / (3 * 210000 * sec.inertia), rel=1e-12)
    assert r["sigma"] == pytest.approx(100 * 500 * 10 / sec.inertia, rel=1e-12)
    assert r["safety_factor"] == pytest.approx(300 / r["sigma"])
    assert st.beam("ss_udl", 1, 1000, 210000, st.rect(20, 40))["deflection"] == pytest.approx(5 * 1000 ** 4 / (384 * 210000 * 20 * 40 ** 3 / 12))


def test_buckling_regimes_and_bolt():
    slender = st.column_buckling(210000, st.circle(20), 1000, 1.0, 300)
    stocky = st.column_buckling(210000, st.circle(20), 200, 1.0, 300)
    assert slender["regime"].startswith("Euler") and stocky["regime"].startswith("Johnson")
    assert stocky["p_crit"] < st.circle(20).area * 300
    b = st.bolt_joint(10, 40, 0.2, 640, 5000)
    assert b["preload"] == pytest.approx(40000 / (0.2 * 10)) and b["bolt_load"] > b["preload"] and b["clamp_load"] < b["preload"]


def test_torsion_vessel_vibration():
    assert st.shaft_torsion(1e5, 30, 500, 80000)["tau"] == pytest.approx(16 * 1e5 / (math.pi * 30 ** 3), rel=1e-9)
    assert st.thin_vessel(2, 200, 3)["hoop"] == pytest.approx(66.667, abs=1e-3)
    assert st.spring_mass_fn(10, 1) == pytest.approx(15.9155, abs=1e-3)
    assert st.cantilever_fn(210000, st.rect(20, 5), 300, 7850) == pytest.approx(46.4, abs=0.2)


def test_lab_tab_runs_all_calculators():
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from interface.lab_tab import LabTab
    out = LabTab().run_all()
    assert len(out) == 9
    for k, text in out.items():
        assert "Não foi possível" not in text, (k, text)
        assert "Hipóteses" in text
    # entrada inválida vira mensagem, não exceção
    from interface.lab_tab import LabTab as T
    t = T()
    t.widgets["column"].set_value("L", 1)
    assert isinstance(t.widgets["column"].compute(), str)


# ------------------------------------------------------------------ biblioteca
@pytest.mark.parametrize("key", sorted(PARTS))
def test_library_parts_make_valid_solids(key):
    shp = PARTS[key].make()
    assert g.volume(shp) > 0
    lo, hi = g.bbox(shp)
    assert all(h > l for l, h in zip(lo, hi))


def test_library_rejects_out_of_range():
    p = PARTS["parafuso_sextavado"]
    with pytest.raises(ValueError):
        p.make(length=1e6)
    with pytest.raises(KeyError):
        p.make(inexistente=1)


# ------------------------------------------------------------------ projetos
def test_registry_consistent():
    keys = [p.key for p in all_projects()]
    assert keys == ["motor", "f1", "redutor", "suspensao", "ponte"]
    assert project_for_name("f1_2026").key == "f1" and project_for_name("nada") is None
    assert get("f1").material_for("Halo arco direito") == "Titanium Ti-6Al-4V (Grade 5)"
    assert get("f1").material_for("Monocoque (celula de sobrevivencia)") is None            # compósito: não consta do banco
    assert get("f1").material_for("Halo pilar central") == get("f1").typical["Halo"]


def test_small_projects_build_and_export(tmp_path):
    from core.cad_engine import CadEngine
    from modules.importer import ProjectImporter
    for key, n_min in (("redutor", 40), ("suspensao", 20)):
        pd = get(key)
        path = tmp_path / pd.step_name
        mod = __import__(pd.module, fromlist=["write"])
        mod.write(path)
        res = ProjectImporter(CadEngine()).import_file(path)
        assert len(list(res.root.leaves())) >= n_min, key


def test_f1_mechanism_and_materials(tmp_path):
    from core.cad_engine import CadEngine
    from modules.importer import ProjectImporter
    from samples.mechanisms import build_mechanism
    pd = get("f1")
    pd.step_path.parent.mkdir(exist_ok=True)
    path = pd.ensure_step()
    res = ProjectImporter(CadEngine()).import_file(path)

    class C:
        def leaves(self_inner):
            return list(res.root.leaves())
    mech = build_mechanism(C())
    assert len(mech.links) == 4                    # rodas diant., rodas tras., flap diant., elemento tras.
    for link in mech.links:
        for t in (0, 90, 360, 719):
            m = np.asarray(link.matrix(t) if hasattr(link, "matrix") else link.fn(t))
            assert np.all(np.isfinite(m))
            R = m[:3, :3]
            assert np.allclose(R @ R.T, np.eye(3), atol=1e-9) and np.linalg.det(R) == pytest.approx(1.0)
    flap = mech.links[2]
    m0 = np.asarray(flap.fn(0))
    m360 = np.asarray(flap.fn(360))
    assert np.allclose(m0, np.eye(4), atol=1e-9) and not np.allclose(m360, np.eye(4))
    assert np.allclose(np.asarray(flap.fn(720)), np.eye(4), atol=1e-9)             # periódico


# ------------------------------------------------------------------ janela
def test_window_predefined_library_and_materials(engine):
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from interface.main_window import MainWindow
    w = MainWindow(engine=engine)
    try:
        w.open_predefined("redutor", ask_split=False, background=False)
        n = len(w.project.components.leaves())
        assert n >= 40 and w.project.name == "redutor_2_estagios"
        assert w.apply_typical_materials() > 20
        w.add_library_part("parafuso_sextavado", {"length": 40}, pos=(500, 0, 0))
        assert len(w.project.components.leaves()) == n + 1
        added = [l for l in w.project.components.leaves() if "Parafuso sextavado" in l.name]
        assert added and added[-1].material is None                              # nunca atribui material sozinho
        w.add_library_part("rolamento_esferas", None, new_project=True)
        assert len(w.project.components.leaves()) == 1
        w.open_lab()
        assert w.central_tabs.currentWidget() is w.lab_tab
    finally:
        w.project.dirty = False
        w.close()
