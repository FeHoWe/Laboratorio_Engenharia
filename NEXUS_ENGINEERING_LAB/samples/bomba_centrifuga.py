"""Bomba centrífuga de simples estágio com voluta (modelo de referência paramétrico) — V2.7.

Eixo ao longo de X; sucção axial (−X), descarga tangencial (+Z) na voluta. Rotor fechado com 6 palhetas curvas, eixo, mancal, base e parafusos.
HONESTIDADE: voluta simplificada (espiral por polígono de raio crescente), palhetas por arcos aproximados, sem selo mecânico detalhado, sem curvas
H-Q nem NPSH. É geometria didática; use a aba Aerodinâmica/Estrutural só com números seus.
"""
from __future__ import annotations
import math
from pathlib import Path
from samples._common import L, at, g, group, RawNode, write_step, ROOT

R2, R1, BW, HUB = 110.0, 45.0, 22.0, 22.0
TYPICAL: dict = {}


def volute_profile(n=96, r0=118.0, r1=168.0):
    """Contorno (y,z) da espiral: raio cresce de r0 a r1 em 360° (início em +Z, sentido anti-horário)."""
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        r = r0 + (r1 - r0) * i / n
        pts.append((-r * math.sin(a), r * math.cos(a)))
    return pts


def impeller():
    disc_r = g.cut(g.cyl(R2, 5, at=(0, 0, 0), axis=g.X), g.cyl(HUB, 5, axis=g.X))
    shroud = g.cut(g.cyl(R2, 5, at=(BW + 5, 0, 0), axis=g.X), g.cyl(R1, 5, at=(BW + 5, 0, 0), axis=g.X))
    vanes = []
    for k in range(6):
        a0 = 2 * math.pi * k / 6
        pts = []
        for i in range(0, 13):
            t = i / 12
            r = R1 + (R2 - R1) * t
            a = a0 - 0.9 * t                              # curvatura para trás
            pts.append((-r * math.sin(a), r * math.cos(a)))
        thick = [(p[0] + 3 * math.cos(a0 - 0.9 * i / 12), p[1] + 3 * math.sin(a0 - 0.9 * i / 12)) for i, p in enumerate(pts)]
        vanes.append(g.extrude(pts + thick[::-1], "yz", 5, BW))
    hub = g.cut(g.cyl(34, BW + 10, axis=g.X), g.cyl(HUB, BW + 10, axis=g.X))
    return g.clean(g.fuse(disc_r, shroud, hub, *vanes))


def build_bomba() -> RawNode:
    kids = []
    # carcaça: volute extrudada (X de 0 a BW+30), olho de sucção e bocal de descarga
    prof = volute_profile()
    inner = [(y * 0.0 + y, z) for y, z in prof]
    outer = [(y * 1.0 + (y / math.hypot(y, z)) * 14, z + (z / math.hypot(y, z)) * 14) for y, z in prof]
    solid_outer = g.extrude(outer, "yz", -6, BW + 34)
    casing = g.cut(g.extrude(outer, "yz", -6, BW + 34, holes=[inner]), g.cyl(42, 120, at=(BW / 2 - 6, 0, 90), axis=g.Z))
    back = g.cut(g.cyl(185, 12, at=(BW + 28, 0, 0), axis=g.X), g.cyl(30, 12, at=(BW + 28, 0, 0), axis=g.X))
    kids.append(group("Carcaca", L("Voluta", g.clean(casing)), L("Tampa traseira", g.clean(back))))
    suction = g.cut(g.cyl(70, 78, at=(-84, 0, 0), axis=g.X), g.cyl(55, 78, at=(-84, 0, 0), axis=g.X))
    flange_s = g.cut(g.cyl(100, 14, at=(-98, 0, 0), axis=g.X), g.cyl(55, 14, at=(-98, 0, 0), axis=g.X))
    adapt = g.cut(g.cyl(55, 120, at=(BW / 2 - 6, 0, 100), axis=g.Z), solid_outer)
    disch = g.cut(g.fuse(adapt, g.cyl(55, 100, at=(BW / 2 - 6, 0, 190), axis=g.Z)), g.cyl(42, 200, at=(BW / 2 - 6, 0, 95), axis=g.Z))
    disch = g.cut(disch, g.cyl(185, 12, at=(BW + 28, 0, 0), axis=g.X))
    kids.append(group("Bocais", L("Bocal de succao", g.clean(suction)), L("Flange de succao", g.clean(flange_s)), L("Bocal de descarga", g.clean(disch))))
    kids.append(group("Rotor hidraulico", L("Rotor fechado (6 palhetas)", impeller())))
    shaft = g.cyl(HUB, 300, at=(-10, 0, 0), axis=g.X)
    kids.append(group("Eixo", L("Eixo da bomba", shaft), L("Luva do eixo", g.cut(g.cyl(30, 40, at=(BW + 12, 0, 0), axis=g.X), g.cyl(HUB, 40, at=(BW + 12, 0, 0), axis=g.X)))))
    bear = [L("Rolamento dianteiro", PARTS_bearing(44, 80, 16), at(BW + 62, 0, 0)), L("Rolamento traseiro", PARTS_bearing(44, 80, 16), at(BW + 190, 0, 0))]
    house = g.cut(g.cyl(58, 190, at=(BW + 52, 0, 0), axis=g.X), g.cyl(40, 190, at=(BW + 52, 0, 0), axis=g.X))
    kids.append(group("Mancal", L("Caixa de mancais", g.clean(house)), *bear))
    kids.append(group("Base", L("Base de apoio", g.box(-60, BW + 260, -100, 100, -220, -200)),
                      L("Pe do mancal", g.box(BW + 90, BW + 150, -80, 80, -200, -58))))
    return RawNode("Bomba centrifuga com voluta", children=kids)


def PARTS_bearing(bore, od, w):
    from samples._common import PARTS
    return g.rot(PARTS["rolamento_esferas"].make(bore=bore, od=od, width=w), g.Y, math.pi / 2)


def write(path: Path) -> Path:
    return write_step(build_bomba, path)


if __name__ == "__main__":
    print("Gerado:", write(ROOT / "samples" / "bomba_centrifuga.step"))
