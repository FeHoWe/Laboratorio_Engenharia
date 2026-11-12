"""Carro de Fórmula 1 de 2026 (modelo paramétrico SIMPLIFICADO baseado no regulamento) — V2.3.

HONESTIDADE: as equipes não publicam seus CAD; este NÃO é o carro de nenhuma equipe nem um modelo de produção. É um modelo de referência
construído em sólidos B-rep reais com as dimensões do regulamento técnico de 2026 verificadas em fontes públicas:
  entre-eixos 3400 mm · largura máx. 1900 mm · massa mínima 768 kg (sem combustível, com piloto) · rodas de 18" · pneus 25 mm (diant.)
  e 30 mm (tras.) mais estreitos que em 2025 · V6 turbo híbrido 1,6 L (alesagem 80 mm × curso 53 mm) · MGU-K de até 350 kW · sem MGU-H ·
  aerodinâmica ativa (modo curva / modo reta) · assoalho sem túneis Venturi.
Valores NÃO verificados e aproximados: largura dos pneus (305/405 mm de 2025 menos 25/30 mm), diâmetro externo do pneu (720 mm),
dimensões das asas, geometria de suspensão (pontos de fixação plausíveis, NÃO de um carro real), posições internas, comprimento de biela.
Carenagens são cascas ocas (loft) de espessura constante; a massa do conjunto é PARCIAL (sem compósitos: o banco não tem fibra de carbono).
Elementos internos (suspensão, caixa de câmbio, radiadores) encostam nas cascas em alguns pontos de fixação: não é um modelo livre de colisões.

Eixos: x lateral (direita +), y longitudinal (eixo dianteiro em y=0, traseiro em y=3400; a frente do carro aponta para -y), z para cima (solo z=0).
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
from samples.geo import X, Y, Z  # noqa: E402

WB = 3400.0
MAX_WIDTH = 1900.0
R_TYRE = 360.0                       # Ø externo ≈ 720 mm (aproximado)
R_RIM = 228.6                        # roda de 18" (457,2 mm)
W_TYRE_F, W_TYRE_R = 280.0, 375.0    # largura dos pneus (2025: 305/405 − 25/30)
XF = MAX_WIDTH / 2 - W_TYRE_F / 2    # centro do pneu dianteiro em x
XR = MAX_WIDTH / 2 - W_TYRE_R / 2
AERO_FRONT_FLAP = 16.0               # abertura (°) dos flaps ativos dianteiros do modo curva para o modo reta (ILUSTRATIVA)
AERO_REAR_FLAP = 38.0                # idem, elemento superior da asa traseira (ILUSTRATIVA)
FRONT_FLAP_HINGE = (-640.0, 205.0)   # (y, z) da articulação do flap móvel da asa dianteira
REAR_FLAP_HINGE = (4090.0, 905.0)    # (y, z) da articulação do elemento superior da asa traseira
AXLE_Z = R_TYRE
SHELL = 14.0                         # espessura das cascas ocas (mm)


def at(x=0.0, y=0.0, z=0.0):
    return translation_matrix([x, y, z])


def both(shape):
    """(direita, esquerda): a esquerda é o espelho em x=0."""
    return shape, g.mirror_x(shape)


def hollow(sections, t=SHELL, ext=6.0):
    """Casca oca aberta nas pontas: loft externo menos loft interno (seções reduzidas de 2t e prolongadas ``ext`` nas pontas)."""
    outer = g.loft_y(sections)
    inner = [(y, max(w - 2 * t, 8.0), max(h - 2 * t, 8.0), xc, zc, n) for y, w, h, xc, zc, n in sections]
    a, b = inner[0], inner[-1]
    inner = [(a[0] - ext,) + a[1:]] + inner + [(b[0] + ext,) + b[1:]]
    return g.cut(outer, g.loft_y(inner))


# ------------------------------------------------------------------ pontos duros (hardpoints) de cada canto — usados também pelo mecanismo
SIDES = (("direita", 1), ("esquerda", -1))
RACK_Y_OFFSET = 140.0
RACK_HALF = 190.0


def axle_geom(front: bool):
    return (0.0 if front else WB), (XF if front else XR), (W_TYRE_F if front else W_TYRE_R)


def corner_hp(front: bool, sign: int = 1) -> dict:
    """Pontos (referencial do CORPO, carro em repouso) de um canto. ``sign``=+1 direita, −1 esquerda (espelhado em x)."""
    y, xc, wt = axle_geom(front)
    s = 1.0 if front else -1.0                                # +1: pontos de direção atrás do eixo (dianteira); −1: à frente (traseira)

    def rel(lx, ly, lz):                                      # coordenadas locais do eixo da roda (lado direito, x para fora) → corpo
        return np.array([sign * (xc + lx), y + ly, AXLE_Z + lz])

    hp = {"front": front, "sign": sign, "y": y, "xc": xc, "wt": wt,
          "C": rel(0, 0, 0), "lo_u": rel(-92, 0, -210), "up_u": rel(-92, 0, 60), "tr_u": rel(-92, 120 * s, -90), "H0": rel(-122, 0, 0),
          "rod_u": rel(-130, 0, -155) if front else rel(-130, 0, 30),
          "lo_a": [np.array([sign * 200.0, y - 260.0, 150.0]), np.array([sign * 200.0, y + 300.0, 160.0])],
          "up_a": [np.array([sign * 190.0, y - 200.0, 340.0]), np.array([sign * 190.0, y + 280.0, 355.0])],
          "tr_a": np.array([sign * 190.0, y + RACK_Y_OFFSET * s, 270.0])}
    if front:
        pr = np.array([sign * 120.0, y + 60.0, 430.0])
        hp.update(pr=pr, A0=pr + [0, 0, -35.0], D0=pr + [sign * 40.0, 0, 15.0], M=np.array([sign * 70.0, y - 120.0, 500.0]))
    else:
        pr = np.array([sign * 200.0, y - 70.0, 250.0])
        hp.update(pr=pr, A0=pr + [0, 0, 35.0], D0=pr + [sign * 45.0, 0, -10.0], M=np.array([sign * 120.0, y + 130.0, 170.0]))
    hp["d_bj"] = float(np.linalg.norm(hp["up_u"] - hp["lo_u"]))
    hp["L_tr"] = float(np.linalg.norm(hp["tr_u"] - hp["tr_a"]))
    hp["L_rod"] = float(np.linalg.norm(hp["rod_u"] - hp["A0"]))
    hp["P_d"] = np.array([sign * 150.0, WB, AXLE_Z])          # ponta interna do semi-eixo (só traseira)
    return hp


# ------------------------------------------------------------------ rodas e freios (geometria no referencial LOCAL do eixo da roda, lado direito)
def tyre(width):
    w = width / 2
    prof = [(-w + 12, R_RIM), (-w + 4, R_RIM + 35), (-w, R_RIM + 80), (-w + 3, R_TYRE - 40), (-w + 18, R_TYRE - 8), (-w + 50, R_TYRE),
            (w - 50, R_TYRE), (w - 18, R_TYRE - 8), (w - 3, R_TYRE - 40), (w, R_RIM + 80), (w - 4, R_RIM + 35), (w - 12, R_RIM)]
    return g.revolve(prof, "x")


def rim(width, outer_sign=1):
    """Roda de 18": aro + alma com 8 furos de alívio e 5 furos de aerodinâmica; a alma fica no lado externo (sinal ``outer_sign``)."""
    ww = width - 40
    prof = [(-ww / 2, R_RIM - 5), (-ww / 2, R_RIM), (ww / 2, R_RIM), (ww / 2, R_RIM - 5), (ww / 2 - 26, R_RIM - 5), (ww / 2 - 26, 40),
            (ww / 2 - 40, 40), (ww / 2 - 40, R_RIM - 5)]
    body = g.revolve(prof, "x")
    holes = [g.cyl(32, 40, at=(ww / 2 - 44, 130 * math.cos(2 * math.pi * i / 8), 130 * math.sin(2 * math.pi * i / 8)), axis=X) for i in range(8)]
    holes += [g.cyl(14, 40, at=(ww / 2 - 44, 185 * math.cos(2 * math.pi * (i + 0.5) / 8), 185 * math.sin(2 * math.pi * (i + 0.5) / 8)), axis=X) for i in range(8)]
    body = g.clean(g.cut(body, *holes))
    return body if outer_sign > 0 else g.mirror_x(body)


