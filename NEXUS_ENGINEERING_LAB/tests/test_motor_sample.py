"""O motor 4 cilindros de exemplo é um modelo real: estrutura, sólidos únicos e sem interferências."""
import itertools

import numpy as np
import pytest
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common

from core.project_manager import ProjectManager
from modules.explode_engine import ExplodeParams
from modules.importer import ProjectImporter


@pytest.fixture(scope="module")
def motor(engine, tmp_path_factory):
    from samples.motor_4_cilindros import write
    path = write(tmp_path_factory.mktemp("sample") / "motor.step")
    pr = ProjectManager(engine).new_project("motor")
    res = ProjectImporter(engine, pr.ids).import_file(str(path))
    pr.set_root(res.root)
    return pr, res


def test_structure_and_counts(motor):
    pr, res = motor
    names = [l.name.split(" #")[0] for l in pr.components.leaves()]
    assert len(names) == 180
    for expected, n in (("Pistao", 4), ("Biela", 4), ("Pino do pistao", 4), ("Valvula de admissao", 8),
                        ("Valvula de escape", 8), ("Vela de ignicao", 4), ("Parafuso do cabecote", 10),
                        ("Mola de valvula de admissao", 8), ("Mola de valvula de escape", 8), ("Roda dentada do comando de admissao", 1),
                        ("Roda dentada do virabrequim", 1), ("Correia dentada", 1), ("Dente da correia", 100), ("Roda tensora dentada", 1), ("Eixo do tensor", 1), ("Suporte do tensor", 1),
                        ("Engrenagem do comando de admissao", 1), ("Engrenagem do comando de escape", 1)):
        assert names.count(expected) == n, expected
    for single in ("Bloco do motor", "Cabecote", "Virabrequim", "Volante do motor", "Carter de oleo"):
        assert names.count(single) == 1
    assert not res.report.has_splittable                      # nenhuma peça é um composto de vários sólidos
    groups = {n.name for n in pr.components.all() if n.children}
    assert {"Estrutura", "Conjunto rotativo", "Comando de valvulas", "Ignicao"} <= groups


def test_every_part_is_one_valid_solid(motor, engine):
    pr, _ = motor
    for l in pr.components.leaves():
        assert engine.count_solids(l.shape) == 1, l.name
        assert engine.properties(l.shape).volume > 0, l.name


def test_realistic_dimensions(motor, engine):
    pr, _ = motor
    box = pr.components.bbox(pr.components.root)
    assert box.size[0] > 450 and 250 < box.size[2] < 600
    piston = next(l for l in pr.components.leaves() if l.name == "Pistao")
    from modules.measure_engine import MeasureEngine
    d = MeasureEngine(pr.components).diameters(piston)
    assert any(abs(x.diameter - 85.6) < 0.01 for x in d)       # Ø do pistão = Ø do cilindro - folga
    crank = next(l for l in pr.components.leaves() if l.name == "Virabrequim")
    assert engine.properties(crank.shape).volume > 1e6


def test_no_interference_between_parts(motor, engine):
    pr, _ = motor
    leaves = pr.components.leaves()
    boxes = [pr.components.bbox(l) for l in leaves]
    bad = []
    for i, j in itertools.combinations(range(len(leaves)), 2):
        a, b = boxes[i], boxes[j]
        if np.any(a.max < b.min - 1e-6) or np.any(b.max < a.min - 1e-6):
            continue
        common = BRepAlgoAPI_Common(leaves[i].shape, leaves[j].shape).Shape()
        vol = engine.properties(common).volume or 0.0
        if vol > 1.0:
            bad.append((leaves[i].name, leaves[j].name, round(vol, 1)))
    assert bad == []


def test_explode_and_restore_whole_engine(motor):
    pr, _ = motor
    off = pr.assembly.target_explode_all(ExplodeParams(factor=1.0, mode="radial"))
    pr.assembly.apply_offsets(off)
    assert pr.assembly.is_exploded()
    assert len(pr.components.displaced_ids()) >= 50
    pr.assembly.restore()
    assert pr.assembly.verify_restored()


def test_window_opens_sample(engine, monkeypatch, tmp_path):
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from interface.main_window import MainWindow
    w = MainWindow(engine=engine)
    w.open_sample_engine(ask_split=False, background=False)
    assert len(w.project.components.leaves()) == 180 and len(w.scene.parts) == 180
    w.project.dirty = False
    w.close()


def test_springs_belt_and_ducts(motor, engine):
    """V1.7: mola helicoidal com volume de fio esperado, correia fechada e dutos/galerias cortados."""
    import math
    pr, _ = motor
    by = {}
    for l in pr.components.leaves():
        by.setdefault(l.name.split(" #")[0], l)
    spring = engine.properties(by["Mola de valvula de admissao"].shape).volume
    height = pr.components.bbox(by["Mola de valvula de admissao"]).size[2]       # a mola pode estar comprimida pelo lóbulo em θ=0
    pitch = (height - 3.0) / 6.0
    expected = math.pi * 1.5 ** 2 * 6.0 * math.hypot(2 * math.pi * 7.5, pitch)    # seção do fio x comprimento da hélice
    assert spring == pytest.approx(expected, rel=0.01)
    belt = by["Correia dentada"]
    from samples.motor_4_cilindros import belt_design
    perim = belt_design()['path'].length + 2 * math.pi * 3.0                         # perímetro na meia espessura da faixa
    assert engine.properties(belt.shape).volume == pytest.approx(8.0 * 3.0 * perim, rel=0.02)   # largura x espessura x perímetro
    # dutos: o cabeçote tem 8 furos radiais Ø14/Ø16 a mais que um corte sem dutos (verificado pelas faces cilíndricas)
    from modules.measure_engine import MeasureEngine
    head_d = {round(d.diameter, 1) for d in MeasureEngine(pr.components).diameters(by["Cabecote"])}
    assert 16.0 in head_d and 14.0 in head_d                                       # dutos de admissão e escape
    block_d = {round(d.diameter, 1) for d in MeasureEngine(pr.components).diameters(by["Bloco do motor"])}
    assert 5.0 in block_d                                                          # galerias de óleo
