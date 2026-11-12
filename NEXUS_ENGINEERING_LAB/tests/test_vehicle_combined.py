import math
import pytest
from modules import vehicle_combined as vc, vehicle_lateral as vl


def test_fx_zero_reproduz_modelo_lateral():
    v = vl.exemplo_ilustrativo()
    for vel in (20.0, 40.0):
        assert vc.ay_limite_com_fx(v, vel)["ay_ms2"] == pytest.approx(vl.ay_limite(v, vel)["ay_ms2"], rel=1e-9)


def test_tracao_reduz_ay_e_monotonico_e_frenagem_tambem():
    v = vl.exemplo_ilustrativo(); a0 = vc.ay_limite_com_fx(v, 30)["ay_ms2"]
    a1 = vc.ay_limite_com_fx(v, 30, 0, 2000)["ay_ms2"]; a2 = vc.ay_limite_com_fx(v, 30, 0, 4000)["ay_ms2"]
    assert a0 > a1 > a2
    assert vc.ay_limite_com_fx(v, 30, -3000, -3000)["ay_ms2"] < a0


def test_fx_maior_que_atrito_e_inviavel():
    v = vl.exemplo_ilustrativo()
    r = vc.ay_limite_com_fx(v, 30, 0, 1e6)
    assert r["viavel"] is False and r["ay_ms2"] == 0.0


def test_circulo_de_atrito_exato_em_um_pneu():
    v = vl.exemplo_ilustrativo(); cg = vl.cargas_eixos(v, 30, 0.0)
    mu = v.mu_r; fz = cg["r_int"] + cg["r_ext"]; fx = 0.6 * mu * fz
    assert vc.fy_max_eixo_com_fx(v, "r", 30, 0.0, fx) == pytest.approx(mu * fz * math.sqrt(1 - 0.36), rel=1e-9)


def test_gg_simetrico_e_validacao():
    v = vl.exemplo_ilustrativo(); g = vc.diagrama_gg(v, 30, 9)
    assert len(g) == 9 and max(a for _, a in g if a is not None) >= g[4][1] - 1e-9
    with pytest.raises(ValueError): vc.diagrama_gg(v, 30, 9, 1.5)


def test_rigidez_rolagem():
    assert vc.rigidez_rolagem(30000, 1.5) == pytest.approx(0.5 * 30000 * 2.25)
    assert vc.rigidez_rolagem(30000, 1.5, 5000) == pytest.approx(0.5 * 30000 * 2.25 + 5000)
    with pytest.raises(ValueError): vc.rigidez_rolagem(0, 1.5)


def test_pino_mestre_3d_analitico():
    # eixo inclinado 6° (topo p/ trás) e 8° (topo p/ dentro): construído a partir dos ângulos
    h = 0.20; B = (0.0, 0.50, 0.10)
    D = (B[0] - h * math.tan(math.radians(6)), B[1] - h * math.tan(math.radians(8)), B[2] + h)
    P = (0.02, 0.62, 0.0); r = vc.pino_mestre_3d(B, D, P)
    assert r["caster_graus"] == pytest.approx(6, abs=1e-9) and r["kpi_graus"] == pytest.approx(8, abs=1e-9)
    t = -0.10 / h; gx = B[0] + t * (D[0] - B[0]); gy = B[1] + t * (D[1] - B[1])
    assert r["trail_m"] == pytest.approx(gx - P[0])
    # sinal por construção: caster positivo (topo p/ trás) com contato exatamente sob a rótula inferior → interseção à frente → trail > 0
    assert vc.pino_mestre_3d(B, D, (B[0], 0.62, 0.0))["trail_m"] > 0 and r["scrub_m"] == pytest.approx(P[1] - gy)
    with pytest.raises(ValueError): vc.pino_mestre_3d(B, (0, 0.5, 0.05), P)


def test_dialogo_gg_e_ajuste_csv(tmp_path):
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from interface.vehicle_geo_dialog import VehicleGeoDialog
    d = VehicleGeoDialog(); d.calc_gg(); t = d.out_g.toPlainText()
    assert "ay_max" in t and "ERRO" not in t
    d.gg["m"].setValue(1e-9); d.gg["a"].setValue(0.0); d.calc_gg()
    p = tmp_path / "t.csv"; import numpy as np
    from modules import vehicle_lateral as vl
    p.write_text("alpha_graus,fz_N,fy_N\n" + "\n".join(f"{a},{3500},{vl.pneu_fy(np.radians(a), 3500, 60000, 1.4)}" for a in np.linspace(-14, 14, 30)))
    d.ajustar_csv(str(p)); assert "C_α = 60000" in d.out_f.toPlainText() or "C_α = 6000" in d.out_f.toPlainText()
    d.ajustar_csv(str(tmp_path / "nao_existe.csv")); assert "ERRO" in d.out_f.toPlainText()


def test_roda_levantando_conserva_carga_do_eixo():
    v = vl.VeiculoLateral(m=800, iz=1000, a=1.2, b=1.2, h=1.3, tf=0.8, tr=0.8, c_f=80000, c_r=80000, mu_f=1.3, mu_r=1.3)
    cg = vl.cargas_eixos(v, 30.0, 25.0)
    assert cg["f_ext"] == 0.0 and cg["f_int"] == pytest.approx(cg["fzf"]) and cg["r_ext"] + cg["r_int"] == pytest.approx(cg["fzr"])
    cg0 = vl.cargas_eixos(v, 30.0, 0.5)                                      # sem levantar: soma conservada como antes
    assert cg0["f_int"] + cg0["f_ext"] == pytest.approx(cg0["fzf"]) and cg0["f_ext"] > 0
