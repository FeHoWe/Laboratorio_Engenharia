"""Guindaste torre (grua) treliçado (modelo de referência paramétrico) — V2.7.

Mastro de seção 1,5 × 1,5 m (8 módulos de 3 m, cantoneiras/tubos com contraventamento em X), plataforma giratória com cabine, lança de 30 m
(treliça triangular), contralança de 10 m com contrapesos, carrinho e bloco de gancho. Eixo Z vertical, lança ao longo de +X na posição inicial.
HONESTIDADE: perfis tubulares simplificados, nós sem chapas/parafusos, sem cabos de aço reais (um cabo reto), sem dimensionamento por norma
nem diagrama de cargas. A animação (giro, carrinho) é prescrita. Bom para testar treliças (aba Treliça/Pórtico) com seus números.
"""
from __future__ import annotations
import math
import numpy as np
from pathlib import Path
from samples._common import L, at, g, group, RawNode, write_step, ROOT

TYPICAL: dict = {}
MOD, W, NMOD = 3000.0, 1500.0, 8
H_MAST = MOD * NMOD
JIB_L, CJ_L, JIB_W, JIB_H = 30000.0, 10000.0, 1400.0, 1800.0
Z0 = H_MAST + 1200.0                               # referência da altura da lança
ZP = H_MAST + 35.0                                 # coroa de giro apoiada sobre as travessas do topo do mastro (tangente)


def tube_t(p1, p2, r, r_in, t1=0.0, t2=0.0):
    """Barra tubular entre dois nós com as pontas recuadas (t1, t2): o membro termina na SUPERFÍCIE do banzo, sem penetrá-lo."""
    a, b = np.array(p1, float), np.array(p2, float)
    d = (b - a) / np.linalg.norm(b - a)
    return g.tube(a + d * t1, b - d * t2, r, r_in)


def mast():
    mem = []
    c = W / 2
    legs = [(-c, -c), (c, -c), (c, c), (-c, c)]
    for i, (x, y) in enumerate(legs):
        mem.append(L(f"Perna do mastro {i + 1}", g.tube((x, y, 0), (x, y, H_MAST), 60, 50)))
    for m in range(NMOD):
        z0, z1 = m * MOD, (m + 1) * MOD
        for i in range(4):
            (xa, ya), (xb, yb) = legs[i], legs[(i + 1) % 4]
            a, b = ((xa, ya, z0), (xb, yb, z1)) if (m + i) % 2 == 0 else ((xa, ya, z1), (xb, yb, z0))
            mem.append(L(f"Diagonal do mastro {m + 1}-{i + 1}", tube_t(a, b, 35, 28, 215, 215)))      # recuo: ponta fora da perna (r60)
        for i in range(4):
            (xa, ya), (xb, yb) = legs[i], legs[(i + 1) % 4]
            mem.append(L(f"Travessa do mastro {m + 1}-{i + 1}", tube_t((xa, ya, z1), (xb, yb, z1), 35, 28, 60, 60)))
    return mem


def truss_side(xs, zb, zt, half_w, tag_d, tag_t, r_d, r_di, trim_d, r_t, r_ti, trim_t):
    """Painéis de treliça triangular: diagonais em zigue-zague de cada lado e travessas inferiores, todas recuadas dos banzos."""
    out = []
    for i in range(len(xs) - 1):
        for sgn in (-1, 1):
            if i % 2 == 0:
                a, b = (xs[i], sgn * half_w, zb), (xs[i + 1], 0.0, zt)
            else:
                a, b = (xs[i], 0.0, zt), (xs[i + 1], sgn * half_w, zb)
            out.append(L(f"{tag_d} {i + 1}{'e' if sgn < 0 else 'd'}", tube_t(a, b, r_d, r_di, trim_d, trim_d)))
        out.append(L(f"{tag_t} {i + 1}", tube_t((xs[i], -half_w, zb), (xs[i], half_w, zb), r_t, r_ti, trim_t, trim_t)))
    return out