def web_planes(width):
    ww = width - 40
    return ww / 2 - 40, ww / 2 - 26                          # (face interna, face externa) da alma da roda, relativo ao centro


def brake_disc_local():
    d = g.cut(g.cyl(139, 28, at=(-58, 0, 0), axis=X), g.cyl(66, 28, at=(-58, 0, 0), axis=X))
    holes = [g.cyl(5, 28, at=(-58, 108 * math.cos(2 * math.pi * i / 36), 108 * math.sin(2 * math.pi * i / 36)), axis=X) for i in range(36)]
    holes += [g.cyl(4, 28, at=(-58, 126 * math.cos(2 * math.pi * (i + 0.5) / 36), 126 * math.sin(2 * math.pi * (i + 0.5) / 36)), axis=X) for i in range(36)]
    return g.clean(g.cut(d, *holes))


def caliper_local():
    """Pinça em C que abraça o disco (x −58…−30) na posição das 12 h, com suporte até a manga."""
    body = g.fuse(g.box(-68, -20, -55, 55, 95, 175), g.box(-72, -60, -50, 50, 60, 180))
    return g.clean(g.cut(body, g.box(-60, -28, -60, 60, 90, 168)))


def upright_local(front: bool):
    """Manga de eixo: placa x −112…−72 com furo do cubo, esferas das rótulas, braço de direção e ressalto do push/pull-rod."""
    s = 1.0 if front else -1.0
    plate = g.box(-112, -72, -55, 55, -250, 190)
    plate = g.fuse(plate, g.sphere(20, at=(-92, 0, -210)), g.sphere(20, at=(-92, 0, 60)))
    arm = g.box(-112, -72, 40 * s, 135 * s, -105, -75) if front else g.box(-112, -72, -135, -40, -105, -75)
    plate = g.fuse(plate, arm, g.sphere(15, at=(-92, 120 * s, -90)))
    zr = -155 if front else 30
    plate = g.fuse(plate, g.cyl(16, 18, at=(-130, 0, zr), axis=X))
    return g.clean(g.cut(plate, g.cyl(36, 60, at=(-120, 0, 0), axis=X)))


