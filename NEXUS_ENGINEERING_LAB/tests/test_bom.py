"""BOM com massa: regras de honestidade, totais, centro de massa e exportação."""
import csv

import pytest
from openpyxl import load_workbook

from modules.bom import BomBuilder, export_csv, export_xlsx
from samples.motor_materials import TYPICAL, material_for
from tests.conftest import find


@pytest.fixture
def builder(motor_project):
    return BomBuilder(motor_project.components, motor_project.materials)


def test_no_material_means_no_mass(builder):
    rep = builder.build()
    assert rep.total_mass_g == 0 and not rep.complete
    assert rep.parts_with_mass == 0 and len(rep.missing) == rep.total_parts > 0
    assert rep.center_of_mass is None and "PARCIAL" in rep.summary()


def test_partial_total_and_exact_mass(motor_project, builder):
    p = motor_project
    bloco = find(p, "Bloco")
    p.components.set_material(bloco.id, "Aço carbono")
    vol = builder.inspector.inspect(bloco).volume
    rep = builder.build()
    assert rep.total_mass_g == pytest.approx(vol / 1000 * 7.85)
    assert rep.parts_with_mass == 1 and not rep.complete
    assert bloco.name not in rep.missing and len(rep.missing) == rep.total_parts - 1
    assert rep.center_of_mass is not None


def test_all_parts_complete_and_quantity_grouping(motor_project, builder):
    p = motor_project
    for leaf in p.components.leaves():
        p.components.set_material(leaf.id, "Aço carbono")
    rep = builder.build()
    assert rep.complete and not rep.missing
    assert sum(l.qty for l in rep.lines) == rep.total_parts
    assert sum(l.mass_total_g for l in rep.lines) == pytest.approx(rep.total_mass_g)
    assert sum(l.pct for l in rep.lines) == pytest.approx(100.0)
    assert rep.by_material[0][0] == "Aço carbono" and rep.by_material[0][1] == rep.total_parts
    assert sum(g for _, g in rep.by_group) == pytest.approx(rep.total_mass_g)


def test_typical_materials_exist_in_library(motor_project):
    lib = motor_project.materials
    for part, mat in TYPICAL.items():
        assert lib.get(mat) is not None, f"{part}: '{mat}' não existe no banco"
    assert material_for("Pistao 3") == TYPICAL["Pistao"]
    assert material_for("Pino do pistao 2") == TYPICAL["Pino do pistao"]   # prefixo mais longo vence
    assert material_for("Vela de ignicao 1") is None and material_for("Junta do cabecote") is None


def test_exports(motor_project, builder, tmp_path):
    for leaf in motor_project.components.leaves():
        motor_project.components.set_material(leaf.id, "Aço carbono")
    rep = builder.build()
    c = export_csv(rep, tmp_path / "b.csv")
    rows = list(csv.reader(open(c, encoding="utf-8-sig"), delimiter=";"))
    assert rows[0][:4] == ["Item", "Componente", "Grupo", "Qtd"] and len(rows) >= len(rep.lines) + 1
    x = export_xlsx(rep, tmp_path / "b.xlsx", "Teste")
    wb = load_workbook(x)
    assert wb.sheetnames == ["BOM", "Por material", "Por grupo", "Pendências"]
    ws = wb["BOM"]
    formulas = [c.value for r in ws.iter_rows() for c in r if isinstance(c.value, str) and c.value.startswith("=SUM(")]
    assert len(formulas) == 2                                  # total de peças e de massa com SOMA viva


def test_window_typical_materials_and_bom(engine, tmp_path):
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from interface.main_window import MainWindow
    w = MainWindow(engine=engine)
    w.open_sample_engine(ask_split=False, background=False)
    assert w.build_bom().total_mass_g == 0                      # nada atribuído sozinho
    n = w.apply_typical_materials()
    assert n == 175                                               # tudo, exceto 4 velas e a junta
    rep = w.build_bom()
    assert not rep.complete and len(rep.missing) == 5
    assert all(x.startswith(("Vela", "Junta")) for x in rep.missing)
    assert len(rep.by_group) >= 4                                 # Estrutura, Conjunto rotativo, Comando...
    assert 20_000 < rep.total_mass_g < 120_000                  # motor didático: dezenas de kg
    x = export_xlsx(rep, tmp_path / "m.xlsx", "Motor")
    assert x.stat().st_size > 5000
    w.project.dirty = False
    w.close()
