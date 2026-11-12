"""Banco SQL de densidades e sua integração com a biblioteca de materiais."""
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "data"))
import build_materials_db as bdb  # noqa: E402
from modules.material_manager import DEFAULT_DB, MaterialLibrary  # noqa: E402


@pytest.fixture(scope="module")
def db():
    con = sqlite3.connect(DEFAULT_DB)
    yield con
    con.close()


def test_database_is_complete_and_traceable(db):
    assert db.execute("SELECT COUNT(*) FROM materials").fetchone()[0] >= 800
    assert db.execute("SELECT COUNT(*) FROM categories").fetchone()[0] >= 20
    # toda linha tem fonte com URL e o valor original
    assert db.execute("SELECT COUNT(*) FROM v_materials WHERE source_url NOT LIKE 'http%' OR orig_text = ''").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM v_materials WHERE density_min <= 0 OR density_max < density_min").fetchone()[0] == 0
    # faixa plausível (g/cm3): do isopor (0,015) ao ósmio (22,6)
    lo, hi = db.execute("SELECT MIN(density_min), MAX(density_max) FROM materials").fetchone()
    assert 0.01 < lo and hi < 23


@pytest.mark.parametrize("name,expected", [
    ("Water - pure", 1.0), ("Iron", 7.85), ("Aluminum alloy - 6061", 2.72), ("Gold", 19.32),
    ("Mercury", 13.593), ("AISI 304 stainless steel", 0.289 * 27.6799),
])
def test_known_densities(db, name, expected):
    row = db.execute("SELECT density_typ FROM materials WHERE name_en LIKE ? || '%'", (name,)).fetchone()
    assert row[0] == pytest.approx(expected, rel=0.01)


def test_unit_conversions():
    assert bdb.parse_range("7700 - 8700") == (7700.0, 8700.0)
    rows = {r["name_en"]: r for r in bdb.build_rows() if r["source"] == "MECHANICALC"}
    assert rows["AISI 1020 carbon steel"]["lo"] == pytest.approx(7.833, abs=0.001)


def test_library_loads_db_and_keeps_builtins():
    lib = MaterialLibrary()
    assert lib.db_error is None and lib.db_count >= 800
    assert lib.get("Aço carbono").density_g_cm3 == pytest.approx(7.85)       # nativo continua igual
    assert len(lib.categories()) >= 20
    hits = lib.search("6061")
    assert hits and all(m.source for m in hits)
    assert len(lib.quick_names()) == 11                                        # combos continuam curtos


def test_library_without_db_still_works(tmp_path):
    lib = MaterialLibrary(tmp_path / "nao_existe.db")
    assert lib.db_error and len(lib.names()) == 11
    assert lib.get("Aço carbono") is not None


def test_project_roundtrip_keeps_db_material_without_db(motor_project, tmp_path):
    from core.project_manager import ProjectManager
    from tests.test_project_export_selection import find
    lib = motor_project.materials
    name = lib.search("6061")[0].name
    bloco = find(motor_project, "Bloco")
    motor_project.components.set_material(bloco.id, name)
    pm = ProjectManager(motor_project.engine)
    f = tmp_path / "p.nexus"
    pm.save(motor_project, f)
    import modules.material_manager as mm
    old = mm.DEFAULT_DB
    mm.DEFAULT_DB = tmp_path / "ausente.db"          # simula máquina sem o banco
    try:
        orig_init = mm.MaterialLibrary.__init__.__defaults__
        mm.MaterialLibrary.__init__.__defaults__ = (tmp_path / "ausente.db",)
        again = pm.open(f)
    finally:
        mm.MaterialLibrary.__init__.__defaults__ = orig_init
        mm.DEFAULT_DB = old
    assert again.materials.get(name).density_g_cm3 == pytest.approx(lib.get(name).density_g_cm3)


def test_picker_dialog_filters():
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from PySide6.QtWidgets import QDialogButtonBox
    from interface.material_picker import MaterialPicker
    lib = MaterialLibrary()
    dlg = MaterialPicker(lib)
    total = dlg.list.count()
    assert total == len(lib.names())
    dlg.search.setText("6061")
    assert 0 < dlg.list.count() < 10
    dlg.search.setText("zzzz-nao-existe")
    assert dlg.list.count() == 0 and not dlg.buttons.button(QDialogButtonBox.Ok).isEnabled()
    dlg.search.setText("")
    dlg.category.setCurrentText("Madeiras")
    assert 100 <= dlg.list.count() <= 120
