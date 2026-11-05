"""Gerador do modelo de exemplo: motor 4 cilindros em linha (DOHC 16V), em mm.

Tudo é geometria sólida real (booleanas do OpenCascade), sem malhas fingindo ser CAD.
Eixos: virabrequim ao longo de X (frente em x<0, volante em x>360); cilindros ao longo de Z;
admissão em y<0, escape em y>0. Curso 86 mm, diâmetro 86 mm, biela 145 mm, passo entre cilindros 90 mm.
Ordem de ignição 1-3-4-2: pistões 1 e 4 no PMS, 2 e 3 no PMI.

V1.7 acrescentou: molas helicoidais das válvulas (varredura de fio em hélice), rodas dentadas (virabrequim e
comandos), correia dentada e dutos internos (dutos de admissão/escape no cabeçote e galerias de óleo cegas no bloco).
V1.9 (motor 173 peças): correia com 96 dentes e razão 2:1 exata (20 e 40 dentes), comando de escape por engrenagens 1:1,
hastes de válvula com pastilha que toca o lóbulo (levantamento derivado da geometria) e frente remodelada. As molas continuam
simplificadas (sem passo variável nem extremidades esquadrejadas) e o estado modelado é o de θ=0 (válvulas já empurradas).

Os nomes ficam sem acento porque o STEP via OpenCascade perde acentos em nomes de instâncias.

Uso:  python -m samples.motor_4_cilindros [saida.step]
"""
from __future__ import annotations

import sys
from pathlib import Path

import functools

import numpy as np
import math

from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakeWire
from OCP.BRepLib import BRepLib
from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipeShell
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCone, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakePrism
from OCP.GC import GC_MakeArcOfCircle
from OCP.GeomAbs import GeomAbs_Shape
from OCP.Geom import Geom_CylindricalSurface
from OCP.Geom2d import Geom2d_Line
from OCP.gp import gp_Ax3, gp_Circ, gp_Dir2d, gp_Pnt2d, gp_Vec
from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
from OCP.TopoDS import TopoDS_Shape
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.cad_engine import CadEngine, RawNode  # noqa: E402
from core.geometry import translation_matrix  # noqa: E402
from modules.kinematics import hull_path  # noqa: E402

# ------------------------------------------------------------------ parâmetros
N_CYL = 4
PITCH = 90.0
CX = [45.0 + PITCH * i for i in range(N_CYL)]        # x do eixo de cada cilindro
BORE_R = 43.0
THROW = 43.0                                         # raio da manivela (curso 86)
ROD_LEN = 145.0
PIN_R = 10.0
UP = [True, False, False, True]                      # 1-3-4-2: pistões 1 e 4 no PMS
DECK = 218.5                                         # topo do bloco
GASKET = 1.5
HEAD_TOP = 275.0
PORT_Z = 229.0                                       # altura do eixo dos dutos no cabeçote
CAM_Z = 312.0                                        # eixo dos comandos (acima das molas)
BLOCK_LEN = 360.0
SWEEP = 80.0                                         # raio livre do cárter (varredura da manivela e das bielas)
SKIRT = 92.0                                         # meia-largura da saia do bloco e do cárter

X, Y, Z = (1, 0, 0), (0, 1, 0), (0, 0, 1)


# ------------------------------------------------------------------ primitivas
def box(x0, x1, y0, y1, z0, z1) -> TopoDS_Shape:
    return BRepPrimAPI_MakeBox(gp_Pnt(x0, y0, z0), x1 - x0, y1 - y0, z1 - z0).Shape()


def cyl(r, length, at=(0, 0, 0), axis=Z) -> TopoDS_Shape:
    """Cilindro de raio r que começa em ``at`` e se estende ``length`` ao longo de ``axis``."""
    return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(*at), gp_Dir(*axis)), r, length).Shape()


def cone(r1, r2, h, at=(0, 0, 0), axis=Z) -> TopoDS_Shape:
    return BRepPrimAPI_MakeCone(gp_Ax2(gp_Pnt(*at), gp_Dir(*axis)), r1, r2, h).Shape()


def fuse(*shapes) -> TopoDS_Shape:
    out = shapes[0]
    for s in shapes[1:]:
        out = BRepAlgoAPI_Fuse(out, s).Shape()
    return out


def cut(base, *tools) -> TopoDS_Shape:
    out = base
    for t in tools:
        out = BRepAlgoAPI_Cut(out, t).Shape()
    return out


def clean(shape) -> TopoDS_Shape:
    """Une faces coplanares/cilíndricas geradas pelas booleanas (modelo mais limpo)."""
    u = ShapeUpgrade_UnifySameDomain(shape, True, True, True)
    u.Build()
    return u.Shape()


def move(shape, v):
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.gp import gp_Trsf, gp_Vec
    t = gp_Trsf()
    t.SetTranslation(gp_Vec(*v))
    return BRepBuilderAPI_Transform(shape, t, True).Shape()


