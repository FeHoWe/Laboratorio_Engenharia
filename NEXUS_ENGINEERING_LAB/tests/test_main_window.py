"""Testes da janela principal (precisam de display: rodar com xvfb-run -a pytest)."""
import os
import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(app, engine):
    from interface.main_window import MainWindow
    w = MainWindow(engine=engine)
    w.config["animation_ms"] = 50
    w.explode_bar.animate_check.setChecked(False)
    w.show()
    yield w
    w.project.dirty = False
    w.close()


def test_empty_window(win):
    assert "NEXUS" in win.windowTitle()
    assert not win.project.components.leaves()


def test_import_step_builds_scene_and_tree(win, step_file):
    win.import_model(str(step_file), background=False, ask_split=False)
    leaves = win.project.components.leaves()
    assert len(leaves) == 7
    assert len(win.scene.parts) == len(leaves)
    assert win.panel.tree.topLevelItemCount() >= 1
    assert win.project.dirty


def test_selection_sync_tree_and_3d(win, step_file):
    win.import_model(str(step_file), background=False, ask_split=False)
    leaf = win.project.components.leaves()[0]
    win.selection.select(leaf.id, source="tree")
    assert win.scene.highlighted == {leaf.id}
    assert win.props.name_edit.text() == leaf.name
    win._on_pick(None, False)
    assert win.scene.highlighted == set()


def test_split_prompt_path(win, step_file):
    win.import_model(str(step_file), background=False, ask_split=True)
    comps = win.project.components
    assert not any(n.split_backup is None and n.geometry_kind.name == "MULTI_SOLID" for n in comps.leaves())
    assert len(win.scene.parts) == len(comps.leaves())


def test_explode_restore(win, step_file):
    win.import_model(str(step_file), background=False, ask_split=False)
    win.explode_all()
    assert win.project.assembly.is_exploded()
    assert "Explodida" in win.state_label.text()
    win.restore_assembly()
    assert not win.project.assembly.is_exploded()
    assert win.project.assembly.verify_restored()
    assert win.state_label.text() == "Montada"


def test_explode_animated(win, step_file, app):
    import time
    win.import_model(str(step_file), background=False, ask_split=False)
    win.explode_bar.animate_check.setChecked(True)
    win.explode_all()
    t = time.time()
    while win.animator.running and time.time() - t < 3:
        app.processEvents()
    assert win.project.assembly.is_exploded()


def test_hide_isolate_showall(win, step_file):
    win.import_model(str(step_file), background=False, ask_split=False)
    leaf = win.project.components.leaves()[0]
    win.selection.select(leaf.id, source="tree")
    win.hide_selected()
    assert not win.project.components.is_effectively_visible(leaf)
    win.isolate_selected()
    vis = [l for l in win.project.components.leaves() if win.project.components.is_effectively_visible(l)]
    assert vis == [leaf] or leaf in vis
    win.show_all()
    assert all(win.project.components.is_effectively_visible(l) for l in win.project.components.leaves())


def test_material_and_mass(win, step_file):
    win.import_model(str(step_file), background=False, ask_split=False)
    leaf = win.project.components.leaves()[0]
    win.selection.select(leaf.id, source="tree")
    win._set_material(leaf.id, win.project.materials.names()[0])
    assert win.props.mass.text() not in ("—", "não disponível")


def test_group_and_save_open(win, step_file, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QInputDialog
    win.import_model(str(step_file), background=False, ask_split=False)
    leaves = win.project.components.leaves()[:2]
    win.selection.select([l.id for l in leaves], source="tree")
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("Meu grupo", True)))
    win.group_selected()
    assert any(n.name == "Meu grupo" for n in win.project.components.all())
    path = str(tmp_path / "p.nexus")
    assert win.save_project_as(path)
    assert not win.project.dirty
    n = len(win.project.components.leaves())
    assert win.open_project(path)
    assert len(win.project.components.leaves()) == n
    assert any(g.name == "Meu grupo" for g in win.project.components.all())
    assert len(win.scene.parts) == n


