"""Sketch 2D editável → sólido (extrusão) com furos automáticos por aninhamento.

Entidades (todas fechadas): {"t":"rect","x0","y0","x1","y1"}, {"t":"circle","cx","cy","r"}, {"t":"poly","pts":[[x,y],...]} (≥3 pontos, não se
autointersecta). Plano "XY"|"XZ"|"YZ" com `offset` ao longo da normal. Perfis contidos em OUTRO perfil viram FUROS (profundidade de aninhamento
ímpar subtrai); pares somam (ilha dentro de furo). Editável: add/modify/delete; `validate()` explica o que está errado; `area()` líquida exata.
LIMITES: sem restrições geométricas (paralelismo/tangência) nem cotas dirigidas — as cotas são os próprios números das entidades; sem arcos
livres (use círculo ou polígono). Perfis que se cruzam sem conter um ao outro são rejeitados.
"""
from __future__ import annotations

import math

from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon, BRepBuilderAPI_MakeWire
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.gp import gp_Ax2, gp_Circ, gp_Dir, gp_Pnt, gp_Vec

PLANOS = {"XY": ((0, 0, 1), lambda u, v, o: (u, v, o)), "XZ": ((0, -1, 0), lambda u, v, o: (u, o, v)), "YZ": ((1, 0, 0), lambda u, v, o: (o, u, v))}


class SketchError(ValueError):
    pass


def _poly_pts(e: dict) -> list:
    t = e["t"]
    if t == "rect":
        x0, x1 = sorted((e["x0"], e["x1"])); y0, y1 = sorted((e["y0"], e["y1"]))
        return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    if t == "poly":
        return [tuple(p) for p in e["pts"]]
    if t == "circle":
        return [(e["cx"] + e["r"] * math.cos(2 * math.pi * i / 96), e["cy"] + e["r"] * math.sin(2 * math.pi * i / 96)) for i in range(96)]
    raise SketchError(f"entidade desconhecida: {t}")


def _shoelace(p) -> float:
    return 0.5 * sum(p[i][0] * p[(i + 1) % len(p)][1] - p[(i + 1) % len(p)][0] * p[i][1] for i in range(len(p)))


def _inside(pt, poly) -> bool:
    x, y = pt; c = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % len(poly)]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c


def _segs_cross(a, b, c, d) -> bool:
    def o(p, q, r): return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    return o(a, b, c) * o(a, b, d) < 0 and o(c, d, a) * o(c, d, b) < 0


def _self_intersects(p) -> bool:
    n = len(p)
    for i in range(n):
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            if _segs_cross(p[i], p[(i + 1) % n], p[j], p[(j + 1) % n]):
                return True
    return False


class Sketch:
    def __init__(self, plane: str = "XY", offset: float = 0.0, entities: list | None = None):
        if plane not in PLANOS:
            raise SketchError("plano deve ser XY, XZ ou YZ")
        self.plane, self.offset, self.entities = plane, float(offset), [dict(e) for e in (entities or [])]

    # --- edição
    def add(self, **e) -> int:
        self._chk(e); self.entities.append(e); return len(self.entities) - 1

    def modify(self, i: int, **kw) -> None:
        old = dict(self.entities[i]); self.entities[i].update(kw)
        try:
            self._chk(self.entities[i])
        except SketchError:
            self.entities[i] = old; raise

    def delete(self, i: int) -> None:
        del self.entities[i]

    def to_dict(self) -> dict:
        return {"plane": self.plane, "offset": self.offset, "entities": [dict(e) for e in self.entities]}

    @classmethod
    def from_dict(cls, d: dict) -> "Sketch":
        return cls(d.get("plane", "XY"), d.get("offset", 0.0), d.get("entities", []))

    def _chk(self, e: dict) -> None:
        if e.get("t") == "circle" and not e.get("r", 0) > 0:
            raise SketchError("círculo: raio deve ser > 0")
        p = _poly_pts(e)
        if len(p) < 3:
            raise SketchError("polígono precisa de ≥ 3 pontos")
        if e["t"] != "circle" and _self_intersects(p):
            raise SketchError("polígono se autointersecta (gravata-borboleta)")
        if abs(_shoelace(p)) < 1e-12:
            raise SketchError("perfil com área nula")

    # --- topologia
    def _depth(self):
        polys = [_poly_pts(e) for e in self.entities]
        depth = []
        for i, p in enumerate(polys):
            d = 0
            for j, q in enumerate(polys):
                if i != j and abs(_shoelace(q)) > abs(_shoelace(p)) and _inside(p[0], q):
                    d += 1
            depth.append(d)
        return polys, depth

    def validate(self) -> None:
        if not self.entities:
            raise SketchError("sketch vazio")
        for e in self.entities:
            self._chk(e)
        polys, _ = self._depth()
        for i in range(len(polys)):
            for j in range(i + 1, len(polys)):
                a, b = polys[i], polys[j]
                if any(_segs_cross(a[k], a[(k + 1) % len(a)], b[m], b[(m + 1) % len(b)]) for k in range(len(a)) for m in range(len(b))):
                    raise SketchError(f"perfis {i} e {j} se cruzam sem um conter o outro")

    def area(self) -> float:
        """Área líquida (furos subtraem). Círculo usa πr² exato."""
        self.validate(); _, depth = self._depth(); tot = 0.0
        for e, d in zip(self.entities, depth):
            a = math.pi * e["r"] ** 2 if e["t"] == "circle" else abs(_shoelace(_poly_pts(e)))
            tot += a if d % 2 == 0 else -a
        return tot

    # --- geometria OCP
    def _face(self, e: dict):
        n, mp = PLANOS[self.plane]
        P = lambda u, v: gp_Pnt(*mp(u, v, self.offset))  # noqa: E731
        if e["t"] == "circle":
            ax = gp_Ax2(P(e["cx"], e["cy"]), gp_Dir(*n))
            w = BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(gp_Circ(ax, e["r"])).Edge()).Wire()
        else:
            mk = BRepBuilderAPI_MakePolygon()
            for u, v in _poly_pts(e):
                mk.Add(P(u, v))
            mk.Close(); w = mk.Wire()
        return BRepBuilderAPI_MakeFace(w, True).Face()

    def extrude(self, distance: float):
        """Sólido por extrusão ao longo da normal do plano (distance>0 no sentido +normal; <0 no oposto)."""
        if distance == 0:
            raise SketchError("distância de extrusão não pode ser 0")
        self.validate(); n, _ = PLANOS[self.plane]; _, depth = self._depth()
        vec = gp_Vec(*(c * distance for c in n))
        solid = None
        for e, d in sorted(zip(self.entities, depth), key=lambda x: x[1]):
            s = BRepPrimAPI_MakePrism(self._face(e), vec).Shape()
            if solid is None:
                solid = s
            else:
                alg = (BRepAlgoAPI_Fuse if d % 2 == 0 else BRepAlgoAPI_Cut)(solid, s)
                alg.Build()
                if not alg.IsDone():
                    raise SketchError("falha ao combinar perfis")
                solid = alg.Shape()
        return solid