def hub_local(width):
    wi, wo = web_planes(width)
    shaft = g.cyl(34, wo + 122, at=(-122, 0, 0), axis=X)
    return g.clean(g.fuse(shaft, g.cyl(62, 14, at=(-72, 0, 0), axis=X), g.cyl(60, 14, at=(wi - 14, 0, 0), axis=X)))


def wheel_nut_local(width):
    wo = web_planes(width)[1]
    n = g.cyl(46, 24, at=(wo, 0, 0), axis=X)
    return g.clean(g.cut(n, g.cyl(12, 24, at=(wo + 12, 0, 0), axis=X)))


# ------------------------------------------------------------------ monocoque e carenagens (cascas ocas)
MONO_SECS = [(-260, 360, 260, 0, 285, 3.2), (150, 520, 400, 0, 300, 3.2), (650, 660, 520, 0, 330, 3.4),
             (1200, 600, 500, 0, 330, 3.4), (1950, 420, 420, 0, 330, 3.2)]


def monocoque():
    body = hollow(MONO_SECS, 18.0)
    cockpit = g.fuse(g.box(-200, 200, 640, 1280, 470, 800), g.box(-250, 250, 720, 1200, 500, 800))
    return g.clean(g.cut(body, cockpit))


def cockpit_rim():
    outer = g.box(-262, 262, 700, 1220, 470, 505)
    return g.clean(g.cut(outer, g.box(-218, 218, 740, 1180, 460, 515)))


def nose_cone():
    return hollow([(-1010, 90, 80, 0, 215, 2.8), (-700, 200, 150, 0, 235, 3.0), (-260, 360, 260, 0, 285, 3.2)], 10.0)


def floor_plate():
    pts = [(-720, 300), (-780, 900), (-830, 1700), (-780, 3000), (-600, 3400), (600, 3400), (780, 3000), (830, 1700), (780, 900), (720, 300)]
    return g.extrude(pts, "xy", 40.0, 14.0)


def plank():
    return g.box(-150, 150, 520, 3300, 26.0, 40.0)


def diffuser():
    return g.extrude([(3300, 40), (4250, 330), (4250, 345), (3300, 54)], "yz", -430.0, 860.0)


def diffuser_strake(h=50.0):
    return g.extrude([(3330, 54), (4240, 345), (4240, 345 - h), (3330, 54)], "yz", -4.0, 8.0)


def engine_cover():
    return hollow([(1250, 300, 300, 0, 720, 2.6), (1800, 420, 360, 0, 640, 2.8), (2600, 380, 380, 0, 600, 3.0),
                   (3300, 260, 330, 0, 480, 3.0), (4050, 90, 160, 0, 360, 2.6)], 8.0)


def airbox():
    return hollow([(1050, 250, 250, 0, 790, 2.2), (1350, 300, 300, 0, 760, 2.4), (1800, 380, 330, 0, 680, 2.8)], 8.0)


def shark_fin():
    return g.extrude([(2400, 770), (3950, 440), (3950, 505), (3300, 690), (2700, 830), (2400, 830)], "yz", -4.0, 8.0)


def sidepod():
    return hollow([(700, 300, 300, 470, 250, 3.0), (1400, 380, 280, 430, 250, 3.0), (2200, 300, 230, 340, 235, 3.0), (3000, 140, 140, 220, 225, 3.0)], 8.0)


def radiator():
    return g.box(0, 130, 0, 520, 0, 230)


def gearbox():
    return hollow([(2600, 420, 380, 0, 330, 3.0), (3000, 380, 340, 0, 325, 3.0), (3480, 280, 280, 0, 320, 3.0)], 12.0)


def differential():
    return g.cyl(70, 300, at=(-150, WB, AXLE_Z), axis=X)


def rear_crash():
    return hollow([(3480, 280, 280, 0, 320, 3.0), (3850, 220, 240, 0, 330, 3.0), (4130, 170, 200, 0, 360, 3.0)], 10.0)


def halo_parts():
    r = 17
    return [("Halo pilar central", g.tube((0, 700, 440), (0, 960, 790), r)),
            ("Halo arco direito", g.tube((0, 960, 790), (230, 1150, 735), r)),
            ("Halo arco esquerdo", g.tube((0, 960, 790), (-230, 1150, 735), r)),
            ("Halo apoio direito", g.tube((230, 1150, 735), (240, 1210, 500), r)),
            ("Halo apoio esquerdo", g.tube((-230, 1150, 735), (-240, 1210, 500), r))]


def seat():
    return g.loft_y([(900, 420, 80, 0, 450, 3.0), (1250, 420, 330, 0, 540, 3.0)])


COLUMN_P0, COLUMN_P1 = np.array([0.0, 650.0, 440.0]), np.array([0.0, 780.0, 570.0])