def test_export(win, step_file, tmp_path):
    win.import_model(str(step_file), background=False, ask_split=False)
    out = tmp_path / "out.step"
    assert win.export_model(str(out), include_explosion=False)
    assert out.stat().st_size > 1000
    stl = tmp_path / "out.stl"
    assert win.export_model(str(stl), include_explosion=False)


def test_views_and_projection(win, step_file):
    win.import_model(str(step_file), background=False, ask_split=False)
    for v in ("front", "top", "right", "iso"):
        win.set_view(v)
    win.actions_by_key["perspective"].setChecked(False)
    assert not win.scene.is_perspective
    win.actions_by_key["perspective"].setChecked(True)
    assert win.scene.is_perspective


def test_simulation_menu_disabled(win):
    for k in ("sim_motion", "sim_materials", "sim_fem", "sim_thermal", "assistant"):
        assert not win.actions_by_key[k].isEnabled()


def test_threaded_import(win, stl_file, app):
    import time
    win.import_model(str(stl_file), background=True, ask_split=False)
    t = time.time()
    while win.busy and time.time() - t < 20:
        app.processEvents()
        time.sleep(0.01)
    assert win.project.components.leaves()


def test_measure_two_parts_draws_line_and_logs(win, step_file):
    win.import_model(str(step_file), background=False, ask_split=False)
    comps = win.project.components
    a = next(l for l in comps.leaves() if l.name == "Bloco")
    b = next(l for l in comps.leaves() if l.name == "Pistao")
    win.selection.select([a.id], source="tree")
    win.measure_selected()                                  # só uma peça: avisa e não mede
    assert any(lv == "warn" for lv, _ in win.console.messages[-1:])
    win.selection.select([a.id, b.id], source="tree")
    win.explode_all()
    win.measure_selected()
    assert win.last_measurement.exact
    assert "menor distância" in win.console.messages[-3][1] or any("menor distância" in m for _, m in win.console.messages)
    assert win.scene.has_measure_line == (win.last_measurement.min_distance > 0)
    win.selection.clear("tree")
    assert not win.scene.has_measure_line                   # trocar a seleção limpa a linha


def test_measure_menu_entries_exist(win):
    assert win.actions_by_key["measure"].isEnabled()
    assert win.actions_by_key["measure"].shortcut().toString() == "Ctrl+M"


def test_section_cut_and_holo_toggle(win, step_file):
    win.import_model(str(step_file), background=False, ask_split=False)
    assert win.scene.holo and win.scene.section is None
    win.section_bar.enable_check.setChecked(True)
    win.section_bar.axis_combo.setCurrentIndex(0)           # plano X
    win.section_bar.slider.setValue(250)
    axis, pos, flip = win.scene.section
    lo, hi = win.scene.section_range(0)
    assert axis == 0 and pos == pytest.approx(lo + 0.25 * (hi - lo))
    assert any("CORTE" in ln for ln in win.scene.hud_lines)
    win.section_bar.enable_check.setChecked(False)
    assert win.scene.section is None
    win.section_bar.holo_check.setChecked(False)
    assert not win.scene.holo
    win.section_bar.holo_check.setChecked(True)
    assert win.scene.holo


def test_hud_tracks_state_and_selection(win, step_file):
    win.import_model(str(step_file), background=False, ask_split=False)
    hud = " ".join(win.scene.hud_lines)
    assert "MONTADA" in hud and "PECAS" in hud
    win.explode_all()
    assert "EXPLODIDA" in " ".join(win.scene.hud_lines)
    leaf = win.project.components.leaves()[0]
    win.selection.select(leaf.id, source="tree")
    assert leaf.name in " ".join(win.scene.hud_lines)


def test_angle_and_diameter_commands(win, step_file):
    win.import_model(str(step_file), background=False, ask_split=False)
    comps = win.project.components
    vira = next(l for l in comps.leaves() if l.name == "Virabrequim")
    pist = next(l for l in comps.leaves() if l.name == "Pistao")
    win.selection.select([vira.id, pist.id], source="tree")
    win.measure_angle()
    assert win.last_angle.angle_deg == pytest.approx(90.0, abs=1e-6)
    win.selection.select(pist.id, source="tree")
    win.list_diameters()
    assert any("Ø 16,000" in m for _, m in win.console.messages)
    assert "Ø 16,00" in win.props.diams.text()
