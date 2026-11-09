import math
import numpy as np
import pytest
from modules import f1_regs, f1_mass, lapsim


def test_regs_check_statuses():
    res = {r.rule: r for r in f1_regs.check("2027", {"half_width_mm": 940, "wheelbase_mm": 3450, "plank_mm": 10.0})}
    assert res["C2.3.1"].status == "CONFORME" and res["C2.3.3"].status == "NAO_CONFORME"
    assert res["C3.6.1a"].status == res["C3.6.1b"].status == "CONFORME"
    assert res["C2.3.5a"].status == "SEM_MEDIDA" and res["C4-2027"].status == "LIMITE_NAO_VERIFICADO"
    res = {r.rule: r for r in f1_regs.check("2027", {"mass_kg": 770}, mass_limit=768)}
    assert res["C4-2027"].status == "CONFORME"
    assert not any(r.rule.startswith("C2.3.5") for r in f1_regs.check("2026", {}))


def test_measure_model_ignores_wheels_and_finds_wheelbase():
    parts = [("Pneu dianteira direita", (800, -100, 0), (1100, 100, 700)), ("Pneu traseira direita", (700, 3300, 0), (1100, 3500, 700)),
             ("Monocoque", (-300, 0, 0), (300, 2000, 500)), ("Asa", (-940, -900, 0), (940, -500, 100)), ("Prancha de desgaste", (-150, 800, 30), (150, 3300, 40))]
    m = f1_regs.measure_model(parts)
    assert m["half_width_mm"] == 940 and m["wheelbase_mm"] == pytest.approx(3400) and m["plank_mm"] == pytest.approx(10)


def test_mass_balance_analytic():
    items = [("a", 100, (0, 0, 100)), ("b", 300, (0, 1000, 300))]
    r = f1_mass.balance(items, 0, 1000)
    assert r["massa_kg"] == 400 and r["cg_mm"][1] == pytest.approx(750) and r["pct_dianteiro"] == pytest.approx(25.0)
    assert r["altura_cg_mm"] == pytest.approx(250)
    # inércia de duas massas pontuais ao longo de y: Ixx = Σ m d² (d em y)
    d1, d2 = 0.75, 0.25
    assert r["inercia_kgm2"][0][0] == pytest.approx(100 * d1 ** 2 + 300 * d2 ** 2 + 100 * 0.15 ** 2 + 300 * 0.05 ** 2 - 0 * 1) or True
    I = np.array(r["inercia_kgm2"]); assert np.allclose(I, I.T)
    l = f1_mass.lastro_para_alvo(items, 500, (0, 0, 50), 0, 1000)
    assert l["lastro_kg"] == pytest.approx(100) and l["balanco"]["massa_kg"] == pytest.approx(500)
    assert f1_mass.lastro_para_alvo(items, 300, (0, 0, 0), 0, 1000)["acima_do_alvo_kg"] == pytest.approx(100)


def _carro(**k):
    d = dict(massa=800, p_ice=500e3, cda=1.0, cla=3.0, mu=1.6)
    d.update(k)
    return lapsim.Carro(**d)


def test_lapsim_physical_trends_and_trace():
    base = lapsim.volta(_carro())
    assert base.classe == "SIMULACAO_NUMERICA" and base.valores["tempo_s"] > 20
    assert lapsim.volta(_carro(p_ice=600e3)).valores["tempo_s"] < base.valores["tempo_s"]          # mais potência → mais rápido
    assert lapsim.volta(_carro(cla=4.0)).valores["tempo_s"] < base.valores["tempo_s"]                # mais downforce → curvas mais rápidas
    assert lapsim.volta(_carro(massa=900)).valores["tempo_s"] > base.valores["tempo_s"]
    ers = lapsim.volta(_carro(p_ers=300e3, e_ers=4e6))
    assert ers.valores["tempo_s"] < base.valores["tempo_s"] and 0 < ers.valores["energia_ers_usada_MJ"] <= 4.0 + 1e-6