def steering_wheel_local():
    """Volante (construído com a face normal em +Z; depois orientado ao longo da coluna): aro retangular, empunhaduras, painel e botões."""
    core = g.box(-95, 95, -22, 22, -10, 10)
    grips = [g.cut(g.box(sx * 95, sx * 150, -60, 60, -14, 14), g.cyl(30, 40, at=(sx * 128, 0, -20))) for sx in (-1, 1)]
    top = g.box(-95, 95, 28, 42, -10, 10)
    screen = g.box(-55, 55, -26, 26, 10, 22)
    buttons = [g.cyl(7, 8, at=(bx, by, 10)) for bx, by in ((-75, 12), (-75, -12), (75, 12), (75, -12), (-48, 0), (48, 0))]
    return g.clean(g.fuse(core, *grips, top, screen, *buttons, g.cyl(14, 40, at=(0, 0, -40))))


def helmet():
    return g.scale_xyz(g.sphere(1.0, at=(0, 0, 0)), 135, 165, 140)


def driver_torso():
    return g.loft_y([(900, 420, 120, 0, 470, 2.6), (1250, 440, 360, 0, 520, 2.6)])


def mirror_stem():
    return g.fuse(g.tube((260, 760, 520), (400, 700, 640), 8), g.box(380, 470, 660, 760, 620, 670))


# ------------------------------------------------------------------ asas
def wing_element(span, chord, thick, camber, incidence_deg, y0, z0, invert=True):
    pts = g.airfoil(chord, thick, camber, 0.4)
    inc = math.radians(incidence_deg)
    ys, zs = [], []
    for px, pz in pts:
        pz = -pz if invert else pz
        ys.append(px * math.cos(inc) - pz * math.sin(inc))              # rotação +x: y→z
        zs.append(px * math.sin(inc) + pz * math.cos(inc))
    poly = [(y0 + a, z0 + b) for a, b in zip(ys, zs)]
    return g.extrude(poly, "yz", -span / 2, span)


def endplate(y0, y1, z0, z1, thickness=10):
    return g.extrude([(y0, z0), (y1, z0 + 30), (y1, z1), (y0 + 40, z1 + 20)], "yz", 0.0, thickness)


def front_wing_parts():
    out = [("Asa dianteira elemento principal", wing_element(1800, 300, 0.10, 0.06, 6, -980, 110)),
           ("Asa dianteira flap fixo", wing_element(1750, 230, 0.10, 0.06, 14, -700, 185)),
           ("Asa dianteira flap intermediario", wing_element(1720, 210, 0.09, 0.06, 19, -670, 200)),
           ("Asa dianteira flap ativo", wing_element(1700, 190, 0.09, 0.06, 24, -640, 215))]
    ep = endplate(-1000, -420, 70, 300)
    out += [("Asa dianteira placa lateral direita", g.move(ep, (900, 0, 0))), ("Asa dianteira placa lateral esquerda", g.move(ep, (-910, 0, 0)))]
    foot = g.box(795, 912, -1000, -430, 62, 70)
    out += [("Asa dianteira sapata da placa direita", foot), ("Asa dianteira sapata da placa esquerda", g.mirror_x(foot))]
    casc = [wing_element(170, 130, 0.08, 0.05, 22, -700, 285), wing_element(170, 120, 0.08, 0.05, 28, -640, 330)]
    for i, c in enumerate(casc):
        cr = g.move(c, (815, 0, 0))
        out += [(f"Asa dianteira cascata direita {i + 1}", cr), (f"Asa dianteira cascata esquerda {i + 1}", g.mirror_x(cr))]
    vane = g.extrude([(-960, 70), (-440, 100), (-440, 110), (-960, 80)], "yz", 0.0, 6.0)
    for i, x in enumerate((820, 740)):
        out += [(f"Asa dianteira aleta vertical direita {i + 1}", g.move(vane, (x, 0, 150))), (f"Asa dianteira aleta vertical esquerda {i + 1}", g.move(g.mirror_x(vane), (-x, 0, 150)))]
    py = g.loft_y([(-380, 60, 110, 90, 240, 2.6), (-200, 100, 160, 100, 260, 2.6)])
    out += [("Pilar da asa dianteira direito", py), ("Pilar da asa dianteira esquerdo", g.mirror_x(py))]
    return out


def rear_wing_parts():
    out = [("Asa traseira plano principal", wing_element(1000, 380, 0.11, 0.07, 14, 3980, 760)),
           ("Asa traseira elemento intermediario", wing_element(1000, 280, 0.10, 0.07, 22, 4030, 840)),
           ("Asa traseira elemento ativo", wing_element(1000, 220, 0.09, 0.07, 32, 4090, 905)),
           ("Asa traseira beam wing", wing_element(760, 200, 0.08, 0.05, 8, 3930, 470))]
    ep = endplate(3960, 4380, 700, 1010)
    out += [("Asa traseira placa lateral direita", g.move(ep, (500, 0, 0))), ("Asa traseira placa lateral esquerda", g.move(ep, (-510, 0, 0)))]
    louv = g.extrude([(4000, 930), (4330, 930), (4330, 940), (4000, 940)], "yz", 0.0, 4.0)
    for i, x in enumerate((470, 440)):
        out += [(f"Asa traseira aleta da placa direita {i + 1}", g.move(louv, (x, 0, -i * 70))), (f"Asa traseira aleta da placa esquerda {i + 1}", g.move(louv, (-x - 4, 0, -i * 70)))]
    out += [("Pilar da asa traseira", g.box(-25, 25, 4100, 4180, 360, 780)), ("Luz traseira de chuva", g.box(-60, 60, 4380, 4400, 330, 400)),
            ("Pilar do beam wing direito", g.box(165, 185, 4000, 4060, 360, 480)), ("Pilar do beam wing esquerdo", g.box(-185, -165, 4000, 4060, 360, 480))]
    return out