def rotx(shape, ang_rad: float):
    """Gira a forma em torno do eixo X (pela origem), regra da mão direita."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.gp import gp_Ax1, gp_Trsf
    t = gp_Trsf()
    t.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(1, 0, 0)), ang_rad)
    return BRepBuilderAPI_Transform(shape, t, True).Shape()


def at(x=0.0, y=0.0, z=0.0) -> np.ndarray:
    return translation_matrix([x, y, z])


# ------------------------------------------------------------------ componentes
def engine_block() -> TopoDS_Shape:
    # saia do cárter alargada (V1.8): a manivela e o olhal grande da biela varrem raio de até 76 mm
    body = fuse(box(0, BLOCK_LEN, -65, 65, -45, DECK), box(0, BLOCK_LEN, -SKIRT, SKIRT, -45, 30))
    bores = [cyl(BORE_R, DECK + 45, at=(cx, 0, -20)) for cx in CX]
    crank_cavity = fuse(box(8, BLOCK_LEN - 8, -SWEEP, SWEEP, -46, 0), cyl(SWEEP, BLOCK_LEN - 16, at=(8, 0, 0), axis=X))
    end_holes = [cyl(24, 9, at=(-0.5, 0, 0), axis=X), cyl(44, 9, at=(BLOCK_LEN - 8.5, 0, 0), axis=X)]
    # galerias de água/óleo: furos de parafuso do cabeçote
    bolt_holes = [cyl(6, 75, at=(bx, by, DECK - 75)) for bx, by in head_bolt_positions()]
    # galerias de óleo cegas (uma de cada lado, entre os cilindros e a parede externa)
    galleries = [cyl(2.5, 330.5, at=(-0.5, gy, 120), axis=X) for gy in (-47.0, 47.0)]
    return clean(cut(body, *bores, crank_cavity, *end_holes, *bolt_holes, *galleries))


def head_bolt_positions():
    xs = [20.0, 90.0, 180.0, 270.0, 340.0]
    return [(x, y) for y in (-57.0, 57.0) for x in xs]


def head_gasket() -> TopoDS_Shape:
    plate = box(0, BLOCK_LEN, -65, 65, DECK, DECK + GASKET)
    holes = [cyl(BORE_R, GASKET, at=(cx, 0, DECK)) for cx in CX]
    bolts = [cyl(6, GASKET, at=(bx, by, DECK)) for bx, by in head_bolt_positions()]
    return clean(cut(plate, *holes, *bolts))


def cylinder_head() -> TopoDS_Shape:
    z0 = DECK + GASKET
    body = box(0, BLOCK_LEN, -65, 65, z0, HEAD_TOP)
    cavity = box(8, BLOCK_LEN - 8, -48, 48, 255, HEAD_TOP)                      # câmara dos comandos (aberta em cima)
    chambers = [cyl(43, 10, at=(cx, 0, z0)) for cx in CX]                         # câmaras de combustão
    plug = [cyl(7.5, 255 - z0, at=(cx, 0, z0)) for cx in CX]                     # furo da vela
    guides = [cyl(4.0, 255 - z0, at=(cx + dx, y, z0)) for cx in CX for dx in (-17, 17) for y in (-20, 20)]
    bolts = [cyl(6, HEAD_TOP - z0, at=(bx, by, z0)) for bx, by in head_bolt_positions()]
    # dutos internos: do flange de cada coletor até a câmara de combustão (admissão em y<0, escape em y>0)
    ports = [cyl(8.0, 31, at=(cx, -65.5, PORT_Z), axis=Y) for cx in CX] + \
            [cyl(7.0, 31, at=(cx, 34.5, PORT_Z), axis=Y) for cx in CX]
    return clean(cut(body, cavity, *chambers, *plug, *guides, *bolts, *ports))


def valve_cover() -> TopoDS_Shape:
    shell = box(5, BLOCK_LEN - 5, -49, 49, HEAD_TOP, 352)
    inner = box(11, BLOCK_LEN - 11, -46.5, 46.5, HEAD_TOP - 1, 346)
    ports = [cyl(11, 75, at=(cx, 0, 290)) for cx in CX]                           # bocal de acesso às velas
    cam_holes = [cyl(12, 8, at=(4, cy, CAM_Z), axis=X) for cy in (-26.0, 26.0)]    # passagem dos eixos dos comandos
    return clean(cut(shell, inner, *ports, *cam_holes))


def oil_pan() -> TopoDS_Shape:
    shell = box(0, BLOCK_LEN, -SKIRT, SKIRT, -112, -45)
    inner = box(9, BLOCK_LEN - 9, -(SKIRT - 9), SKIRT - 9, -103, -44)
    return clean(cut(shell, inner))


def crankshaft() -> TopoDS_Shape:
    """Virabrequim: 5 mancais principais, 4 moentes, 8 braços com contrapesos, ponta dianteira e flange.

    Não há núcleo contínuo: entre os braços só existe o moente, para a biela poder girar em volta dele.
    """
    parts = [cyl(22, 74, at=(-66, 0, 0), axis=X)]                                   # ponta dianteira (polia)
    for m in (20.0, 90.0, 180.0, 270.0, 340.0):
        w = 12.0 if m in (20.0, 340.0) else 16.0
        parts.append(cyl(30, 2 * w, at=(m - w, 0, 0), axis=X))                     # mancais principais
    parts.append(cyl(22, 12, at=(352, 0, 0), axis=X))
    parts.append(cyl(42, 10, at=(354, 0, 0), axis=X))                              # flange do volante
    for cx, up in zip(CX, UP):
        zc = THROW if up else -THROW
        parts.append(cyl(25, 32, at=(cx - 16, 0, zc), axis=X))                     # moente (munhão da biela)
        for side in (-1, 1):
            xw = cx + side * 23 - 7
            web = fuse(cyl(28, 14, at=(xw, 0, 0), axis=X), cyl(28, 14, at=(xw, 0, zc), axis=X),
                       box(xw, xw + 14, -28, 28, min(0, zc), max(0, zc)))
            counter = cut(cyl(52, 14, at=(xw, 0, 0), axis=X),
                          box(xw - 1, xw + 15, -60, 60, 0 if up else -60, 60 if up else 0))   # só o lado oposto à manivela
            parts += [web, counter]
    return clean(fuse(*parts))


def connecting_rod() -> TopoDS_Shape:
    """Biela com o olhal maior (moente) em z=0 e o menor (pino) em z=ROD_LEN."""
    big = cut(cyl(33, 26, at=(-13, 0, 0), axis=X), cyl(25.3, 26, at=(-13, 0, 0), axis=X))
    small = cut(cyl(17, 28, at=(-14, 0, ROD_LEN), axis=X), cyl(PIN_R + 0.2, 28, at=(-14, 0, ROD_LEN), axis=X))
    beam = box(-7, 7, -13, 13, 30, ROD_LEN - 14)
    web = box(-2.5, 2.5, -18, 18, 30, ROD_LEN - 14)
    return clean(fuse(big, small, beam, web))


def piston() -> TopoDS_Shape:
    """Pistão com o centro do pino em z=0 (coroa em z=+30, saia até z=-32)."""
    r = BORE_R - 0.2
    body = cyl(r, 62, at=(0, 0, -32))
    grooves = [cut(cyl(r + 1, 2.6, at=(0, 0, z)), cyl(r - 2.2, 2.6, at=(0, 0, z))) for z in (24.0, 19.0, 14.0)]
    hollow = cyl(r - 5.3, 51.5, at=(0, 0, -33))
    bosses = [cyl(19.5, 24, at=(-38, 0, 0), axis=X), cyl(19.5, 24, at=(14, 0, 0), axis=X)]
    pin_hole = cyl(PIN_R, 80, at=(-40, 0, 0), axis=X)
    dish = cyl(26, 2.5, at=(0, 0, 27.5))
    return clean(cut(fuse(cut(body, *grooves, hollow, dish), *bosses), pin_hole))


def wrist_pin() -> TopoDS_Shape:
    return clean(cut(cyl(PIN_R, 68, at=(-34, 0, 0), axis=X), cyl(5.5, 68, at=(-34, 0, 0), axis=X)))


# Ordem de ignição 1-3-4-2: ângulo de manivela (0..720°) do PMS de explosão de cada cilindro; em θ=0 os pistões 1 e 4 estão no PMS
FIRE_DEG = [0.0, 540.0, 180.0, 360.0]

# ---- perfil do comando (V1.9): levantamento polinomial suave + seguidor de ROLETE; abertura derivada do contato rolete×came
CAM_Y = 26.0                                         # |y| dos eixos dos comandos
CAM_BASE_R = 12.0                                    # raio do círculo-base do comando
ROLL_R, ROLL_W = 6.0, 9.0                            # rolete do seguidor (na ponta da haste da válvula)
LIFT_H = 7.5                                         # levantamento máximo (mm)
PHI_H = math.radians(58.0)                           # meia-duração no comando (124° de comando = 248° de manivela)
VALVE_Y = 20.0                                       # |y| das válvulas (guias do cabeçote)
LASH = 0.1                                           # folga de válvula (mm)
ROLL_Z0 = CAM_Z - math.sqrt((CAM_BASE_R + ROLL_R) ** 2 - (CAM_Y - VALVE_Y) ** 2) - LASH   # centro do rolete com a válvula fechada
CAM_STEP = 0.5                                       # passo da tabela de levantamento (graus de comando)


FOOT_H = 0.4                                         # "pé" de ataque suave (mm): faz a válvula sair da folga com velocidade baixa
PHI_FOOT = math.radians(101.0)                        # meia-largura do pé (no comando)


def _bump(theta, height, phi):
    u = np.abs(theta) / phi
    inside = u < 1.0
    h = np.where(inside, height * (1.0 - u * u) ** 3, 0.0)
    dh = np.where(inside, height * 3.0 * (1.0 - u * u) ** 2 * (-2.0 * u) / phi * np.sign(theta), 0.0)
    return h, dh


def _lift_law(theta):
    """h(θ) e h'(θ) (θ a partir do nariz, rad): lóbulo principal H·(1-u²)³ + pé largo e baixo (rampa de folga), ambos C² nas pontas."""
    h1, d1 = _bump(theta, LIFT_H - FOOT_H, PHI_H)
    h2, d2 = _bump(theta, FOOT_H, PHI_FOOT)
    return h1 + h2, d1 + d2


