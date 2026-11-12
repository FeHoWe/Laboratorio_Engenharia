"""Primitivas geométricas (OpenCascade) compartilhadas pela biblioteca de peças e pelos projetos predefinidos. Unidades: mm.

Tudo é sólido B-rep real (sem malhas). Os nomes ficam sem acento nas peças dos projetos porque o STEP via OpenCascade perde acentos.
"""
from __future__ import annotations

import math
from typing import Sequence

import numpy as np

from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon, BRepBuilderAPI_Transform
from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections
from OCP.BRepPrimAPI import (BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCone, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakePrism,
                             BRepPrimAPI_MakeRevol, BRepPrimAPI_MakeSphere, BRepPrimAPI_MakeTorus)
from OCP.gp import gp_Ax1, gp_Ax2, gp_Dir, gp_GTrsf, gp_Pnt, gp_Trsf, gp_Vec
from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
from OCP.TopoDS import TopoDS_Shape

X, Y, Z = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)


def box(x0, x1, y0, y1, z0, z1) -> TopoDS_Shape:
    return BRepPrimAPI_MakeBox(gp_Pnt(min(x0, x1), min(y0, y1), min(z0, z1)), abs(x1 - x0), abs(y1 - y0), abs(z1 - z0)).Shape()


def cyl(r, length, at=(0, 0, 0), axis=Z) -> TopoDS_Shape:
    """Cilindro de raio r que começa em ``at`` e se estende ``length`` ao longo de ``axis``."""
    return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(*at), gp_Dir(*axis)), r, length).Shape()


def cone(r1, r2, h, at=(0, 0, 0), axis=Z) -> TopoDS_Shape:
    return BRepPrimAPI_MakeCone(gp_Ax2(gp_Pnt(*at), gp_Dir(*axis)), r1, r2, h).Shape()


def sphere(r, at=(0, 0, 0)) -> TopoDS_Shape:
    return BRepPrimAPI_MakeSphere(gp_Pnt(*at), r).Shape()


def torus(R, r, at=(0, 0, 0), axis=Z) -> TopoDS_Shape:
    return BRepPrimAPI_MakeTorus(gp_Ax2(gp_Pnt(*at), gp_Dir(*axis)), R, r).Shape()


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
    u = ShapeUpgrade_UnifySameDomain(shape, True, True, True)
    u.Build()
    return u.Shape()


def move(shape, v) -> TopoDS_Shape:
    t = gp_Trsf()
    t.SetTranslation(gp_Vec(*v))
    return BRepBuilderAPI_Transform(shape, t, True).Shape()


def rot(shape, axis, ang_rad, pivot=(0, 0, 0)) -> TopoDS_Shape:
    t = gp_Trsf()
    t.SetRotation(gp_Ax1(gp_Pnt(*pivot), gp_Dir(*axis)), ang_rad)
    return BRepBuilderAPI_Transform(shape, t, True).Shape()


def mirror_x(shape) -> TopoDS_Shape:
    """Espelho em relação ao plano x = 0 (peça do lado oposto)."""
    t = gp_Trsf()
    t.SetMirror(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(1, 0, 0)))
    return BRepBuilderAPI_Transform(shape, t, True).Shape()


def scale_xyz(shape, sx, sy, sz) -> TopoDS_Shape:
    g = gp_GTrsf()
    from OCP.gp import gp_Mat, gp_XYZ
    g.SetVectorialPart(gp_Mat(sx, 0, 0, 0, sy, 0, 0, 0, sz))
    from OCP.BRepBuilderAPI import BRepBuilderAPI_GTransform
    return BRepBuilderAPI_GTransform(shape, g, True).Shape()


def _unit(v):
    v = np.asarray(v, dtype=float)
    return v / np.linalg.norm(v)


def orient_z_to(shape, direction, origin=(0, 0, 0)) -> TopoDS_Shape:
    """Gira uma forma construída ao longo de +Z para apontar em ``direction`` e a leva a ``origin``."""
    d = _unit(direction)
    z = np.array([0.0, 0.0, 1.0])
    axis = np.cross(z, d)
    s = float(np.linalg.norm(axis))
    if s < 1e-12:
        out = shape if d[2] > 0 else rot(shape, X, math.pi)
    else:
        out = rot(shape, tuple(axis / s), math.atan2(s, float(np.dot(z, d))))
    return move(out, origin)


def tube(p1, p2, r, r_in: float = 0.0) -> TopoDS_Shape:
    """Barra cilíndrica (ou tubo, se ``r_in``>0) entre dois pontos."""
    p1, p2 = np.asarray(p1, float), np.asarray(p2, float)
    length = float(np.linalg.norm(p2 - p1))
    body = cyl(r, length)
    if r_in > 0:
        body = cut(body, cyl(r_in, length))
    return orient_z_to(body, p2 - p1, p1)


def polygon_face(points3d: Sequence[Sequence[float]]):
    mk = BRepBuilderAPI_MakePolygon()
    for p in points3d:
        mk.Add(gp_Pnt(*[float(c) for c in p]))
    mk.Close()
    return mk