# ------------------------------------------------------------------ aerodinâmica do assoalho
def floor_aero_parts():
    out = []
    edge = g.extrude([(700, 54), (2900, 54), (2900, 100), (1500, 150), (700, 105)], "yz", 0.0, 6.0)
    fence = g.extrude([(750, 54), (1050, 54), (1050, 150), (750, 120)], "yz", 0.0, 5.0)
    for s, sg in SIDES:
        e = g.move(edge, (705, 0, 0)) if sg > 0 else g.mirror_x(g.move(edge, (705, 0, 0)))
        out.append((f"Aba lateral do assoalho {s}", e))
        for i, x in enumerate((540, 610, 670)):
            f = g.move(fence, (x, 0, 0))
            out.append((f"Cerca do assoalho {s} {i + 1}", f if sg > 0 else g.mirror_x(f)))
        for i, (x0, x1) in enumerate(((520, 700), (480, 640), (440, 600))):
            vane = g.extrude([(x0, 480 + 150 * i), (x0 + 8, 480 + 150 * i), (x1 + 8, 950 + 100 * i), (x1, 950 + 100 * i)], "xy", 60.0, 200.0 + 40 * i)
            out.append((f"Defletor (bargeboard) {s} {i + 1}", vane if sg > 0 else g.mirror_x(vane)))
        for i, x in enumerate((100, 360)):
            out.append((f"Aleta externa do difusor {s} {i + 1}", g.move(diffuser_strake(40.0), (sg * (x + 20 * i), 0, 0))))
    return out


# ------------------------------------------------------------------ suspensão (geometria a partir dos hardpoints)
def tube_between(p1, p2, r, gap1=0.0, gap2=0.0, r_in=0.0):
    p1, p2 = np.asarray(p1, float), np.asarray(p2, float)
    u = (p2 - p1) / np.linalg.norm(p2 - p1)
    return g.tube(tuple(p1 + u * gap1), tuple(p2 - u * gap2), r, r_in)


def rocker_shape(hp):
    pr, a0, d0 = hp["pr"], hp["A0"], hp["D0"]
    y0 = pr[1]
    tri = g.extrude([(pr[0], pr[2]), (a0[0], a0[2]), (d0[0], d0[2])], "xz", y0 - 9, 18)
    pivot = g.cyl(11, 40, at=(pr[0], y0 - 20, pr[2]), axis=Y)
    return g.clean(g.fuse(tri, pivot, g.cyl(8, 26, at=(a0[0], y0 - 13, a0[2]), axis=Y), g.cyl(8, 26, at=(d0[0], y0 - 13, d0[2]), axis=Y)))


def damper_parts(hp):
    m, d = hp["M"], hp["D0"]
    u = (d - m) / np.linalg.norm(d - m)
    length = float(np.linalg.norm(d - m))
    body = g.tube(tuple(m), tuple(m + u * length * 0.55), 18, 10)
    rod = g.tube(tuple(d), tuple(d - u * length * 0.5), 8.5)
    return body, rod


def suspension_parts(front: bool):
    nm = "dianteira" if front else "traseira"
    out = []
    for s, sg in SIDES:
        hp = corner_hp(front, sg)
        for i, a in enumerate(hp["up_a"]):
            out.append((f"Braco superior {nm} {s} {i + 1}", tube_between(a, hp["up_u"], 11, 0, 20)))
        for i, a in enumerate(hp["lo_a"]):
            out.append((f"Braco inferior {nm} {s} {i + 1}", tube_between(a, hp["lo_u"], 11, 0, 20)))
        out.append((f"Barra de direcao {nm} {s}" if front else f"Tirante de convergencia traseiro {s}", tube_between(hp["tr_a"], hp["tr_u"], 8, 0, 15)))
        out.append((f"{'Barra de acionamento (push-rod)' if front else 'Barra de tracao (pull-rod)'} {nm} {s}", tube_between(hp["rod_u"], hp["A0"], 9, 0, 0)))
        out.append((f"Balancim {nm} {s}", rocker_shape(hp)))
        b, r = damper_parts(hp)
        out += [(f"Amortecedor corpo {nm} {s}", b), (f"Amortecedor haste {nm} {s}", r)]
    return out


def steering_rack_parts():
    y = RACK_Y_OFFSET
    housing = g.tube((-125, y, 270), (125, y, 270), 20, 13)
    rack = g.tube((-RACK_HALF, y, 270), (RACK_HALF, y, 270), 12)
    return housing, rack