def cam_curves(n: int = 1440):
    """(pitch, surface): curva de passo (centro do rolete) e superfície do came (deslocada para dentro de ROLL_R), como (n,2) em (y,z).

    Nariz voltado para baixo (-z) em θ=0; percurso anti-horário no plano (y, z).
    """
    th = np.linspace(-math.pi, math.pi, n, endpoint=False)
    h, dh = _lift_law(th)
    rho = CAM_BASE_R + ROLL_R + h
    pitch = np.stack([rho * np.sin(th), -rho * np.cos(th)], axis=1)
    ty = dh * np.sin(th) + rho * np.cos(th)
    tz = -dh * np.cos(th) + rho * np.sin(th)
    norm = np.hypot(ty, tz)
    n_out = np.stack([tz / norm, -ty / norm], axis=1)                 # à direita do sentido de percurso = para fora
    return pitch, pitch - ROLL_R * n_out


@functools.lru_cache(maxsize=None)
def cam_table(intake: bool) -> tuple:
    """Deslocamento da válvula (mm) em função do ângulo β do nariz (de "para baixo"), passo CAM_STEP.

    O centro do rolete fica sobre a reta vertical da válvula (a 6 mm do eixo do comando, lado conforme admissão/escape) e
    sobre a curva de passo: toma-se o ponto MAIS BAIXO dessa curva girada que cruza a reta. Deslocamento = descida em relação
    à posição de repouso (com a folga).
    """
    side = 1.0 if intake else -1.0
    e = side * (CAM_Y - VALVE_Y)
    pitch, _ = cam_curves()
    y0, z0 = pitch[:, 0], pitch[:, 1]
    rest = ROLL_Z0 - CAM_Z                                            # z do centro do rolete (relativo ao eixo) com folga
    out = []
    for k in range(int(round(360 / CAM_STEP))):
        b = math.radians(k * CAM_STEP)
        yy = y0 * math.cos(b) - z0 * math.sin(b)
        zz = y0 * math.sin(b) + z0 * math.cos(b)
        d = yy - e
        d2 = np.roll(d, -1)
        cross = np.flatnonzero(d * d2 < 0)
        zs = []
        for i in cross:
            t = d[i] / (d[i] - d2[i])
            zs.append(zz[i] + t * (np.roll(zz, -1)[i] - zz[i]))
        zlow = min(zs)
        out.append(float(max(0.0, rest - zlow)))
    return tuple(out)


def cam_peak(intake: bool) -> float:
    """β (graus) do máximo levantamento (média do platô, se houver)."""
    t = np.array(cam_table(intake))
    idx = np.flatnonzero(t >= t.max() - 1e-9)
    return float(np.mean(idx)) * CAM_STEP


