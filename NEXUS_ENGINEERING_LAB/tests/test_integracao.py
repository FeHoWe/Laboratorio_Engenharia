import pytest
from modules import integracao as I
from modules.vehicle_dynamics import Veiculo

V = Veiculo(massa=1000, cd=0.3, area=2.0, crr=0.01, forca_motriz=5000, potencia=80000, mu=1.0)


def _out(**kw):
    o = {"result": {"classe": "SIMULACAO_NUMERICA", "limitacoes": ["sem estudo de malha"]}, "info": {"a_ref_m2": 0.8, "bloqueio_pct": 2.0},
         "pressao": {"cd_pressao": 0.25, "cl_pressao": -0.1}}
    o.update(kw); return o


def test_pressao_apenas_avisa_e_total_estimado_prevalece():
    v, p = I.veiculo_com_cfd(V, _out(), area_real=2.1)
    assert v.cd == 0.25 and v.area == 2.1 and "PRESSÃO" in p["base"] and any("subestimado" in a for a in p["alertas"]) and p["area_origem"].startswith("informada")
    v, p = I.veiculo_com_cfd(V, _out(viscoso={"cd_total_estimado": 0.31, "cl_total_estimado": -0.09}))
    assert v.cd == 0.31 and v.area == 0.8 and "ESTIMADO" in p["base"] and "escala simulada" in p["area_origem"]


def test_recusas_e_bloqueio():
    with pytest.raises(ValueError): I.cd_do_cfd({"result": {"classe": "NAO_EXECUTADO"}})
    with pytest.raises(ValueError): I.cd_do_cfd({"result": {"classe": "SIMULACAO_NUMERICA"}})
    assert any("bloqueio" in a for a in I.cd_do_cfd(_out(info={"a_ref_m2": 1, "bloqueio_pct": 9}))["alertas"])
    with pytest.raises(ValueError): I.veiculo_com_cfd(V, _out(info={"bloqueio_pct": 1}))


def test_le_total_estimado_de_valores_do_resultado():
    o = _out(); o["result"]["valores"] = {"cd_total_estimado": 0.4}
    assert I.cd_do_cfd(o)["cd"] == 0.4


def test_de_resultado_projeto_e_dialogo():
    r = {"nome": "CFD OpenFOAM", "classe": "SIMULACAO_NUMERICA", "solver": "OpenFOAM", "valores": {"cd_total_estimado": 0.35}, "entradas": {"a_ref_m2": 0.9}, "limitacoes": ["ESTIMADO"]}
    o = I.de_resultado_projeto(r); assert I.cd_do_cfd(o)["cd"] == 0.35
    with pytest.raises(ValueError): I.de_resultado_projeto({"nome": "Viga", "valores": {"x": 1}})
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from interface.vehicle_geo_dialog import VehicleGeoDialog
    d = VehicleGeoDialog(); d.calc_cfd_veic(r); t = d.out_c.toPlainText()
    assert "Cd usado = 0.3500" in t and "v máx" in t and "não validado" in t
    d.calc_cfd_veic({"nome": "CFD", "classe": "NAO_EXECUTADO", "valores": {"cd": 0.3}}); assert "ERRO" in d.out_c.toPlainText()