def extrude(points2d, plane: str, offset: float, length: float, holes: Sequence = ()) -> TopoDS_Shape:
    """Prisma de um polígono 2D. ``plane``: 'xy' (extrusão em z), 'yz' (em x) ou 'xz' (em y); ``offset`` é a coordenada da face inicial."""
    def lift(p):
        a, b = p
        return {"xy": (a, b, offset), "yz": (offset, a, b), "xz": (a, offset, b)}[plane]
    vec = {"xy": gp_Vec(0, 0, length), "yz": gp_Vec(length, 0, 0), "xz": gp_Vec(0, length, 0)}[plane]
    face = BRepBuilderAPI_MakeFace(polygon_face([lift(p) for p in points2d]).Wire()).Face()
    body = BRepPrimAPI_MakePrism(face, vec).Shape()
    for h in holes:
        hole = BRepPrimAPI_MakePrism(BRepBuilderAPI_MakeFace(polygon_face([lift(p) for p in h]).Wire()).Face(), vec).Shape()
        body = cut(body, hole)
    return body


def revolve(profile, axis: str = "z", angle_deg: float = 360.0) -> TopoDS_Shape:
    """Sólido de revolução em torno de um eixo pela origem. ``profile`` = [(a, r), ...]: a ao longo do eixo e r radial (>=0)."""
    pts = [(r, 0.0, a) for a, r in profile]                       # plano XZ, eixo Z
    face = BRepBuilderAPI_MakeFace(polygon_face(pts).Wire()).Face()
    body = BRepPrimAPI_MakeRevol(face, gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), math.radians(angle_deg)).Shape()
    if axis == "x":
        body = rot(body, Y, math.pi / 2)
    elif axis == "y":
        body = rot(body, X, -math.pi / 2)
    return body


def superellipse(width: float, height: float, n: float = 2.6, count: int = 36):
    """Pontos (a, b) de uma superelipse |a/w|^n+|b/h|^n=1 (n=2 elipse; n grande → retângulo arredondado)."""
    pts = []
    for i in range(count):
        t = 2 * math.pi * i / count
        c, s = math.cos(t), math.sin(t)
        pts.append((math.copysign(abs(c) ** (2 / n), c) * width / 2, math.copysign(abs(s) ** (2 / n), s) * height / 2))
    return pts


def loft(sections, smooth: bool = True) -> TopoDS_Shape:
    """Sólido por seções: cada seção é uma lista de pontos 3D (polígono fechado) com o MESMO número de pontos."""
    ts = BRepOffsetAPI_ThruSections(True, not smooth)
    for sec in sections:
        ts.AddWire(polygon_face(sec).Wire())
    ts.Build()
    return ts.Shape()


def loft_x(sections, smooth: bool = True) -> TopoDS_Shape:
    """Loft ao longo do eixo X: ``sections`` = [(x, width_y, height_z, yc, zc, n), ...]."""
    secs = []
    for x, w, h, yc, zc, n in sections:
        secs.append([(x, yc + a, zc + b) for a, b in superellipse(w, h, n)])
    return loft(secs, smooth)


def loft_y(sections, smooth: bool = True) -> TopoDS_Shape:
    """Loft ao longo de Y: ``sections`` = [(y, width_x, height_z, xc, zc, n), ...]."""
    secs = []
    for y, w, h, xc, zc, n in sections:
        secs.append([(xc + a, y, zc + b) for a, b in superellipse(w, h, n)])
    return loft(secs, smooth)


def airfoil(chord: float, thick: float = 0.12, camber: float = 0.04, pos: float = 0.4, n: int = 20):
    """Contorno (x, z) fechado de um perfil tipo NACA de 4 dígitos (ponta de fuga com espessura finita). x de 0 a ``chord``."""
    xs = [(1 - math.cos(math.pi * i / n)) / 2 for i in range(n + 1)]
    upper, lower = [], []
    for x in xs:
        yt = 5 * thick * (0.2969 * math.sqrt(x) - 0.1260 * x - 0.3516 * x ** 2 + 0.2843 * x ** 3 - 0.1015 * x ** 4)
        if camber > 0:
            if x < pos:
                yc = camber / pos ** 2 * (2 * pos * x - x * x)
                dyc = 2 * camber / pos ** 2 * (pos - x)
            else:
                yc = camber / (1 - pos) ** 2 * ((1 - 2 * pos) + 2 * pos * x - x * x)
                dyc = 2 * camber / (1 - pos) ** 2 * (pos - x)
        else:
            yc = dyc = 0.0
        th = math.atan(dyc)
        upper.append((x - yt * math.sin(th), yc + yt * math.cos(th)))
        lower.append((x + yt * math.sin(th), yc - yt * math.cos(th)))
    pts = upper + lower[::-1][:-1]
    return [(px * chord, pz * chord) for px, pz in pts]


def bbox(shape):
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    b = Bnd_Box()
    BRepBndLib.Add_s(shape, b)
    return (b.CornerMin().X(), b.CornerMin().Y(), b.CornerMin().Z()), (b.CornerMax().X(), b.CornerMax().Y(), b.CornerMax().Z())


def volume(shape) -> float:
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    p = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, p)
    return p.Mass()


def orient_x_to(shape, direction, origin=(0, 0, 0)) -> TopoDS_Shape:
    """Gira uma forma construída ao longo de +X para apontar em ``direction`` (sem rolagem controlada) e a leva a ``origin``."""
    d = _unit(direction)
    x = np.array([1.0, 0.0, 0.0])
    axis = np.cross(x, d)
    s = float(np.linalg.norm(axis))
    if s < 1e-12:
        out = shape if d[0] > 0 else rot(shape, Z, math.pi)
    else:
        out = rot(shape, tuple(axis / s), math.atan2(s, float(np.dot(x, d))))
    return move(out, origin)