def cam_lift(beta_deg: float, intake: bool) -> float:
    t = cam_table(intake)
    n = len(t)
    f = (beta_deg % 360.0) / CAM_STEP
    i = int(math.floor(f))
    fr = f - i
    return t[i % n] * (1 - fr) + t[(i + 1) % n] * fr


def valve_center_deg(cyl_index: int, intake: bool) -> float:
    """Ângulo de manivela (0..720) projetado para o máximo levantamento: meio do curso de admissão / de escape."""
    f = FIRE_DEG[cyl_index]
    return (f + 360.0 + 90.0) % 720.0 if intake else (f + 270.0) % 720.0


def nose_angle_deg(cyl_index: int, intake: bool) -> float:
    """Ângulo local do nariz do lóbulo no comando (a admissão gira +θ/2; o escape, movido por engrenagem, -θ/2)."""
    c = valve_center_deg(cyl_index, intake)
    return cam_peak(True) - c / 2.0 if intake else cam_peak(False) + c / 2.0


def valve_displacement(theta_deg: float, cyl: int, intake: bool) -> float:
    """Deslocamento (mm, para baixo) da válvula do cilindro ``cyl`` (0..3) com a manivela em theta_deg, derivado do lóbulo."""
    half = (theta_deg - valve_center_deg(cyl, intake)) / 2.0
    return cam_lift(cam_peak(True) + half if intake else cam_peak(False) - half, intake)


@functools.lru_cache(maxsize=None)
def _lobe_solid() -> TopoDS_Shape:
    """Lóbulo (extrudado ROLL_W ao longo de X a partir de x=0), nariz para baixo: spline fechada pela superfície do came."""
    from OCP.GeomAPI import GeomAPI_Interpolate
    from OCP.collections import HArray1_gp_Pnt as TColgp_HArray1OfPnt
    _, surf = cam_curves(240)
    arr = TColgp_HArray1OfPnt(1, len(surf))
    for i, (y, z) in enumerate(surf, start=1):
        arr.SetValue(i, gp_Pnt(0.0, float(y), float(z)))
    it = GeomAPI_Interpolate(arr, True, 1e-6)
    it.Perform()
    wire = BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(it.Curve()).Edge()).Wire()
    return BRepPrimAPI_MakePrism(BRepBuilderAPI_MakeFace(wire).Face(), gp_Vec(ROLL_W, 0, 0)).Shape()


def camshaft(intake: bool = True) -> TopoDS_Shape:
    """Comando com lóbulos de perfil suave, defasados conforme a ordem de ignição. Admissão: ponta até a roda da correia."""
    ext = (-32.0, 47.0) if intake else (-19.0, 34.0)
    parts = [cyl(10, BLOCK_LEN - 30, at=(15, 0, 0), axis=X), cyl(10, ext[1], at=(ext[0], 0, 0), axis=X)]
    lobe = _lobe_solid()
    for i, cx in enumerate(CX):
        rot = rotx(lobe, math.radians(nose_angle_deg(i, intake)))
        for dx in (-17, 17):
            parts.append(move(rot, (cx + dx - ROLL_W / 2, 0, 0)))
        parts.append(cyl(15, 6, at=(cx - 3, 0, 0), axis=X))                        # mancal
    return clean(fuse(*parts))


def valve(head_r: float) -> TopoDS_Shape:
    """Válvula com o prato em z=0, retentor da mola em z=64..66,5 e haste até o rolete (eixo ao longo de X) que toca o comando."""
    zc = ROLL_Z0 - (DECK + GASKET + 1.0)
    return clean(fuse(cyl(head_r, 2.5, at=(0, 0, 0)), cone(head_r, 3.5, 5, at=(0, 0, 2.5)),
                      cyl(3.5, zc, at=(0, 0, 0)), cyl(8.5, 2.5, at=(0, 0, 64)),
                      cyl(ROLL_R, ROLL_W, at=(-ROLL_W / 2, 0, zc), axis=X)))


SPRING_Z0 = 255.0   # assento da mola: piso da câmara dos comandos
SPRING_Z1 = DECK + GASKET + 1.0 + 64.0                        # face inferior do retentor da válvula (z=285)


def coil_spring(r_mean=7.5, wire_r=1.5, z0=SPRING_Z0, z1=SPRING_Z1, turns=6.0) -> TopoDS_Shape:
    """Mola helicoidal (fio circular varrido em hélice), de z0 a z1 com o eixo em (0,0).

    O fio encosta no assento em z0 e no retentor em z1 (contato tangente, sem sobreposição).
    """
    pitch = (z1 - z0 - 2 * wire_r) / turns
    surf = Geom_CylindricalSurface(gp_Ax3(gp_Pnt(0, 0, z0 + wire_r), gp_Dir(0, 0, 1)), r_mean)
    step = math.hypot(2 * math.pi, pitch)
    line = Geom2d_Line(gp_Pnt2d(0, 0), gp_Dir2d(2 * math.pi, pitch))
    edge = BRepBuilderAPI_MakeEdge(line, surf, 0.0, turns * step).Edge()
    BRepLib.BuildCurves3d_s(edge, 1e-6, GeomAbs_Shape.GeomAbs_C1, 14, 400)
    spine = BRepBuilderAPI_MakeWire(edge).Wire()
    tangent = gp_Dir(0, 2 * math.pi * r_mean, pitch)                   # direção do fio no ponto inicial (r_mean, 0, z0+wire_r)
    circ = gp_Circ(gp_Ax2(gp_Pnt(r_mean, 0, z0 + wire_r), tangent), wire_r)
    profile = BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(circ).Edge()).Wire()
    pipe = BRepOffsetAPI_MakePipeShell(spine)
    pipe.SetMode(gp_Dir(0, 0, 1))                                      # modo binormal: mantém a orientação ao longo da hélice
    pipe.Add(profile)
    pipe.Build()
    pipe.MakeSolid()
    return pipe.Shape()


