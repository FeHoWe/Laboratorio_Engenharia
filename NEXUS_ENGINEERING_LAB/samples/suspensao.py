"""Suspensão de roda dianteira esquerda tipo duplo A (quarto de carro de passeio) com mola-amortecedor — modelo de referência (V2.2).

Pneu 225/45 R17 (Ø externo ≈ 634 mm); braços em tubo de aço; mola helicoidal e amortecedor sobre o braço inferior; disco de freio ventilado por
furos e pinça simplificada; travessa do chassi em tubo retangular com chapas de fixação e parafusos. Eixos: x lateral (roda em x=0, chassi em x<0),
y longitudinal, z para cima (solo z=0).
HONESTIDADE: geometria nominal de montagem (pontos de fixação plausíveis, não de um veículo real); sem buchas elásticas, rótulas internas, barra
estabilizadora, curso de suspensão nem cálculo de rigidez.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.cad_engine import CadEngine, RawNode  # noqa: E402
from core.geometry import translation_matrix  # noqa: E402
from samples import geo as g  # noqa: E402
from samples.library import PARTS  # noqa: E402

R_RIM = 17 * 25.4 / 2
R_TYRE = R_RIM + 0.45 * 225
W_TYRE = 225.0
WC = (0.0, 0.0, R_TYRE)                       # centro da roda
TYPICAL = {"Travessa": "Aço carbono", "Chapa": "Aço carbono", "Braco": "Aço-liga AISI 4130", "Manga": "Aluminum alloy 2024-T6",
           "Disco": "Ferro fundido cinzento ASTM A159", "Pinca": "Aluminum alloy 360", "Roda": "Aluminum alloy 360", "Pneu": "Rubber, hard",
           "Mola": "Aço-liga AISI 4140", "Parafuso": "Aço carbono", "Porca": "Aço carbono", "Arruela": "Aço carbono", "Amortecedor": "Aço carbono",
           "Cubo": "Aço-liga AISI 4140"}


def at(x=0.0, y=0.0, z=0.0):
    return translation_matrix([x, y, z])


def build_suspensao() -> RawNode:
    L = lambda name, shape, m=None: RawNode(name, shape=shape, local_matrix=(at() if m is None else m))  # noqa: E731
    wx, wz = WC[0], WC[2]
    # --- roda
    tyre_prof = [(-W_TYRE / 2 + 12, R_RIM), (-W_TYRE / 2, R_RIM + 40), (-W_TYRE / 2 + 6, R_TYRE - 25), (-W_TYRE / 2 + 30, R_TYRE - 3),
                 (-W_TYRE / 2 + 60, R_TYRE), (W_TYRE / 2 - 60, R_TYRE), (W_TYRE / 2 - 30, R_TYRE - 3), (W_TYRE / 2 - 6, R_TYRE - 25),
                 (W_TYRE / 2, R_RIM + 40), (W_TYRE / 2 - 12, R_RIM)]
    rim_prof = [(-80, R_RIM - 6), (-80, R_RIM), (80, R_RIM), (80, R_RIM - 6), (60, R_RIM - 6), (60, 35), (46, 35), (46, R_RIM - 6)]
    rim = g.clean(g.cut(g.revolve(rim_prof, "x"), *[g.cyl(28, 20, at=(40, 105 * math.cos(2 * math.pi * i / 5), 105 * math.sin(2 * math.pi * i / 5)), axis=g.X) for i in range(5)]))
    hub = g.fuse(g.cyl(30, 165, at=(-105, 0, 0), axis=g.X), g.cyl(90, 10, at=(-60, 0, 0), axis=g.X), g.cyl(60, 12, at=(34, 0, 0), axis=g.X))
    wheel = [L("Pneu 225/45 R17", g.revolve(tyre_prof, "x"), at(*WC)), L("Roda 17 pol", rim, at(*WC)), L("Cubo da roda", hub, at(*WC))]
    disc = g.rot(PARTS["disco_freio"].make(od=300, idia=150, thickness=28, holes=24), g.Y, math.pi / 2)
    cal = g.clean(g.rot(g.cut(g.fuse(g.box(-76, -14, -45, 45, wz + 105, wz + 205), g.box(-76, -62, -40, 40, wz + 60, wz + 106)), g.box(-52, -20, -50, 50, wz + 100, wz + 195)), g.X, math.pi / 2, (0, 0, wz)))
    brake = [L("Disco de freio", disc, at(wx - 50, 0, wz)), L("Pinca de freio", cal, at())]
    # --- manga de eixo, rótulas e braços
    up_bj, lo_bj, tr_u = (-85.0, 0.0, 480.0), (-90.0, 0.0, 160.0), (-95.0, 115.0, 300.0)
    RB = 34.0
    d_up = [up_bj[i] - lo_bj[i] for i in range(3)]
    n_up = math.sqrt(sum(a * a for a in d_up))
    u = [a / n_up for a in d_up]
    carrier = g.cut(g.box(-110, -62, -60, 60, wz - 60, wz + 60), g.cyl(30, 60, at=(-110, 0, wz), axis=g.X))
    tube_up = g.tube(tuple(lo_bj[i] + u[i] * (RB + 0.2) for i in range(3)), tuple(up_bj[i] - u[i] * (RB + 0.2) for i in range(3)), 24)
    upright = g.cut(g.fuse(tube_up, carrier), g.cyl(30, 200, at=(-120, 0, wz), axis=g.X))
    ca = {"up": [(-402, -170, 480), (-402, 190, 470)], "lo": [(-402, -210, 190), (-402, 230, 180)]}

    def arm(a, bj, r_out, r_in):
        v = [bj[i] - a[i] for i in range(3)]
        n = math.sqrt(sum(c * c for c in v))
        e = tuple(bj[i] - v[i] / n * (RB + 0.2) for i in range(3))
        return g.tube(a, e, r_out, r_in)

    arms = []
    for nm, key, bj in (("superior", "up", up_bj), ("inferior", "lo", lo_bj)):
        for i, a in enumerate(ca[key]):
            arms.append(L(f"Braco {nm} {i + 1}", arm(a, bj, 14, 11)))
    arms.append(L("Rotula superior", g.sphere(RB, at=up_bj)))
    arms.append(L("Rotula inferior", g.sphere(RB, at=lo_bj)))
    tr_dir = [tr_u[i] - (-402, 150, 300)[i] for i in range(3)]
    arms.append(L("Barra de direcao", g.tube((-402, 150, 300), tr_u, 9)))
    kids = [RawNode("Roda e pneu", children=wheel), RawNode("Freio", children=brake), RawNode("Manga de eixo", children=[L("Manga de eixo", upright)]),
            RawNode("Bracos", children=arms)]
    # --- mola e amortecedor (eixo inclinado do braço inferior ao topo do chassi)
    p_low, p_top = (-250.0, 10.0, 210.0), (-380.0, 10.0, 680.0)
    axis = [p_top[i] - p_low[i] for i in range(3)]
    length = math.sqrt(sum(a * a for a in axis))
    free = min(300.0, length - 120)
    spring = PARTS["mola_compressao"].make(wire_d=11, mean_d=120, turns=7.5, free_length=free)
    damper = g.fuse(g.cyl(24, length * 0.45, at=(0, 0, 8)), g.cyl(11, length - 40, at=(0, 0, 0)))
    pl = g.cut(g.cyl(70, 8), g.cyl(11, 8))
    kids.append(RawNode("Mola e amortecedor", children=[
        L("Mola helicoidal", g.orient_z_to(spring, axis, p_low)), L("Amortecedor", g.orient_z_to(damper, axis, p_low)),
        L("Prato superior da mola", g.orient_z_to(pl, axis, tuple(p_low[i] + axis[i] / length * free for i in range(3)))),
        L("Prato inferior da mola", g.orient_z_to(g.move(pl, (0, 0, -8)), axis, p_low))]))
    # --- chassi (travessa) e chapas soldadas
    rail = PARTS["tubo_retangular"].make(length=900, w=100, h=80, t=4)
    kids.append(RawNode("Chassi", children=[L("Travessa do chassi", g.rot(rail, g.Z, math.pi / 2), at(-460, -450, 300))]))
    plate = PARTS["chapa_furada"].make(length=120, width=90, thickness=8, hole_d=0, nx=0, ny=0, margin=20)
    plates = []
    for nm, p in [("braco superior 1", ca["up"][0]), ("braco superior 2", ca["up"][1]), ("braco inferior 1", ca["lo"][0]), ("braco inferior 2", ca["lo"][1])]:
        plates.append(L(f"Chapa de fixacao {nm}", g.rot(plate, g.Y, math.pi / 2), at(p[0] - 22, p[1] - 45, p[2] + 60)))
    kids.append(RawNode("Chapas", children=plates))
    return RawNode("Suspensao duplo A dianteira esquerda", children=kids)


def write(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    CadEngine().write_step([build_suspensao()], path)
    return path


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "samples" / "suspensao_duplo_a.step"
    print("Gerado:", write(out))
