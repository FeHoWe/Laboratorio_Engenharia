"""Redutor de engrenagens de 2 estágios (modelo de referência paramétrico) — V2.2.

Três eixos paralelos (ao longo de Y), estágio 1: 20 → 60 dentes (módulo 2, distância entre eixos 80 mm); estágio 2: 24 → 48 dentes (módulo 2,5,
distância 90 mm); redução total = (60/20)·(48/24) = 6:1. Carcaça bipartida em z=0, rolamentos rígidos de esferas, tampas e parafusos.
HONESTIDADE: geometria nominal de montagem; sem roscas, chavetas, vedações, lubrificação nem cálculo de capacidade de carga. As engrenagens vêm da
biblioteca (evolvente sem correção de perfil). Sentidos de giro: entrada +, intermediário −, saída + (dois engrenamentos externos).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.cad_engine import CadEngine, RawNode  # noqa: E402
from core.geometry import translation_matrix  # noqa: E402
from samples import geo as g  # noqa: E402
from samples.library import PARTS  # noqa: E402

A1, A2 = 80.0, 90.0                       # distâncias entre eixos dos estágios
XS = [0.0, A1, A1 + A2]                   # x dos eixos 1, 2, 3 (z=0)
Z1, Z2, Z3, Z4 = 20, 60, 24, 48
M1, M2 = 2.0, 2.5
GW = 22.0                                 # largura das engrenagens
BEARS = [(25.0, 52.0, 15.0), (30.0, 62.0, 16.0), (30.0, 62.0, 16.0)]   # 6205 no eixo 1; 6206 nos eixos 2 e 3
Y_IN, Y_OUT = -130.0, 130.0               # faces das paredes laterais da carcaça (y)
TYPICAL = {
    "Carcaca": "Aluminum alloy 360", "Tampa": "Aluminum alloy 360", "Eixo": "Aço-liga AISI 4140", "Engrenagem": "Aço-liga AISI 4140",
    "Rolamento": "Aço-liga AISI 4140", "Parafuso": "Aço carbono", "Porca": "Aço carbono", "Arruela": "Aço carbono",
}


def at(x=0.0, y=0.0, z=0.0):
    return translation_matrix([x, y, z])


def gear_along_y(z_teeth, module, cx, y0, bore, mesh_with=None):
    """Engrenagem com eixo em +Y, centro em (cx, *, 0). ``mesh_with`` = (z_outra, fase_outra): a outra está à ESQUERDA (x menor).

    Fase de engrenamento: com a outra com dente em φA, esta tem vão em π − φA·zA/zB (linha de centros = ângulo π vista daqui).
    """
    shape = PARTS["engrenagem_reta"].make(module=module, teeth=z_teeth, width=GW, bore=bore)
    delta = 2 * math.pi / z_teeth
    phase = 0.0
    if mesh_with is not None:
        zo, ph_o = mesh_with
        phase = (math.pi - delta / 2 - ph_o * zo / z_teeth) % delta
    shape = g.rot(shape, (0, 0, 1), phase)
    shape = g.rot(shape, g.X, -math.pi / 2)               # z → +y
    return g.move(shape, (cx, y0, 0)), phase


BOLT_XY = None  # preenchido em build_redutor


def build_redutor() -> RawNode:
    L = lambda name, shape, m=None: RawNode(name, shape=shape, local_matrix=(at() if m is None else m))  # noqa: E731
    kids = []
    # --- eixos e engrenagens
    g1, ph1 = gear_along_y(Z1, M1, XS[0], -GW / 2, 25.0)
    g2, ph2 = gear_along_y(Z2, M1, XS[1], -GW / 2, 30.0, mesh_with=(Z1, ph1))
    g3, ph3 = gear_along_y(Z3, M2, XS[1], 20, 30.0)
    g4, ph4 = gear_along_y(Z4, M2, XS[2], 20, 30.0, mesh_with=(Z3, ph3))
    shaft_defs = [(XS[0], -170.0, 170.0, 25.0), (XS[1], -150.0, 150.0, 30.0), (XS[2], -150.0, 190.0, 30.0)]
    shafts = []
    for i, (x, y0, y1, d) in enumerate(shaft_defs):
        shafts.append(L(f"Eixo {['de entrada', 'intermediario', 'de saida'][i]}", g.cyl(d / 2, y1 - y0, at=(x, y0, 0), axis=g.Y)))
    kids.append(RawNode("Eixos", children=shafts))
    kids.append(RawNode("Engrenagens", children=[
        L("Engrenagem estagio 1 pinhao (20 dentes)", g1), L("Engrenagem estagio 1 coroa (60 dentes)", g2),
        L("Engrenagem estagio 2 pinhao (24 dentes)", g3), L("Engrenagem estagio 2 coroa (48 dentes)", g4)]))
    # --- rolamentos nas paredes (um em cada lado de cada eixo)
    bearings = []
    for i, x in enumerate(XS):
        bd, bo, bw = BEARS[i]
        bear = PARTS["rolamento_esferas"].make(bore=bd, od=bo, width=bw)
        for side, y in (("lado A", Y_IN), ("lado B", Y_OUT - bw)):
            bearings.append(L(f"Rolamento {'6205' if i == 0 else '6206'} eixo {i + 1} {side}", g.move(g.rot(bear, g.X, -math.pi / 2), (x, y, 0))))
    kids.append(RawNode("Rolamentos", children=bearings))
    # --- carcaça bipartida em z=0 e tampas
    xmin, xmax = XS[0] - 55, XS[2] + 72
    global BOLT_XY
    BOLT_XY = [(xmin + 4, y) for y in (Y_IN - 5, Y_OUT + 5)] + [(xmax - 4, y) for y in (Y_IN - 5, Y_OUT + 5)] + [((XS[0] + XS[1]) / 2, Y_IN - 5), ((XS[1] + XS[2]) / 2, Y_IN - 5), ((XS[0] + XS[1]) / 2, Y_OUT + 5), ((XS[1] + XS[2]) / 2, Y_OUT + 5)]
    def half(sign):
        z0, z1 = (0, 85) if sign > 0 else (-85, 0)
        body = g.box(xmin, xmax, Y_IN - 12, Y_OUT + 12, z0, z1)
        cav = g.box(xmin + 8, xmax - 8, Y_IN + 2, Y_OUT - 2, z0, z1)
        bores = [g.cyl(BEARS[i][1] / 2, 40, at=(x, y, 0), axis=g.Y) for i, x in enumerate(XS) for y in (Y_IN - 12, Y_OUT - 2)]
        thru = [g.cyl(17, 400, at=(x, -200, 0), axis=g.Y) for x in XS]
        return g.clean(g.cut(body, cav, *bores, *thru, *[g.cyl(4.2, 90, at=(x, y, z0 - 2)) for x, y in BOLT_XY]))
    kids.append(RawNode("Carcaca", children=[L("Carcaca inferior", half(-1)), L("Carcaca superior", half(1))]))
    caps = []
    for i, x in enumerate(XS):
        cap = g.clean(g.cut(g.cyl(BEARS[i][1] / 2 + 8, 10, axis=g.Y), g.cyl(16, 10, axis=g.Y)))
        caps.append(L(f"Tampa de rolamento eixo {i + 1} lado A", cap, at(x, Y_IN - 22, 0)))
        caps.append(L(f"Tampa de rolamento eixo {i + 1} lado B", cap, at(x, Y_OUT + 12, 0)))
    kids.append(RawNode("Tampas", children=caps))
    # --- parafusos de união da carcaça (M8 x 25, em z=0 por fora da cavidade) com porca e arruela
    bolt, nut, wash = PARTS["parafuso_sextavado"].make(d=8, length=178), PARTS["porca_sextavada"].make(d=8), PARTS["arruela_lisa"].make(d=8)
    fast = []
    for i, (x, y) in enumerate(BOLT_XY):
        fast += [L(f"Parafuso M8x178 {i + 1}", bolt, at(x, y, 85 + 1.6)), L(f"Arruela M8 {i + 1}", wash, at(x, y, 85)),
                 L(f"Porca M8 {i + 1}", nut, at(x, y, -85 - 6.8))]
    kids.append(RawNode("Fixacao", children=fast))
    return RawNode("Redutor de engrenagens 2 estagios (6 para 1)", children=kids)


def write(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    CadEngine().write_step([build_redutor()], path)
    return path


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "samples" / "redutor_2_estagios.step"
    print("Gerado:", write(out))