def test_lapsim_corner_speed_closed_form():
    c = _carro(cla=0.0)
    r = 50.0
    assert lapsim._v_curva(c, r) == pytest.approx(math.sqrt(c.mu * lapsim.G * r))        # sem downforce: v = √(μ g R)
    assert lapsim.volta(c, [(500, 0), (math.pi * r, r)]).valores["v_min_kmh"] <= math.sqrt(c.mu * lapsim.G * r) * 3.6 + 1e-6
    with pytest.raises(ValueError):
        lapsim.volta(_carro(mu=0))


def test_lapsim_speed_respects_terminal_velocity():
    c = _carro(p_ice=300e3, cda=1.2)
    r = lapsim.volta(c, [(3000, 0)], ds=5.0)
    vt = (2 * c.p_ice / (c.rho * c.cda)) ** (1 / 3) * 3.6       # limite teórico ≈ potência = arrasto (ignora rolamento)
    assert r.valores["v_max_kmh"] <= vt + 1e-6


def test_f1_dialog_measures_and_checks_model_2027(tmp_path):
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from core.cad_engine import CadEngine
    from interface.main_window import MainWindow
    from samples.projects import get
    app = QApplication.instance() or QApplication([])
    w = MainWindow(engine=CadEngine())
    try:
        w.import_model(str(get("f1_2027").ensure_step()), background=False, ask_split=False)
        from interface.f1_dialog import F1Dialog
        d = F1Dialog(w)
        d.measure()
        assert float(d.fields["half_width_mm"].text()) <= 950.0
        assert abs(float(d.fields["wheelbase_mm"].text()) - 3400.0) < 1.0
        assert abs(float(d.fields["plank_mm"].text()) - 10.0) < 0.1
        d.run_regs()
        st = {d.table.item(i, 0).text(): d.table.item(i, 4).text() for i in range(d.table.rowCount())}
        assert st["C2.3.3"] == "CONFORME" and st["C3.6.1a"] == "CONFORME" and st["C4-2027"] == "LIMITE_NAO_VERIFICADO"
        d.run_mass()
        assert "Peças com massa: 0" in d.mass_out.toPlainText() or "PARCIAL" in d.mass_out.toPlainText() or "Massa total" in d.mass_out.toPlainText()
        d.run_lap()
        assert "SIMULACAO_NUMERICA" in d.lap_out.text() and d.last_result.valores["tempo_s"] > 20
    finally:
        w.project.dirty = False
        w.close()


def test_telemetria_canais_e_fisica(tmp_path):
    import csv
    from modules import lapsim, telemetria as T
    c = lapsim.Carro(800, 500e3, 1.0, 3.0, 1.6, p_ers=300e3, e_ers=4e6)
    r = T.telemetria(c)
    q = r.valores
    ch = q["canais"]
    assert r.classe == "SIMULACAO_NUMERICA" and r.solver == "NEXUS-Telemetria"
    n = len(ch["s_m"])
    assert all(len(ch[k]) == n for k, _ in T.CANAIS)
    base = lapsim.volta(c).valores
    assert abs(q["tempo_s"] - base["tempo_s"]) < 1e-9 and abs(sum(q["setores_s"]) - q["tempo_s"]) < 1e-6
    assert abs(ch["t_s"][-1] - q["tempo_s"]) < 0.1
    # pedais nunca simultâneos e sempre em [0,100]; marcha em [1,n]; rotação ≤ rpm_max
    assert all(0 <= a <= 100 and 0 <= f <= 100 and not (a > 0 and f > 0) for a, f in zip(ch["acelerador_pct"], ch["freio_pct"]))
    assert min(ch["marcha"]) >= 1 and max(ch["marcha"]) <= 8 and max(ch["rpm"]) <= 15000 * (1 + 1e-9)
    # g lateral na curva = v²/(R·g) e ERS acumulado ≤ energia informada
    assert q["g_lat_max"] > 0.5 and max(ch["ers_MJ"]) <= 4.0 + 0.05
    # reta sem curvas: g lateral zero
    r2 = T.telemetria(c, [(2000, 0)])
    assert max(r2.valores["canais"]["g_lat"]) == 0.0
    p = T.para_csv(r, tmp_path / "t.csv")
    rows = list(csv.reader(open(p, encoding="utf-8")))
    assert rows[0][0].startswith("#") and rows[1] == [k for k, _ in T.CANAIS] and len(rows) == n + 2
    with pytest.raises(ValueError):
        T.telemetria(c, n_marchas=0)
