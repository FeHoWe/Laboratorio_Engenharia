"""Edição paramétrica com HISTÓRICO sobre um sólido-base (STEP importado ou peça da biblioteca).

O resultado é SEMPRE regenerado do sólido-base reaplicando as operações em ordem (receita determinística):
mudar um parâmetro de uma operação antiga reconstrói tudo depois dela; operações podem ser suprimidas,
removidas, desfeitas/refeitas. Operações: translate, rotate, scale, hole, box_cut, box_add, fillet, chamfer.
Limitação honesta: não há referência topológica persistente (nomeação de faces/arestas) — seletores são
geométricos (por eixo ou 'all'); se uma edição a montante mudar a topologia, seletores são reavaliados.
"""
from __future__ import annotations
import json, math, time
from pathlib import Path
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform, BRepBuilderAPI_GTransform
from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet, BRepFilletAPI_MakeChamfer
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeSphere
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.GeomAbs import GeomAbs_Line
from OCP.STEPControl import STEPControl_Reader
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS
from OCP.gp import gp_Ax1, gp_Ax2, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
from .fea_voxel import exact_volume

OPS = {"translate": ["dx", "dy", "dz"], "rotate": ["px", "py", "pz", "ax", "ay", "az", "angle_deg"], "scale": ["factor"],
       "hole": ["x", "y", "z", "dx", "dy", "dz", "diameter", "depth"], "box_cut": ["x0", "y0", "z0", "x1", "y1", "z1"],
       "box_add": ["x0", "y0", "z0", "x1", "y1", "z1"], "fillet": ["radius"], "chamfer": ["distance"],
       "sketch_extrude": ["sketch", "distance", "mode"],
       "boolean": ["mode", "tool", "x", "y", "z", "a", "b", "c"],
       # V4.1
       "counterbore": ["x", "y", "z", "dx", "dy", "dz", "diameter", "depth", "cb_diameter", "cb_depth"],
       "linear_pattern": ["mode", "tool", "x", "y", "z", "a", "b", "c", "count", "sx", "sy", "sz"],
       "circular_pattern": ["mode", "tool", "x", "y", "z", "a", "b", "c", "count", "cx", "cy", "cz", "ax", "ay", "az", "angle_deg"],
       "mirror": ["plane", "offset"],
       "shell": ["thickness", "open_face"]}
BOOL_MODES = ("union", "cut", "common")
BOOL_TOOLS = ("box", "cylinder", "sphere", "step")


class CadHistoryError(Exception):
    pass


def load_step(path):
    r = STEPControl_Reader()
    if r.ReadFile(str(path)) != 1:
        raise CadHistoryError(f"não foi possível ler {path}")
    r.TransferRoots(); s = r.OneShape()
    if s.IsNull():
        raise CadHistoryError("STEP sem geometria")
    return s


def _edges(shape, sel):
    ex = TopExp_Explorer(shape, TopAbs_EDGE); out = []; seen = []
    while ex.More():
        e = TopoDS.Edge(ex.Current()); ex.Next()
        if any(e.IsSame(s) for s in seen):
            continue
        seen.append(e)
        if sel == "all":
            out.append(e); continue
        modo, eixo = sel.split(":")
        ax = {"x": (1, 0, 0), "y": (0, 1, 0), "z": (0, 0, 1)}[eixo]
        if modo in ("top", "bottom"):                       # V4.1: arestas contidas no plano extremo (máx./mín.) do eixo
            out.append(e); continue
        c = BRepAdaptor_Curve(e)
        if c.GetType() == GeomAbs_Line:
            d = c.Line().Direction()
            if abs(abs(d.X()*ax[0] + d.Y()*ax[1] + d.Z()*ax[2]) - 1) < 1e-9:
                out.append(e)
    if sel != "all" and sel.split(":")[0] in ("top", "bottom"):
        out = _arestas_no_plano_extremo(shape, out, sel.split(":")[1], sel.startswith("top"))
    return out


def _bbox(shape):
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    b = Bnd_Box(); BRepBndLib.Add_s(shape, b); b.SetGap(0.0)
    a, c = b.CornerMin(), b.CornerMax()
    return (a.X(), a.Y(), a.Z(), c.X(), c.Y(), c.Z())      # xmin, ymin, zmin, xmax, ymax, zmax


