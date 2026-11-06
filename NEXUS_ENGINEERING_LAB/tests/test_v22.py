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
    assert len(out) == 12
    for k, text in out.items():
        assert "Não foi possível" not in text, (k, text)
        assert "Hipóteses" in text or "Hipotese" in text
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


def _f1_components():
    from core.cad_engine import CadEngine
    from modules.importer import ProjectImporter
    pd = get("f1")
    path = pd.ensure_step()
    res = ProjectImporter(CadEngine()).import_file(path)

    class C:
        def leaves(self_inner):
            return list(res.root.leaves())
    return C(), res


def test_f1_mechanism_links_rigid_and_periodic():
    from samples.mechanisms import build_mechanism
    comps, _ = _f1_components()
    mech = build_mechanism(comps)
    assert len(mech.links) >= 55 and mech.period_deg == 720.0
    ids = [i for ln in mech.links for i in ln.ids]
    assert len(ids) == len(set(ids)) == len(comps.leaves())            # cada peça tem exatamente um movimento
    for link in mech.links:
        for t in (0, 45, 90, 200, 359, 540):
            m = np.asarray(link.fn(float(t)))
            assert np.all(np.isfinite(m))
            R = m[:3, :3]
            assert np.allclose(R @ R.T, np.eye(3), atol=1e-8) and np.linalg.det(R) == pytest.approx(1.0, abs=1e-8), link.label
        assert np.allclose(link.fn(0.0), link.fn(720.0), atol=1e-6), link.label      # ciclo fecha


def test_f1_suspension_constraints_hold_through_the_cycle():
    from samples import f1_mechanism as M, f1_2026 as F
    for t in np.arange(0.0, 720.0, 23.0):
        st = M.car_state(float(t))
        Binv = np.linalg.inv(st["B"])
        for (front, sign), cor in M._corners().items():
            key = ("F" if front else "R") + M.SIDE_KEY[sign]
            hp = cor.hp
            r = st[key]
            ap = lambda m, p: (Binv @ m @ np.append(p, 1.0))[:3]          # ponto no referencial do corpo
            u_lo, u_up = ap(r["U"], hp["lo_u"]), ap(r["U"], hp["up_u"])
            assert np.linalg.norm(u_up - u_lo) == pytest.approx(hp["d_bj"], abs=1e-6)                    # manga rígida
            assert np.linalg.norm(u_lo - ap(r["LA"], hp["lo_u"])) < 1e-6                                 # rótula inferior sobre o braço inferior
            assert np.linalg.norm(u_up - ap(r["UA"], hp["up_u"])) < 1e-6                                 # idem superior
            rack = st["sc"]["rack"] if front else 0.0
            assert np.linalg.norm(ap(r["U"], hp["tr_u"]) - (hp["tr_a"] + [rack, 0, 0])) == pytest.approx(hp["L_tr"], abs=1e-6)   # barra de direção
            assert np.linalg.norm(ap(r["U"], hp["rod_u"]) - ap(r["RK"], hp["A0"])) == pytest.approx(hp["L_rod"], abs=1e-6)       # push/pull-rod
            assert np.linalg.norm(ap(r["PR"], hp["A0"]) - ap(r["RK"], hp["A0"])) < 1e-6
            assert np.linalg.norm(ap(r["DB"], hp["M"]) - hp["M"]) < 1e-9                                  # amortecedor preso ao chassi
            assert np.linalg.norm(ap(r["DR"], hp["D0"]) - ap(r["RK"], hp["D0"])) < 1e-6                   # haste presa ao balancim
            cz = (st[key]["U"] @ np.append(hp["C"], 1.0))[2]
            assert cz == pytest.approx(F.AXLE_Z, abs=0.6)                                                # roda segue no solo


def test_f1_scenario_steering_and_aero():
    from samples import f1_mechanism as M
    assert M.wheel_angle_deg(90.0) > 10 > 0 > M.wheel_angle_deg(270.0) < -10          # esquerda em 90°, direita em 270°
    assert abs(M.wheel_angle_deg(180.0)) < 1.0                                      # reta: quase zero (só bump-steer)
    assert M.scenario(0.0)["blend"] == pytest.approx(1.0) and M.scenario(90.0)["blend"] == pytest.approx(0.0, abs=1e-12)
    assert M.car_state(90.0)["sc"]["roll"] > 0 > M.car_state(270.0)["sc"]["roll"]


def test_f1_engine_slider_crank_exact():
    from samples import f1_2026 as F, f1_mechanism as M
    for sg in (1, -1):
        for j in range(3):
            for phi in np.linspace(0, 2 * np.pi, 13):
                pp, cp = F.piston_pin(j, sg, phi), F.crank_pin(j, phi, sg)
                assert np.linalg.norm(pp - cp) == pytest.approx(F.CONROD_L, abs=1e-9)                # biela de comprimento constante
                ax = F.bank_axis(sg)
                d = pp - F.cyl_origin(j, sg)
                assert np.linalg.norm(d - np.dot(d, ax) * ax) < 1e-9                                 # pino fica no eixo do cilindro
    # curso total do pistão = 53 mm (±erro da razão biela/manivela)
    zs = [np.dot(F.piston_pin(0, 1, p) - F.cyl_origin(0, 1), F.bank_axis(1)) for p in np.linspace(0, 2 * np.pi, 721)]
    assert max(zs) - min(zs) == pytest.approx(F.STROKE, abs=0.8)
    assert np.allclose(M.piston_local(0.0, 0, 1), np.eye(4)) and np.allclose(M.rod_local(0.0, 1, -1), np.eye(4), atol=1e-9)
    assert np.allclose(M.piston_local(90.0, 0, 1), np.eye(4), atol=1e-9)                              # 90° de entrada = 1 volta do virabrequim


