import numpy as np, pytest
from modules import fea_study as S
from samples.library import PARTS

def test_study_cantilever_traced():
    s = PARTS["tubo_retangular"].make(length=120, w=40, h=40, t=4)
    r, d = S.run(s, 2.0, 210000, 0.3, "xmin", "xmax", (0, 0, -100), sigma_yield=250)
    assert r.classe == "SIMULACAO_NUMERICA" and r.solver == "NEXUS-Tet4"
    assert abs(r.valores["reacao_N"][2] - 100) < 1e-6
    assert r.valores["fator_seguranca_escoamento_ref"] > 0
    assert any("escada" in l for l in r.limitacoes)

def test_no_yield_no_safety_factor():
    s = PARTS["chapa_furada"].make(length=60, width=30, thickness=6, hole_d=0, nx=0, ny=0)
    r, _ = S.run(s, 3.0, 70000, 0.33, "xmin", "xmax", (500, 0, 0))
    assert "fator_seguranca_escoamento_ref" not in r.valores
    with pytest.raises(ValueError): S.run(s, 3.0, 70000, 0.33, "xmin", "xmin", (1, 0, 0))

def test_fea_dialog_runs():
    import os; os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from interface.fea_dialog import FeaDialog
    d = FeaDialog(); d.sync = True; d.part.setCurrentIndex(list(PARTS).index("chapa_furada"))
    d.pspin["hole_d"].setValue(0); d.pspin["nx"].setValue(0); d.pspin["ny"].setValue(0); d.pspin["length"].setValue(60); d.pspin["width"].setValue(30)
    d.E.setValue(70000); d.nu.setValue(0.33); d.h.setValue(3); d.F[0].setValue(300)
    d.run()
    assert "SIMULACAO_NUMERICA" in d.out.toPlainText() and "NEXUS-Tet" in d.out.toPlainText()


def test_convergence_study():
    s = PARTS["tubo_retangular"].make(length=100, w=40, h=40, t=4)
    r = S.convergencia(s, [4.0, 2.0], 210000, 0.3, "xmin", "xmax", (0, 0, -100), tol_pct=50)
    assert len(r.valores["malhas"]) == 2 and r.valores["malhas"][0]["h"] == 4.0
    assert r.valores["malhas"][1]["u_max_mm"] >= r.valores["malhas"][0]["u_max_mm"]   # refino → mais flexível (Tet4)
    with pytest.raises(ValueError): S.convergencia(s, [2.0], 210000, 0.3, "xmin", "xmax", (0, 0, -1))


def test_fea_dialog_modal():
    import os; os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from interface.fea_dialog import FeaDialog
    d = FeaDialog(); d.sync = True; d.part.setCurrentIndex(list(PARTS).index("chapa_furada"))
    for k, v in dict(hole_d=0, nx=0, ny=0, length=60, width=30).items(): d.pspin[k].setValue(v)
    d.E.setValue(70000); d.nu.setValue(0.33); d.h.setValue(5); d.rho.setValue(2.7e-9)
    d.modal(); assert "freq_Hz" in d.out.toPlainText()


def test_study_tet10_voxel_cantilever_accurate():
    s = PARTS["chapa_furada"].make(length=100, width=20, thickness=10, hole_d=0, nx=0, ny=0)
    r4, _ = S.run(s, 5.0, 210000, 0.3, "xmin", "xmax", (0, 0, -100), mesher="voxel", order=1)
    r10, _ = S.run(s, 5.0, 210000, 0.3, "xmin", "xmax", (0, 0, -100), mesher="voxel", order=2)
    b, hh, L, P, E = 20., 10., 100., 100., 210000.
    I = b*hh**3/12; G = E/2.6
    tim = P*L**3/(3*E*I) + P*L/(G*(5/6)*b*hh)
    assert r10.solver == "NEXUS-Tet10"
    assert abs(r10.valores["u_max_mm"]/tim - 1) < 0.08, r10.valores["u_max_mm"]/tim
    assert r10.valores["u_max_mm"] > r4.valores["u_max_mm"]          # Tet4 mais rígido


def test_dof_limit_guard():
    s = PARTS["chapa_furada"].make(length=100, width=20, thickness=10, hole_d=0, nx=0, ny=0)
    with pytest.raises(ValueError): S.run(s, 0.5, 210000, 0.3, "xmin", "xmax", (0, 0, -1), mesher="voxel", order=2)




def test_fea_dialog_async_does_not_block():
    import os, time; os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from interface.fea_dialog import FeaDialog
    d = FeaDialog(); d.part.setCurrentIndex(list(PARTS).index("chapa_furada"))
    for k, v in dict(hole_d=0, nx=0, ny=0, length=60, width=30).items(): d.pspin[k].setValue(v)
    d.E.setValue(70000); d.nu.setValue(0.33); d.h.setValue(4); d.F[0].setValue(300); d.mesher.setCurrentIndex(d.mesher.findData("voxel"))
    d.run(); assert d._busy and d.out.toPlainText().startswith("Calculando")      # retorna imediatamente
    t0 = time.time()
    while d._busy and time.time() - t0 < 60: app.processEvents(); time.sleep(0.01)
    assert not d._busy and "SIMULACAO_NUMERICA" in d.out.toPlainText()
    d._worker.wait()
