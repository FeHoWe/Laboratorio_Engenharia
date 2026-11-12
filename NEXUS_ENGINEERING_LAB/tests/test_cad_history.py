import math, pytest
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Pnt
from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
from modules.cad_history import CadHistory, CadHistoryError, load_step
from modules.fea_voxel import shape_bbox

def box(a=20, b=20, c=10):
    return BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), a, b, c).Shape()

def test_hole_volume_and_param_edit():
    h = CadHistory(box())
    i = h.add("hole", x=10, y=10, z=-1, dx=0, dy=0, dz=1, diameter=4, depth=12)
    assert abs(h.volume() - (4000 - math.pi*4*10)) < 1e-6
    h.set_param(i, "diameter", 6); assert abs(h.volume() - (4000 - math.pi*9*10)) < 1e-6
    with pytest.raises(CadHistoryError): h.set_param(i, "diameter", -1)
    assert h.ops[i]["params"]["diameter"] == 6                       # rollback

def test_undo_redo_suppress():
    h = CadHistory(box())
    h.add("translate", dx=5, dy=0, dz=0); h.add("scale", factor=2)
    assert abs(h.volume() - 4000*8) < 1e-6
    h.undo(); assert abs(h.volume() - 4000) < 1e-6 and shape_bbox(h.shape)[0][0] == pytest.approx(5, abs=1e-6)
    h.redo(); h.suppress(1); assert abs(h.volume() - 4000) < 1e-6
    h.undo(); h.undo(); h.add("scale", factor=3); assert not h.redo()   # ramo descartado
    assert abs(h.volume() - 4000*27) < 1e-4

def test_fillet_chamfer_reduce_volume_and_fail_gracefully():
    h = CadHistory(box())
    h.add("fillet", radius=2, edges="axis:z")
    assert abs(h.volume() - (4000 - 4*(4 - math.pi)*10)) < 1e-6        # 4 arestas z: (r²−πr²/4)·L cada
    with pytest.raises(CadHistoryError): h.add("fillet", radius=50, edges="all")
    assert len(h.ops) == 1
    h2 = CadHistory(box()); h2.add("chamfer", distance=1, edges="axis:z"); assert abs(h2.volume() - (4000 - 4*0.5*10)) < 1e-6

def test_boxes_and_step_roundtrip(tmp_path):
    h = CadHistory(box()); h.add("box_cut", x0=0, y0=0, z0=5, x1=10, y1=20, z1=11); h.add("box_add", x0=20, y0=0, z0=0, x1=25, y1=20, z1=10)
    assert abs(h.volume() - (4000 - 10*20*5 + 5*20*10)) < 1e-6
    w = STEPControl_Writer(); w.Transfer(box(), STEPControl_AsIs); w.Write(str(tmp_path/"b.step"))
    b = load_step(tmp_path/"b.step"); h3 = CadHistory.from_dict(h.to_dict(), b)
    assert abs(h3.volume() - h.volume()) < 1e-6
    with pytest.raises(CadHistoryError): load_step(tmp_path/"nao.step")

def test_missing_params():
    with pytest.raises(CadHistoryError): CadHistory(box()).add("hole", x=1)


def test_dialog_flow():
    import os; os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from interface.cad_history_dialog import CadHistoryDialog
    d = CadHistoryDialog(); d.use_part(); v0 = d.hist.volume()
    d.hist.add("scale", factor=2); d.refresh(); assert d.lst.count() == 1 and abs(d.hist.volume() - 8*v0) < 1e-3*v0
    d.undo(); assert abs(d.hist.volume() - v0) < 1e-6 * v0
