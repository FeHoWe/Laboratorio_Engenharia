import pytest
from modules import lapsim as ls, lapsim_veiculo as lv, vehicle_lateral as vl


def _carro(mu=1.3, h=0.0001, cla=0.0):
    return vl.VeiculoLateral(m=800, iz=1000, a=1.2, b=1.2, h=h, tf=1.6, tr=1.6, c_f=80000, c_r=80000, mu_f=mu, mu_r=mu, cla=cla)


def test_sem_transferencia_e_sem_aero_reproduz_ponto_material():
    v = _carro()
    a = lv.volta(v, 300e3, 0.7, ds=4.0)
    b = ls.volta(ls.Carro(massa=800, p_ice=300e3, cda=0.7, cla=0.0, mu=1.3), ds=4.0)
    assert a.valores["tempo_s"] == pytest.approx(b.valores["tempo_s"], rel=0.03)               # mesma física: círculo de atrito, μ único


def test_sem_sensibilidade_do_mu_a_carga_a_transferencia_nao_muda_o_limite():
    base = lv.volta(_carro(), 300e3, 0.7, ds=4.0).valores["tempo_s"]
    alto = lv.volta(vl.VeiculoLateral(m=800, iz=1000, a=1.2, b=1.2, h=1.3, tf=0.8, tr=0.8, c_f=80000, c_r=80000, mu_f=1.3, mu_r=1.3), 300e3, 0.7, ds=4.0).valores["tempo_s"]
    assert alto == pytest.approx(base, rel=1e-3)          # μ constante: soma de aderência por eixo é conservada, mesmo com roda levantando (com sens_mu = 0)


def test_com_sensibilidade_do_mu_a_transferencia_de_carga_deixa_a_volta_mais_lenta():
    kw = dict(m=800, iz=1000, a=1.2, b=1.2, h=0.9, tf=0.8, tr=0.8, c_f=80000, c_r=80000, mu_f=1.3, mu_r=1.3)
    t0 = lv.volta(vl.VeiculoLateral(**kw), 300e3, 0.7, ds=4.0).valores["tempo_s"]
    t1 = lv.volta(vl.VeiculoLateral(sens_mu_f=0.25, sens_mu_r=0.25, **kw), 300e3, 0.7, ds=4.0).valores["tempo_s"]
    assert t1 > t0 * 1.005


def test_aderencia_e_potencia_monotonicas_e_validacao():
    t1 = lv.volta(_carro(mu=1.0), 300e3, 0.7, ds=5.0).valores["tempo_s"]; t2 = lv.volta(_carro(mu=1.6), 300e3, 0.7, ds=5.0).valores["tempo_s"]
    assert t2 < t1
    assert lv.volta(_carro(), 600e3, 0.7, ds=5.0).valores["tempo_s"] < lv.volta(_carro(), 200e3, 0.7, ds=5.0).valores["tempo_s"]
    with pytest.raises(ValueError): lv.volta(_carro(), 0, 0.7)
    r = lv.volta(_carro(), 300e3, 0.7, ds=5.0); assert r.classe == "SIMULACAO_NUMERICA" and any("SINTÉTICA" in x for x in r.limitacoes)


def test_dialogo_volta():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from interface.vehicle_geo_dialog import VehicleGeoDialog
    d = VehicleGeoDialog(); d.calc_gg(); assert "ERRO" not in d.out_g.toPlainText()
    d.calc_volta(); assert "SINTÉTICO" in d.out_g.toPlainText() and "ERRO" not in d.out_g.toPlainText()
