"""Ponte treliçada de aço (vão 12 m, tipo Pratt com banzos paralelos) — modelo de referência (V2.2).

Duas treliças planas (y = ±1500 mm) de 6 painéis de 2000 mm e altura 2000 mm: banzos e montantes/diagonais em tubo retangular, chapas de nó com
parafusos M16, travessas de piso em viga I, contraventamento superior em tubo e tabuleiro em chapas. Eixos: x ao longo do vão, y transversal, z para cima.
HONESTIDADE: geometria nominal para estudo e montagem; os perfis NÃO foram dimensionados (sem cálculo de cargas, flambagem, ligações nem normas).
Os esforços para a aba de fadiga vêm de você. Bom projeto de teste para vigas, tubos e fixadores da biblioteca.
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

PANELS, PANEL, H, HALF_W = 6, 2000.0, 2000.0, 1500.0
TYPICAL = {"Banzo": "ASTM A36 steel", "Montante": "ASTM A36 steel", "Diagonal": "ASTM A36 steel", "Travessa": "ASTM A36 steel",
           "Contraventamento": "ASTM A36 steel", "Chapa de no": "ASTM A36 steel", "Tabuleiro": "ASTM A36 steel", "Parafuso": "Aço carbono",
           "Porca": "Aço carbono", "Arruela": "Aço carbono"}


def at(x=0.0, y=0.0, z=0.0):
    return translation_matrix([x, y, z])


def member(p1, p2, w, h, t):
    p1, p2 = np.array(p1, float), np.array(p2, float)
    length = float(np.linalg.norm(p2 - p1))
    return g.orient_x_to(PARTS["tubo_retangular"].make(length=length, w=w, h=h, t=t), p2 - p1, p1)


def build_ponte() -> RawNode:
    L = lambda name, shape, m=None: RawNode(name, shape=shape, local_matrix=(at() if m is None else m))  # noqa: E731
    kids = []
    bolt, nut, wash = PARTS["parafuso_sextavado"].make(d=16, length=40), PARTS["porca_sextavada"].make(d=16), PARTS["arruela_lisa"].make(d=16)
    gusset = PARTS["chapa_furada"].make(length=360, width=360, thickness=12, hole_d=0, nx=0, ny=0, margin=20)
    gusset = g.cut(gusset, *[g.cyl(8.5, 12, at=(180 + dx, 180 + dz, 0)) for dx, dz in ((-90, -90), (90, 90))])
    for side, y in (("A", -HALF_W), ("B", HALF_W)):
        mem = []
        for i in range(PANELS + 1):
            xb = i * PANEL
            mem.append(L(f"Montante {side}{i}", member((xb, y, 70), (xb, y, H - 70), 100, 100, 6)))
        for i in range(PANELS):
            x0, x1 = i * PANEL, (i + 1) * PANEL
            mem.append(L(f"Banzo inferior {side}{i + 1}", member((x0, y, 0), (x1, y, 0), 140, 140, 8)))
            mem.append(L(f"Banzo superior {side}{i + 1}", member((x0, y, H), (x1, y, H), 140, 140, 8)))
            a, b = ((x0, y, H), (x1, y, 0)) if i < PANELS // 2 else ((x0, y, 0), (x1, y, H))     # diagonais tracionadas apontam para o centro
            d = (np.array(b) - np.array(a)) / math.hypot(PANEL, H)
            mem.append(L(f"Diagonal {side}{i + 1}", member(tuple(np.array(a) + 200 * d), tuple(np.array(b) - 200 * d), 90, 90, 5)))
        kids.append(RawNode(f"Trelica {side}", children=mem))
        gus, fas = [], []
        for i in range(PANELS + 1):
            for zlev, tag in ((0.0, "inferior"), (H, "superior")):
                px = i * PANEL
                gus.append(L(f"Chapa de no {side}{i} {tag}", g.rot(gusset, g.X, math.pi / 2), at(px - 180, y + 82, zlev - 180)))
                for k, (dx, dz) in enumerate(((-90, -90), (90, 90))):
                    fas += [L(f"Parafuso M16 {side}{i} {tag} {k + 1}", g.rot(bolt, g.X, -math.pi / 2), at(px + dx, y + 85, zlev + dz)),
                            L(f"Arruela M16 {side}{i} {tag} {k + 1}", g.rot(wash, g.X, -math.pi / 2), at(px + dx, y + 82, zlev + dz)),
                            L(f"Porca M16 {side}{i} {tag} {k + 1}", g.rot(nut, g.X, -math.pi / 2), at(px + dx, y + 70 - 14.8, zlev + dz))]
        kids.append(RawNode(f"Nos {side}", children=gus + fas))
    beams = [L(f"Travessa de piso {i}", g.rot(PARTS["viga_i"].make(length=2 * HALF_W + 140, h=200, b=100, tw=5.6, tf=8.5), g.Z, math.pi / 2),
               at(i * PANEL, -HALF_W - 70, -290)) for i in range(PANELS + 1)]
    kids.append(RawNode("Travessas", children=beams))
    brace = [L(f"Contraventamento superior {i}", member((i * PANEL, -HALF_W + 82, H), (i * PANEL, HALF_W - 82, H), 80, 80, 5)) for i in range(PANELS + 1)]
    kids.append(RawNode("Contraventamento", children=brace))
    deck = PARTS["chapa_furada"].make(length=PANEL, width=2 * HALF_W - 180, thickness=10, hole_d=0, nx=0, ny=0, margin=20)
    kids.append(RawNode("Tabuleiro", children=[L(f"Tabuleiro {i + 1}", deck, at(i * PANEL, -HALF_W + 90, -190)) for i in range(PANELS)]))
    return RawNode("Ponte trelicada de aco (vao 12 m)", children=kids)


def write(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    CadEngine().write_step([build_ponte()], path)
    return path


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "samples" / "ponte_trelicada.step"
    print("Gerado:", write(out))
