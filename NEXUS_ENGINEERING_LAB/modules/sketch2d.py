"""Sketch 2D editável → sólido (extrusão) com furos automáticos por aninhamento.

Entidades (todas fechadas): {"t":"rect","x0","y0","x1","y1"}, {"t":"circle","cx","cy","r"}, {"t":"poly","pts":[[x,y],...]} (≥3 pontos, não se
autointersecta). Plano "XY"|"XZ"|"YZ" com `offset` ao longo da normal. Perfis contidos em OUTRO perfil viram FUROS (profundidade de aninhamento
ímpar subtrai); pares somam (ilha dentro de furo). Editável: add/modify/delete; `validate()` explica o que está errado; `area()` líquida exata.
V3.6: entidades com ARCOS EXATOS — {"t":"rrect","x0","y0","x1","y1","r"} (retângulo de cantos arredondados) e {"t":"slot","cx0","cy0","cx1","cy1","w"}
(rasgo oblongo: dois semicírculos de largura w ligados por retas) — e RESTRIÇÕES aplicadas em sequência (`restricoes`): horizontal/vertical de um segmento
de polígono, comprimento de segmento, raio igual, concêntrico, ponto fixo. NÃO é um solver geral: cada restrição é aplicada na ordem e todas são
reverificadas no fim; conflito é reportado (SketchError), não resolvido. Arcos livres por 3 pontos continuam fora do escopo.
LIMITES: cotas dirigidas são os próprios números das entidades. Perfis que se cruzam sem conter um ao outro são rejeitados.
"""
from __future__ import annotations

import math

from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon, BRepBuilderAPI_MakeWire
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism, BRepPrimAPI_MakeRevol
from OCP.gp import gp_Ax1, gp_Ax2, gp_Circ, gp_Dir, gp_Pnt, gp_Vec

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
    if t == "rrect":
        x0, x1 = sorted((e["x0"], e["x1"])); y0, y1 = sorted((e["y0"], e["y1"])); r = e["r"]
        out = []
        for cx, cy, a0 in ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
            out += [(cx + r * math.cos(math.radians(a0 + 90 * k / 16)), cy + r * math.sin(math.radians(a0 + 90 * k / 16))) for k in range(17)]
        return out
    if t == "slot":
        (ax, ay), (bx, by), r = (e["cx0"], e["cy0"]), (e["cx1"], e["cy1"]), e["w"] / 2
        th = math.atan2(by - ay, bx - ax); out = []
        for c, a0 in (((bx, by), th - math.pi / 2), ((ax, ay), th + math.pi / 2)):
            out += [(c[0] + r * math.cos(a0 + math.pi * k / 32), c[1] + r * math.sin(a0 + math.pi * k / 32)) for k in range(33)]
        return out
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


