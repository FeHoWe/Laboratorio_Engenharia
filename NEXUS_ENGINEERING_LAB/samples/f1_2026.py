"""Carro de Fórmula 1 de 2026 (modelo paramétrico SIMPLIFICADO baseado no regulamento) — V2.2.

HONESTIDADE: as equipes não publicam seus CAD; este NÃO é o carro de nenhuma equipe nem um modelo de produção. É um modelo de referência
construído em sólidos B-rep reais com as dimensões do regulamento técnico de 2026 que foram verificadas em fontes públicas:
  entre-eixos 3400 mm · largura máx. 1900 mm · massa mínima 768 kg (sem combustível, com piloto) · rodas de 18" · pneus 25 mm (diant.)
  e 30 mm (tras.) mais estreitos que em 2025 · V6 turbo híbrido 1,6 L (alesagem 80 mm × curso 53 mm) · MGU-K de até 350 kW · sem MGU-H ·
  aerodinâmica ativa (modo curva / modo reta) · assoalho sem túneis Venturi.
Valores NÃO verificados e aproximados: largura dos pneus (305/405 mm de 2025 menos 25/30 mm), diâmetro externo do pneu (720 mm),
dimensões das asas, geometria de suspensão, posições internas. Carenagens são cascas macias de seções (loft); a massa do conjunto é
PARCIAL (sem compósitos, pois o banco não tem fibra de carbono) e não representa a massa do carro.

Eixos: x lateral (direita +), y longitudinal (eixo dianteiro em y=0, traseiro em y=3400; a frente do carro aponta para -y), z para cima (solo z=0).
O animador gira as rodas e abre/fecha os elementos ativos das asas (modo curva ↔ modo reta).
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
AERO_FRONT_FLAP = 16.0               # abertura (°) dos flaps ativos dianteiros do modo curva para o modo reta
AERO_REAR_FLAP = 38.0                # idem, elemento superior da asa traseira
FRONT_FLAP_HINGE = (-640.0, 205.0)   # (y, z) da articulação do flap móvel da asa dianteira
REAR_FLAP_HINGE = (4090.0, 905.0)    # (y, z) da articulação do elemento superior da asa traseira
AXLE_Z = R_TYRE


def at(x=0.0, y=0.0, z=0.0):
    return translation_matrix([x, y, z])


def both(shape):
    """(direita, esquerda): a esquerda é o espelho em x=0."""
    return shape, g.mirror_x(shape)


# ------------------------------------------------------------------ rodas e freios
def tyre(width):
    w = width / 2
    prof = [(-w + 12, R_RIM), (-w + 4, R_RIM + 35), (-w, R_RIM + 80), (-w + 3, R_TYRE - 40), (-w + 18, R_TYRE - 8), (-w + 50, R_TYRE),
            (w - 50, R_TYRE), (w - 18, R_TYRE - 8), (w - 3, R_TYRE - 40), (w, R_RIM + 80), (w - 4, R_RIM + 35), (w - 12, R_RIM)]
    return g.revolve(prof, "x")


def rim(width, outer_sign=1):
    """Roda: aro + alma com furos de alívio; o lado externo (alma) fica no sinal ``outer_sign`` de x."""
    ww = width - 40
    prof = [(-ww / 2, R_RIM - 5), (-ww / 2, R_RIM), (ww / 2, R_RIM), (ww / 2, R_RIM - 5), (ww / 2 - 26, R_RIM - 5), (ww / 2 - 26, 40),
            (ww / 2 - 40, 40), (ww / 2 - 40, R_RIM - 5)]
    body = g.revolve(prof, "x")
    holes = [g.cyl(32, 40, at=(ww / 2 - 44, 130 * math.cos(2 * math.pi * i / 8), 130 * math.sin(2 * math.pi * i / 8)), axis=X) for i in range(8)]
    body = g.clean(g.cut(body, *holes))
    return body if outer_sign > 0 else g.mirror_x(body)


def brake_disc_x(side):
    d = g.cut(g.cyl(139, 30, axis=X), g.cyl(60, 30, axis=X))
    holes = [g.cyl(5, 30, at=(0, 100 * math.cos(2 * math.pi * i / 24), 100 * math.sin(2 * math.pi * i / 24)), axis=X) for i in range(24)]
    d = g.clean(g.cut(d, *holes))
    return d if side > 0 else g.mirror_x(d)


def caliper():
    body = g.box(0, 70, -60, 60, 0, 90)
    return g.clean(g.cut(body, g.box(15, 55, -62, 62, 20, 70)))


def upright(front: bool):
    body = g.fuse(g.box(-45, 45, -50, 50, -230, 260), g.cyl(55, 90, at=(-45, 0, 0), axis=X))
    return g.clean(g.cut(body, g.cyl(36, 100, at=(-50, 0, 0), axis=X)))


def hub(width):
    return g.clean(g.fuse(g.cyl(34, width - 40, at=(-(width - 40) / 2 + 20, 0, 0), axis=X), g.cyl(50, 24, at=(-(width - 40) / 2 + 20, 0, 0), axis=X)))


# ------------------------------------------------------------------ monocoque e carenagens
def monocoque():
    body = g.loft_y([(-260, 360, 260, 0, 285, 3.2), (150, 520, 400, 0, 300, 3.2), (650, 660, 520, 0, 330, 3.4),
                     (1200, 600, 500, 0, 330, 3.4), (1950, 420, 420, 0, 330, 3.2)])
    cockpit = g.fuse(g.box(-200, 200, 640, 1280, 470, 800), g.box(-250, 250, 720, 1200, 500, 800))
    return g.clean(g.cut(body, cockpit))


def nose_cone():
    return g.loft_y([(-1010, 90, 80, 0, 215, 2.8), (-700, 200, 150, 0, 235, 3.0), (-260, 360, 260, 0, 285, 3.2)])


def floor_plate():
    pts = [(-720, 300), (-780, 900), (-830, 1700), (-780, 3000), (-600, 3400), (600, 3400), (780, 3000), (830, 1700), (780, 900), (720, 300)]
    return g.extrude(pts, "xy", 40.0, 14.0)


def plank():
    return g.box(-150, 150, 520, 3300, 26.0, 40.0)


def diffuser():
    return g.extrude([(3300, 40), (4250, 330), (4250, 345), (3300, 54)], "yz", -430.0, 860.0)


def diffuser_strake():
    return g.extrude([(3330, 54), (4240, 345), (4240, 295), (3330, 54)], "yz", -4.0, 8.0)


def engine_cover():
    return g.loft_y([(1250, 300, 300, 0, 720, 2.6), (1800, 420, 360, 0, 640, 2.8), (2600, 380, 380, 0, 600, 3.0),
                     (3300, 260, 330, 0, 480, 3.0), (4050, 90, 160, 0, 360, 2.6)])


def airbox():
    return g.loft_y([(1050, 250, 250, 0, 790, 2.2), (1350, 300, 300, 0, 760, 2.4), (1800, 380, 330, 0, 680, 2.8)])


def sidepod():
    return g.loft_y([(700, 300, 300, 470, 250, 3.0), (1400, 380, 280, 430, 250, 3.0), (2200, 300, 230, 340, 235, 3.0), (3000, 140, 140, 220, 225, 3.0)])


def radiator():
    return g.box(0, 140, 0, 520, 0, 240)


def gearbox():
    return g.loft_y([(2600, 420, 380, 0, 330, 3.0), (3000, 380, 340, 0, 325, 3.0), (3480, 280, 280, 0, 320, 3.0)])


def differential():
    return g.cyl(70, 300, at=(-150, 3400, 330), axis=X)


def rear_crash():
    return g.loft_y([(3480, 280, 280, 0, 320, 3.0), (3850, 220, 240, 0, 330, 3.0)])


def halo_parts():
    r = 17
    return [("Halo pilar central", g.tube((0, 700, 440), (0, 960, 790), r)),
            ("Halo arco direito", g.tube((0, 960, 790), (230, 1150, 735), r)),
            ("Halo arco esquerdo", g.tube((0, 960, 790), (-230, 1150, 735), r)),
            ("Halo apoio direito", g.tube((230, 1150, 735), (240, 1210, 500), r)),
            ("Halo apoio esquerdo", g.tube((-230, 1150, 735), (-240, 1210, 500), r))]


def seat():
    return g.loft_y([(900, 420, 80, 0, 450, 3.0), (1250, 420, 330, 0, 540, 3.0)])


def steering_wheel():
    rimw = g.cut(g.box(-150, 150, -15, 15, -60, 60), g.box(-80, 80, -20, 20, -30, 30))
    return g.clean(g.fuse(rimw, g.cyl(10, 160, at=(0, 10, 0), axis=Y)))


def helmet():
    return g.sphere(140, at=(0, 1000, 680))


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
           ("Asa dianteira flap ativo", wing_element(1700, 190, 0.09, 0.06, 24, -640, 215))]
    ep = endplate(-1000, -420, 70, 300)
    out += [("Asa dianteira placa lateral direita", g.move(ep, (900, 0, 0))), ("Asa dianteira placa lateral esquerda", g.move(ep, (-910, 0, 0)))]
    py = g.loft_y([(-380, 60, 110, 90, 240, 2.6), (-200, 100, 160, 100, 260, 2.6)])
    out += [("Pilar da asa dianteira direito", py), ("Pilar da asa dianteira esquerdo", g.mirror_x(py))]
    return out


def rear_wing_parts():
    out = [("Asa traseira plano principal", wing_element(1000, 380, 0.11, 0.07, 14, 3980, 760)),
           ("Asa traseira elemento intermediario", wing_element(1000, 280, 0.10, 0.07, 22, 4030, 840)),
           ("Asa traseira elemento ativo", wing_element(1000, 220, 0.09, 0.07, 32, 4090, 905))]
    ep = endplate(3960, 4380, 700, 1010)
    out += [("Asa traseira placa lateral direita", g.move(ep, (500, 0, 0))), ("Asa traseira placa lateral esquerda", g.move(ep, (-510, 0, 0)))]
    out += [("Pilar da asa traseira", g.box(-25, 25, 4100, 4180, 380, 780)), ("Luz traseira de chuva", g.box(-60, 60, 4380, 4400, 330, 400))]
    return out


# ------------------------------------------------------------------ suspensão
def susp_points(front: bool):
    y = 0.0 if front else WB
    x = XF if front else XR
    return dict(
        up_u=(x - 90, y, 420), lo_u=(x - 90, y, 150), tr_u=(x - 100, y + (120 if front else -120), 270),
        up_a=[(190, y - 200, 340), (190, y + 280, 355)], lo_a=[(200, y - 260, 150), (200, y + 300, 160)],
        tr_a=(180, y + (140 if front else -140), 270), rod_u=(x - 100, y, 185), rod_a=(130, y + (60 if front else -60), 410))


def wishbone_parts(front: bool):
    pts, r = susp_points(front), 11
    nm = "dianteira" if front else "traseira"
    out = []
    for s, sgn in (("direita", 1), ("esquerda", -1)):
        def m(p):
            return (p[0] * sgn, p[1], p[2])
        for i, a in enumerate(pts["up_a"]):
            out.append((f"Braco superior {nm} {s} {i + 1}", g.tube(m(a), m(pts["up_u"]), r)))
        for i, a in enumerate(pts["lo_a"]):
            out.append((f"Braco inferior {nm} {s} {i + 1}", g.tube(m(a), m(pts["lo_u"]), r)))
        out.append((f"Barra de direcao {nm} {s}" if front else f"Tirante de convergencia traseiro {s}", g.tube(m(pts["tr_a"]), m(pts["tr_u"]), 8)))
        out.append((f"{'Barra de acionamento (push-rod)' if front else 'Barra de tracao (pull-rod)'} {nm} {s}",
                    g.tube(m(pts["rod_u"]), m(pts["rod_a"]), 9)))
    return out


def rocker():
    return g.clean(g.cut(g.box(-45, 45, -30, 30, -20, 20), g.cyl(8, 60, at=(-30, 0, 0), axis=X)))


def damper():
    return g.fuse(g.cyl(18, 190, at=(0, 0, 0), axis=Y), g.cyl(8, 60, at=(0, -60, 0), axis=Y))


# ------------------------------------------------------------------ unidade de potência V6 1,6 L (alesagem 80 × curso 53)
BORE, STROKE, CYL_PITCH = 80.0, 53.0, 100.0
EZ, EY0 = 305.0, 2060.0                      # altura do eixo do virabrequim e início do bloco


def pu_bank_block():
    body = g.box(-95, 95, 0, 3 * CYL_PITCH, 60, 230)
    bores = [g.cyl(BORE / 2, 175, at=(0, CYL_PITCH * (i + 0.5), 55), axis=Z) for i in range(3)]
    return g.clean(g.cut(body, *bores))


def pu_bank_head():
    body = g.box(-95, 95, 0, 3 * CYL_PITCH, 230, 300)
    return g.clean(g.cut(body, *[g.cyl(18, 70, at=(0, CYL_PITCH * (i + 0.5), 230), axis=Z) for i in range(3)]))


def pu_piston():
    p = g.cut(g.cyl(BORE / 2 - 0.5, 44, at=(0, 0, 0), axis=Z), g.cyl(BORE / 2 - 9, 30, at=(0, 0, 0), axis=Z))
    return g.clean(g.fuse(p, g.cyl(10, 10, at=(0, 0, 44), axis=Z)))


def pu_crank():
    shaft = g.cyl(26, 3 * CYL_PITCH + 140, at=(0, -70, 0), axis=Y)
    webs = [g.cyl(55, 12, at=(0, CYL_PITCH * (i + 0.5) - 6, 0), axis=Y) for i in range(3)]
    return g.clean(g.fuse(shaft, *webs))


def transform_to_bank(shape, sign):
    s = g.rot(shape, Y, sign * math.radians(45.0))
    return g.move(s, (0, EY0 + 70, EZ))


def pu_plenum():
    return g.loft_y([(2090, 300, 160, 0, 595, 2.6), (2400, 360, 190, 0, 600, 2.6), (2700, 300, 160, 0, 595, 2.6)])


def pu_turbo():
    comp = g.cone(95, 40, 80, at=(0, 2740, 470), axis=Y)
    turb = g.cone(70, 40, 70, at=(0, 2840, 470), axis=Y)
    return g.clean(g.fuse(comp, turb, g.cyl(28, 60, at=(0, 2820, 470), axis=Y)))


def pu_mguk():
    return g.clean(g.fuse(g.cyl(62, 150, at=(0, 1900, EZ), axis=Y), g.cyl(30, 60, at=(0, 1850, EZ), axis=Y)))


def pu_exhaust(sign):
    return g.tube((sign * 130, 2150, 480), (0, 2780, 470), 24, 21)


# ------------------------------------------------------------------ montagem
def build_f1() -> RawNode:
    L = lambda name, shape, m=None: RawNode(name, shape=shape, local_matrix=(at() if m is None else m))  # noqa: E731
    root_children = []

    # --- carroceria e chassi
    chassis = [L("Monocoque (celula de sobrevivencia)", monocoque()), L("Nariz (estrutura de impacto frontal)", nose_cone()),
               L("Piso (assoalho plano)", floor_plate()), L("Prancha de desgaste", plank()), L("Difusor", diffuser()),
               L("Aleta do difusor direita", g.move(diffuser_strake(), (230, 0, 0))), L("Aleta do difusor esquerda", g.move(diffuser_strake(), (-234, 0, 0))),
               L("Estrutura de impacto traseira", rear_crash()), L("Banco do piloto", seat())]
    root_children.append(RawNode("Chassi", children=chassis))
    body = [L("Cobertura do motor", engine_cover()), L("Entrada de ar (airbox)", airbox())]
    sp = sidepod()
    body += [L("Lateral direita (sidepod)", sp), L("Lateral esquerda (sidepod)", g.mirror_x(sp))]
    rd = radiator()
    body += [L("Radiador direito", g.move(rd, (320, 780, 120))), L("Radiador esquerdo", g.move(g.mirror_x(rd), (-320, 780, 120)))]
    ms = mirror_stem()
    body += [L("Retrovisor direito", ms), L("Retrovisor esquerdo", g.mirror_x(ms))]
    root_children.append(RawNode("Carroceria", children=body))
    root_children.append(RawNode("Seguranca (Halo)", children=[L(n, s) for n, s in halo_parts()]))
    root_children.append(RawNode("Cockpit", children=[L("Volante", steering_wheel(), at(0, 780, 570)), L("Coluna de direcao", g.tube((0, 650, 440), (0, 780, 570), 16), at()),
                                                      L("Capacete do piloto (referencia)", helmet()), L("Torso do piloto (referencia)", driver_torso())]))

    # --- aerodinâmica
    root_children.append(RawNode("Asa dianteira", children=[L(n, s) for n, s in front_wing_parts()]))
    root_children.append(RawNode("Asa traseira", children=[L(n, s) for n, s in rear_wing_parts()]))

    # --- unidade de potência
    blk, head, pis, crank = pu_bank_block(), pu_bank_head(), pu_piston(), pu_crank()
    pu = [L("Virabrequim", g.move(crank, (0, EY0 + 70, EZ)))]
    for s, sg in (("direito", 1), ("esquerdo", -1)):
        pu.append(L(f"Bloco do banco {s}", transform_to_bank(blk, sg)))
        pu.append(L(f"Cabecote do banco {s}", transform_to_bank(head, sg)))
        for i in range(3):
            pu.append(L(f"Pistao {s} {i + 1}", transform_to_bank(g.move(pis, (0, CYL_PITCH * (i + 0.5), 150)), sg)))
    pu += [L("Plenum de admissao", pu_plenum()), L("Turbocompressor", pu_turbo()), L("MGU-K", pu_mguk()),
           L("Escape direito", pu_exhaust(1)), L("Escape esquerdo", pu_exhaust(-1))]
    root_children.append(RawNode("Unidade de potencia V6 1.6 turbo", children=pu))
    root_children.append(RawNode("Armazenamento de energia e combustivel", children=[
        L("Bateria (ES)", g.box(-190, 190, 1250, 1620, 70, 240)), L("Tanque de combustivel", g.box(-220, 220, 1650, 2030, 90, 400))]))
    root_children.append(RawNode("Transmissao", children=[L("Caixa de cambio", gearbox()), L("Diferencial", differential()),
                                                         L("Semi-eixo direito", g.tube((70, 3400, 330), (XR - 60, 3400, AXLE_Z), 18)),
                                                         L("Semi-eixo esquerdo", g.tube((-70, 3400, 330), (-(XR - 60), 3400, AXLE_Z), 18))]))

    # --- eixos: suspensão e rodas
    for front in (True, False):
        y = 0.0 if front else WB
        nm = "dianteira" if front else "traseira"
        w_t = W_TYRE_F if front else W_TYRE_R
        x = XF if front else XR
        kids = [L(n, s) for n, s in wishbone_parts(front)]
        kids += [L(f"Balancim {nm} direito", rocker(), at(130, y + (60 if front else -60), 430)), L(f"Balancim {nm} esquerdo", rocker(), at(-130, y + (60 if front else -60), 430)),
                 L(f"Amortecedor {nm} direito", damper(), at(60, y - 20, 420)), L(f"Amortecedor {nm} esquerdo", damper(), at(-60, y - 20, 420))]
        root_children.append(RawNode(f"Suspensao {nm}", children=kids))
        wheels = []
        for s, sg in (("direita", 1), ("esquerda", -1)):
            xc = sg * x
            wheels += [L(f"Pneu {nm} {s}", tyre(w_t), at(xc, y, AXLE_Z)),
                       L(f"Roda {nm} {s}", rim(w_t, sg), at(xc, y, AXLE_Z)),
                       L(f"Disco de freio {nm} {s}", brake_disc_x(sg), at(sg * (x - w_t / 2 + 70), y, AXLE_Z)),
                       L(f"Cubo {nm} {s}", hub(w_t) if sg > 0 else g.mirror_x(hub(w_t)), at(xc, y, AXLE_Z)),
                       L(f"Manga de eixo {nm} {s}", upright(front) if sg > 0 else g.mirror_x(upright(front)), at(sg * (x - w_t / 2 + 100), y, AXLE_Z)),
                       L(f"Pinca de freio {nm} {s}", caliper() if sg > 0 else g.mirror_x(caliper()), at(sg * (x - w_t / 2 + 40), y, AXLE_Z + 125))]
        root_children.append(RawNode(f"Rodas {nm}", children=wheels))
    return RawNode("Carro F1 2026 (modelo de referencia)", children=root_children)


def write(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    CadEngine().write_step([build_f1()], path)
    return path


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "samples" / "f1_2026.step"
    print("Gerado:", write(out))
