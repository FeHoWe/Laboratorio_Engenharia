"""Biblioteca de peças paramétricas de engenharia (V2.2): fixadores, rolamentos, engrenagens, perfis, molas, flanges…

Cada peça é um sólido B-rep REAL (OpenCascade), gerado a partir de parâmetros; a origem e o eixo de cada peça estão descritos em ``note``.
Honestidade: as dimensões dos fixadores seguem tabelas ISO usuais (ISO 4017/4762 cabeça, ISO 4032 porca, ISO 7089 arruela) e servem para
MONTAGEM/VISUALIZAÇÃO; roscas NÃO são modeladas (haste lisa); rolamentos são simplificados (anéis e esferas, sem gaiola nem vedação);
engrenagens são de dentes retos com perfil de evolvente sem correção de perfil. Nenhum material é atribuído automaticamente.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from samples import geo as g


@dataclass
class Param:
    key: str
    label: str
    default: float
    lo: float
    hi: float
    unit: str = "mm"
    decimals: int = 2


@dataclass
class PartDef:
    key: str
    title: str
    category: str
    params: list[Param]
    build: Callable[..., object]
    note: str = ""

    def defaults(self) -> dict:
        return {p.key: p.default for p in self.params}

    def make(self, **kw):
        vals = self.defaults()
        for k, v in kw.items():
            if k not in vals:
                raise KeyError(f"Parâmetro desconhecido '{k}' para {self.key}")
            vals[k] = v
        for p in self.params:
            if not (p.lo <= vals[p.key] <= p.hi):
                raise ValueError(f"{self.title}: '{p.label}' deve estar entre {p.lo:g} e {p.hi:g} {p.unit}")
        return self.build(**vals)


# ------------------------------------------------------------------ tabelas ISO (métricas, passo grosso)
METRIC = {  # d: (s chave sextavado, k cabeça sextavada, m porca, dk cabeça Allen, s Allen, arruela d1, d2, h)
    3: (5.5, 2.0, 2.4, 5.5, 2.5, 3.2, 7.0, 0.5),
    4: (7.0, 2.8, 3.2, 7.0, 3.0, 4.3, 9.0, 0.8),
    5: (8.0, 3.5, 4.7, 8.5, 4.0, 5.3, 10.0, 1.0),
    6: (10.0, 4.0, 5.2, 10.0, 5.0, 6.4, 12.0, 1.6),
    8: (13.0, 5.3, 6.8, 13.0, 6.0, 8.4, 16.0, 1.6),
    10: (16.0, 6.4, 8.4, 16.0, 8.0, 10.5, 20.0, 2.0),
    12: (18.0, 7.5, 10.8, 18.0, 10.0, 13.0, 24.0, 2.5),
    14: (21.0, 8.8, 12.8, 21.0, 12.0, 15.0, 28.0, 2.5),
    16: (24.0, 10.0, 14.8, 24.0, 14.0, 17.0, 30.0, 3.0),
    20: (30.0, 12.5, 18.0, 30.0, 17.0, 21.0, 37.0, 3.0),
    24: (36.0, 15.0, 21.5, 36.0, 19.0, 25.0, 44.0, 4.0),
}


def _metric(d: float) -> tuple:
    key = min(METRIC, key=lambda k: abs(k - d))
    if abs(key - d) > 0.01:
        raise ValueError(f"Diâmetro M{d:g} fora da tabela (use {', '.join(f'M{k}' for k in METRIC)}).")
    return METRIC[key]


def _hexagon(across_flats: float):
    r = across_flats / math.sqrt(3)                       # raio circunscrito
    return [(r * math.cos(math.pi / 6 + i * math.pi / 3), r * math.sin(math.pi / 6 + i * math.pi / 3)) for i in range(6)]


# ------------------------------------------------------------------ fixadores
def hex_bolt(d, length):
    s, k, *_ = _metric(d)
    head = g.extrude(_hexagon(s), "xy", 0.0, k)
    shank = g.cyl(d / 2, length, at=(0, 0, -length))
    return g.clean(g.fuse(head, shank))


def socket_bolt(d, length):
    _, _, _, dk, ss, *_ = _metric(d)
    head = g.cyl(dk / 2, d, at=(0, 0, 0))
    socket = g.extrude(_hexagon(ss), "xy", d * 0.4, d)
    shank = g.cyl(d / 2, length, at=(0, 0, -length))
    return g.clean(g.cut(g.fuse(head, shank), socket))


def hex_nut(d):
    s, _, m, *_ = _metric(d)
    return g.clean(g.cut(g.extrude(_hexagon(s), "xy", 0.0, m), g.cyl(d / 2, m)))


def washer(d):
    *_, d1, d2, h = _metric(d)
    return g.clean(g.cut(g.cyl(d2 / 2, h), g.cyl(d1 / 2, h)))


# ------------------------------------------------------------------ rolamento rígido de esferas
def ball_bearing(bore, od, width):
    if od <= bore + 4:
        raise ValueError("Rolamento: D externo deve ser maior que o furo + 4 mm.")
    dm = (od + bore) / 2
    db = 0.30 * (od - bore)
    inner = g.cut(g.cyl(dm / 2 - db / 2 + 0.15, width), g.cyl(bore / 2, width))
    outer = g.cut(g.cyl(od / 2, width), g.cyl(dm / 2 + db / 2 - 0.15, width))
    n = max(6, int(math.pi * dm / (db * 1.30)))
    balls = [g.sphere(db / 2, at=(dm / 2 * math.cos(2 * math.pi * i / n), dm / 2 * math.sin(2 * math.pi * i / n), width / 2)) for i in range(n)]
    return g.fuse(inner, outer, *balls)


# ------------------------------------------------------------------ engrenagem de dentes retos (evolvente)
def spur_gear(module, teeth, width, bore, pressure_deg=20.0):
    z, m, al = int(teeth), module, math.radians(pressure_deg)
    if z < 12:
        raise ValueError("Engrenagem: use pelo menos 12 dentes (sem correção de perfil).")
    rp, rb = m * z / 2, m * z / 2 * math.cos(al)
    ra, rf = rp + m, rp - 1.25 * m
    if bore / 2 >= rf - 1.5 * m:
        raise ValueError("Engrenagem: furo grande demais para o diâmetro de pé.")
    inv = lambda a: math.tan(a) - a  # noqa: E731
    half_p = (math.pi * m / 2 - 0.04 * m) / (2 * rp)          # folga entre flancos ≈ 0,04·m (0,08·m na engrenagem acoplada)
    half = lambda r: half_p + inv(al) - inv(math.acos(min(1.0, rb / r)))  # noqa: E731
    r0 = max(rb, rf)
    rs = np.linspace(r0, ra, 9)
    delta = 2 * math.pi / z
    pts = []
    for j in range(z):
        c = j * delta
        if rf < rb:
            pts.append((rf * math.cos(c - half(rb)), rf * math.sin(c - half(rb))))
        for r in rs:
            pts.append((r * math.cos(c - half(r)), r * math.sin(c - half(r))))
        a_l, a_r = c - half(ra), c + half(ra)
        for i in (1, 2):
            a = a_l + (a_r - a_l) * i / 3
            pts.append((ra * math.cos(a), ra * math.sin(a)))
        for r in rs[::-1]:
            pts.append((r * math.cos(c + half(r)), r * math.sin(c + half(r))))
        if rf < rb:
            pts.append((rf * math.cos(c + half(rb)), rf * math.sin(c + half(rb))))
        a0, a1 = c + half(r0), c + delta - half(r0)
        for i in (1, 2):
            a = a0 + (a1 - a0) * i / 3
            pts.append((rf * math.cos(a), rf * math.sin(a)))
    body = g.extrude(pts, "xy", 0.0, width)
    return g.clean(g.cut(body, g.cyl(bore / 2, width)))


# ------------------------------------------------------------------ eixos, buchas, polias, discos
def stepped_shaft(d1, l1, d2, l2, d3, l3):
    prof, z = [(0.0, 0.0)], 0.0
    for d, l in ((d1, l1), (d2, l2), (d3, l3)):
        prof += [(z, d / 2), (z + l, d / 2)]
        z += l
    prof.append((z, 0.0))
    return g.revolve(prof, "z")


def bushing(od, idia, length):
    if idia >= od:
        raise ValueError("Bucha: diâmetro interno deve ser menor que o externo.")
    return g.clean(g.cut(g.cyl(od / 2, length), g.cyl(idia / 2, length)))


def v_pulley(od, bore, width):
    groove = width * 0.5
    prof = [(0.0, bore / 2), (0.0, od / 2), (width / 2 - groove / 2, od / 2), (width / 2, od / 2 - groove * 0.9),
            (width / 2 + groove / 2, od / 2), (width, od / 2), (width, bore / 2)]
    return g.revolve(prof, "z")


def brake_disc(od, idia, thickness, holes):
    disc = g.cut(g.cyl(od / 2, thickness), g.cyl(idia / 2, thickness))
    r_mid, hr = (od + idia) / 4, max(2.0, (od - idia) / 22)
    cutters = [g.cyl(hr, thickness, at=(r_mid * math.cos(2 * math.pi * i / holes), r_mid * math.sin(2 * math.pi * i / holes), 0))
               for i in range(int(holes))]
    return g.clean(g.cut(disc, *cutters))


def flange(od, bore, thickness, pcd, bolts, bolt_d):
    if pcd / 2 + bolt_d / 2 >= od / 2 or pcd / 2 - bolt_d / 2 <= bore / 2:
        raise ValueError("Flange: furos de parafuso devem ficar entre o furo central e a borda.")
    body = g.cut(g.cyl(od / 2, thickness), g.cyl(bore / 2, thickness))
    holes = [g.cyl(bolt_d / 2, thickness, at=(pcd / 2 * math.cos(2 * math.pi * i / bolts), pcd / 2 * math.sin(2 * math.pi * i / bolts), 0))
             for i in range(int(bolts))]
    return g.clean(g.cut(body, *holes))


# ------------------------------------------------------------------ chapas e perfis (comprimento ao longo de +X, seção em y-z)
def plate(length, width, thickness, hole_d, nx, ny, margin):
    body = g.box(0, length, 0, width, 0, thickness)
    if hole_d <= 0 or nx < 1 or ny < 1:
        return body
    xs = [margin + (length - 2 * margin) * (i / (nx - 1) if nx > 1 else 0.5) for i in range(int(nx))]
    ys = [margin + (width - 2 * margin) * (j / (ny - 1) if ny > 1 else 0.5) for j in range(int(ny))]
    return g.clean(g.cut(body, *[g.cyl(hole_d / 2, thickness, at=(x, y, 0)) for x in xs for y in ys]))


def rect_tube(length, w, h, t):
    if 2 * t >= min(w, h):
        raise ValueError("Tubo retangular: espessura grande demais.")
    return g.cut(g.box(0, length, -w / 2, w / 2, -h / 2, h / 2), g.box(0, length, -w / 2 + t, w / 2 - t, -h / 2 + t, h / 2 - t))


def round_tube(length, od, t):
    if 2 * t >= od:
        raise ValueError("Tubo redondo: espessura grande demais.")
    return g.cut(g.cyl(od / 2, length, axis=g.X), g.cyl(od / 2 - t, length, axis=g.X))


def i_beam(length, h, b, tw, tf):
    pts = [(-b / 2, -h / 2), (b / 2, -h / 2), (b / 2, -h / 2 + tf), (tw / 2, -h / 2 + tf), (tw / 2, h / 2 - tf), (b / 2, h / 2 - tf),
           (b / 2, h / 2), (-b / 2, h / 2), (-b / 2, h / 2 - tf), (-tw / 2, h / 2 - tf), (-tw / 2, -h / 2 + tf), (-b / 2, -h / 2 + tf)]
    return g.extrude(pts, "yz", 0.0, length)


def angle_bar(length, a, b, t):
    return g.extrude([(0, 0), (a, 0), (a, t), (t, t), (t, b), (0, b)], "yz", 0.0, length)


def u_channel(length, h, b, t):
    pts = [(0, 0), (b, 0), (b, t), (t, t), (t, h - t), (b, h - t), (b, h), (0, h)]
    return g.extrude(pts, "yz", 0.0, length)


# ------------------------------------------------------------------ mola helicoidal de compressão (eixo Z, base em z=0)
def compression_spring(wire_d, mean_d, turns, free_length):
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
    from OCP.BRepLib import BRepLib
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipeShell
    from OCP.Geom import Geom_CylindricalSurface
    from OCP.Geom2d import Geom2d_Line
    from OCP.GeomAbs import GeomAbs_Shape
    from OCP.gp import gp_Ax2, gp_Ax3, gp_Circ, gp_Dir, gp_Dir2d, gp_Pnt, gp_Pnt2d
    from OCP.gp import gp_Ax2  # noqa: F811
    r_mean, wire_r = mean_d / 2, wire_d / 2
    pitch = (free_length - wire_d) / turns
    if pitch <= wire_d:
        raise ValueError("Mola: comprimento livre pequeno demais (espiras se tocariam). Aumente o comprimento ou reduza as espiras.")
    surf = Geom_CylindricalSurface(gp_Ax3(gp_Pnt(0, 0, wire_r), gp_Dir(0, 0, 1)), r_mean)
    step = math.hypot(2 * math.pi, pitch)
    edge = BRepBuilderAPI_MakeEdge(Geom2d_Line(gp_Pnt2d(0, 0), gp_Dir2d(2 * math.pi, pitch)), surf, 0.0, turns * step).Edge()
    BRepLib.BuildCurves3d_s(edge, 1e-6, GeomAbs_Shape.GeomAbs_C1, 14, 400)
    spine = BRepBuilderAPI_MakeWire(edge).Wire()
    circ = gp_Circ(gp_Ax2(gp_Pnt(r_mean, 0, wire_r), gp_Dir(0, 2 * math.pi * r_mean, pitch)), wire_r)
    profile = BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(circ).Edge()).Wire()
    pipe = BRepOffsetAPI_MakePipeShell(spine)
    pipe.SetMode(gp_Dir(0, 0, 1))
    pipe.Add(profile)
    pipe.Build()
    pipe.MakeSolid()
    return pipe.Shape()


# ------------------------------------------------------------------ registro
def _P(key, label, default, lo, hi, unit="mm", dec=2):
    return Param(key, label, default, lo, hi, unit, dec)


_M = [_P("d", "Diâmetro nominal M", 8, 3, 24, "mm", 0)]
PARTS: dict[str, PartDef] = {p.key: p for p in [
    PartDef("parafuso_sextavado", "Parafuso sextavado (ISO 4017, haste lisa)", "Fixadores", _M + [_P("length", "Comprimento da haste", 30, 5, 300)],
            hex_bolt, "Cabeça em z=0…k; haste de z=-L a 0 (eixo Z). Rosca não modelada."),
    PartDef("parafuso_allen", "Parafuso de cabeça cilíndrica com sextavado interno (ISO 4762)", "Fixadores",
            _M + [_P("length", "Comprimento da haste", 30, 5, 300)], socket_bolt, "Cabeça em z=0…d; haste de z=-L a 0. Rosca não modelada."),
    PartDef("porca_sextavada", "Porca sextavada (ISO 4032)", "Fixadores", _M, hex_nut, "Eixo Z, de z=0 a m. Rosca interna não modelada."),
    PartDef("arruela_lisa", "Arruela lisa (ISO 7089)", "Fixadores", _M, washer, "Eixo Z, de z=0 a h."),
    PartDef("rolamento_esferas", "Rolamento rígido de esferas", "Rolamentos",
            [_P("bore", "Diâmetro interno d", 25, 5, 200), _P("od", "Diâmetro externo D", 52, 12, 400), _P("width", "Largura B", 15, 3, 100)],
            ball_bearing, "Eixo Z, de z=0 a B. Anéis + esferas fundidos (sem gaiola nem vedação). Ex.: 6205 = 25/52/15."),
    PartDef("engrenagem_reta", "Engrenagem cilíndrica de dentes retos (evolvente)", "Transmissão",
            [_P("module", "Módulo", 2, 0.5, 12, "mm", 2), _P("teeth", "Número de dentes", 24, 12, 150, "", 0), _P("width", "Largura", 15, 2, 150),
             _P("bore", "Furo", 20, 4, 200), _P("pressure_deg", "Ângulo de pressão", 20, 14.5, 25, "°", 1)],
            spur_gear, "Eixo Z, de z=0 a largura; sem correção de perfil nem arredondamento de pé."),
    PartDef("polia_v", "Polia em V simples", "Transmissão", [_P("od", "Diâmetro externo", 90, 30, 500), _P("bore", "Furo", 20, 5, 100), _P("width", "Largura", 24, 8, 100)],
            v_pulley, "Revolução em torno de Z. Perfil de canal simplificado."),
    PartDef("eixo_escalonado", "Eixo escalonado (3 trechos)", "Transmissão",
            [_P("d1", "Ø trecho 1", 25, 4, 200), _P("l1", "Comprimento 1", 40, 1, 600), _P("d2", "Ø trecho 2", 30, 4, 200),
             _P("l2", "Comprimento 2", 120, 1, 600), _P("d3", "Ø trecho 3", 25, 4, 200), _P("l3", "Comprimento 3", 40, 1, 600)],
            stepped_shaft, "Eixo Z, de z=0 ao comprimento total. Sem chavetas, rasgos ou chanfros."),
    PartDef("bucha", "Bucha / luva", "Transmissão", [_P("od", "Ø externo", 30, 4, 300), _P("idia", "Ø interno", 20, 2, 290), _P("length", "Comprimento", 25, 1, 400)],
            bushing, "Eixo Z."),
    PartDef("disco_freio", "Disco de freio ventilado por furos", "Transmissão",
            [_P("od", "Ø externo", 278, 100, 500), _P("idia", "Ø interno", 140, 30, 400), _P("thickness", "Espessura", 32, 4, 60), _P("holes", "Furos", 24, 0, 120, "", 0)],
            brake_disc, "Eixo Z; furos de resfriamento simplificados."),
    PartDef("flange", "Flange com furos de parafuso", "Estrutura",
            [_P("od", "Ø externo", 120, 40, 600), _P("bore", "Furo central", 50, 5, 400), _P("thickness", "Espessura", 12, 2, 60),
             _P("pcd", "Ø do círculo de furos", 90, 20, 560), _P("bolts", "Nº de furos", 6, 3, 24, "", 0), _P("bolt_d", "Ø dos furos", 9, 3, 40)],
            flange, "Eixo Z, de z=0 a espessura."),
    PartDef("chapa_furada", "Chapa retangular com furos", "Estrutura",
            [_P("length", "Comprimento (x)", 200, 10, 6000), _P("width", "Largura (y)", 100, 10, 6000), _P("thickness", "Espessura (z)", 6, 0.5, 100),
             _P("hole_d", "Ø dos furos (0 = sem)", 9, 0, 100), _P("nx", "Furos em x", 3, 0, 30, "", 0), _P("ny", "Furos em y", 2, 0, 30, "", 0),
             _P("margin", "Margem", 20, 3, 300)], plate, "Canto em (0,0,0); x=comprimento, y=largura, z=espessura."),
    PartDef("tubo_retangular", "Tubo retangular / quadrado", "Estrutura",
            [_P("length", "Comprimento", 1000, 10, 12000), _P("w", "Largura (y)", 40, 10, 400), _P("h", "Altura (z)", 40, 10, 400), _P("t", "Parede", 2.5, 0.8, 20)],
            rect_tube, "Comprimento ao longo de +X, seção centrada em (y,z)=0."),
    PartDef("tubo_redondo", "Tubo redondo", "Estrutura",
            [_P("length", "Comprimento", 1000, 10, 12000), _P("od", "Ø externo", 33.7, 6, 400), _P("t", "Parede", 3.2, 0.5, 30)],
            round_tube, "Comprimento ao longo de +X, eixo em y=z=0."),
    PartDef("viga_i", "Viga I (seção duplo T)", "Estrutura",
            [_P("length", "Comprimento", 1000, 10, 12000), _P("h", "Altura", 100, 20, 600), _P("b", "Largura da mesa", 55, 10, 300),
             _P("tw", "Alma", 4.1, 1, 30), _P("tf", "Mesa", 5.7, 1, 40)], i_beam, "Comprimento ao longo de +X, seção centrada. Sem raios de concordância."),
    PartDef("cantoneira", "Cantoneira (L)", "Estrutura",
            [_P("length", "Comprimento", 1000, 10, 12000), _P("a", "Aba horizontal", 50, 10, 300), _P("b", "Aba vertical", 50, 10, 300), _P("t", "Espessura", 5, 1, 30)],
            angle_bar, "Comprimento ao longo de +X; canto da seção em (y,z)=(0,0)."),
    PartDef("perfil_u", "Perfil U", "Estrutura",
            [_P("length", "Comprimento", 1000, 10, 12000), _P("h", "Altura", 80, 20, 400), _P("b", "Mesa", 45, 10, 200), _P("t", "Espessura", 5, 1, 30)],
            u_channel, "Comprimento ao longo de +X; canto da seção em (y,z)=(0,0)."),
    PartDef("mola_compressao", "Mola helicoidal de compressão", "Molas",
            [_P("wire_d", "Ø do fio", 3, 0.5, 30), _P("mean_d", "Ø médio", 20, 4, 300), _P("turns", "Espiras", 8, 2, 40, "", 1), _P("free_length", "Comprimento livre", 60, 5, 600)],
            compression_spring, "Eixo Z, de z=0 ao comprimento livre. Pontas sem esquadrejamento."),
]}
CATEGORIES = sorted({p.category for p in PARTS.values()}, key=lambda c: ["Fixadores", "Rolamentos", "Transmissão", "Estrutura", "Molas"].index(c))


def parts_in(category: str) -> list[PartDef]:
    return [p for p in PARTS.values() if p.category == category]