def test_f1_materials_registry():
    assert get("f1").material_for("Halo arco direito") == "Titanium Ti-6Al-4V (Grade 5)"
    assert get("f1").material_for("Rotor do compressor") is None


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


# ------------------------------------------------------------------ treliça (MEF de barras) e relatório
def test_truss_fem_closed_forms():
    from modules import truss_fem as T
    # triângulo: carga vertical P no ápice (simétrico) → barras inclinadas −P/(2 sin α), base em tração P/(2 tg α)
    P = 1000.0
    t = T.parse(f"NODE A 0 0 0 fix=xyz\nNODE B 1000 0 0 fix=yz\nNODE C 500 0 500 fix=y\nBAR a A C 100 200000\nBAR b B C 100 200000\nBAR c A B 100 200000\nLOAD C 0 0 -{P}")
    r = T.solve(t)
    assert r.force["a"] == pytest.approx(-P / (2 * math.sin(math.pi / 4)), rel=1e-9)
    assert r.force["c"] == pytest.approx(P / (2 * math.tan(math.pi / 4)), rel=1e-9)
    assert r.equilibrium_error < 1e-12
    # barra axial simples: u = F L/(E A)
    t = T.parse("NODE A 0 0 0 fix=xyz\nNODE B 200 0 0 fix=yz\nBAR a A B 50 210000\nLOAD B 5000 0 0")
    assert T.solve(t).displacement["B"][0] == pytest.approx(5000 * 200 / (210000 * 50), rel=1e-12)


def test_truss_warren_symmetry_and_errors():
    from modules import truss_fem as T
    t = T.parse(T.warren_example())
    r = T.solve(t)
    assert r.equilibrium_error < 1e-12
    assert r.reactions["B0"][2] == pytest.approx(r.reactions["B6"][2]) == pytest.approx(125000.0)       # 5 cargas de 50 kN / 2
    assert r.force["m7"] == pytest.approx(225000.0)                                                       # banzo inferior central: M/h = (125·6 − 50·(2+4)... ) = 225 kN
    with pytest.raises(T.TrussError):
        T.solve(T.parse("NODE A 0 0 0 fix=xyz\nNODE B 1000 0 0\nBAR a A B 100 200000\nLOAD B 0 0 -1"))      # mecanismo
    with pytest.raises(T.TrussError):
        T.parse("BAR x A B 1 1")                                                                           # nó inexistente
    with pytest.raises(T.TrussError):
        T.parse("FOO 1 2")


def test_lab_report_export(tmp_path):
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from interface.lab_tab import LabTab
    lab = LabTab()
    p = lab.widgets["beam"].export_report(str(tmp_path / "viga.md"))
    txt = open(p, encoding="utf-8").read()
    assert "## Entradas" in txt and "Flecha máxima" in txt
    q = lab.truss.export_report(str(tmp_path / "t.md"))
    assert "NODE B0" in open(q, encoding="utf-8").read()


# ------------------------------------------------------------------ interferência
def test_interference_finder_and_dialog(tmp_path, engine):
    from core.cad_engine import RawNode
    from core.geometry import translation_matrix
    from modules.importer import ProjectImporter
    from modules.interference import find_interferences, to_csv
    L = lambda n, s, x=0.0: RawNode(n, shape=s, local_matrix=translation_matrix([x, 0, 0]))
    root = RawNode("t", children=[L("A", g.box(0, 20, 0, 20, 0, 20)), L("B", g.box(10, 30, 0, 20, 0, 20)), L("C", g.box(20, 40, 0, 20, 0, 20)),   # A×B = 10·20·20; B×C = 10·20·20
                                  L("D", g.box(100, 120, 0, 20, 0, 20)), L("E", g.box(20, 40, 0, 20, 0, 20)) if False else L("F", g.box(120, 140, 0, 20, 0, 20))])
    path = tmp_path / "t.step"
    engine.write_step([root], path)
    res = ProjectImporter(engine).import_file(path)

    class C:
        def leaves(self_inner):
            return list(res.root.leaves())
    cl = find_interferences(C(), 1.0)
    assert len(cl) == 2 and all(abs(c.volume - 4000.0) < 1.0 for c in cl)            # D×F e A×C apenas se tocam em face: não contam
    assert "volume_mm3" in to_csv(cl)
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from interface.main_window import MainWindow
    w = MainWindow(engine=engine)
    try:
        w.import_model(str(path), background=False, ask_split=False)
        dlg = w.show_interference()
        assert len(dlg.run()) == 2
        assert dlg.export_csv(str(tmp_path / "i.csv")) and (tmp_path / "i.csv").exists()
    finally:
        w.project.dirty = False
        w.close()


def test_lab_frame_widget(tmp_path):
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from interface.lab_tab import LabTab
    lab = LabTab()
    txt = lab.frame.compute()
    assert "Pórtico espacial de vigas" in txt and "erro de equilíbrio global" in txt
    p = lab.frame.export_report(str(tmp_path / "p.md"))
    body = open(p, encoding="utf-8").read()
    assert "Pórtico (MEF de vigas)" in body and "BEAM c1" in body
    lab.frame.edit.setPlainText("NODE A 0 0 0 fix=xyz\nNODE B 1000 0 0\nBEAM b A B 1000 1e6 1e6 2e6 210000 80000\nLOAD B 0 0 -1\n")
    assert "hipostática" in lab.frame.compute()