# ------------------------------------------------------------ correia dentada (V1.9: dentes, 2:1 exato)
N_IDLER, IDLER_Y, IDLER_Z = 18, 60.0, 165.0   # roda tensora dentada (apoio fixo, lado +y, encosta na face de dentes)
N_CRANK, N_CAM = 20, 40                   # dentes da roda do virabrequim e da roda do comando de admissão (2:1 exato)
BELT_X0, BELT_W = -29.0, 8.0              # correia entre x=-29 e x=-21
SPROCKET_X0, SPROCKET_W = -30.0, 10.0     # rodas dentadas entre x=-30 e x=-20
GEAR_X0, GEAR_W, GEAR_R = -19.0, 8.0, 25.8  # engrenagens que ligam os dois comandos (x=-19..-11)
TOOTH_H, TOOTH_W, GROOVE_W = 3.0, 4.6, 5.0
BELT_T = 3.0


@functools.lru_cache(maxsize=None)
def belt_design() -> dict:
    """Passo da correia resolvido para que o comprimento seja um número inteiro de passos (dentes) e as rodas tenham 2:1."""
    def build(p):
        rc, rm, ri = N_CRANK * p / (2 * math.pi), N_CAM * p / (2 * math.pi), N_IDLER * p / (2 * math.pi)
        return rc, rm, ri, hull_path([(0.0, 0.0, rc), (IDLER_Y, IDLER_Z, ri), (-CAM_Y, CAM_Z, rm)])
    m = 100
    lo, hi = 8.5, 10.5
    f = lambda p: build(p)[3].length - m * p  # noqa: E731
    for _ in range(100):
        mid = (lo + hi) / 2
        lo, hi = (lo, mid) if f(lo) * f(mid) <= 0 else (mid, hi)
    p = (lo + hi) / 2
    rc, rm, ri, path = build(p)
    s0 = [k * p for k in range(m)]
    # fase das ranhuras: um dente de referência em cada arco (arcos: 1 = roda tensora, 3 = comando, 5 = virabrequim)
    starts, acc = [], 0.0
    for pc in path.pieces:
        starts.append(acc)
        acc += pc["len"]
    def ref_angle(piece_idx, center):
        a0, ln = starts[piece_idx], path.pieces[piece_idx]["len"]
        sk = next(x for x in s0 if a0 + 1e-6 < x < a0 + ln - 1e-6)
        pt = path.at(sk)[0]
        return math.atan2(pt[1] - center[1], pt[0] - center[0])
    return {"p": p, "m": m, "rc": rc, "rm": rm, "ri": ri, "path": path, "s0": s0, "i_idler": 1, "i_cam": 3, "i_crank": 5,
            "phi_crank": ref_angle(5, (0.0, 0.0)), "phi_cam": ref_angle(3, (-CAM_Y, CAM_Z)),
            "phi_idler": ref_angle(1, (IDLER_Y, IDLER_Z))}