def _area_exata(e: dict) -> float:
    t = e["t"]
    if t == "circle": return math.pi * e["r"] ** 2
    if t == "rrect": return abs(e["x1"] - e["x0"]) * abs(e["y1"] - e["y0"]) - (4 - math.pi) * e["r"] ** 2
    if t == "slot": return math.hypot(e["cx1"] - e["cx0"], e["cy1"] - e["cy0"]) * e["w"] + math.pi * (e["w"] / 2) ** 2
    return abs(_shoelace(_poly_pts(e)))


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
        if e.get("t") == "rrect":
            w, h = abs(e["x1"] - e["x0"]), abs(e["y1"] - e["y0"])
            if not (e.get("r", 0) > 0 and 2 * e["r"] <= min(w, h) + 1e-12):
                raise SketchError("retângulo arredondado: 0 < r ≤ metade do menor lado")
        if e.get("t") == "slot":
            if not e.get("w", 0) > 0 or math.hypot(e["cx1"] - e["cx0"], e["cy1"] - e["cy0"]) <= 0:
                raise SketchError("rasgo: largura > 0 e centros distintos")
        p = _poly_pts(e)
        if len(p) < 3:
            raise SketchError("polígono precisa de ≥ 3 pontos")
        if e["t"] not in ("circle", "rrect", "slot") and _self_intersects(p):
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
            a = _area_exata(e)
            tot += a if d % 2 == 0 else -a
        return tot

    # --- geometria OCP
    def _face(self, e: dict):
        n, mp = PLANOS[self.plane]
        P = lambda u, v: gp_Pnt(*mp(u, v, self.offset))  # noqa: E731
        if e["t"] in ("rrect", "slot"):
            return BRepBuilderAPI_MakeFace(self._wire_arcos(e, P), True).Face()
        if e["t"] == "circle":
            ax = gp_Ax2(P(e["cx"], e["cy"]), gp_Dir(*n))
            w = BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(gp_Circ(ax, e["r"])).Edge()).Wire()
        else:
            mk = BRepBuilderAPI_MakePolygon()
            for u, v in _poly_pts(e):
                mk.Add(P(u, v))
            mk.Close(); w = mk.Wire()
        return BRepBuilderAPI_MakeFace(w, True).Face()

    def _wire_arcos(self, e, P):
        from OCP.GC import GC_MakeArcOfCircle
        mk = BRepBuilderAPI_MakeWire()
        seg = lambda a, b: mk.Add(BRepBuilderAPI_MakeEdge(P(*a), P(*b)).Edge())  # noqa: E731
        arc = lambda a, m, b: mk.Add(BRepBuilderAPI_MakeEdge(GC_MakeArcOfCircle(P(*a), P(*m), P(*b)).Value()).Edge())  # noqa: E731
        if e["t"] == "rrect":
            x0, x1 = sorted((e["x0"], e["x1"])); y0, y1 = sorted((e["y0"], e["y1"])); r = e["r"]; k = r * (1 - math.sqrt(0.5))
            seg((x0 + r, y0), (x1 - r, y0)); arc((x1 - r, y0), (x1 - k, y0 + k), (x1, y0 + r))
            seg((x1, y0 + r), (x1, y1 - r)); arc((x1, y1 - r), (x1 - k, y1 - k), (x1 - r, y1))
            seg((x1 - r, y1), (x0 + r, y1)); arc((x0 + r, y1), (x0 + k, y1 - k), (x0, y1 - r))
            seg((x0, y1 - r), (x0, y0 + r)); arc((x0, y0 + r), (x0 + k, y0 + k), (x0 + r, y0))
        else:
            ax, ay, bx, by, r = e["cx0"], e["cy0"], e["cx1"], e["cy1"], e["w"] / 2
            L = math.hypot(bx - ax, by - ay); ux, uy = (bx - ax) / L, (by - ay) / L; nx, ny = -uy, ux
            a1, a2, b1, b2 = (ax - r * nx, ay - r * ny), (ax + r * nx, ay + r * ny), (bx - r * nx, by - r * ny), (bx + r * nx, by + r * ny)
            seg(a1, b1); arc(b1, (bx + r * ux, by + r * uy), b2); seg(b2, a2); arc(a2, (ax - r * ux, ay - r * uy), a1)
        return mk.Wire()

    def resolver(self, restricoes: list) -> dict:
        """Solver geral (mínimos quadrados) — ver `sketch_solver`. Em conflito o sketch volta ao estado original."""
        from . import sketch_solver
        return sketch_solver.resolver(self, restricoes)

    # --- restrições (aplicadas em sequência; reverificadas)
    def restringir(self, restricoes: list) -> list:
        """Aplica restrições na ordem e devolve a lista das violadas ao final (vazia = todas satisfeitas). Tipos:
        {"k":"horizontal"|"vertical","e":i,"s":j}  segmento j (ponto j→j+1) do polígono i;  {"k":"comprimento","e":i,"s":j,"L":x}  (move o ponto j+1);
        {"k":"raio_igual","a":i,"b":j}  (b recebe o raio de a; círculo/rrect);  {"k":"concentrico","a":i,"b":j}  (círculo b → centro de a);
        {"k":"fixo","e":i,"p":j,"x":x,"y":y}  ponto j do polígono i vai para (x,y)."""
        for c in restricoes:
            k = c["k"]
            if k in ("horizontal", "vertical", "comprimento", "fixo"):
                e = self.entities[c["e"]]
                if e["t"] != "poly": raise SketchError("restrição de segmento exige polígono")
                P = e["pts"]; n = len(P)
                if k == "fixo": P[c["p"] % n] = [c["x"], c["y"]]; continue
                i, j = c["s"] % n, (c["s"] + 1) % n
                if k == "horizontal": P[j] = [P[j][0], P[i][1]]
                elif k == "vertical": P[j] = [P[i][0], P[j][1]]
                else:
                    d = math.hypot(P[j][0] - P[i][0], P[j][1] - P[i][1])
                    if d == 0 or c["L"] <= 0: raise SketchError("comprimento: segmento nulo ou L ≤ 0")
                    P[j] = [P[i][0] + (P[j][0] - P[i][0]) * c["L"] / d, P[i][1] + (P[j][1] - P[i][1]) * c["L"] / d]
            elif k == "raio_igual":
                a, b = self.entities[c["a"]], self.entities[c["b"]]
                if a["t"] not in ("circle", "rrect") or b["t"] not in ("circle", "rrect"): raise SketchError("raio_igual exige círculo ou rrect")
                b["r"] = a["r"]
            elif k == "concentrico":
                a, b = self.entities[c["a"]], self.entities[c["b"]]
                if a["t"] != "circle" or b["t"] != "circle": raise SketchError("concentrico exige dois círculos")
                b["cx"], b["cy"] = a["cx"], a["cy"]
            else:
                raise SketchError(f"restrição desconhecida: {k}")
        bad = []
        for c in restricoes:
            k = c["k"]
            try:
                if k in ("horizontal", "vertical", "comprimento", "fixo"):
                    P = self.entities[c["e"]]["pts"]; n = len(P)
                    if k == "fixo": ok = abs(P[c["p"] % n][0] - c["x"]) < 1e-9 and abs(P[c["p"] % n][1] - c["y"]) < 1e-9
                    else:
                        A, B = P[c["s"] % n], P[(c["s"] + 1) % n]
                        ok = abs(A[1] - B[1]) < 1e-9 if k == "horizontal" else abs(A[0] - B[0]) < 1e-9 if k == "vertical" else abs(math.hypot(B[0] - A[0], B[1] - A[1]) - c["L"]) < 1e-9
                elif k == "raio_igual": ok = abs(self.entities[c["a"]]["r"] - self.entities[c["b"]]["r"]) < 1e-9
                else: ok = abs(self.entities[c["a"]]["cx"] - self.entities[c["b"]]["cx"]) < 1e-9 and abs(self.entities[c["a"]]["cy"] - self.entities[c["b"]]["cy"]) < 1e-9
            except (KeyError, IndexError): ok = False
            if not ok: bad.append(c)
        return bad                                                         # restrições posteriores podem desfazer anteriores: aparece aqui

    def _combinar(self, gerar):
        """Gera o sólido de cada perfil com `gerar(face)` e combina por aninhamento (profundidade ímpar subtrai)."""
        self.validate(); _, depth = self._depth()
        solid = None
        for e, d in sorted(zip(self.entities, depth), key=lambda x: x[1]):
            s = gerar(self._face(e))
            if solid is None:
                solid = s
            else:
                alg = (BRepAlgoAPI_Fuse if d % 2 == 0 else BRepAlgoAPI_Cut)(solid, s)
                alg.Build()
                if not alg.IsDone():
                    raise SketchError("falha ao combinar perfis")
                solid = alg.Shape()
        return solid

    def extrude(self, distance: float):
        """Sólido por extrusão ao longo da normal do plano (distance>0 no sentido +normal; <0 no oposto)."""
        if distance == 0:
            raise SketchError("distância de extrusão não pode ser 0")
        n, _ = PLANOS[self.plane]
        vec = gp_Vec(*(c * distance for c in n))
        return self._combinar(lambda face: BRepPrimAPI_MakePrism(face, vec).Shape())

    def varrer(self, caminho: list):
        """V4.2 — sólido por VARREDURA do perfil ao longo de uma poligonal 3D `caminho` = [[x,y,z], …] (≥ 2 pontos; o perfil deve estar no
        início do caminho e, de preferência, perpendicular ao primeiro trecho). Cantos vivos geram a transição padrão do OpenCascade."""
        from OCP.BRepBuilderAPI import BRepBuilderAPI_RightCorner
        from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipeShell
        from OCP.BRepTools import BRepTools
        pts = [tuple(float(c) for c in p) for p in caminho]
        if len(pts) < 2 or any(len(p) != 3 for p in pts):
            raise SketchError("caminho: lista de pontos [x, y, z] com pelo menos 2 pontos")
        if any(math.dist(a, b) < 1e-9 for a, b in zip(pts, pts[1:])):
            raise SketchError("caminho com dois pontos consecutivos iguais")
        mk = BRepBuilderAPI_MakePolygon()
        for p in pts:
            mk.Add(gp_Pnt(*p))
        spine = mk.Wire()
        def gerar(face):
            mk2 = BRepOffsetAPI_MakePipeShell(spine)
            mk2.SetMode(False)                                       # Frenet corrigido (estável em poligonais)
            mk2.SetTransitionMode(BRepBuilderAPI_RightCorner)        # canto em esquadro (mitre)
            mk2.Add(BRepTools.OuterWire_s(face))
            mk2.Build()
            if not mk2.IsDone() or not mk2.MakeSolid():
                raise SketchError("varredura falhou (perfil fora do início do caminho ou caminho inadequado)")
            return mk2.Shape()
        return self._combinar(gerar)

    def revolve(self, angle_deg: float, axis: list | tuple):
        """V4.1b — sólido por REVOLUÇÃO em torno de um eixo DO PLANO do esboço: `axis` = (u0, v0, u1, v1) em coordenadas do esboço.
        Ângulo em (0, 360]. O eixo não pode cortar o interior de um perfil (o resultado seria inválido; a verificação do sólido recusa)."""
        if not (0 < abs(angle_deg) <= 360):
            raise SketchError("ângulo de revolução deve estar em (0, 360] graus")
        if len(axis) != 4:
            raise SketchError("eixo = (u0, v0, u1, v1)")
        u0, v0, u1, v1 = (float(x) for x in axis)
        if math.hypot(u1 - u0, v1 - v0) < 1e-9:
            raise SketchError("eixo de revolução degenerado")
        _, mp = PLANOS[self.plane]
        p0, p1 = mp(u0, v0, self.offset), mp(u1, v1, self.offset)
        ax = gp_Ax1(gp_Pnt(*p0), gp_Dir(p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]))
        ang = math.radians(angle_deg)
        return self._combinar(lambda face: BRepPrimAPI_MakeRevol(face, ax, ang).Shape())


def loft(secoes: list, reto: bool = False):
    """V4.2 — sólido por LOFT entre perfis: `secoes` = lista de dicts de Sketch com UMA entidade fechada cada (≥ 2, em planos/offsets distintos).
    `reto=True` liga com superfícies regradas; False deixa o OpenCascade suavizar entre 3+ seções."""
    from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections
    from OCP.BRepTools import BRepTools
    if len(secoes) < 2:
        raise SketchError("loft precisa de pelo menos 2 seções")
    mk = BRepOffsetAPI_ThruSections(True, bool(reto))
    for d in secoes:
        sk = Sketch.from_dict(d); sk.validate()
        if len(sk.entities) != 1:
            raise SketchError("cada seção do loft deve ter exatamente 1 perfil")
        mk.AddWire(BRepTools.OuterWire_s(sk._face(sk.entities[0])))
    mk.Build()
    if not mk.IsDone():
        raise SketchError("loft falhou (seções incompatíveis ou torcidas)")
    return mk.Shape()
