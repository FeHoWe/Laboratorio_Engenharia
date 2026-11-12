"""V4.1 — CAD avançado: furo escareado, padrões linear/circular, espelhar, casca, seleção de arestas topo/base. Volumes conferidos contra fórmulas fechadas."""
import math
import pytest
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Pnt
from modules.cad_history import CadHistory, CadHistoryError
from modules.fea_voxel import shape_bbox


def box(a=40, b=40, c=10):
    return BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), a, b, c).Shape()


def test_furo_escareado():
    h = CadHistory(box())
    h.add("counterbore", x=20, y=20, z=10, dx=0, dy=0, dz=-1, diameter=4, depth=10, cb_diameter=8, cb_depth=3)
    esperado = 16000 - math.pi * 4 ** 2 * 3 - math.pi * 2 ** 2 * 7        # rebaixo (r=4, 3 mm) + furo (r=2) nos 7 mm restantes
    assert h.volume() == pytest.approx(esperado, abs=1e-6)
    with pytest.raises(CadHistoryError):
        h.add("counterbore", x=5, y=5, z=10, dx=0, dy=0, dz=-1, diameter=8, depth=10, cb_diameter=4, cb_depth=3)
    assert len(h.ops) == 1                                                # operação inválida não entra


def test_padrao_linear_de_furos():
    h = CadHistory(box())
    h.add("linear_pattern", mode="cut", tool="cylinder", x=5, y=20, z=-1, a=4, b=12, axis="z", count=4, sx=10, sy=0, sz=0)
    assert h.volume() == pytest.approx(16000 - 4 * math.pi * 4 * 10, abs=1e-6)


def test_padrao_circular_furos_em_circulo_de_parafusos():
    h = CadHistory(box())
    h.add("circular_pattern", mode="cut", tool="cylinder", x=30, y=20, z=-1, a=3, b=12, axis="z", count=6,
          cx=20, cy=20, cz=0, ax=0, ay=0, az=1, angle_deg=360)
    assert h.volume() == pytest.approx(16000 - 6 * math.pi * 1.5 ** 2 * 10, abs=1e-6)
    with pytest.raises(CadHistoryError):
        h.add("circular_pattern", mode="cut", tool="cylinder", x=30, y=20, z=-1, a=3, b=12, count=3, cx=0, cy=0, cz=0, ax=0, ay=0, az=0, angle_deg=360)


def test_padrao_arco_parcial_usa_count_menos_um_passos():
    h = CadHistory(box(60, 60, 10))
    h.add("circular_pattern", mode="cut", tool="cylinder", x=45, y=30, z=-1, a=2, b=12, axis="z", count=3,
          cx=30, cy=30, cz=0, ax=0, ay=0, az=1, angle_deg=180)             # 0°, 90°, 180°
    assert h.volume() == pytest.approx(36000 - 3 * math.pi * 1.0 * 10, abs=1e-6)


def test_espelhar_dobra_o_volume_de_peca_encostada_no_plano():
    h = CadHistory(box(20, 20, 10))
    h.add("mirror", plane="x", offset=0.0)
    (x0, _, _), (x1, _, _) = shape_bbox(h.shape)
    assert (x0, x1) == (pytest.approx(-20), pytest.approx(20))
    assert h.volume() == pytest.approx(2 * 4000, abs=1e-6)
    with pytest.raises(CadHistoryError):
        h.add("mirror", plane="w", offset=0)


def test_casca_aberta_em_cima():
    h = CadHistory(box(40, 40, 20))
    h.add("shell", thickness=2, open_face="+z")
    assert h.volume() == pytest.approx(40 * 40 * 20 - 36 * 36 * 18, abs=1e-4)
    with pytest.raises(CadHistoryError):
        h.add("shell", thickness=30, open_face="+z")
    with pytest.raises(CadHistoryError):
        h.add("shell", thickness=1, open_face="cima")


def test_filete_so_nas_arestas_do_topo():
    h = CadHistory(box(20, 20, 10))
    h.add("fillet", radius=2, edges="top:z")
    # 4 arestas do topo (comprimento 20): perda (r² − πr²/4)·L cada, MAS nos cantos há encontro com as verticais não filetadas
    v = h.volume()
    assert 4000 - 4 * (4 - math.pi) * 20 - 1e-6 <= v < 4000                  # menos que o bloco, mais que filetar tudo
    h2 = CadHistory(box(20, 20, 10)); h2.add("fillet", radius=2, edges="bottom:z")
    assert h2.volume() == pytest.approx(v, abs=1e-6)                         # simetria topo × base
    h3 = CadHistory(box(20, 20, 10)); h3.add("chamfer", distance=1, edges="top:z")
    # 4 prismas triangulares de 20 mm, menos a sobreposição de 4 cantos (cada um conta uma pirâmide d³/3 duas vezes)
    assert h3.volume() == pytest.approx(4000 - 4 * 0.5 * 20 + 4 * 1 / 3, abs=1e-6)


def test_receita_reaplicavel_e_serializavel():
    h = CadHistory(box())
    h.add("shell", thickness=2, open_face="+z")
    h.add("linear_pattern", mode="union", tool="box", x=5, y=5, z=0, a=3, b=3, c=3, count=3, sx=10, sy=0, sz=0)
    v = h.volume()
    h2 = CadHistory.from_dict(h.to_dict(), box())
    assert h2.volume() == pytest.approx(v, abs=1e-6)
    h2.suppress(0); assert h2.volume() != pytest.approx(v)
