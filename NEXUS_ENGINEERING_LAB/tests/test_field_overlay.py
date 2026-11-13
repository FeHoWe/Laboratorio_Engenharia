"""Mapa de campo (von Mises/Cp) dentro do visualizador 3D."""
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from interface.viewport import Viewport

app = QApplication.instance() or QApplication([])


def _tets():
    pts = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1], [1, 1, 1]], float)
    return pts, np.array([[0, 1, 2, 3], [1, 2, 3, 4]])


def test_set_field_point_and_clear():
    vp = Viewport()
    pts, t = _tets()
    info = vp.show_field(pts, t, np.arange(5.0), "point", "von Mises", "MPa")
    assert info["min"] == 0 and info["max"] == 4 and info["elementos"] == 2
    assert vp.scene.field_info is not None
    vp.clear_field()
    assert vp.scene.field_info is None and vp.scene._field_actors == []


def test_set_field_cell_and_deformed():
    vp = Viewport()
    pts, t = _tets()
    info = vp.show_field(pts, t, [1.0, 2.0], "cell", displacement=np.ones((5, 3)) * 0.01, disp_scale=10)
    assert info["deformada"] is True


def test_field_rejects_bad_input():
    vp = Viewport()
    pts, t = _tets()
    with pytest.raises(ValueError):
        vp.show_field(pts, t, [1.0, 2.0, 3.0], "point")
    with pytest.raises(ValueError):
        vp.show_field(pts, t, [np.nan] * 5, "point")
    with pytest.raises(ValueError):
        vp.show_field(pts, t[:, :3], np.zeros(5), "point")


def test_tet10_and_surface_field():
    vp = Viewport()
    pts = np.random.rand(10, 3)
    info = vp.show_field(pts, np.arange(10)[None, :], np.arange(10.0), "point")
    assert info["elementos"] == 1
    sp = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], float)
    info = vp.show_surface_field(sp, [[0, 1, 2, 3]], [-0.5], title="Cp")
    assert info["tipo"] == "superficie"
    with pytest.raises(ValueError):
        vp.show_surface_field(sp, [[0, 1, 2, 3]], [1.0, 2.0])


def test_field_restores_parts_visibility():
    vp = Viewport()
    pts, t = _tets()
    vp.show_field(pts, t, np.arange(5.0), "point", hide_parts=True)
    vp.clear_field()
    assert vp.scene._field_hidden == []


def test_fea_dialog_shows_map_in_main_viewport():
    from interface.fea_dialog import FeaDialog
    from interface.main_window import MainWindow
    FeaDialog.sync = True
    mw = MainWindow()
    d = FeaDialog(mw)
    d.E.setValue(200000); d.nu.setValue(0.3); d.F[2].setValue(-100); d.h.setValue(4.0)
    d.mesher.setCurrentIndex(d.mesher.findData("voxel")); d.order.setCurrentIndex(d.order.findData(1))
    d.run()
    assert "nexus" in d._campos
    d.defscale.setValue(5)
    d.show_in_viewer()
    info = mw.viewport.scene.field_info
    assert info and info["unidade"] == "MPa" and info["max"] > 0 and info["deformada"] is True
    mw.clear_field_map()
    assert mw.viewport.scene.field_info is None


def test_fea_job_writes_field_npz(tmp_path):
    from modules import fea_job
    from samples.library import PARTS
    k = next(iter(PARTS))
    out = fea_job.run_static(k, {}, 4.0, 200000, 0.3, "xmin", "xmax", [0, 0, -100], None, "voxel", 1, str(tmp_path), False)
    import numpy as np
    z = np.load(out["campo"])
    assert z["vm"].shape[0] == z["tets"].shape[0] and str(z["loc"]) == "cell" and z["tets"].shape[1] == 4


def test_fea_job_tet10_field_is_nodal(tmp_path):
    from modules import fea_job
    from samples.library import PARTS
    import numpy as np
    k = next(iter(PARTS))
    out = fea_job.run_static(k, {}, 4.0, 200000, 0.3, "xmin", "xmax", [0, 0, -100], None, "voxel", 2, str(tmp_path), False)
    z = np.load(out["campo"])
    assert str(z["loc"]) == "point" and z["vm"].shape[0] == z["nodes"].shape[0] and z["tets"].shape[1] == 10


def test_fea_dialog_analisa_campo_criticas_consulta_e_fator(monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    avisos = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: avisos.append(a[-1]))   # sem diálogo modal bloqueando o teste
    from interface.fea_dialog import FeaDialog
    from interface.main_window import MainWindow
    FeaDialog.sync = True
    mw = MainWindow()
    d = FeaDialog(mw)
    d.analisar_campo()                                              # sem estudo: avisa, não quebra
    assert avisos and "Execute um estudo" in avisos[0]
    d.E.setValue(200000); d.nu.setValue(0.3); d.F[2].setValue(-100); d.h.setValue(4.0)
    d.mesher.setCurrentIndex(d.mesher.findData("voxel")); d.order.setCurrentIndex(d.order.findData(2))
    d.run()
    assert d._campos["nexus"]["loc"] == "point"
    d.q_ponto.setText("0,0,0"); d.analisar_campo()
    t = d.out.toPlainText()
    assert "Regiões críticas" in t and "Nó mais próximo" in t and "Fator visual sugerido" in t and "não é critério de falha" in t
    assert d.defscale.value() > 0
    d.q_ponto.setText("abc"); d.analisar_campo()
    assert "Não foi possível analisar" in d.out.toPlainText()
