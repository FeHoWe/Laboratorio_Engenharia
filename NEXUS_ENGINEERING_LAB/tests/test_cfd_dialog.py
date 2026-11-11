"""Diálogo de CFD + job isolado. A execução real roda se o OpenFOAM existir (pula caso contrário); não valida Cd."""
import time

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from modules import cfd_job, solver_registry as sr

app = QApplication.instance() or QApplication([])
HAS_OF = sr.detect("OpenFOAM").instalado


def test_preparar_caso_writes_case_and_scales_domain(tmp_path):
    import trimesh
    m = trimesh.creation.box(extents=(0.4, 0.2, 0.1))
    info = cfd_job.preparar_caso(tmp_path / "c", m.vertices, m.faces, 20.0, 50, (20, 10, 8), 0.05, None, 1.225, 1.5e-5)
    assert (tmp_path / "c/constant/triSurface/corpo.stl").exists() and (tmp_path / "c/system/blockMeshDict").exists()
    assert abs(info["L_m"] - 0.4) < 1e-9 and abs(info["a_ref_m2"] - 0.02) < 2e-4 and "PROJETADA" in info["a_ref_origem"] and abs(info["a_caixa_m2"] - 0.02) < 1e-9
    assert 0 < info["bloqueio_pct"] < 5
    assert cfd_job.preparar_caso(tmp_path / "d", m.vertices, m.faces, 20.0, 50, (20, 10, 8), 0, 0.5, 1.225, 1.5e-5)["a_ref_origem"] == "informada"
    with pytest.raises(ValueError):
        cfd_job.preparar_caso(tmp_path / "e", np.zeros((3, 3)), [[0, 1, 2]], 20.0, 50, (20, 10, 8), 0, None, 1.225, 1.5e-5)


@pytest.mark.skipif(HAS_OF, reason="só vale sem OpenFOAM")
def test_job_without_openfoam_is_not_executed(tmp_path):
    r = cfd_job.run_case(part_key="x", out_dir=str(tmp_path))
    assert r["result"]["classe"] == "NAO_EXECUTADO" and not r["result"]["valores"] and r["campo"] is None


def test_dialog_validation_and_no_result_message(monkeypatch):
    from interface import cfd_dialog
    from interface.cfd_dialog import CfdDialog
    msgs = []
    monkeypatch.setattr(cfd_dialog.QMessageBox, "warning", lambda *a, **k: msgs.append(a[2]))
    monkeypatch.setattr(cfd_dialog.QMessageBox, "information", lambda *a, **k: msgs.append(a[2]))
    d = CfdDialog()
    d.run()
    assert d._job is None and "STL" in msgs[-1]
    d.stl.setText("x.stl"); d.cdref.setValue(0.5)
    d.run()
    assert d._job is None and "FONTE" in msgs[-1]
    d.show_cp()
    assert "Não há campo" in msgs[-1]


@pytest.mark.skipif(not HAS_OF, reason="OpenFOAM não instalado")
def test_dialog_real_run_progress_cancel_and_cp_map(tmp_path):
    from interface.cfd_dialog import CfdDialog
    from interface.main_window import MainWindow
    mw = MainWindow()
    d = CfdDialog(mw)
    d.sync = True
    d.part.setCurrentIndex(1)
    d.it.setValue(40); d.cx.setValue(24); d.cy.setValue(10); d.cz.setValue(8)
    d.run()
    t0 = time.time()
    while d._job is not None and not d._job.terminal and time.time() - t0 < 900:
        app.processEvents(); time.sleep(0.3)
    d._poll()
    assert d.last is not None, d.out.toPlainText()[-600:]
    assert d.last.classe in ("SIMULACAO_NUMERICA", "NAO_EXECUTADO") and d.last.classe != "VALIDADO"
    if d.campo:
        d.show_cp()
        info = mw.viewport.scene.field_info
        assert info and info["tipo"] == "superficie" and np.isfinite(info["min"]) and np.isfinite(info["max"])
        mw.clear_field_map()


@pytest.mark.skipif(not HAS_OF, reason="OpenFOAM não instalado")
def test_dialog_cancel_stops_job():
    from interface.cfd_dialog import CfdDialog
    d = CfdDialog()
    d.part.setCurrentIndex(1)
    d.it.setValue(5000)
    d.run()
    time.sleep(3)
    d.cancel()
    t0 = time.time()
    while not d._job.terminal and time.time() - t0 < 60:
        app.processEvents(); time.sleep(0.2)
    d._poll()
    assert d._job.state == "CANCELLED" and "Cancelado" in d.out.toPlainText()


def test_cp_points_return_to_original_frame(tmp_path):
    import trimesh
    m = trimesh.creation.box(extents=(40, 20, 10)); m.apply_translation([100, 50, 30])      # mm, fora da origem
    info = cfd_job.preparar_caso(tmp_path / "c", m.vertices * 0.001, m.faces, 20.0, 20, (20, 10, 8), 0.02, None, 1.225, 1.5e-5)
    stl = trimesh.load(tmp_path / "c/constant/triSurface/corpo.stl")
    back = cfd_job.para_coords_originais(stl.vertices, info["origem_m"], info["gap_m"], 0.001)
    a = np.array(sorted(map(tuple, np.round(back, 3)))); b = np.array(sorted(map(tuple, np.round(m.vertices, 3))))
    assert a.shape == b.shape and np.allclose(a, b, atol=1e-3)


def test_projected_area_is_real_and_free_air_centers_body(tmp_path):
    import trimesh
    sph = trimesh.creation.icosphere(subdivisions=3, radius=0.5)
    assert abs(cfd_job.area_frontal_projetada(sph.vertices, sph.faces) - np.pi / 4) / (np.pi / 4) < 0.01
    info = cfd_job.preparar_caso(tmp_path / "c", sph.vertices, sph.faces, 20.0, 20, (20, 10, 10), 0.0, None, 1.225, 1.5e-5, ar_livre=True)
    z0, z1 = info["caixa_m"][4], info["caixa_m"][5]
    stl = trimesh.load(tmp_path / "c/constant/triSurface/corpo.stl")
    assert abs((stl.bounds[0][2] + stl.bounds[1][2]) / 2 - (z0 + z1) / 2) < 1e-9          # centrado em z → domínio simétrico
    assert "ground {type symmetryPlane;}" in (tmp_path / "c/0/U").read_text().replace("ground {type symmetryPlane;}", "ground {type symmetryPlane;}")
    assert "ground { type wall" not in (tmp_path / "c/system/blockMeshDict").read_text() and "symmetryPlane; faces ((0 3 2 1))" in (tmp_path / "c/system/blockMeshDict").read_text()