# ------------------------------------------------------------------ unidade de potência V6 1,6 L (alesagem 80 × curso 53), banco a 90°
BORE, STROKE, CYL_PITCH = 80.0, 53.0, 100.0
EZ, EY0 = 305.0, 2060.0                      # altura do eixo do virabrequim e início do bloco
Y_CRANK0 = EY0 + 70.0                        # y do início da seção dos cilindros
R_CRANK = STROKE / 2
BANK_ANGLE = math.radians(45.0)              # cada banco inclinado 45° (V de 90°)
CRANK_ALPHA = (0.0, 2 * math.pi / 3, 4 * math.pi / 3)   # ângulos dos moentes (3 moentes a 120°)
BANK_DY = {1: -12.0, -1: 12.0}               # deslocamento longitudinal de cada banco (bielas lado a lado no mesmo moente)
CONROD_L = 145.5                             # comprimento entre centros (ilustrativo)
PIN_Z = 22.0                                 # posição do pino do pistão no sistema local do pistão (origem na saia)


def bank_axis(sign):
    return np.array([sign * math.sin(BANK_ANGLE), 0.0, math.cos(BANK_ANGLE)])


def cyl_origin(j, sign):
    return np.array([0.0, Y_CRANK0 + CYL_PITCH * (j + 0.5) + BANK_DY[sign], EZ])


def crank_pin(j, phi, sign=1):
    """Centro do moente j com o virabrequim girado de ``phi`` (rad, rotação positiva em torno de +Y)."""
    a = CRANK_ALPHA[j] + phi
    o = cyl_origin(j, sign)
    return np.array([0.0, o[1], EZ]) + R_CRANK * np.array([math.sin(a), 0.0, math.cos(a)])


def piston_pin(j, sign, phi):
    """Centro do pino do pistão (sobre o eixo do cilindro) para o ângulo ``phi`` do virabrequim: |P − C| = comprimento da biela."""
    o = cyl_origin(j, sign)
    c = crank_pin(j, phi, sign) - o
    ax = bank_axis(sign)
    s_c = float(np.dot(c, ax))
    perp2 = float(np.dot(c, c)) - s_c * s_c
    s = s_c + math.sqrt(CONROD_L ** 2 - perp2)
    return o + s * ax


def pu_bank_block():
    body = g.box(-95, 95, 0, 3 * CYL_PITCH, 60, 230)
    bores = [g.cyl(BORE / 2, 175, at=(0, CYL_PITCH * (i + 0.5), 55), axis=Z) for i in range(3)]
    return g.clean(g.cut(body, *bores))


def pu_bank_head():
    body = g.box(-95, 95, 0, 3 * CYL_PITCH, 230, 300)
    return g.clean(g.cut(body, *[g.cyl(18, 70, at=(0, CYL_PITCH * (i + 0.5), 230), axis=Z) for i in range(3)]))


def pu_valve_cover():
    return g.box(-80, 80, 20, 3 * CYL_PITCH - 20, 300, 330)


def pu_piston_local():
    """Pistão com origem no CENTRO DO PINO, eixo ao longo de +Z (coroa em cima): saia oca, calota e pino transversal (eixo Y)."""
    skirt = g.cyl(BORE / 2 - 0.5, 56, at=(0, 0, -PIN_Z - 6))
    skirt = g.cut(skirt, g.cyl(BORE / 2 - 8, 26, at=(0, 0, -PIN_Z - 6)))
    crown = g.cut(g.cyl(BORE / 2 - 0.5, 4, at=(0, 0, 28)), g.sphere(36, at=(0, 0, 60)))
    pin = g.cyl(9, 70, at=(0, -35, 0), axis=Y)
    return g.clean(g.fuse(skirt, crown, pin))


def pu_conrod_local():
    """Biela ao longo de +Z: olhal do moente em z=0 (furo Ø41), olhal do pino em z=L (furo Ø19), haste I simplificada. Espessura 22 em Y."""
    big = g.cut(g.cyl(27, 22, at=(0, -11, 0), axis=Y), g.cyl(20.5, 22, at=(0, -11, 0), axis=Y))
    small = g.cut(g.cyl(14, 22, at=(0, -11, CONROD_L), axis=Y), g.cyl(9.5, 22, at=(0, -11, CONROD_L), axis=Y))
    shank = g.box(-8, 8, -11, 11, 22, CONROD_L - 12)
    return g.clean(g.fuse(big, small, shank))


def pu_crank():
    """Virabrequim em repouso (phi=0): eixo Ø52, 3 moentes (Ø40) a 120° com duas bochechas cada, engrenagem de acionamento do MGU-K na frente."""
    parts = [g.cyl(26, 3 * CYL_PITCH + 140, at=(0, -70, 0), axis=Y)]
    for j in range(3):
        yj = CYL_PITCH * (j + 0.5)
        a = CRANK_ALPHA[j]
        cx, cz = R_CRANK * math.sin(a), R_CRANK * math.cos(a)
        parts.append(g.cyl(20, 50, at=(cx, yj - 25, cz), axis=Y))
        parts += [g.cyl(48, 14, at=(0, yj - 39, 0), axis=Y), g.cyl(48, 14, at=(0, yj + 25, 0), axis=Y)]
    gear = g.cut(g.cyl(70, 12, at=(0, -70, 0), axis=Y), *[g.cyl(10, 12, at=(40 * math.sin(2 * math.pi * i / 6), -70, 40 * math.cos(2 * math.pi * i / 6)), axis=Y) for i in range(6)])
    parts.append(gear)
    return g.clean(g.fuse(*parts))


