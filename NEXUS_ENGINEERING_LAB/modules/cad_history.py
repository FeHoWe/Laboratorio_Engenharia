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
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform, BRepBuilderAPI_GTransform
from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet, BRepFilletAPI_MakeChamfer
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
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
       "box_add": ["x0", "y0", "z0", "x1", "y1", "z1"], "fillet": ["radius"], "chamfer": ["distance"]}


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
        ax = {"x": (1, 0, 0), "y": (0, 1, 0), "z": (0, 0, 1)}[sel.split(":")[1]]
        c = BRepAdaptor_Curve(e)
        if c.GetType() == GeomAbs_Line:
            d = c.Line().Direction()
            if abs(abs(d.X()*ax[0] + d.Y()*ax[1] + d.Z()*ax[2]) - 1) < 1e-9:
                out.append(e)
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
    raise CadHistoryError(f"operação desconhecida: {t}")


def _bool(alg):
    alg.Build()
    if not alg.IsDone(): raise CadHistoryError("operação booleana falhou")
    return alg.Shape()


class CadHistory:
    def __init__(self, base_shape, base_ref: str = "biblioteca"):
        self.base = base_shape; self.base_ref = base_ref; self.ops: list[dict] = []; self.cursor = 0

    # --- edição
    def add(self, type_, **params):
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
