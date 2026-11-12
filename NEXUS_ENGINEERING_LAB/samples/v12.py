"""Motor V12 a 60° (modelo de referência paramétrico) — V2.7.

Virabrequim ao longo de X (6 moentes, fases 0/240/120/120/240/0°), dois bancos de 6 cilindros a ±30° da vertical (plano YZ), passo 100 mm,
diâmetro 86 mm, curso 80 mm (raio da manivela 40 mm), biela 140 mm. Cada moente carrega 2 bielas lado a lado (uma por banco).
HONESTIDADE: sem comando de válvulas/válvulas/coletores/refrigeração/óleo; bloco, cabeçotes e cárter são volumes simplificados. A ordem de ignição
real depende do projeto; aqui as fases do virabrequim são as de um V12 60° típico, só para a animação biela-manivela.
"""
from __future__ import annotations
import math
from pathlib import Path
from samples._common import L, at, g, group, RawNode, write_step, ROOT

NC, PITCH, BORE, RC, LROD = 6, 100.0, 86.0, 40.0, 140.0
HALF_V = math.radians(30.0)
PHASES = [0, 240, 120, 120, 240, 0]                  # graus por moente
XC = [i * PITCH for i in range(NC)]
DECK = 215.0                                         # distância do eixo do virabrequim ao plano do cabeçote (ao longo do eixo do banco)
ROD_DX = 14.0                                        # deslocamento axial das bielas em cada moente (±)
TYPICAL: dict = {}


def bank_axis(b):                                    # b = +1 (lado +Y) ou -1; vetor unitário (y, z)
    return (b * math.sin(HALF_V), math.cos(HALF_V))


def pin_pos(i, theta_deg):                           # (y,z) do moente i com o virabrequim em theta (convenção do motor 4 cil.)
    t = math.radians(PHASES[i] + theta_deg)
    return -RC * math.sin(t), RC * math.cos(t)


def slider(i, b, theta_deg):
    """(s, (py,pz)): distância do pino do pistão ao eixo do virabrequim ao longo do banco b e posição do moente."""
    py, pz = pin_pos(i, theta_deg); ay, az = bank_axis(b)
    along = py * ay + pz * az
    perp = py * az - pz * ay
    return along + math.sqrt(LROD ** 2 - perp ** 2), (py, pz)


def _to_axis(shape, b, s):
    """Leva uma peça construída ao longo de +Z (origem na base) para o eixo do banco b, a distância s do eixo X."""
    ay, az = bank_axis(b)
    ang = -b * HALF_V                                # rotação em torno de X que leva +Z para (ay, az)
    return g.move(g.rot(shape, g.X, ang), (0, ay * s, az * s))


def rod_shape():
    big = g.cut(g.cyl(28, 22, at=(-11, 0, 0), axis=g.X), g.cyl(24.5, 22, at=(-11, 0, 0), axis=g.X))
    small = g.cut(g.cyl(14, 22, at=(-11, 0, LROD), axis=g.X), g.cyl(10, 22, at=(-11, 0, LROD), axis=g.X))
    web = g.extrude([(-10, 24), (10, 24), (6, LROD - 12), (-6, LROD - 12)], "yz", -8, 16)     # perfil em (y,z): haste
    return g.clean(g.fuse(big, small, web))


