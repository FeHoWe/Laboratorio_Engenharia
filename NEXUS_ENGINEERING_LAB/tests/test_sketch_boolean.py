import math

import pytest

from modules.cad_history import CadHistory, CadHistoryError
from modules.fea_voxel import exact_volume
from modules.sketch2d import Sketch, SketchError
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Pnt


def box(dx=100, dy=60, dz=20):
    return BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), dx, dy, dz).Shape()


def test_rect_and_circle_extrusion_exact_volumes():
    s = Sketch("XY", 0, [{"t": "rect", "x0": 0, "y0": 0, "x1": 20, "y1": 10}])
    assert abs(s.area() - 200) < 1e-9 and abs(exact_volume(s.extrude(5)) - 1000) < 1e-6
    c = Sketch("XY", 0, [{"t": "circle", "cx": 0, "cy": 0, "r": 4}])
    assert abs(exact_volume(c.extrude(10)) - math.pi * 16 * 10) < 1e-6


def test_nested_profile_becomes_hole_and_island():
    s = Sketch("XY", 0, [{"t": "rect", "x0": 0, "y0": 0, "x1": 40, "y1": 40}, {"t": "circle", "cx": 20, "cy": 20, "r": 8}])
    assert abs(s.area() - (1600 - math.pi * 64)) < 1e-9
    assert abs(exact_volume(s.extrude(3)) - (1600 - math.pi * 64) * 3) < 1e-4
    s.add(t="rect", x0=17, y0=17, x1=23, y1=23)                       # ilha dentro do furo soma
    assert abs(s.area() - (1600 - math.pi * 64 + 36)) < 1e-9
    assert abs(exact_volume(s.extrude(3)) - (1600 - math.pi * 64 + 36) * 3) < 1e-3


def test_planes_and_negative_extrusion():
    for pl in ("XY", "XZ", "YZ"):
        assert abs(exact_volume(Sketch(pl, 7, [{"t": "rect", "x0": 0, "y0": 0, "x1": 10, "y1": 10}]).extrude(-4)) - 400) < 1e-6


def test_edit_and_validation_errors():
    s = Sketch("XY", 0, [{"t": "rect", "x0": 0, "y0": 0, "x1": 10, "y1": 10}])
    s.modify(0, x1=30); assert abs(s.area() - 300) < 1e-9
    with pytest.raises(SketchError):
        s.add(t="poly", pts=[[0, 0], [10, 10], [10, 0], [0, 10]])           # gravata-borboleta
    with pytest.raises(SketchError):
        s.add(t="circle", cx=0, cy=0, r=0)
    s2 = Sketch("XY", 0, [{"t": "rect", "x0": 0, "y0": 0, "x1": 10, "y1": 10}, {"t": "rect", "x0": 5, "y0": 5, "x1": 20, "y1": 20}])
    with pytest.raises(SketchError):
        s2.validate()                                                         # se cruzam sem conter
    with pytest.raises(SketchError):
        Sketch("AB")
    with pytest.raises(SketchError):
        Sketch("XY").extrude(1)
    s.delete(0); assert s.entities == []


def test_history_sketch_cut_and_roundtrip():
    h = CadHistory(box(), "teste"); v0 = h.volume()
    sk = Sketch("XY", 0, [{"t": "circle", "cx": 50, "cy": 30, "r": 5}]).to_dict()
    h.add("sketch_extrude", sketch=sk, distance=20, mode="cut")
    assert abs(h.volume() - (v0 - math.pi * 25 * 20)) < 1e-3
    h2 = CadHistory.from_dict(h.to_dict(), box()); assert abs(h2.volume() - h.volume()) < 1e-6
    h.undo(); assert abs(h.volume() - v0) < 1e-6
    h.redo(); h.suppress(0); assert abs(h.volume() - v0) < 1e-6
    with pytest.raises(CadHistoryError):
        h.add("sketch_extrude", sketch=sk, distance=20, mode="xx")
    with pytest.raises(CadHistoryError):
        h.add("sketch_extrude", sketch={"plane": "XY", "offset": 0, "entities": []}, distance=5, mode="add")


def test_boolean_union_cut_common_exact():
    v = 100 * 60 * 20
    h = CadHistory(box(), "t")
    h.add("boolean", mode="union", tool="box", x=100, y=0, z=0, a=50, b=60, c=20)       # encostada: +60000
    assert abs(h.volume() - (v + 50 * 60 * 20)) < 1e-3
    h = CadHistory(box(), "t")
    h.add("boolean", mode="cut", tool="cylinder", x=50, y=30, z=-1, a=10, b=22, axis="z")
    assert abs(h.volume() - (v - math.pi * 25 * 20)) < 1e-3
    h = CadHistory(box(), "t")
    h.add("boolean", mode="common", tool="box", x=50, y=0, z=0, a=100, b=60, c=20)
    assert abs(h.volume() - 50 * 60 * 20) < 1e-3
    h = CadHistory(box(), "t")
    h.add("boolean", mode="cut", tool="sphere", x=0, y=0, z=0, a=10, b=0, c=0)           # 1/8 da esfera dentro da caixa
    assert abs(h.volume() - (v - (4 / 3) * math.pi * 1000 / 8)) < 1e-2