def poly_prism(points_yz, x0: float, length: float) -> TopoDS_Shape:
    """Prisma (ao longo de X, de x0 a x0+length) de um polígono fechado dado por [(y, z), ...]."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakePolygon
    mk = BRepBuilderAPI_MakePolygon()
    for y, z in points_yz:
        mk.Add(gp_Pnt(x0, float(y), float(z)))
    mk.Close()
    return BRepPrimAPI_MakePrism(BRepBuilderAPI_MakeFace(mk.Wire()).Face(), gp_Vec(length, 0, 0)).Shape()


# perfil trapezoidal (tipo HTD simplificado) do dente da correia e da ranhura; h = distância ao círculo primitivo (+ = para o centro)
TOOTH_BASE_W, TOOTH_TIP_W = 5.4, 3.6
TOOTH_H0, TOOTH_H1 = -TOOTH_H / 2 + 0.15, TOOTH_H / 2 - 0.10        # base (lado da correia) e ponta do dente
GROOVE_CLR = 0.3                                                    # folga lateral dente/ranhura


def _tooth_halfwidth(h: float, extra: float = 0.0) -> float:
    """Meia-largura do dente na profundidade h (linear entre a base e a ponta), mais ``extra``."""
    return 0.5 * (TOOTH_TIP_W + (TOOTH_BASE_W - TOOTH_TIP_W) * (TOOTH_H1 - h) / (TOOTH_H1 - TOOTH_H0)) + extra


def sprocket(n: int, r_pitch: float, bore: float, phi_ref: float) -> TopoDS_Shape:
    """Roda dentada: perfil com ranhuras trapezoidais (n), alinhadas à fase ``phi_ref``, e flanges laterais."""
    r_out = r_pitch + TOOTH_H / 2
    step = 2 * math.pi / n
    h_top, h_bot = -TOOTH_H / 2, TOOTH_H / 2          # da superfície externa até o fundo da ranhura (h>0 vai para o centro)
    pts = []
    for j in range(n):
        phi = phi_ref + j * step                       # ângulo polar do eixo da ranhura j
        er, et = math.cos(phi), math.sin(phi)          # radial (y,z) e tangencial anti-horário
        tr, tt = -et, er
        def at_(r, t):
            return (r * er + t * tr, r * et + t * tt)
        wt = _tooth_halfwidth(h_top, GROOVE_CLR)
        wb = _tooth_halfwidth(h_bot, GROOVE_CLR)
        # entra na ranhura pelo lado de menor t (sentido anti-horário): topo -> fundo -> fundo -> topo
        def top(t):                                    # ponto da boca da ranhura EXATAMENTE no raio externo (sem estourar o círculo)
            a = phi + math.atan2(t, r_out)
            return (r_out * math.cos(a), r_out * math.sin(a))
        pts += [top(-wt), at_(r_pitch - h_bot, -wb), at_(r_pitch - h_bot, wb), top(wt)]
        # terra entre ranhuras: arco no raio externo
        a0 = math.atan2(wt, r_out)
        a1 = step - a0
        k = 4
        for i in range(1, k):
            a = a0 + (a1 - a0) * i / k
            pts.append((r_out * math.cos(phi + a), r_out * math.sin(phi + a)))
    teeth = poly_prism(pts, BELT_X0, BELT_W)
    flange_r = r_out + 2.5
    fl = [cyl(flange_r, 1.0, at=(SPROCKET_X0, 0, 0), axis=X), cyl(flange_r, 1.0, at=(BELT_X0 + BELT_W, 0, 0), axis=X)]
    return clean(cut(fuse(teeth, *fl), cyl(bore, SPROCKET_W, at=(SPROCKET_X0, 0, 0), axis=X)))


GEAR_Z, GEAR_M, GEAR_ALPHA = 26, 2.0, math.radians(20.0)     # engrenagens dos comandos: módulo 2, 26 dentes, pressão 20° (passo 52 = distância entre eixos)
GEAR_ROOT_R = 0.30                                           # raio de concordância no pé do dente (mm; < folga de cabeça 0,5 mm)
GEAR_BACKLASH = 0.10                                         # redução da espessura do dente no círculo primitivo (mm)


def _inv(a: float) -> float:
    return math.tan(a) - a


def gear(second: bool = False) -> TopoDS_Shape:
    """Engrenagem cilíndrica de dentes retos com perfil de EVOLVENTE (módulo 2, 26 dentes), centrada na origem.

    ``second=False``: dentes em jδ (a partir de +y, anti-horário); ``second=True``: defasada de π+δ/2 para engrenar com a primeira
    com centros em y=∓26. Pé do dente com concordância de 0,3 mm (menor que a folga de cabeça de 0,5 mm).
    """
    m, z, al = GEAR_M, GEAR_Z, GEAR_ALPHA
    rp, rb = m * z / 2, m * z / 2 * math.cos(al)
    ra, rf = rp + m, rp - 1.25 * m
    delta = 2 * math.pi / z
    s = math.pi * m / 2 - GEAR_BACKLASH
    half_p = s / (2 * rp)

    def half_ang(r):                                          # meia espessura angular do dente no raio r (r >= rb)
        return half_p + _inv(al) - _inv(math.acos(min(1.0, rb / r)))

    rs = np.linspace(max(rb, rf), ra, 9)
    phi0 = (math.pi + delta / 2) if second else 0.0
    pts = []
    for j in range(z):
        c = phi0 + j * delta
        if rf < rb:                                           # arredondamento do pé + trecho radial até a circunferência de base
            th0 = c - half_ang(rb)
            for t in np.linspace(math.pi, math.pi / 2, 6):
                r_ = rf + GEAR_ROOT_R + GEAR_ROOT_R * math.cos(t)
                a_ = th0 + (-GEAR_ROOT_R + GEAR_ROOT_R * math.sin(t)) / r_
                pts.append((r_ * math.cos(a_), r_ * math.sin(a_)))
        for r in rs:                                          # flanco esquerdo (subindo)
            a = c - half_ang(r)
            pts.append((r * math.cos(a), r * math.sin(a)))
        a_l, a_r = c - half_ang(ra), c + half_ang(ra)
        for i in (1, 2):                                      # topo
            a = a_l + (a_r - a_l) * i / 3
            pts.append((ra * math.cos(a), ra * math.sin(a)))
        for r in rs[::-1]:                                    # flanco direito (descendo)
            a = c + half_ang(r)
            pts.append((r * math.cos(a), r * math.sin(a)))
        fil = GEAR_ROOT_R / rf if rf < rb else 0.0
        if rf < rb:
            th1 = c + half_ang(rb)
            for t in np.linspace(math.pi / 2, math.pi, 6):
                r_ = rf + GEAR_ROOT_R + GEAR_ROOT_R * math.cos(t)
                a_ = th1 + (GEAR_ROOT_R - GEAR_ROOT_R * math.sin(t)) / r_
                pts.append((r_ * math.cos(a_), r_ * math.sin(a_)))
        nxt = c + delta - half_ang(rb if rf < rb else rf) - fil    # fundo até o início do arredondamento do próximo dente
        a_start = c + half_ang(rb if rf < rb else rf) + fil
        for i in range(1, 3):
            a = a_start + (nxt - a_start) * i / 3
            pts.append((rf * math.cos(a), rf * math.sin(a)))
    body = poly_prism(pts, GEAR_X0, GEAR_W)
    return clean(cut(body, cyl(10.2, GEAR_W, at=(GEAR_X0, 0, 0), axis=X)))


def belt_tooth() -> TopoDS_Shape:
    """Dente trapezoidal; z local aponta para dentro (para a roda), origem no círculo primitivo."""
    pts = [(-_tooth_halfwidth(TOOTH_H0), TOOTH_H0), (_tooth_halfwidth(TOOTH_H0), TOOTH_H0),
           (_tooth_halfwidth(TOOTH_H1), TOOTH_H1), (-_tooth_halfwidth(TOOTH_H1), TOOTH_H1)]
    return poly_prism(pts, BELT_X0, BELT_W)


def _hull_face(circles, extra: float):
    """Contorno convexo (no plano y-z, em x=BELT_X0) que envolve os círculos [(y, z, r)] em sentido anti-horário."""
    n = len(circles)
    tang = []      # para cada par (i -> i+1): ângulo da normal externa, pontos de tangência
    for i in range(n):
        ay, az, ra = circles[i]
        by, bz, rb = circles[(i + 1) % n]
        ra, rb = ra + extra, rb + extra
        dy, dz = by - ay, bz - az
        L = math.hypot(dy, dz)
        uy, uz = dy / L, dz / L
        vy, vz = uz, -uy                                    # perpendicular à direita (lado de fora no sentido anti-horário)
        k = (ra - rb) / L
        c = math.sqrt(1 - k * k)
        ny, nz = k * uy + c * vy, k * uz + c * vz
        tang.append(((ay + ra * ny, az + ra * nz), (by + rb * ny, bz + rb * nz), (ny, nz)))
    edges = []
    for i in range(n):
        (p1, p2, _) = tang[i]
        edges.append(BRepBuilderAPI_MakeEdge(gp_Pnt(BELT_X0, *p1), gp_Pnt(BELT_X0, *p2)).Edge())
        cy_, cz_, r_ = circles[(i + 1) % n]
        nxt = tang[(i + 1) % n]
        circ = gp_Circ(gp_Ax2(gp_Pnt(BELT_X0, cy_, cz_), gp_Dir(1, 0, 0), gp_Dir(0, 1, 0)), r_ + extra)
        arc = GC_MakeArcOfCircle(circ, gp_Pnt(BELT_X0, *p2), gp_Pnt(BELT_X0, *nxt[0]), True).Value()
        edges.append(BRepBuilderAPI_MakeEdge(arc).Edge())
    mk = BRepBuilderAPI_MakeWire()
    for e in edges:
        mk.Add(e)
    return BRepBuilderAPI_MakeFace(mk.Wire()).Face()


def timing_belt() -> TopoDS_Shape:
    """Faixa fechada da correia (sem dentes; os dentes são peças separadas) em volta das rodas do virabrequim e do comando."""
    d = belt_design()
    circles = [(0.0, 0.0, d["rc"]), (IDLER_Y, IDLER_Z, d["ri"]), (-CAM_Y, CAM_Z, d["rm"])]
    outer = BRepPrimAPI_MakePrism(_hull_face(circles, TOOTH_H / 2 + BELT_T), gp_Vec(BELT_W, 0, 0)).Shape()
    inner = BRepPrimAPI_MakePrism(_hull_face(circles, TOOTH_H / 2), gp_Vec(BELT_W, 0, 0)).Shape()
    return clean(cut(outer, inner))


def tensioner_pin() -> TopoDS_Shape:
    """Eixo do tensor com cabeça (centrado na origem, ao longo de X: da cabeça em x=-38 até o suporte em x=-6)."""
    return clean(fuse(cyl(4.0, 32, at=(-38, 0, 0), axis=X), cyl(7.0, 4, at=(-38, 0, 0), axis=X)))


def tensioner_bracket() -> TopoDS_Shape:
    """Suporte do tensor: placa aparafusada na face frontal do cabeçote/bloco (x=-6..0) com um cubo para o eixo."""
    plate = box(-6, 0, -26, 26, -26, 26)
    boss = cyl(10.0, 6, at=(-6, 0, 0), axis=X)
    return clean(fuse(plate, boss))


def spark_plug() -> TopoDS_Shape:
    """Vela com a ponta em z=0: rosca r 6,8 (33), sextavado r 9,5 (16), isolador r 5,5 (14) e terminal."""
    return clean(fuse(cyl(6.8, 33, at=(0, 0, 0)), cyl(9.5, 16, at=(0, 0, 33)),
                      cyl(5.5, 14, at=(0, 0, 49)), cyl(3, 5, at=(0, 0, 63))))


def flywheel() -> TopoDS_Shape:
    disc = cyl(150, 30, at=(364, 0, 0), axis=X)
    pocket = cut(cyl(138, 12, at=(382, 0, 0), axis=X), cyl(60, 12, at=(382, 0, 0), axis=X))
    hub = cyl(42.0, 30, at=(364, 0, 0), axis=X)
    return clean(cut(disc, pocket, hub))


def pulley() -> TopoDS_Shape:
    body = cyl(70, 24, at=(-58, 0, 0), axis=X)
    grooves = [cut(cyl(71, 2.5, at=(-54 + i * 6, 0, 0), axis=X), cyl(65, 2.5, at=(-54 + i * 6, 0, 0), axis=X)) for i in range(3)]
    return clean(cut(body, cyl(22.2, 24, at=(-58, 0, 0), axis=X), *grooves))


def intake_manifold() -> TopoDS_Shape:
    zc, yp = 250.0, -150.0
    outer = [cyl(36, 300, at=(30, yp, zc), axis=X)]
    inner = [cyl(31, 300, at=(30, yp, zc), axis=X)]
    for cx in CX:
        outer += [cyl(22, 85, at=(cx, yp, zc), axis=Y), box(cx - 32, cx + 32, -72, -65, zc - 30, zc + 30)]
        inner.append(cyl(17, 90, at=(cx, yp, zc), axis=Y))
    inner += [cyl(5, 8, at=(cx + dx, -73, zc + dz), axis=Y) for cx in CX for dx in (-24, 24) for dz in (-24, 24)]
    flange = fuse(*outer)
    inlet = cyl(34, 60, at=(330, yp, zc), axis=X)
    return clean(cut(fuse(flange, inlet), *inner, cyl(29, 62, at=(330, yp, zc), axis=X)))


def exhaust_manifold() -> TopoDS_Shape:
    zc, yp = 245.0, 120.0
    outer, inner = [], []
    for cx in CX:
        outer += [cyl(20, 55, at=(cx, 65, zc), axis=Y), box(cx - 30, cx + 30, 65, 72, zc - 30, zc + 30)]
        inner.append(cyl(15, 56, at=(cx, 65, zc), axis=Y))
    outer.append(cyl(30, 340, at=(10, yp, zc), axis=X))
    outer.append(cyl(28, 70, at=(350, yp, zc), axis=X))
    inner.append(cyl(24, 340, at=(10, yp, zc), axis=X))
    inner.append(cyl(22, 72, at=(350, yp, zc), axis=X))
    return clean(cut(fuse(*outer), *inner))


def oil_filter() -> TopoDS_Shape:
    can = fuse(cyl(38, 88, at=(0, 0, 0), axis=Y), cyl(41, 8, at=(0, 0, 0), axis=Y))
    return clean(cut(can, cyl(9, 8, at=(0, 0, 0), axis=Y)))


def alternator() -> TopoDS_Shape:
    shell = cut(cyl(44, 92, at=(0, 0, 0), axis=X), cyl(38, 70, at=(10, 0, 0), axis=X))
    cap = cyl(40, 12, at=(92, 0, 0), axis=X)
    ear = box(10, 50, -12, 12, 34, 54)
    shaft = cyl(8, 30, at=(-30, 0, 0), axis=X)
    return clean(fuse(shell, cap, ear, shaft))


def head_bolt() -> TopoDS_Shape:
    return clean(fuse(cyl(6, 102, at=(0, 0, 0)), cyl(7.4, 2, at=(0, 0, 102)), cyl(7.0, 8, at=(0, 0, 104))))


# ------------------------------------------------------------------ montagem
def build_motor() -> RawNode:
    rod, pist, pin = connecting_rod(), piston(), wrist_pin()
    vin, vex = valve(16.0), valve(14.0)
    tooth = belt_tooth()
    plug, bolt = spark_plug(), head_bolt()

    def pin_z(up: bool) -> float:
        return THROW if up else -THROW

    structure = RawNode("Estrutura", children=[
        RawNode("Bloco do motor", shape=engine_block()),
        RawNode("Junta do cabecote", shape=head_gasket()),
        RawNode("Cabecote", shape=cylinder_head()),
        RawNode("Tampa de valvulas", shape=valve_cover()),
        RawNode("Carter de oleo", shape=oil_pan()),
        RawNode("Parafusos do cabecote", children=[
            RawNode("Parafuso do cabecote", shape=bolt, local_matrix=at(bx, by, HEAD_TOP - 102))
            for bx, by in head_bolt_positions()]),
    ])

    rotating = RawNode("Conjunto rotativo", children=[
        RawNode("Virabrequim", shape=crankshaft()),
        RawNode("Volante do motor", shape=flywheel()),
        RawNode("Polia do virabrequim", shape=pulley()),
        RawNode("Bielas", children=[
            RawNode("Biela", shape=rod, local_matrix=at(cx, 0, pin_z(up))) for cx, up in zip(CX, UP)]),
        RawNode("Pistoes", children=[
            RawNode("Pistao", shape=pist, local_matrix=at(cx, 0, pin_z(up) + ROD_LEN)) for cx, up in zip(CX, UP)]),
        RawNode("Pinos dos pistoes", children=[
            RawNode("Pino do pistao", shape=pin, local_matrix=at(cx, 0, pin_z(up) + ROD_LEN)) for cx, up in zip(CX, UP)]),
    ])

    z_valve = DECK + GASKET + 1.0
    spring_cache: dict = {}

    def spring_for(c: int, intake: bool):
        """Mola no estado de θ=0: comprimida do mesmo tanto que a válvula já foi empurrada pelo lóbulo."""
        d0 = round(valve_displacement(0.0, c, intake), 3)
        if d0 not in spring_cache:
            spring_cache[d0] = coil_spring(z1=SPRING_Z1 - d0)
        return spring_cache[d0]

    bd = belt_design()
    timing = RawNode("Comando de valvulas", children=[
        RawNode("Comando de admissao", shape=camshaft(True), local_matrix=at(0, -CAM_Y, CAM_Z)),
        RawNode("Comando de escape", shape=camshaft(False), local_matrix=at(0, CAM_Y, CAM_Z)),
        RawNode("Roda dentada do comando de admissao", shape=sprocket(N_CAM, bd["rm"], 10.2, bd["phi_cam"]),
                local_matrix=at(0, -CAM_Y, CAM_Z)),
        RawNode("Engrenagem do comando de admissao", shape=gear(False), local_matrix=at(0, -CAM_Y, CAM_Z)),
        RawNode("Engrenagem do comando de escape", shape=gear(True), local_matrix=at(0, CAM_Y, CAM_Z)),
        RawNode("Roda dentada do virabrequim", shape=sprocket(N_CRANK, bd["rc"], 22.2, bd["phi_crank"])),
        RawNode("Roda tensora dentada", shape=sprocket(N_IDLER, bd["ri"], 4.3, bd["phi_idler"]), local_matrix=at(0, IDLER_Y, IDLER_Z)),
        RawNode("Eixo do tensor", shape=tensioner_pin(), local_matrix=at(0, IDLER_Y, IDLER_Z)),
        RawNode("Suporte do tensor", shape=tensioner_bracket(), local_matrix=at(0, IDLER_Y, IDLER_Z)),
        RawNode("Correia dentada", shape=timing_belt()),
        RawNode("Dentes da correia", children=[
            RawNode("Dente da correia", shape=tooth, local_matrix=bd["path"].frame(sk)) for sk in bd["s0"]]),
        RawNode("Molas das valvulas de admissao", children=[
            RawNode("Mola de valvula de admissao", shape=spring_for(c, True), local_matrix=at(CX[c] + dx, -20, 0))
            for c in range(N_CYL) for dx in (-17, 17)]),
        RawNode("Molas das valvulas de escape", children=[
            RawNode("Mola de valvula de escape", shape=spring_for(c, False), local_matrix=at(CX[c] + dx, 20, 0))
            for c in range(N_CYL) for dx in (-17, 17)]),
        RawNode("Valvulas de admissao", children=[
            RawNode("Valvula de admissao", shape=vin, local_matrix=at(CX[c] + dx, -20, z_valve - valve_displacement(0.0, c, True)))
            for c in range(N_CYL) for dx in (-17, 17)]),
        RawNode("Valvulas de escape", children=[
            RawNode("Valvula de escape", shape=vex, local_matrix=at(CX[c] + dx, 20, z_valve - valve_displacement(0.0, c, False)))
            for c in range(N_CYL) for dx in (-17, 17)]),
    ])
    ignition = RawNode("Ignicao", children=[
        RawNode("Vela de ignicao", shape=plug, local_matrix=at(cx, 0, 229)) for cx in CX])
    air = RawNode("Admissao e escape", children=[
        RawNode("Coletor de admissao", shape=intake_manifold()),
        RawNode("Coletor de escape", shape=exhaust_manifold()),
    ])
    accessories = RawNode("Perifericos", children=[
        RawNode("Filtro de oleo", shape=oil_filter(), local_matrix=at(110, SKIRT, -5)),
        RawNode("Alternador", shape=alternator(), local_matrix=at(-166, -95, 40)),
    ])
    return RawNode("Motor 4 cilindros", children=[structure, rotating, timing, ignition, air, accessories])


def write(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    CadEngine().write_step([build_motor()], path)
    return path


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "samples" / "motor_4_cilindros.step"
    print("Gerado:", write(out))
