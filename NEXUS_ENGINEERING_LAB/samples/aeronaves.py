"""Aviões (V2.8): Cessna 172S, Supermarine Spitfire (Merlin) e Airbus A320-200 — modelos de REFERÊNCIA por medidas públicas.

HONESTIDADE: geometria paramétrica simplificada (fuselagem em loft, asas por perfil NACA de 4 dígitos, superfícies móveis separadas), NÃO réplica nem projeto
aerodinamicamente validado; sem CFD, sem estrutura interna, sem motor real (hélice/fan e núcleo ilustrativos).
Dados com fonte (consultados 2026-11): 
  Cessna 172S (AOPA): envergadura 36 ft 1 in, comprimento 27 ft 2 in, altura 8 ft 11 in, área 174 ft², Lycoming IO-360-L2A 180 hp, hélice bipá McCauley passo fixo.
  Spitfire (Wikipedia, valores de uma variante Merlin 45 usados como referência): comprimento 9,12 m, envergadura 11,23 m, altura 3,48 m, área 22,49 m²; hélice tripá 9 ft 8 in.
  A320-200 (Wikipedia/aerocorner): comprimento 37,57 m, envergadura 35,80 m, altura da deriva 11,76 m, diâmetro da fuselagem 3,95 m, enflechamento 25°, 2 turbofans.
ILUSTRATIVO/estimado: cordas (escolhidas para dar a área citada), diedro, perfis, posição de motores/trens de pouso, diâmetro de hélice (Cessna), diâmetro do fan (A320).
Eixos: x do nariz (0) para a cauda (+), y para a asa direita, z para cima (solo z=0). Animações prescritas (hélice/fan giram; ailerons, flaps, profundor e leme oscilam).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform  # noqa: E402
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Trsf  # noqa: E402

from samples._common import L, RawNode, g, group, write_step  # noqa: E402

X, Y, Z = g.X, g.Y, g.Z
FAR = 60000.0


def _orient(shape):
    """Garante sólido com volume positivo (alguns lofts saem invertidos e fazem o corte booleano agir como interseção)."""
    from OCP.GProp import GProp_GProps
    from OCP.BRepGProp import BRepGProp
    pr = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, pr)
    return shape.Reversed() if pr.Mass() < 0 else shape


def mirror_y(shape):
    t = gp_Trsf()
    t.SetMirror(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 1, 0)))
    return BRepBuilderAPI_Transform(shape, t, True).Shape()


def wing_loft(stations, camber=0.02, pos=0.4, n=14):
    """Asa meia (y≥0): stations = [(y, corda, x_bordo_ataque, z_bordo_ataque, espessura_relativa)]."""
    secs = []
    for y, c, xl, zl, t in stations:
        pts = g.airfoil(c, t, camber, pos, n)
        secs.append([(xl + px, y, zl + pz) for px, pz in pts])
    return g.loft(secs)


def lower_z(c, t, camber, pos, frac, n=14):
    pts = g.airfoil(c, t, camber, pos, n)
    low = pts[n + 1:]
    return min(low, key=lambda p: abs(p[0] - frac * c))[1]


def upper_max(c, t, camber, pos, n=14):
    return max(p[1] for p in g.airfoil(c, t, camber, pos, n))


def lower_min(c, t, camber, pos, n=14):
    return min(p[1] for p in g.airfoil(c, t, camber, pos, n))


def split_aft(wing, y0, y1, xh0, xh1, zlo=-5000.0, zhi=9000.0):
    """Separa a superfície móvel (região atrás da linha de dobradiça entre (xh0,y0) e (xh1,y1)). Devolve (parte fixa, superfície)."""
    region = g.extrude([(xh0, y0), (xh1, y1), (FAR, y1), (FAR, y0)], "xy", zlo, zhi - zlo)
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    surf = BRepAlgoAPI_Common(wing, region).Shape()
    return g.cut(wing, region), surf


def split_aft_xz(fin, z0, z1, xh0, xh1):
    """Idem para a deriva (loft em z): região atrás da dobradiça no plano xz."""
    region = g.extrude([(xh0, z0), (xh1, z1), (FAR, z1), (FAR, z0)], "xz", -2000.0, 4000.0)
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    return g.cut(fin, region), BRepAlgoAPI_Common(fin, region).Shape()


def fin_loft(stations, n=12):
    """Deriva: stations = [(z, corda, x_le, espessura)] com perfil simétrico; espessura no eixo y."""
    secs = []
    for z, c, xl, t in stations:
        pts = g.airfoil(c, t, 0.0, 0.4, n)
        secs.append([(xl + px, pz, z) for px, pz in pts])
    return g.loft(secs)


def blade_loft(r0, r1, chord0, chord1, x0, z0, thick=0.12, pitch0=28.0, pitch1=10.0, n=10, count=5):
    secs = []
    for i in range(count):
        f = i / (count - 1)
        r = r0 + (r1 - r0) * f
        c = chord0 + (chord1 - chord0) * f
        th = math.radians(pitch0 + (pitch1 - pitch0) * f)
        sec = []
        for px, pz in g.airfoil(c, thick, 0.04, 0.4, n):
            a, b = pz, px - 0.3 * c
            sec.append((x0 + a * math.cos(th) - b * math.sin(th), a * math.sin(th) + b * math.cos(th), z0 + r))
        secs.append(sec)
    return g.loft(secs)


def hinge_axis(p0, p1):
    d = np.array(p1, float) - np.array(p0, float)
    return d / np.linalg.norm(d)


def wheel(r, w, x, y, z):
    return g.cyl(r, w, at=(x, y - w / 2, z), axis=Y)


MECH: dict = {}


def _register(key, spin, surfaces):
    """spin: [(nomes, (y, z), razão)]; surfaces: [(nomes, ponto, eixo, amp_graus, fase_graus)]."""
    MECH[key] = {"spin": spin, "surf": surfaces}


# ------------------------------------------------------------------ Cessna 172S
def build_cessna172() -> RawNode:
    FUS_TOP = 2050.0
    kids = []
    cowl = g.loft_x([(150, 760, 640, 0, 1050, 2.4), (1100, 1050, 1150, 0, 1230, 2.6)])
    cabin = g.loft_x([(1100, 1050, 1150, 0, 1230, 2.6), (2400, 1120, 1500, 0, 1300, 2.6), (3600, 950, 1350, 0, 1330, 2.6)])
    tail = g.loft_x([(3600, 950, 1350, 0, 1330, 2.6), (6000, 420, 700, 0, 1330, 2.6), (7900, 80, 160, 0, 1400, 2.4)])
    kids.append(group("Fuselagem", L("Capo do motor", cowl), L("Cabine", cabin), L("Cone de cauda", tail)))
    # asa alta: b = 10998 mm, área 16,17 m²  →  corda média 1470 (raiz 1600, ponta 1340)
    cr, ct, half = 1600.0, 1340.0, 5499.0
    chord = lambda y: cr + (ct - cr) * y / half  # noqa: E731
    zroot = FUS_TOP - lower_min(cr, 0.12, 0.02, 0.4) + 2.0
    zle = lambda y: zroot + y * math.tan(math.radians(1.5))  # noqa: E731
    xle = 1500.0
    ys = [0.0, 1500.0, 3300.0, 5499.0]
    wing = wing_loft([(y, chord(y), xle, zle(y), 0.12) for y in ys], 0.02, 0.4)
    sp = {}
    surf = []
    fl_main, flap = split_aft(wing, 800, 3200, xle + 0.7 * chord(800), xle + 0.7 * chord(3200))
    ai_main, ail = split_aft(fl_main, 3300, 5400, xle + 0.7 * chord(3300), xle + 0.7 * chord(5400))
    wings = [L("Asa direita", ai_main), L("Asa esquerda", mirror_y(ai_main)), L("Flape direito", flap), L("Flape esquerdo", mirror_y(flap)),
             L("Aileron direito", ail), L("Aileron esquerdo", mirror_y(ail))]
    kids.append(group("Asa", *wings))
    # montantes (de cada lado): da lateral da cabine à face inferior da asa em y=3000
    yst = 3000.0
    xa = xle + 0.40 * chord(yst)
    zl = zle(yst) + lower_z(chord(yst), 0.12, 0.02, 0.4, 0.40) - 40.0
    st = g.tube((2250.0, 495.0, 800.0), (xa, yst, zl), 22)
    kids.append(group("Montantes da asa", L("Montante direito", st), L("Montante esquerdo", mirror_y(st))))
    # empenagem
    cr_s, ct_s, hs, xs = 1200.0, 800.0, 1725.0, 7000.0
    cs = lambda y: cr_s + (ct_s - cr_s) * y / hs  # noqa: E731
    zs = 1625.0
    stab = wing_loft([(0.0, cs(0), xs, zs, 0.09), (hs, cs(hs), xs, zs, 0.09)], 0.0, 0.4)
    xh = xs + 0.62 * ct_s
    st_main, elev = split_aft(stab, 0.0, hs, xh, xh)
    kids.append(group("Empenagem horizontal", L("Estabilizador direito", st_main), L("Estabilizador esquerdo", mirror_y(st_main)),
                      L("Profundor direito", elev), L("Profundor esquerdo", mirror_y(elev))))
    ztop = zs + upper_max(cr_s, 0.09, 0.0, 0.4)
    fin = fin_loft([(ztop, 1200.0, 6900.0, 0.09), (2718.0, 650.0, 7600.0, 0.09)])
    xhf = 6900.0 + 0.70 * 1200.0
    fin_main, rudder = split_aft_xz(fin, ztop - 10, 2800.0, 7740.0, 7600.0 + 0.7 * 650.0)
    kids.append(group("Empenagem vertical", L("Deriva", fin_main), L("Leme", rudder)))
    # trem de pouso triciclo fixo
    gear = [L("Perna do trem principal direita", g.tube((2300.0, 330.0, 556.0), (2300.0, 1160.0, 602.0), 24)), L("Perna do trem principal esquerda", g.tube((2300.0, -330.0, 556.0), (2300.0, -1160.0, 602.0), 24)),
            L("Pneu principal direito", wheel(300, 170, 2300.0, 1250.0, 300)), L("Pneu principal esquerdo", wheel(300, 170, 2300.0, -1250.0, 300)),
            L("Perna do trem do nariz", g.tube((1000.0, 0.0, 660.0), (1000.0, 0.0, 521.0), 24)), L("Pneu do nariz", wheel(260, 130, 1000.0, 0.0, 260))]
    kids.append(group("Trem de pouso", *gear))
    # hélice bipá fixa (ø ≈ 1,9 m ILUSTRATIVO) e carenagem
    zc = 1050.0
    b1 = blade_loft(135.0, 950.0, 180.0, 110.0, 100.0, zc)
    kids.append(group("Helice", L("Carenagem da helice (spinner)", g.cone(0.0, 140.0, 150.0, at=(0, 0, zc), axis=X)), L("Pa da helice 1", b1), L("Pa da helice 2", g.rot(b1, X, math.pi, (0, 0, zc)))))
    # --- mecanismo
    hinge = lambda y0, y1, h: (np.array([xle + h * chord(y0), y0, zle(y0)]), hinge_axis((xle + h * chord(y0), y0, zle(y0)), (xle + h * chord(y1), y1, zle(y1))))  # noqa: E731
    p, a = hinge(3300, 5400, 0.7)
    sa = [(["Aileron direito"], p, a, 18.0, 0.0), (["Aileron esquerdo"], p * np.array([1, -1, 1]), a * np.array([1, -1, 1]), 18.0, 0.0)]
    p, a = hinge(800, 3200, 0.7)
    sa += [(["Flape direito"], p, a, 20.0, 0.0), (["Flape esquerdo"], p * np.array([1, -1, 1]), a * np.array([1, -1, 1]), 20.0, 180.0)]
    sa += [(["Profundor direito", "Profundor esquerdo"], np.array([xh, 0.0, zs]), np.array([0.0, 1.0, 0.0]), 15.0, 0.0),
           (["Leme"], np.array([7740.0, 0.0, 2200.0]), np.array([0.0, 0.0, 1.0]), 20.0, 0.0)]
    _register("cessna", [(["Pa da helice 1", "Pa da helice 2", "Carenagem da helice (spinner)"], (0.0, zc), 8.0)], sa)
    return RawNode("Cessna 172S (modelo de referencia)", children=kids)


def write_cessna(path):
    return write_step(build_cessna172, path)


# ------------------------------------------------------------------ Spitfire
def build_spitfire() -> RawNode:
    half, c0 = 5615.0, 2550.0
    eta = lambda y: y / half  # noqa: E731
    chord = lambda y: c0 * math.sqrt(max(1 - eta(y) ** 2, 1e-4))  # noqa: E731
    xq = 3300.0
    xle = lambda y: xq - 0.25 * chord(y)  # noqa: E731
    zle = lambda y: 1250.0 + y * math.tan(math.radians(6.0))  # noqa: E731
    thick = lambda y: 0.13 - 0.04 * eta(y)  # noqa: E731
    ys = [0.0, 0.15 * half, 0.35 * half, 0.55 * half, 0.75 * half, 0.9 * half, 0.995 * half]
    wing = wing_loft([(y, chord(y), xle(y), zle(y), thick(y)) for y in ys], 0.02, 0.4)
    fus = g.loft_x([(330, 560, 700, 0, 1500, 2.2), (1500, 850, 1000, 0, 1520, 2.2), (3500, 800, 1150, 0, 1600, 2.2), (6500, 450, 700, 0, 1560, 2.2), (8900, 100, 200, 0, 1620, 2.2)])
    hs, cs0, cs1, xs, zs = 1600.0, 900.0, 600.0, 8000.0, 1600.0
    csf = lambda y: cs0 + (cs1 - cs0) * y / hs  # noqa: E731
    stab = wing_loft([(0.0, cs0, xs, zs, 0.09), (hs, cs1, xs + 150, zs, 0.09)], 0.0, 0.4)
    fin = fin_loft([(1500.0, 1100.0, 7700.0, 0.09), (3480.0, 520.0, 8450.0, 0.09)])
    stab = g.cut(stab, fin)
    fus = g.cut(fus, wing, mirror_y(wing), stab, mirror_y(stab), fin)
    h_ai, h_fl = 0.75, 0.72
    hx = lambda y, h: xle(y) + h * chord(y)  # noqa: E731
    w1, flap = split_aft(wing, 700, 3100, hx(700, h_fl), hx(3100, h_fl))
    w2, ail = split_aft(w1, 3300, 5200, hx(3300, h_ai), hx(5200, h_ai))
    kids = [group("Fuselagem", L("Fuselagem", fus))]
    kids.append(group("Asa", L("Asa direita", w2), L("Asa esquerda", mirror_y(w2)), L("Flape direito", flap), L("Flape esquerdo", mirror_y(flap)),
                      L("Aileron direito", ail), L("Aileron esquerdo", mirror_y(ail))))
    xh = xs + 0.60 * 750.0
    st_main, elev = split_aft(stab, 0.0, hs, xh, xh + 90)
    kids.append(group("Empenagem horizontal", L("Estabilizador direito", st_main), L("Estabilizador esquerdo", mirror_y(st_main)), L("Profundor direito", elev), L("Profundor esquerdo", mirror_y(elev))))
    fin_main, rudder = split_aft_xz(fin, 1480.0, 3500.0, 8280.0, 8700.0)
    kids.append(group("Empenagem vertical", L("Deriva", fin_main), L("Leme", rudder)))
    # trem: pernas sob a asa em y=1900; roda de cauda
    yl = 1900.0
    zl = zle(yl) + lower_z(chord(yl), thick(yl), 0.02, 0.4, 0.35) - 30.0
    xl = xle(yl) + 0.35 * chord(yl)
    leg = g.tube((xl, yl, zl), (xl, yl + 50.0, 680.0), 30)
    gear = [L("Perna do trem principal direita", leg), L("Perna do trem principal esquerda", mirror_y(leg)), L("Pneu principal direito", wheel(330, 120, xl, yl + 50.0, 330)),
            L("Pneu principal esquerdo", wheel(330, 120, xl, -(yl + 50.0), 330)), L("Perna da roda de cauda", g.cut(g.tube((8500.0, 0.0, 1470.0), (8500.0, 0.0, 301.0), 25), fus)), L("Roda de cauda", wheel(150, 70, 8500.0, 0.0, 150))]
    kids.append(group("Trem de pouso", *gear))
    zc = 1500.0
    b1 = blade_loft(175.0, 1473.0, 230.0, 150.0, 150.0, zc, pitch0=30.0, pitch1=12.0)
    kids.append(group("Helice", L("Carenagem da helice (spinner)", g.cone(0.0, 170.0, 330.0, at=(0, 0, zc), axis=X)), L("Pa da helice 1", b1),
                      L("Pa da helice 2", g.rot(b1, X, 2 * math.pi / 3, (0, 0, zc))), L("Pa da helice 3", g.rot(b1, X, 4 * math.pi / 3, (0, 0, zc)))))
    hinge = lambda y0, y1, h: (np.array([hx(y0, h), y0, zle(y0)]), hinge_axis((hx(y0, h), y0, zle(y0)), (hx(y1, h), y1, zle(y1))))  # noqa: E731
    p, a = hinge(3300, 5200, h_ai)
    mir = np.array([1, -1, 1])
    sa = [(["Aileron direito"], p, a, 18.0, 0.0), (["Aileron esquerdo"], p * mir, a * mir, 18.0, 0.0)]
    p, a = hinge(700, 3100, h_fl)
    sa += [(["Flape direito"], p, a, 20.0, 0.0), (["Flape esquerdo"], p * mir, a * mir, 20.0, 180.0)]
    sa += [(["Profundor direito", "Profundor esquerdo"], np.array([xh, 0.0, zs]), np.array([0.0, 1.0, 0.0]), 15.0, 0.0), (["Leme"], np.array([8280.0, 0.0, 2200.0]), np.array([0.0, 0.0, 1.0]), 20.0, 0.0)]
    _register("spitfire", [(["Pa da helice 1", "Pa da helice 2", "Pa da helice 3", "Carenagem da helice (spinner)"], (0.0, zc), 8.0)], sa)
    return RawNode("Supermarine Spitfire (modelo de referencia)", children=kids)


# ------------------------------------------------------------------ Airbus A320-200
def build_a320() -> RawNode:
    half, cr, ct = 17900.0, 5600.0, 1300.0
    chord = lambda y: cr + (ct - cr) * y / half  # noqa: E731
    xq = lambda y: 13500.0 + y * math.tan(math.radians(25.0))  # quarto de corda a 25°
    xle = lambda y: xq(y) - 0.25 * chord(y)  # noqa: E731
    zle = lambda y: 2900.0 + y * math.tan(math.radians(5.0))  # noqa: E731
    thick = lambda y: 0.14 - 0.04 * y / half  # noqa: E731
    ys = [0.0, 2000.0, 6000.0, 12000.0, half]
    wing = wing_loft([(y, chord(y), xle(y), zle(y), thick(y)) for y in ys], 0.015, 0.4)
    zc = 3925.0
    fus = g.loft_x([(0, 300, 300, 0, 3300, 2.0), (900, 2200, 2400, 0, 3600, 2.0), (3000, 3800, 3900, 0, 3900, 2.0), (5000, 3950, 3950, 0, zc, 2.0), (27500, 3950, 3950, 0, zc, 2.0),
                    (34000, 1700, 1900, 0, 4500, 2.0), (37570, 300, 400, 0, 4900, 2.0)], False)   # loft reto: o suave gerava sólido inválido para booleanos
    fus = _orient(fus)
    hs = 6225.0
    cst = lambda y: 3600.0 + (1300.0 - 3600.0) * y / hs  # noqa: E731
    xst = lambda y: 33000.0 + y * math.tan(math.radians(29.0))  # noqa: E731
    stab = wing_loft([(0.0, cst(0), xst(0), 4650.0, 0.10), (hs, cst(hs), xst(hs), 4650.0, 0.10)], 0.0, 0.4)
    fin = fin_loft([(4300.0, 6200.0, 29800.0, 0.10), (11760.0, 2000.0, 35000.0, 0.10)])
    stab = g.cut(stab, fin)
    fus = g.cut(fus, wing, mirror_y(wing), stab, mirror_y(stab), fin)
    hx = lambda y, h: xle(y) + h * chord(y)  # noqa: E731
    w = wing
    surfs = {}
    for nm, y0, y1, h in (("Aileron", 13500.0, 17400.0, 0.78), ("Flape interno", 2300.0, 5300.0, 0.72), ("Flape externo", 6200.0, 12000.0, 0.72)):
        w, s = split_aft(w, y0, y1, hx(y0, h), hx(y1, h))
        surfs[nm] = (s, y0, y1, h)
    kids = [group("Fuselagem", L("Fuselagem", fus))]
    wl = [L("Asa direita", w), L("Asa esquerda", mirror_y(w))]
    for nm, (s, *_r) in surfs.items():
        wl += [L(f"{nm} direito", s), L(f"{nm} esquerdo", mirror_y(s))]
    kids.append(group("Asa", *wl))
    xh = xst(0) + 0.70 * 1300.0
    st_main, elev = split_aft(stab, 0.0, hs, xst(hs) + 0.70 * 1300.0, xst(hs) + 0.70 * 1300.0)
    kids.append(group("Empenagem horizontal", L("Estabilizador direito", st_main), L("Estabilizador esquerdo", mirror_y(st_main)), L("Profundor direito", elev), L("Profundor esquerdo", mirror_y(elev))))
    xrud = lambda z: 29800.0 + (z - 4300.0) * (35000.0 - 29800.0) / (11760.0 - 4300.0) + 0.70 * (6200.0 + (2000.0 - 6200.0) * (z - 4300.0) / (11760.0 - 4300.0))  # noqa: E731
    fin_main, rudder = split_aft_xz(fin, 4290.0, 11800.0, xrud(4290.0), xrud(11800.0))
    kids.append(group("Empenagem vertical", L("Deriva", fin_main), L("Leme", rudder)))
    # motores (y=±5750)
    ye = 5750.0
    xl, cl = xle(ye), chord(ye)
    zlo = zle(ye) + lower_min(cl, thick(ye), 0.015, 0.4)
    RN = 1070.0
    zcen = zlo - 500.0 - RN
    x0 = xl - 2500.0
    outer = [(0, 960), (250, 1040), (1400, RN), (2700, 900), (3400, 430)]
    inner = [(0, 900), (250, 930), (500, 900), (2000, 880), (2800, 780), (3400, 380)]
    nac = g.revolve([(a, r) for a, r in outer] + [(a, r) for a, r in inner[::-1]], "x")
    nac = g.move(nac, (x0, ye, zcen))
    pyl = g.cut(g.box(xl + 50.0, xl + 650.0, ye - 150.0, ye + 150.0, zcen + RN, zlo + 300.0), wing)   # topo aparado pela asa: encosta sem penetrar
    hub = g.cyl(300, 200, at=(450, 0, 0), axis=X)
    blades = [g.rot(g.rot(g.box(460, 640, -9, 9, 290, 870), (0, 0, 1), math.radians(30), (550, 0, 290)), X, 2 * math.pi * k / 20) for k in range(20)]
    fan = g.move(g.clean(g.fuse(hub, *blades)), (x0, ye, zcen))
    core = g.move(g.cyl(420, 2300, at=(800, 0, 0), axis=X), (x0, ye, zcen))
    eng = [L("Nacele direita", nac), L("Pilone direito", pyl), L("Fan direito", fan), L("Nucleo do motor direito", core)]
    mir = np.array([1, -1, 1])
    eng += [L("Nacele esquerda", mirror_y(nac)), L("Pilone esquerdo", mirror_y(pyl)), L("Fan esquerdo", mirror_y(fan)), L("Nucleo do motor esquerdo", mirror_y(core))]
    kids.append(group("Motores", *eng))
    # trem de pouso
    yw = 3800.0
    zl = zle(yw) + lower_z(chord(yw), thick(yw), 0.015, 0.4, 0.40) - 40.0
    xw = xle(yw) + 0.40 * chord(yw)
    zh = 585.0
    g_main = []
    for sgn in (1, -1):
        tag = "direito" if sgn > 0 else "esquerdo"
        g_main += [L(f"Perna do trem principal {tag}", g.tube((xw, sgn * yw, zl), (xw, sgn * yw, zh + 60.0), 90)), L(f"Eixo do truque {tag}", g.cyl(60, 200, at=(xw, sgn * yw - 100, zh), axis=Y)),
                   L(f"Pneu principal interno {tag}", wheel(585, 380, xw, sgn * (yw - 290), zh)), L(f"Pneu principal externo {tag}", wheel(585, 380, xw, sgn * (yw + 290), zh))]
    g_main += [L("Perna do trem do nariz", g.tube((4500.0, 0.0, zc - 1975.0), (4500.0, 0.0, 450.0), 55)), L("Pneu do nariz direito", wheel(380, 260, 4500.0, 190.0, 380)), L("Pneu do nariz esquerdo", wheel(380, 260, 4500.0, -190.0, 380))]
    kids.append(group("Trem de pouso", *g_main))
    hinge = lambda y0, y1, h: (np.array([hx(y0, h), y0, zle(y0)]), hinge_axis((hx(y0, h), y0, zle(y0)), (hx(y1, h), y1, zle(y1))))  # noqa: E731
    sa = []
    for nm, (s, y0, y1, h) in surfs.items():
        p, a = hinge(y0, y1, h)
        amp = 20.0 if nm == "Aileron" else 22.0
        sa += [([f"{nm} direito"], p, a, amp, 0.0), ([f"{nm} esquerdo"], p * mir, a * mir, amp, 0.0 if nm == "Aileron" else 180.0)]
    sa += [(["Profundor direito", "Profundor esquerdo"], np.array([xst(hs) + 0.70 * 1300.0, 0.0, 4650.0]), np.array([0.0, 1.0, 0.0]), 12.0, 0.0),
           (["Leme"], np.array([xrud(8000.0), 0.0, 8000.0]), np.array([0.0, 0.0, 1.0]), 15.0, 0.0)]
    _register("a320", [(["Fan direito"], (ye, zcen), 12.0), (["Fan esquerdo"], (-ye, zcen), 12.0)], sa)
    return RawNode("Airbus A320-200 (modelo de referencia)", children=kids)



def write_spitfire(path):
    return write_step(build_spitfire, path)


def write_a320(path):
    return write_step(build_a320, path)


BUILDERS = {"cessna": build_cessna172, "spitfire": build_spitfire, "a320": build_a320}