def test_boolean_with_step_file_and_errors(tmp_path):
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer
    w = STEPControl_Writer(); w.Transfer(box(10, 10, 10), STEP := STEPControl_AsIs); assert w.Write(str(tmp_path / "t.step")) == IFSelect_RetDone
    h = CadHistory(box(), "t")
    h.add("boolean", mode="cut", tool="step", path=str(tmp_path / "t.step"), x=20, y=20, z=5, a=0, b=0, c=0)
    assert abs(h.volume() - (100 * 60 * 20 - 1000)) < 1e-3
    for bad in (dict(mode="xor", tool="box"), dict(mode="cut", tool="torus"), dict(mode="cut", tool="box", a=0, b=1, c=1), dict(mode="cut", tool="sphere", a=-1)):
        with pytest.raises(CadHistoryError):
            h.add("boolean", **{"x": 0, "y": 0, "z": 0, "a": 1, "b": 1, "c": 1, **bad})


def test_sketch_dialog_builds_and_applies(monkeypatch):
    from PySide6.QtWidgets import QApplication
    from interface import sketch_dialog as SD
    app = QApplication.instance() or QApplication([])
    h = CadHistory(box(), "t"); v0 = h.volume()
    d = SD.SketchDialog(None, h)
    d._try(t="circle", cx=50, cy=30, r=5)
    assert "círculo" in d.lst.item(0).text() and "Área líquida: 78.5398" in d.info.text()
    msgs = []
    monkeypatch.setattr(SD.QMessageBox, "warning", lambda *a, **k: msgs.append(a[2]))
    d._try(t="poly", pts=[[0, 0], [10, 10], [10, 0], [0, 10]])
    assert len(d.sk.entities) == 1 and "autointersecta" in msgs[-1]
    d.dist.setValue(20); d.mode.setCurrentText("cut"); d.apply()
    assert abs(h.volume() - (v0 - math.pi * 25 * 20)) < 1e-3 and h.ops[-1]["type"] == "sketch_extrude"


def test_arcos_exatos_rrect_slot_volume():
    import math
    from OCP.GProp import GProp_GProps
    from OCP.BRepGProp import BRepGProp
    def vol(sh):
        g = GProp_GProps(); BRepGProp.VolumeProperties_s(sh, g); return g.Mass()
    s = Sketch("XY"); s.add(t="rrect", x0=0, y0=0, x1=20, y1=10, r=3)
    assert vol(s.extrude(5)) == pytest.approx((200 - (4 - math.pi) * 9) * 5, rel=1e-9) and s.area() == pytest.approx(200 - (4 - math.pi) * 9)
    s = Sketch("XY"); s.add(t="slot", cx0=0, cy0=0, cx1=10, cy1=0, w=4)
    assert vol(s.extrude(2)) == pytest.approx((10 * 4 + math.pi * 4) * 2, rel=1e-9)
    s = Sketch("XY"); s.add(t="rrect", x0=0, y0=0, x1=30, y1=20, r=2); s.add(t="slot", cx0=8, cy0=10, cx1=22, cy1=10, w=6)   # rasgo dentro vira furo
    assert s.area() == pytest.approx(600 - (4 - math.pi) * 4 - (14 * 6 + math.pi * 9)) and vol(s.extrude(1)) == pytest.approx(s.area(), rel=1e-9)
    with pytest.raises(SketchError): Sketch().add(t="rrect", x0=0, y0=0, x1=10, y1=4, r=3)
    with pytest.raises(SketchError): Sketch().add(t="slot", cx0=0, cy0=0, cx1=0, cy1=0, w=2)


def test_restricoes_sequenciais_e_conflito():
    s = Sketch("XY"); s.add(t="poly", pts=[[0, 0], [10, 1], [11, 8], [0, 7]]); s.add(t="circle", cx=2, cy=2, r=1); s.add(t="circle", cx=5, cy=5, r=2)
    bad = s.restringir([{"k": "horizontal", "e": 0, "s": 0}, {"k": "vertical", "e": 0, "s": 1}, {"k": "comprimento", "e": 0, "s": 0, "L": 12},
                        {"k": "raio_igual", "a": 1, "b": 2}, {"k": "concentrico", "a": 1, "b": 2}])
    assert [c["k"] for c in bad] == ["vertical"]                                   # o comprimento moveu P1 depois da vertical: ordem importa, e é REPORTADO
    P = s.entities[0]["pts"]; assert P[1][1] == P[0][1] and P[1][0] - P[0][0] == pytest.approx(12) and s.entities[2]["r"] == 1 and s.entities[2]["cx"] == 2
    bad = Sketch("XY", 0, [{"t": "poly", "pts": [[0, 0], [10, 0], [10, 5], [0, 5]]}]).restringir([{"k": "horizontal", "e": 0, "s": 0}, {"k": "fixo", "e": 0, "p": 1, "x": 10, "y": 3}])
    assert bad and bad[0]["k"] == "horizontal"                                    # fixo moveu o ponto e desfez a horizontal: conflito REPORTADO
    with pytest.raises(SketchError): Sketch("XY", 0, [{"t": "circle", "cx": 0, "cy": 0, "r": 1}]).restringir([{"k": "horizontal", "e": 0, "s": 0}])