def pu_flywheel():
    """Disco de embreagem de 8 furos, na traseira do virabrequim."""
    return g.cut(g.cyl(92, 14, at=(0, 0, 0), axis=Y), *[g.cyl(11, 14, at=(58 * math.sin(2 * math.pi * i / 8), 0, 58 * math.cos(2 * math.pi * i / 8)), axis=Y) for i in range(8)])


def pu_turbo_wheel(radius, blades, r_hub, blade_h, y0, length):
    """Rotor com pás (eixo ao longo de Y, centrado em x=0, z=0 local; deslocar depois)."""
    hub = g.cone(r_hub, r_hub * 0.55, length, at=(0, y0, 0), axis=Y)
    bl = []
    for i in range(blades):
        a = 2 * math.pi * i / blades
        b = g.box(-1.6, 1.6, y0 + 4, y0 + length - 4, r_hub * 0.55, radius)
        bl.append(g.rot(b, Y, a))
    return g.clean(g.fuse(hub, *bl))


def pu_plenum():
    return g.loft_y([(2090, 300, 160, 0, 595, 2.6), (2400, 360, 190, 0, 600, 2.6), (2700, 300, 160, 0, 595, 2.6)])


def pu_turbo_housing():
    return g.clean(g.cut(g.cyl(100, 190, at=(0, 2690, 470), axis=Y), g.cyl(88, 190, at=(0, 2690, 470), axis=Y)))


def pu_mguk():
    return g.clean(g.fuse(g.cyl(62, 150, at=(0, 1900, EZ), axis=Y), g.cyl(30, 40, at=(0, 2050, EZ), axis=Y)))


def pu_exhaust(sign):
    return g.tube((sign * 130, 2150, 480), (0, 2780, 470), 24, 21)


def pu_tailpipe():
    return g.tube((0, 2900, 470), (0, 4140, 335), 30, 26)


