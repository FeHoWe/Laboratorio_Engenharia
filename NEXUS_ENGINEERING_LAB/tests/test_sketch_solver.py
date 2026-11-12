import math, pytest
from modules.sketch2d import Sketch, SketchError


def _tri():
    s = Sketch("XY"); s.add(t="poly", pts=[[0, 0], [10, 1], [11, 8], [0, 7]]); return s


def test_retangulo_a_partir_de_quadrilatero_torto():
    s = _tri()
    r = s.resolver([{"k": "horizontal", "e": 0, "s": 0}, {"k": "vertical", "e": 0, "s": 1}, {"k": "horizontal", "e": 0, "s": 2}, {"k": "vertical", "e": 0, "s": 3},
                    {"k": "fixo", "e": 0, "p": 0, "x": 0, "y": 0}, {"k": "comprimento", "e": 0, "s": 0, "L": 12}, {"k": "comprimento", "e": 0, "s": 1, "L": 5}])
    assert r["resolvido"] and r["residuo_max"] < 1e-6
    P = s.entities[0]["pts"]
    assert P[1] == pytest.approx([12, 0], abs=1e-6) and P[2] == pytest.approx([12, 5], abs=1e-6) and P[3] == pytest.approx([0, 5], abs=1e-6)
    assert s.area() == pytest.approx(60, abs=1e-5)


def test_ordem_nao_importa_diferente_do_sequencial():
    # o caso que o aplicador sequencial reportava como violado (comprimento depois de vertical) o solver resolve
    s = _tri()
    r = s.resolver([{"k": "horizontal", "e": 0, "s": 0}, {"k": "vertical", "e": 0, "s": 1}, {"k": "comprimento", "e": 0, "s": 0, "L": 12}])
    assert r["resolvido"]
    P = s.entities[0]["pts"]; assert P[1][1] == pytest.approx(P[0][1], abs=1e-6) and P[2][0] == pytest.approx(P[1][0], abs=1e-6) and math.hypot(P[1][0] - P[0][0], P[1][1] - P[0][1]) == pytest.approx(12, abs=1e-6)


def test_paralelo_perpendicular_tangentes_e_raios():
    s = Sketch("XY"); s.add(t="poly", pts=[[0, 0], [10, 0], [10, 6], [1, 5]]); s.add(t="circle", cx=3, cy=3, r=1); s.add(t="circle", cx=7, cy=3, r=2)
    r = s.resolver([{"k": "paralelo", "e1": 0, "s1": 0, "e2": 0, "s2": 2}, {"k": "perpendicular", "e1": 0, "s1": 0, "e2": 0, "s2": 1},
                    {"k": "raio", "e": 1, "r": 1.5}, {"k": "tangente_circulos", "a": 1, "b": 2, "tipo": "ext"}, {"k": "tangente_reta_circulo", "e": 0, "s": 0, "c": 1}])
    assert r["resolvido"], r
    c1, c2 = s.entities[1], s.entities[2]
    assert c1["r"] == pytest.approx(1.5, abs=1e-6) and math.hypot(c1["cx"] - c2["cx"], c1["cy"] - c2["cy"]) == pytest.approx(c1["r"] + c2["r"], abs=1e-6)


def test_conflito_devolve_original():
    s = _tri(); antes = [list(p) for p in s.entities[0]["pts"]]
    r = s.resolver([{"k": "comprimento", "e": 0, "s": 0, "L": 5}, {"k": "comprimento", "e": 0, "s": 0, "L": 9}])
    assert r["resolvido"] is False and r["violadas"] and s.entities[0]["pts"] == antes


def test_erros():
    with pytest.raises(SketchError): Sketch("XY", 0, [{"t": "circle", "cx": 0, "cy": 0, "r": 1}]).resolver([{"k": "horizontal", "e": 0, "s": 0}])
    with pytest.raises(SketchError): _tri().resolver([{"k": "xyz"}])