def _arestas_no_plano_extremo(shape, edges, eixo, topo, tol=1e-6):
    i = "xyz".index(eixo)
    ext = _bbox(shape)[3 + i if topo else i]
    out = []
    for e in edges:
        b = _bbox(e)
        if abs(b[i] - ext) < tol and abs(b[3 + i] - ext) < tol:
            out.append(e)
    return out


def _faces_extremas(shape, lado, tol=1e-6):
    """Faces planas cuja normal externa é ±eixo (lado '+z', '-x'…) e que estão no plano extremo."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Plane
    from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
    sinal = 1.0 if lado[0] == "+" else -1.0; i = "xyz".index(lado[1])
    cand = []
    ex = TopExp_Explorer(shape, TopAbs_FACE)
    while ex.More():
        f = TopoDS.Face(ex.Current()); ex.Next()
        sf = BRepAdaptor_Surface(f)
        if sf.GetType() != GeomAbs_Plane:
            continue
        pl = sf.Plane(); d = pl.Axis().Direction(); n = [d.X(), d.Y(), d.Z()]
        if f.Orientation() == TopAbs_REVERSED:
            n = [-x for x in n]
        if n[i] * sinal > 1 - 1e-9:
            cand.append((pl.Location().Coord(i + 1) * sinal, f))
    if not cand:
        return []
    m = max(c for c, _ in cand)
    return [f for c, f in cand if abs(c - m) < tol]


def _copias_padrao(shape_ferramenta, t, p):
    n = int(p["count"])
    if n < 1 or n > 1000:
        raise CadHistoryError("padrão: count deve estar entre 1 e 1000")
    out = []
    for k in range(n):
        tr = gp_Trsf()
        if t == "linear_pattern":
            tr.SetTranslation(gp_Vec(p["sx"] * k, p["sy"] * k, p["sz"] * k))
        else:
            if (p["ax"], p["ay"], p["az"]) == (0, 0, 0):
                raise CadHistoryError("padrão circular: eixo nulo")
            total = p["angle_deg"]
            passo = total / n if abs(abs(total) - 360.0) < 1e-9 else (total / (n - 1) if n > 1 else 0.0)
            tr.SetRotation(gp_Ax1(gp_Pnt(p["cx"], p["cy"], p["cz"]), gp_Dir(p["ax"], p["ay"], p["az"])), math.radians(passo * k))
        out.append(BRepBuilderAPI_Transform(shape_ferramenta, tr, True).Shape())
    return out


def _apply(shape, op):
    t, p = op["type"], op["params"]
    if t == "translate":
        tr = gp_Trsf(); tr.SetTranslation(gp_Vec(p["dx"], p["dy"], p["dz"])); return BRepBuilderAPI_Transform(shape, tr, True).Shape()
    if t == "rotate":
        tr = gp_Trsf(); tr.SetRotation(gp_Ax1(gp_Pnt(p["px"], p["py"], p["pz"]), gp_Dir(p["ax"], p["ay"], p["az"])), math.radians(p["angle_deg"]))
        return BRepBuilderAPI_Transform(shape, tr, True).Shape()
    if t == "scale":
        if p["factor"] <= 0: raise CadHistoryError("fator de escala deve ser > 0")
        tr = gp_Trsf(); tr.SetScale(gp_Pnt(0, 0, 0), p["factor"]); return BRepBuilderAPI_Transform(shape, tr, True).Shape()
    if t == "hole":
        if p["diameter"] <= 0 or p["depth"] <= 0: raise CadHistoryError("furo: diâmetro e profundidade devem ser > 0")
        cyl = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(p["x"], p["y"], p["z"]), gp_Dir(p["dx"], p["dy"], p["dz"])), p["diameter"] / 2, p["depth"]).Shape()
        return _bool(BRepAlgoAPI_Cut(shape, cyl))
    if t in ("box_cut", "box_add"):
        x0, x1 = sorted((p["x0"], p["x1"])); y0, y1 = sorted((p["y0"], p["y1"])); z0, z1 = sorted((p["z0"], p["z1"]))
        if min(x1-x0, y1-y0, z1-z0) <= 0: raise CadHistoryError("caixa degenerada")
        b = BRepPrimAPI_MakeBox(gp_Pnt(x0, y0, z0), x1-x0, y1-y0, z1-z0).Shape()
        return _bool((BRepAlgoAPI_Cut if t == "box_cut" else BRepAlgoAPI_Fuse)(shape, b))
    if t in ("fillet", "chamfer"):
        mk = BRepFilletAPI_MakeFillet(shape) if t == "fillet" else BRepFilletAPI_MakeChamfer(shape)
        v = p["radius"] if t == "fillet" else p["distance"]
        if v <= 0: raise CadHistoryError("valor deve ser > 0")
        es = _edges(shape, p.get("edges", "all"))
        if not es: raise CadHistoryError("nenhuma aresta selecionada")
        for e in es: mk.Add(v, e)
        mk.Build()
        if not mk.IsDone(): raise CadHistoryError(f"{t} falhou (raio/distância grande demais para a geometria)")
        return mk.Shape()
    if t == "sketch_extrude":
        from .sketch2d import Sketch, SketchError
        if p["mode"] not in ("add", "cut"):
            raise CadHistoryError("sketch_extrude: mode deve ser 'add' ou 'cut'")
        try:
            s = Sketch.from_dict(p["sketch"]).extrude(p["distance"])
        except SketchError as e:
            raise CadHistoryError(f"sketch inválido: {e}")
        return _bool((BRepAlgoAPI_Fuse if p["mode"] == "add" else BRepAlgoAPI_Cut)(shape, s))
    if t == "boolean":
        if p["mode"] not in BOOL_MODES or p["tool"] not in BOOL_TOOLS:
            raise CadHistoryError(f"boolean: mode ∈ {BOOL_MODES}, tool ∈ {BOOL_TOOLS}")
        tool = _bool_tool(p)
        return _bool({"union": BRepAlgoAPI_Fuse, "cut": BRepAlgoAPI_Cut, "common": BRepAlgoAPI_Common}[p["mode"]](shape, tool))
    if t == "counterbore":
        if min(p["diameter"], p["depth"], p["cb_diameter"], p["cb_depth"]) <= 0:
            raise CadHistoryError("furo escareado: todas as dimensões devem ser > 0")
        if p["cb_diameter"] <= p["diameter"]:
            raise CadHistoryError("furo escareado: o diâmetro do rebaixo deve ser maior que o do furo")
        ax = gp_Ax2(gp_Pnt(p["x"], p["y"], p["z"]), gp_Dir(p["dx"], p["dy"], p["dz"]))
        out = _bool(BRepAlgoAPI_Cut(shape, BRepPrimAPI_MakeCylinder(ax, p["diameter"] / 2, p["depth"]).Shape()))
        return _bool(BRepAlgoAPI_Cut(out, BRepPrimAPI_MakeCylinder(ax, p["cb_diameter"] / 2, p["cb_depth"]).Shape()))
    if t in ("linear_pattern", "circular_pattern"):
        if p["mode"] not in ("union", "cut") or p["tool"] not in BOOL_TOOLS:
            raise CadHistoryError("padrão: mode ∈ ('union','cut'), tool ∈ " + str(BOOL_TOOLS))
        alg = BRepAlgoAPI_Fuse if p["mode"] == "union" else BRepAlgoAPI_Cut
        for c in _copias_padrao(_bool_tool(p), t, p):
            shape = _bool(alg(shape, c))
        return shape
    if t == "mirror":
        if p["plane"] not in ("x", "y", "z"):
            raise CadHistoryError("espelhar: plane deve ser 'x', 'y' ou 'z' (plano normal ao eixo)")
        i = "xyz".index(p["plane"]); o = [0.0, 0.0, 0.0]; o[i] = p["offset"]
        nrm = [0, 0, 0]; nrm[i] = 1
        tr = gp_Trsf(); tr.SetMirror(gp_Ax2(gp_Pnt(*o), gp_Dir(*nrm)))
        return _bool(BRepAlgoAPI_Fuse(shape, BRepBuilderAPI_Transform(shape, tr, True).Shape()))
    if t == "shell":
        from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeThickSolid
        from OCP.collections import List_TopoDS_Shape as TopTools_ListOfShape
        if p["thickness"] <= 0:
            raise CadHistoryError("casca: espessura deve ser > 0")
        lado = str(p["open_face"])
        if len(lado) != 2 or lado[0] not in "+-" or lado[1] not in "xyz":
            raise CadHistoryError("casca: open_face deve ser '+x','-x','+y','-y','+z' ou '-z'")
        faces = _faces_extremas(shape, lado)
        if not faces:
            raise CadHistoryError(f"casca: não há face plana em {lado}")
        lst = TopTools_ListOfShape()
        for f in faces: lst.Append(f)
        mk = BRepOffsetAPI_MakeThickSolid()
        mk.MakeThickSolidByJoin(shape, lst, -p["thickness"], 1e-4)
        mk.Build()
        if not mk.IsDone():
            raise CadHistoryError("casca falhou (espessura grande demais para a geometria)")
        return mk.Shape()
    raise CadHistoryError(f"operação desconhecida: {t}")


def _bool_tool(p):
    """Corpo-ferramenta: box (a,b,c = dx,dy,dz a partir de x,y,z); cylinder (a=diâmetro, b=comprimento, eixo p['axis']∈x/y/z, padrão z);
    sphere (a=raio, centro x,y,z); step (arquivo p['path'], deslocado por x,y,z)."""
    t = p["tool"]; o = gp_Pnt(p["x"], p["y"], p["z"])
    if t == "box":
        if min(p["a"], p["b"], p["c"]) <= 0: raise CadHistoryError("caixa-ferramenta degenerada")
        return BRepPrimAPI_MakeBox(o, p["a"], p["b"], p["c"]).Shape()
    if t == "cylinder":
        if p["a"] <= 0 or p["b"] <= 0: raise CadHistoryError("cilindro-ferramenta: diâmetro e comprimento > 0")
        d = {"x": (1, 0, 0), "y": (0, 1, 0), "z": (0, 0, 1)}[p.get("axis", "z")]
        return BRepPrimAPI_MakeCylinder(gp_Ax2(o, gp_Dir(*d)), p["a"] / 2, p["b"]).Shape()
    if t == "sphere":
        if p["a"] <= 0: raise CadHistoryError("esfera-ferramenta: raio > 0")
        return BRepPrimAPI_MakeSphere(o, p["a"]).Shape()
    s = load_step(p["path"])
    tr = gp_Trsf(); tr.SetTranslation(gp_Vec(p["x"], p["y"], p["z"]))
    return BRepBuilderAPI_Transform(s, tr, True).Shape()


def _bool(alg):
    alg.Build()
    if not alg.IsDone(): raise CadHistoryError("operação booleana falhou")
    return alg.Shape()


class CadHistory:
    def __init__(self, base_shape, base_ref: str = "biblioteca"):
        self.base = base_shape; self.base_ref = base_ref; self.ops: list[dict] = []; self.cursor = 0

    # --- edição
    def add(self, type_, **params):
        if type_ in ("boolean", "linear_pattern", "circular_pattern"):
            params.setdefault("b", 0.0); params.setdefault("c", 0.0)         # só caixa/cilindro usam b/c
        missing = [k for k in OPS[type_] if k not in params and not (type_ in ("fillet", "chamfer") and k in ())]
        if type_ not in OPS: raise CadHistoryError("operação desconhecida")
        if missing: raise CadHistoryError(f"parâmetros faltando: {missing}")
        del self.ops[self.cursor:]
        op = {"type": type_, "params": params, "enabled": True, "t": time.time()}
        self.ops.append(op); self.cursor += 1
        try:
            self.rebuild()
        except Exception:
            self.ops.pop(); self.cursor -= 1; raise
        return len(self.ops) - 1

    def set_param(self, index, key, value):
        old = self.ops[index]["params"].get(key); self.ops[index]["params"][key] = value
        try: self.rebuild()
        except Exception: self.ops[index]["params"][key] = old; raise

    def suppress(self, index, flag=True): self.ops[index]["enabled"] = not flag; self.rebuild()
    def undo(self):
        if self.cursor == 0: return False
        self.cursor -= 1; return True
    def redo(self):
        if self.cursor >= len(self.ops): return False
        self.cursor += 1; return True

    def rebuild(self, upto=None):
        s = self.base
        for op in self.ops[: self.cursor if upto is None else upto]:
            if op["enabled"]: s = _apply(s, op)
        if not BRepCheck_Analyzer(s).IsValid(): raise CadHistoryError("sólido resultante inválido")
        return s

    @property
    def shape(self): return self.rebuild()
    def volume(self): return exact_volume(self.shape)

    # --- persistência
    def to_dict(self): return {"base_ref": self.base_ref, "ops": self.ops, "cursor": self.cursor}

    @classmethod
    def from_dict(cls, d, base_shape):
        h = cls(base_shape, d["base_ref"]); h.ops = d["ops"]; h.cursor = d["cursor"]; return h