# ------------------------------------------------------------------ montagem
def build_f1() -> RawNode:
    L = lambda name, shape, m=None: RawNode(name, shape=shape, local_matrix=(at() if m is None else m))  # noqa: E731
    root_children = []

    # --- carroceria e chassi
    chassis = [L("Monocoque (celula de sobrevivencia)", monocoque()), L("Aro do cockpit", cockpit_rim()), L("Nariz (estrutura de impacto frontal)", nose_cone()),
               L("Piso (assoalho plano)", floor_plate()), L("Prancha de desgaste", plank()), L("Difusor", diffuser()),
               L("Aleta do difusor direita", g.move(diffuser_strake(), (230, 0, 0))), L("Aleta do difusor esquerda", g.move(diffuser_strake(), (-234, 0, 0))),
               L("Estrutura de impacto traseira", rear_crash()), L("Banco do piloto", seat()),
               L("Apoio de cabeca", g.box(-110, 110, 1150, 1190, 560, 720)), L("Painel de instrumentos", g.box(-90, 90, 690, 720, 560, 610)),
               L("Caixa de pedais", g.box(-120, 120, 40, 120, 250, 330)), L("Pedal do acelerador", g.box(40, 90, 120, 135, 260, 330)),
               L("Pedal de freio", g.box(-90, -40, 120, 135, 260, 330))]
    root_children.append(RawNode("Chassi", children=chassis))
    body = [L("Cobertura do motor", engine_cover()), L("Entrada de ar (airbox)", airbox()), L("Aleta dorsal (shark fin)", shark_fin())]
    for i in range(6):
        yy = 2980 + 70 * i
        top = 730 - (yy - 2600) * 0.12
        body.append(L(f"Veneziana do motor {i + 1}", g.box(-80, 80, yy, yy + 6, top - 20, top + 22)))
    sp = sidepod()
    body += [L("Lateral direita (sidepod)", sp), L("Lateral esquerda (sidepod)", g.mirror_x(sp))]
    rd = radiator()
    body += [L("Radiador direito", g.move(rd, (345, 780, 130))), L("Radiador esquerdo", g.move(g.mirror_x(rd), (-345, 780, 130)))]
    ms = mirror_stem()
    body += [L("Retrovisor direito", ms), L("Retrovisor esquerdo", g.mirror_x(ms)),
             L("Carcaca do retrovisor direito", g.box(395, 480, 700, 790, 600, 665)), L("Carcaca do retrovisor esquerdo", g.box(-480, -395, 700, 790, 600, 665)),
             L("Camera onboard", g.box(-20, 20, 1040, 1075, 790, 830)), L("Camera do nariz", g.box(-18, 18, -520, -490, 262, 290))]
    root_children.append(RawNode("Carroceria", children=body))
    root_children.append(RawNode("Seguranca (Halo)", children=[L(n, s) for n, s in halo_parts()]))
    wheel_dir = COLUMN_P1 - COLUMN_P0
    wheel_dir = wheel_dir / np.linalg.norm(wheel_dir)
    root_children.append(RawNode("Cockpit", children=[
        L("Volante", g.orient_z_to(steering_wheel_local(), wheel_dir, tuple(COLUMN_P1))),
        L("Coluna de direcao", g.tube(tuple(COLUMN_P0), tuple(COLUMN_P1 - wheel_dir * 18), 16)),
        L("Capacete do piloto (referencia)", g.move(helmet(), (0, 1000, 680))), L("Torso do piloto (referencia)", driver_torso())]))

    # --- aerodinâmica
    root_children.append(RawNode("Asa dianteira", children=[L(n, s) for n, s in front_wing_parts()]))
    root_children.append(RawNode("Asa traseira", children=[L(n, s) for n, s in rear_wing_parts()]))
    root_children.append(RawNode("Aerodinamica do assoalho", children=[L(n, s) for n, s in floor_aero_parts()]))

    # --- unidade de potência
    blk, head, vcov = pu_bank_block(), pu_bank_head(), pu_valve_cover()
    pis, rod = pu_piston_local(), pu_conrod_local()
    pu = [L("Virabrequim", g.move(pu_crank(), (0, Y_CRANK0, EZ))), L("Volante de embreagem", g.move(pu_flywheel(), (0, Y_CRANK0 + 3 * CYL_PITCH + 80, EZ)))]
    for s, sg in (("direito", 1), ("esquerdo", -1)):
        def to_bank(shape, sg=sg):
            return g.move(g.rot(shape, Y, sg * BANK_ANGLE), (0, Y_CRANK0 + BANK_DY[sg], EZ))
        pu.append(L(f"Bloco do banco {s}", to_bank(blk)))
        pu.append(L(f"Cabecote do banco {s}", to_bank(head)))
        pu.append(L(f"Tampa de valvulas {s}", to_bank(vcov)))
        for j in range(3):
            pp = piston_pin(j, sg, 0.0)
            cp = crank_pin(j, 0.0, sg)
            d = pp - cp
            # biela ao longo de Z local: gira Z para d; pistão: gira Z para o eixo do banco
            pu.append(L(f"Pistao {s} {j + 1}", g.move(g.rot(pis, Y, sg * BANK_ANGLE), tuple(pp))))
            pu.append(L(f"Biela {s} {j + 1}", g.orient_z_to(rod, d, tuple(cp))))
    pu += [L("Plenum de admissao", pu_plenum()), L("Carcaca do turbocompressor", pu_turbo_housing()),
           L("Rotor do compressor", g.move(pu_turbo_wheel(90, 11, 40, 50, 0, 80), (0, 2700, 470))),
           L("Rotor da turbina", g.move(pu_turbo_wheel(68, 12, 32, 40, 0, 70), (0, 2790, 470))),
           L("MGU-K", pu_mguk()), L("Escape direito", pu_exhaust(1)), L("Escape esquerdo", pu_exhaust(-1)), L("Ponteira de escape", pu_tailpipe())]
    root_children.append(RawNode("Unidade de potencia V6 1.6 turbo", children=pu))
    root_children.append(RawNode("Armazenamento de energia e combustivel", children=[
        L("Bateria (ES)", g.box(-190, 190, 1250, 1620, 90, 240)), L("Tanque de combustivel", g.box(-220, 220, 1650, 2030, 110, 400))]))
    root_children.append(RawNode("Transmissao", children=[L("Caixa de cambio", gearbox()), L("Diferencial", differential())]))
    housing, rack = steering_rack_parts()
    root_children.append(RawNode("Direcao", children=[L("Carcaca da cremalheira", housing), L("Cremalheira (barra) de direcao", rack)]))

    # --- eixos: suspensão e rodas
    for front in (True, False):
        y, x, w_t = axle_geom(front)
        nm = "dianteira" if front else "traseira"
        root_children.append(RawNode(f"Suspensao {nm}", children=[L(n, s) for n, s in suspension_parts(front)]))
        wheels = []
        for s, sg in SIDES:
            xc = sg * x
            mir = (lambda sh: sh) if sg > 0 else g.mirror_x
            wheels += [L(f"Pneu {nm} {s}", tyre(w_t), at(xc, y, AXLE_Z)),
                       L(f"Roda {nm} {s}", rim(w_t, sg), at(xc, y, AXLE_Z)),
                       L(f"Disco de freio {nm} {s}", mir(brake_disc_local()), at(xc, y, AXLE_Z)),
                       L(f"Cubo {nm} {s}", mir(hub_local(w_t)), at(xc, y, AXLE_Z)),
                       L(f"Porca central {nm} {s}", mir(wheel_nut_local(w_t)), at(xc, y, AXLE_Z)),
                       L(f"Manga de eixo {nm} {s}", mir(upright_local(front)), at(xc, y, AXLE_Z)),
                       L(f"Pinca de freio {nm} {s}", mir(caliper_local()), at(xc, y, AXLE_Z))]
        root_children.append(RawNode(f"Rodas {nm}", children=wheels))
    shaft = []
    for s, sg in SIDES:
        hp = corner_hp(False, sg)
        shaft.append(L(f"Semi-eixo {s}", tube_between(hp["P_d"], hp["C"] + np.array([sg * -122.0 * 1.0, 0.0, 0.0]) * 1.0, 18)))
    root_children[[c.name for c in root_children].index("Transmissao")].children += shaft
    return RawNode("Carro F1 2026 (modelo de referencia)", children=root_children)


def write(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    CadEngine().write_step([build_f1()], path)
    return path


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "samples" / "f1_2026.step"
    print("Gerado:", write(out))
