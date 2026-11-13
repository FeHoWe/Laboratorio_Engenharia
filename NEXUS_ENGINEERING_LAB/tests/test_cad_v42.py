"""V4.2 — varredura, loft e filete de raio variável (volumes contra fórmula fechada)."""
import math
import pytest
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Pnt
from modules.cad_history import CadHistory, CadHistoryError
from modules.sketch2d import Sketch


def box(a=40, b=40, c=10, o=(0, 0, 0)):
    return BRepPrimAPI_MakeBox(gp_Pnt(*o), a, b, c).Shape()


FAR = (500, 500, 500)


def sk(plano="XY", off=0.0, **e):
    s = Sketch(plano, off); s.add(**e); return s.to_dict()


def test_varredura_reta_equivale_a_extrusao():
    h = CadHistory(box(1, 1, 1, FAR))
    h.add("sketch_sweep", sketch=sk(t="rect", x0=0, y0=0, x1=10, y1=5), path=[[0, 0, 0], [0, 0, 20]], mode="add")
    assert h.volume() == pytest.approx(1 + 10 * 5 * 20, rel=1e-9)


def test_varredura_curva_em_L_e_erros():
    h = CadHistory(box(1, 1, 1, FAR))
    h.add("sketch_sweep", sketch=sk(t="circle", cx=0, cy=0, r=2), path=[[0, 0, 0], [0, 0, 20], [20, 0, 20]], mode="add")
    v = h.volume() - 1
    assert 0.9 * math.pi * 4 * 40 < v < 1.1 * math.pi * 4 * 40            # ≈ área × comprimento do caminho (canto em esquadro ≠ exato)
    for caminho in ([[0, 0, 0]], [[0, 0, 0], [0, 0, 0]], [[0, 0], [1, 1]]):
        with pytest.raises(CadHistoryError):
            h.add("sketch_sweep", sketch=sk(t="circle", cx=0, cy=0, r=2), path=caminho, mode="add")
    assert len(h.ops) == 1


def test_loft_tronco_de_cone_e_prisma():
    h = CadHistory(box(1, 1, 1, FAR))
    h.add("loft", sections=[sk(t="circle", cx=0, cy=0, r=5), sk(off=10, t="circle", cx=0, cy=0, r=10)], ruled=True, mode="add")
    assert h.volume() == pytest.approx(1 + math.pi * 10 * (25 + 50 + 100) / 3, rel=1e-6)    # V = πh(r1²+r1r2+r2²)/3
    h2 = CadHistory(box(1, 1, 1, FAR))
    h2.add("loft", sections=[sk(t="rect", x0=0, y0=0, x1=10, y1=10), sk(off=7, t="rect", x0=0, y0=0, x1=10, y1=10)], ruled=True, mode="add")
    assert h2.volume() == pytest.approx(1 + 700, rel=1e-9)


def test_loft_entradas_invalidas():
    h = CadHistory(box(1, 1, 1, FAR))
    c = sk(t="circle", cx=0, cy=0, r=5)
    with pytest.raises(CadHistoryError): h.add("loft", sections=[c], ruled=False, mode="add")
    dois = Sketch("XY", 10.0); dois.add(t="circle", cx=0, cy=0, r=5); dois.add(t="circle", cx=20, cy=0, r=2)
    with pytest.raises(CadHistoryError): h.add("loft", sections=[c, dois.to_dict()], ruled=False, mode="add")
    assert h.ops == []


def test_filete_variavel_volume_exato():
    h = CadHistory(box(40, 40, 10))
    h.nomear("a", "aresta", {"modo": "perto", "ponto": [20, 0, 10]})          # aresta de topo (40 mm), y = 0
    h.add("fillet_variable", radius1=1, radius2=3, edges="nome:a")
    r1, r2, L = 1, 3, 40
    perda = (1 - math.pi / 4) * L * (r1 * r1 + r1 * r2 + r2 * r2) / 3         # ∫ r(x)²(1−π/4) dx com r linear
    # a fórmula supõe seções perpendiculares à aresta; com raio variável a superfície do OpenCascade é levemente inclinada → tolerância de 3 % da PERDA
    assert abs((16000 - h.volume()) - perda) / perda < 0.03
    assert h.volume() < 16000 and (16000 - h.volume()) > (1 - math.pi / 4) * L * r1 * r1
    with pytest.raises(CadHistoryError): h.add("fillet_variable", radius1=0, radius2=3, edges="nome:a")
    with pytest.raises(CadHistoryError): h.add("fillet_variable", radius1=1, radius2=80, edges="all")
    assert len(h.ops) == 1


def test_varredura_pelo_dialogo():
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from interface.sketch_dialog import SketchDialog
    h = CadHistory(box(1, 1, 1, FAR))
    sd = SketchDialog(None, h)
    sd.sk.add(t="rect", x0=0, y0=0, x1=10, y1=5)
    sd.caminho.setText("0,0,0; 0,0,20")
    sd.apply_sweep()
    assert h.ops[-1]["type"] == "sketch_sweep" and h.volume() == pytest.approx(1 + 1000, rel=1e-9)