def build_guindaste() -> RawNode:
    kids = []
    kids.append(group("Fundacao", L("Bloco de fundacao", g.box(-1900, 1900, -1900, 1900, -900, 0))))
    kids.append(group("Mastro", *mast()))
    zb, zt = Z0 + 200, Z0 + 200 + JIB_H
    top_plat = ZP + 600
    kids.append(group("Plataforma giratoria", L("Coroa de giro", g.cut(g.cyl(1100, 400, at=(0, 0, ZP)), g.cyl(900, 400, at=(0, 0, ZP)))),
                      L("Plataforma superior", g.box(-1200, 1200, -900, 2200, ZP + 400, top_plat)),
                      L("Cabine do operador", g.box(300, 1500, 900, 2100, top_plat, top_plat + 1600)),
                      L("Torre de cabos (cat head)", g.tube((0, 0, top_plat), (0, 0, ZP + 6200), 150, 120))))
    # lança: seção triangular (2 banzos inferiores + 1 superior) ao longo de +X, a partir de x=250 até JIB_L-150 (a ponta fecha o resto)
    x_end = JIB_L - 150
    nb = 12
    xs = [250 + (x_end - 250) * i / nb for i in range(nb + 1)]
    jib = []
    for sgn, tag in ((-1, "inferior esq."), (1, "inferior dir.")):
        jib.append(L(f"Banzo {tag} da lanca", g.tube((250, sgn * JIB_W / 2, zb), (x_end, sgn * JIB_W / 2, zb), 80, 68)))
    jib.append(L("Banzo superior da lanca", g.tube((250, 0, zt), (x_end, 0, zt), 80, 68)))
    jib += truss_side(xs, zb, zt, JIB_W / 2, "Diagonal lateral da lanca", "Travessa da lanca", 38, 30, 215, 38, 30, 80)
    jib.append(L("Ponta da lanca", g.box(x_end, JIB_L + 250, -300, 300, zb - 100, zt + 100)))
    for sgn in (-1, 1):
        jib.append(L(f"Apoio da lanca {'esq.' if sgn < 0 else 'dir.'}", g.tube((700, sgn * JIB_W / 2, top_plat), (700, sgn * JIB_W / 2, zb - 80), 60, 50)))
    kids.append(group("Lanca", *jib))
    # contralança e contrapesos
    xc = [-CJ_L + (CJ_L - 250) * i / 6 for i in range(7)]
    cj = [L("Banzo da contralanca esq.", g.tube((-CJ_L, -JIB_W / 2, zb), (-250, -JIB_W / 2, zb), 70, 58)),
          L("Banzo da contralanca dir.", g.tube((-CJ_L, JIB_W / 2, zb), (-250, JIB_W / 2, zb), 70, 58)),
          L("Banzo superior da contralanca", g.tube((-CJ_L, 0, zt), (-250, 0, zt), 70, 58))]
    cj += truss_side(xc, zb, zt, JIB_W / 2, "Diagonal da contralanca", "Travessa da contralanca", 35, 28, 200, 35, 28, 70)
    for sgn in (-1, 1):
        cj.append(L(f"Apoio da contralanca {'esq.' if sgn < 0 else 'dir.'}", g.tube((-700, sgn * JIB_W / 2, top_plat), (-700, sgn * JIB_W / 2, zb - 70), 60, 50)))
    cj.append(L("Contrapeso 1", g.box(-CJ_L + 600, -CJ_L + 2000, -700, 700, zb - 1470, zb - 70)))
    cj.append(L("Contrapeso 2", g.box(-CJ_L + 2100, -CJ_L + 3500, -700, 700, zb - 1470, zb - 70)))
    kids.append(group("Contralanca", *cj))
    # tirantes: da cabeça da torre de cabos até a lança (z da ponta acima do banzo superior, sem penetrá-lo)
    z_top = ZP + 6200
    kids.append(group("Tirantes", L("Tirante da lanca", g.tube((200, 0, z_top - 30), (JIB_L * 0.7, 0, zt + 125), 40)),
                      L("Tirante da contralanca", g.tube((-200, 0, z_top - 30), (-CJ_L * 0.8, 0, zt + 125), 40))))
    x_car = 12000.0
    kids.append(group("Carrinho", L("Carrinho da lanca", g.box(x_car - 450, x_car + 450, -700, 700, zb - 400, zb - 80)),
                      L("Cabo do gancho", g.cyl(25, 9000, at=(x_car, 0, zb - 9400))),
                      L("Bloco do gancho", g.box(x_car - 250, x_car + 250, -200, 200, zb - 10200, zb - 9400)),
                      L("Gancho", g.torus(260, 70, at=(x_car, 0, zb - 10200 - 330), axis=g.Y))))
    return RawNode("Guindaste torre treliçado".replace("ç", "c").replace("í", "i"), children=kids)


def write(path: Path) -> Path:
    return write_step(build_guindaste, path)


if __name__ == "__main__":
    print("Gerado:", write(ROOT / "samples" / "guindaste_torre.step"))
