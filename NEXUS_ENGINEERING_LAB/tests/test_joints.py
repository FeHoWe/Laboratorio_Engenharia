"""Juntas inferidas da geometria."""
import os

import pytest

from modules.joint_finder import KIND_CONCENTRIC, KIND_PLANAR, JointFinder, export_csv
from tests.conftest import find


@pytest.fixture(scope="module")
def sample_report(engine):
    from core.project_manager import ProjectManager
    from modules.importer import ProjectImporter
    from samples.motor_4_cilindros import write
    import tempfile, pathlib
    d = pathlib.Path(tempfile.mkdtemp())
    write(d / "m.step")
    pm = ProjectManager(engine)
    proj = pm.new_project("m")
    proj.set_root(ProjectImporter(engine, proj.ids).import_file(str(d / "m.step")).root)
    return proj, JointFinder(proj.components).find()


def _pair(rep, a, b, kind):
    return [j for j in rep.joints if j.kind == kind and {j.a_name, j.b_name} == {a, b}]


def test_two_touching_boxes_planar(engine, tmp_path):
    from core.project_manager import ProjectManager
    from modules.importer import ProjectImporter
    from tests import fixtures
    f = fixtures.write_engine_step(engine, tmp_path / "e.step")
    pm = ProjectManager(engine)
    proj = pm.new_project("x")
    proj.set_root(ProjectImporter(engine, proj.ids).import_file(str(f)).root)
    rep = JointFinder(proj.components).find()
    assert rep.parts == len(proj.components.leaves())
    assert all(j.inferred for j in rep.joints)


def test_sample_motor_known_relations(sample_report):
    proj, rep = sample_report
    assert rep.parts == 180 and len(rep.clusters) >= 1
    # junta do cabeçote encosta no bloco e no cabeçote (planos)
    assert _pair(rep, "Bloco do motor", "Junta do cabecote", KIND_PLANAR)
    assert _pair(rep, "Junta do cabecote", "Cabecote", KIND_PLANAR)
    # parafuso de cabeçote concêntrico com furo do bloco
    assert any(j.kind == KIND_CONCENTRIC and "Parafuso do cabecote" in (j.a_name + j.b_name)
               and "Bloco" in (j.a_name + j.b_name) for j in rep.joints)
    # biela encosta no pistão
    assert any(j.kind == KIND_PLANAR and {j.a_name, j.b_name} == {"Biela", "Pistao"} for j in rep.joints)
    # peças sem relação real não aparecem ligadas: cárter x pistão
    assert not _pair(rep, "Carter de oleo", "Pistao", KIND_PLANAR)
    assert not _pair(rep, "Carter de oleo", "Pistao", KIND_CONCENTRIC)


def test_csv_export_labels_inferred(sample_report, tmp_path):
    _, rep = sample_report
    out = export_csv(rep, tmp_path / "j.csv")
    txt = out.read_text(encoding="utf-8-sig")
    assert "inferida da geometria" in txt and txt.count("\n") > len(rep.joints)


def test_window_dialog_and_pdf_section(engine, tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from interface.joints_dialog import JointsDialog
    from interface.main_window import MainWindow
    w = MainWindow(engine=engine)
    w.open_sample_engine(ask_split=False, background=False)
    rep = w.find_joints()
    dlg = JointsDialog(rep, w)
    assert dlg.table.rowCount() == len(rep.joints) > 100
    out = w.export_report(str(tmp_path / "r.pdf"), detail_parts=False)
    import subprocess, shutil
    if shutil.which("pdftotext"):
        txt = subprocess.run(["pdftotext", str(out), "-"], capture_output=True, text=True).stdout
        assert "Relações de montagem" in txt
    w.project.dirty = False
    w.close()