def build_v12() -> RawNode:
    kids = []
    L_BLOCK = XC[-1] + PITCH
    x0, x1 = -PITCH / 2, XC[-1] + PITCH / 2
    # bloco: volume em V com cavidade do cárter e furos dos cilindros
    crankcase = g.box(x0, x1, -120, 120, -50, 120)
    banks = [_bank_box(b, x0, x1, 0, DECK - 20, 75) for b in (1, -1)]
    block = g.fuse(crankcase, *banks)
    cav = g.box(x0 + 6, x1 - 6, -92, 92, -50, 100)
    block = g.cut(block, cav, *[g.move(g.rot(g.cyl(BORE / 2, DECK - 20, at=(0, 0, 60)), g.X, -b * HALF_V), (x, 0, 0)) for b in (1, -1) for x in XC])
    shaft_bore = g.cyl(30, x1 - x0 + 20, at=(x0 - 10, 0, 0), axis=g.X)
    kids.append(group("Bloco", L("Bloco do motor V12", g.clean(g.cut(block, shaft_bore)))))
    # cabeçotes e tampas
    heads = []
    for b, tag in ((1, "direito"), (-1, "esquerdo")):
        heads.append(L(f"Cabecote {tag}", _bank_box(b, x0, x1, DECK - 20, DECK + 40, 75)))
        heads.append(L(f"Tampa de valvulas {tag}", _bank_box(b, x0 + 8, x1 - 8, DECK + 40, DECK + 80, 60)))
    kids.append(group("Cabecotes", *heads))
    # virabrequim
    crank = []
    for jn in range(NC + 1):
        crank.append(L(f"Munhao principal {jn + 1}", g.cyl(28, 30, at=(-50 + 100 * jn - 15, 0, 0), axis=g.X)))
    for i in range(NC):
        py, pz = pin_pos(i, 0)
        crank.append(L(f"Moente {i + 1}", g.cyl(24, 50, at=(XC[i] - 25, py, pz), axis=g.X)))
        for sd, xw in ((-1, XC[i] - 33), (1, XC[i] + 25)):
            web = g.fuse(g.cyl(44, 8, at=(xw, 0, 0), axis=g.X), g.cyl(30, 8, at=(xw, py, pz), axis=g.X))
            crank.append(L(f"Braco {i + 1}{'a' if sd < 0 else 'b'}", g.clean(web)))
    crank.append(L("Ponta dianteira do virabrequim", g.cyl(26, 45, at=(x0 - 110, 0, 0), axis=g.X)))
    crank.append(L("Polia do virabrequim", g.cut(g.cyl(80, 26, at=(x0 - 106, 0, 0), axis=g.X), g.cyl(26, 26, at=(x0 - 106, 0, 0), axis=g.X))))
    crank.append(L("Volante do motor", g.cut(g.cyl(150, 34, at=(x1 + 30, 0, 0), axis=g.X), g.cyl(36, 34, at=(x1 + 30, 0, 0), axis=g.X))))
    crank.append(L("Flange traseira do virabrequim", g.cyl(36, 15, at=(x1 + 15, 0, 0), axis=g.X)))
    kids.append(group("Virabrequim", *crank))
    # bielas, pistões, pinos
    rods, pists, pins = [], [], []
    for b, tag in ((1, "D"), (-1, "E")):
        for i in range(NC):
            s0, (py, pz) = slider(i, b, 0)
            dx = ROD_DX * b
            ay, az = bank_axis(b)
            # biela construída ao longo de +Z com olhal grande na origem; levada para o moente e inclinada na direção do pino
            d = (ay * s0 - py, az * s0 - pz); ang = math.atan2(d[1], d[0]) - math.pi / 2
            rod = g.move(g.rot(rod_shape(), g.X, ang), (XC[i] + dx, py, pz))
            rods.append(L(f"Biela {tag}{i + 1}", rod))
            piston = g.cut(g.cyl(BORE / 2 - 0.5, 58, at=(0, 0, 0)), g.cyl(BORE / 2 - 12, 54, at=(0, 0, -1)), g.cyl(10, 100, at=(-50, 0, 37), axis=g.X))
            pgm = g.move(g.rot(piston, g.X, -b * HALF_V), (XC[i], ay * (s0 - 37), az * (s0 - 37)))
            pists.append(L(f"Pistao {tag}{i + 1}", pgm))
            pin = g.cyl(10, 50, at=(XC[i] + dx - 25, ay * s0, az * s0), axis=g.X)
            pins.append(L(f"Pino do pistao {tag}{i + 1}", pin))
    kids.append(group("Bielas", *rods)); kids.append(group("Pistoes", *pists)); kids.append(group("Pinos", *pins))
    # cárter
    pan = g.cut(g.box(x0 - 4, x1 + 4, -140, 140, -170, -50), g.box(x0 + 4, x1 - 4, -128, 128, -158, -49))
    kids.append(group("Carter", L("Carter de oleo", g.clean(pan))))
    return RawNode("Motor V12 60 graus", children=kids)


def _bank_box(b, xa, xb, s0, s1, halfw):
    """Caixa orientada com o banco b entre as distâncias s0 e s1 do eixo X."""
    return g.rot(g.box(xa, xb, -halfw, halfw, s0, s1), g.X, -b * HALF_V)


def write(path: Path) -> Path:
    return write_step(build_v12, path)


if __name__ == "__main__":
    print("Gerado:", write(ROOT / "samples" / "v12.step"))
