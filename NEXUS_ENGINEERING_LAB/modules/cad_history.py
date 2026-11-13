"""Edição paramétrica com HISTÓRICO sobre um sólido-base (STEP importado ou peça da biblioteca).

O resultado é SEMPRE regenerado do sólido-base reaplicando as operações em ordem (receita determinística):
mudar um parâmetro de uma operação antiga reconstrói tudo depois dela; operações podem ser suprimidas,
removidas, desfeitas/refeitas. Operações: translate, rotate, scale, hole, box_cut, box_add, fillet, chamfer.
V4.1b: (1) NOMES PERSISTENTES de faces/arestas — um nome é ligado a um seletor num passo do histórico e depois RASTREADO pelo histórico de
modificação do OpenCascade (Modified/IsDeleted de cada operação), não re-adivinhado por geometria; se a entidade é apagada por uma operação, o
nome fica "perdido" e a reconstrução FALHA com erro explícito (nada é trocado em silêncio). (2) VARIÁVEIS e EXPRESSÕES ("=L/2",
"=op[1].diameter*2") nos parâmetros e (3) RESTRIÇÕES (expressões booleanas, p.ex. "op[2].diameter < op[0].a/2", "volume > 1000") reverificadas a cada
reconstrução; violação desfaz a edição. (4) sketch_revolve — esboço girado em torno de um eixo do plano.
Limitações honestas: o rastreio depende do que o OpenCascade informa em cada operação (casos exóticos de fusão de faces coplanares podem perder o nome —
aí o erro aparece); seletores iniciais ('extrema', 'perto', 'top:z'…) continuam geométricos, só são avaliados UMA vez, no passo em que o nome é ligado;
as restrições são verificações, não um solver (nada é reajustado automaticamente).
"""
from __future__ import annotations
import ast, json, math, operator, time
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
       "sketch_revolve": ["sketch", "angle_deg", "axis", "mode"],
       "sketch_sweep": ["sketch", "path", "mode"],
       "loft": ["sections", "ruled", "mode"],
       "fillet_variable": ["radius1", "radius2"],
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
    n = _ref(sel)
    if n is not None:
        if _RASTREIO is None:
            raise CadHistoryError("nomes só podem ser usados dentro do histórico")
        return list(_RASTREIO.obter(n, "aresta"))
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


_RASTREIO = None      # Rastreio ativo durante rebuild() (None fora dela)


class Rastreio:
    """Acompanha entidades nomeadas (faces/arestas) operação a operação usando o histórico de modificação do OpenCascade."""

    def __init__(self):
        self.vivos: dict[str, list] = {}
        self.tipo: dict[str, str] = {}

    def avancar(self, maker, transform=False):
        for nome, lst in list(self.vivos.items()):
            novo = []
            for e in lst:
                if transform:
                    try:
                        novo.append(maker.ModifiedShape(e))
                    except Exception:  # noqa: BLE001
                        pass
                    continue
                if maker.IsDeleted(e):
                    continue
                mods = list(maker.Modified(e))
                novo.extend(mods) if mods else novo.append(e)
            self.vivos[nome] = novo

    def obter(self, nome, tipo):
        if nome not in self.vivos:
            raise CadHistoryError(f"nome '{nome}' não existe (ou ainda não foi ligado neste ponto do histórico)")
        if self.tipo[nome] != tipo:
            raise CadHistoryError(f"'{nome}' é {self.tipo[nome]}, mas a operação precisa de {tipo}")
        if not self.vivos[nome]:
            raise CadHistoryError(f"referência perdida: '{nome}' foi apagado por uma operação anterior")
        conv = TopoDS.Face if tipo == "face" else TopoDS.Edge          # o OCP devolve TopoDS_Shape genérico após Modified()
        return [conv(e) for e in self.vivos[nome]]


def _ref(nome_ou_sel):
    return nome_ou_sel[5:] if isinstance(nome_ou_sel, str) and nome_ou_sel.startswith("nome:") else None


def _transf(shape, tr):
    mk = BRepBuilderAPI_Transform(shape, tr, True)
    if _RASTREIO is not None:
        _RASTREIO.avancar(mk, True)
    return mk.Shape()


def _unicas(shape, tipo):
    ex = TopExp_Explorer(shape, tipo); out = []
    while ex.More():
        e = ex.Current(); ex.Next()
        if not any(e.IsSame(x) for x in out):
            out.append(e)
    return out


def _entidade_perto(shape, tipo, ponto, tol=1e-9):
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.TopAbs import TopAbs_FACE
    cands = _unicas(shape, TopAbs_FACE if tipo == "face" else TopAbs_EDGE)
    v = BRepBuilderAPI_MakeVertex(gp_Pnt(*[float(c) for c in ponto])).Vertex()
    ds = []
    for c in cands:
        d = BRepExtrema_DistShapeShape(v, c); d.Perform()
        ds.append(d.Value() if d.IsDone() else float("inf"))
    if not ds:
        raise CadHistoryError("nenhuma entidade encontrada")
    ordem = sorted(range(len(ds)), key=lambda i: ds[i])
    if len(ds) > 1 and ds[ordem[1]] - ds[ordem[0]] < tol:
        raise CadHistoryError("seletor 'perto' ambíguo: o ponto é equidistante de mais de uma entidade — mova o ponto")
    return [TopoDS.Face(cands[ordem[0]]) if tipo == "face" else TopoDS.Edge(cands[ordem[0]])]


def _resolver_seletor(shape, tipo, sel):
    modo = sel.get("modo")
    if tipo == "face" and modo == "extrema":
        r = _faces_extremas(shape, sel["lado"])
    elif tipo == "aresta" and modo == "sel":
        r = _edges(shape, sel["sel"])
    elif modo == "perto":
        r = _entidade_perto(shape, "face" if tipo == "face" else "aresta", sel["ponto"])
    else:
        raise CadHistoryError(f"seletor inválido para {tipo}: {sel}")
    if not r:
        raise CadHistoryError("o seletor não encontrou nenhuma entidade")
    return list(r)


# ---- expressões seguras (variáveis, referências op[i].param, restrições)
_BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.Pow: operator.pow,
        ast.Mod: operator.mod, ast.FloorDiv: operator.floordiv}
_CMP = {ast.Lt: operator.lt, ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge, ast.Eq: lambda a, b: abs(a - b) < 1e-9,
        ast.NotEq: lambda a, b: abs(a - b) >= 1e-9}
_FUN = {"sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan, "radians": math.radians, "degrees": math.degrees,
        "min": min, "max": max, "abs": abs}
_CONST = {"pi": math.pi, "e": math.e}


def _avaliar_expr(texto, vars_, ref_op):
    """Avalia `texto` com ast (sem eval). `ref_op(i, chave)` devolve o valor numérico do parâmetro `chave` da operação `i`."""
    try:
        arv = ast.parse(texto.strip().lstrip("="), mode="eval")
    except SyntaxError as exc:
        raise CadHistoryError(f"expressão inválida '{texto}': {exc.msg}")

    def v(n):
        if isinstance(n, ast.Expression): return v(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool): return float(n.value)
        if isinstance(n, ast.Name):
            if n.id in vars_: return vars_[n.id]
            if n.id in _CONST: return _CONST[n.id]
            raise CadHistoryError(f"variável desconhecida '{n.id}' em '{texto}'")
        if isinstance(n, ast.BinOp) and type(n.op) in _BIN:
            try: return _BIN[type(n.op)](v(n.left), v(n.right))
            except ZeroDivisionError: raise CadHistoryError(f"divisão por zero em '{texto}'")
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
            return -v(n.operand) if isinstance(n.op, ast.USub) else v(n.operand)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in _FUN and not n.keywords:
            return _FUN[n.func.id](*[v(a) for a in n.args])
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Subscript) and isinstance(n.value.value, ast.Name) and n.value.value.id == "op":
            idx = n.value.slice
            if isinstance(idx, ast.Constant) and isinstance(idx.value, int):
                return ref_op(idx.value, n.attr)
        if isinstance(n, ast.Compare):
            esq = v(n.left)
            for o, d in zip(n.ops, n.comparators):
                dir_ = v(d)
                if type(o) not in _CMP: raise CadHistoryError(f"comparação não suportada em '{texto}'")
                if not _CMP[type(o)](esq, dir_): return False
                esq = dir_
            return True
        if isinstance(n, ast.BoolOp):
            vals = [bool(v(x)) for x in n.values]
            return all(vals) if isinstance(n.op, ast.And) else any(vals)
        raise CadHistoryError(f"elemento não permitido em '{texto}' (só números, variáveis, + - * / ** %, sqrt/sin/cos/tan/min/max/abs, op[i].parametro)")
    return v(arv)


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
        tr = gp_Trsf(); tr.SetTranslation(gp_Vec(p["dx"], p["dy"], p["dz"])); return _transf(shape, tr)
    if t == "rotate":
        tr = gp_Trsf(); tr.SetRotation(gp_Ax1(gp_Pnt(p["px"], p["py"], p["pz"]), gp_Dir(p["ax"], p["ay"], p["az"])), math.radians(p["angle_deg"]))
        return _transf(shape, tr)
    if t == "scale":
        if p["factor"] <= 0: raise CadHistoryError("fator de escala deve ser > 0")
        tr = gp_Trsf(); tr.SetScale(gp_Pnt(0, 0, 0), p["factor"]); return _transf(shape, tr)
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
        if _RASTREIO is not None:
            _RASTREIO.avancar(mk)
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
    if t == "sketch_revolve":
        from .sketch2d import Sketch, SketchError
        if p["mode"] not in ("add", "cut"):
            raise CadHistoryError("sketch_revolve: mode deve ser 'add' ou 'cut'")
        try:
            s = Sketch.from_dict(p["sketch"]).revolve(p["angle_deg"], p["axis"])
        except SketchError as e:
            raise CadHistoryError(f"sketch inválido: {e}")
        return _bool((BRepAlgoAPI_Fuse if p["mode"] == "add" else BRepAlgoAPI_Cut)(shape, s))
    if t in ("sketch_sweep", "loft"):
        from .sketch2d import Sketch, SketchError, loft
        if p["mode"] not in ("add", "cut"):
            raise CadHistoryError(f"{t}: mode deve ser 'add' ou 'cut'")
        try:
            s = Sketch.from_dict(p["sketch"]).varrer(p["path"]) if t == "sketch_sweep" else loft(p["sections"], bool(p["ruled"]))
        except SketchError as e:
            raise CadHistoryError(f"{t}: {e}")
        return _bool((BRepAlgoAPI_Fuse if p["mode"] == "add" else BRepAlgoAPI_Cut)(shape, s))
    if t == "fillet_variable":
        if p["radius1"] <= 0 or p["radius2"] <= 0:
            raise CadHistoryError("filete variável: raios devem ser > 0")
        es = _edges(shape, p.get("edges", "all"))
        if not es: raise CadHistoryError("nenhuma aresta selecionada")
        mk = BRepFilletAPI_MakeFillet(shape)
        for e in es: mk.Add(p["radius1"], p["radius2"], e)        # raio varia linearmente do início ao fim de cada aresta
        mk.Build()
        if not mk.IsDone(): raise CadHistoryError("filete variável falhou (raio grande demais para a geometria)")
        if _RASTREIO is not None:
            _RASTREIO.avancar(mk)
        return mk.Shape()
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
        if _ref(lado) is not None:
            if _RASTREIO is None:
                raise CadHistoryError("nomes só podem ser usados dentro do histórico")
            faces = list(_RASTREIO.obter(_ref(lado), "face"))
        else:
            if len(lado) != 2 or lado[0] not in "+-" or lado[1] not in "xyz":
                raise CadHistoryError("casca: open_face deve ser '+x','-x','+y','-y','+z', '-z' ou 'nome:<face>'")
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
        if _RASTREIO is not None:
            _RASTREIO.avancar(mk)
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
    if _RASTREIO is not None:
        _RASTREIO.avancar(alg)
    return alg.Shape()


class CadHistory:
    def __init__(self, base_shape, base_ref: str = "biblioteca"):
        self.base = base_shape; self.base_ref = base_ref; self.ops: list[dict] = []; self.cursor = 0
        self.nomes: dict[str, dict] = {}        # nome -> {"tipo": "face"|"aresta", "passo": n, "seletor": {...}}
        self.vars: dict[str, float] = {}         # variáveis para expressões "=..."
        self.restricoes: list[str] = []          # expressões booleanas verificadas a cada reconstrução

    # --- edição
    def add(self, type_, **params):
        if type_ not in OPS: raise CadHistoryError("operação desconhecida")
        if type_ in ("boolean", "linear_pattern", "circular_pattern"):
            params.setdefault("b", 0.0); params.setdefault("c", 0.0)         # só caixa/cilindro usam b/c
        missing = [k for k in OPS[type_] if k not in params]
        if missing: raise CadHistoryError(f"parâmetros faltando: {missing}")
        self._cortar(self.cursor)
        op = {"type": type_, "params": params, "enabled": True, "t": time.time()}
        self.ops.append(op); self.cursor += 1
        try:
            self.rebuild()
        except Exception:
            self.ops.pop(); self.cursor -= 1; raise
        return len(self.ops) - 1

    def _cortar(self, n):
        del self.ops[n:]
        for k in [k for k, v in self.nomes.items() if v["passo"] > n]:
            del self.nomes[k]

    def set_param(self, index, key, value):
        old = self.ops[index]["params"].get(key); self.ops[index]["params"][key] = value
        try: self.rebuild()
        except Exception: self.ops[index]["params"][key] = old; raise

    def suppress(self, index, flag=True):
        self.ops[index]["enabled"] = not flag
        try: self.rebuild()
        except Exception: self.ops[index]["enabled"] = flag; raise

    def undo(self):
        if self.cursor == 0: return False
        self.cursor -= 1; return True
    def redo(self):
        if self.cursor >= len(self.ops): return False
        self.cursor += 1; return True

    # --- V4.1b: nomes persistentes
    def nomear(self, nome, tipo, seletor, passo=None):
        """Liga `nome` a faces ('face') ou arestas ('aresta') escolhidas por `seletor` no ponto `passo` do histórico (padrão: agora).
        Seletores: face {"modo":"extrema","lado":"+z"} | {"modo":"perto","ponto":[x,y,z]}; aresta {"modo":"sel","sel":"top:z"} | {"modo":"perto","ponto":[…]}.
        Use depois como edges="nome:<nome>" (filete/chamfer) ou open_face="nome:<nome>" (casca)."""
        if tipo not in ("face", "aresta"):
            raise CadHistoryError("tipo deve ser 'face' ou 'aresta'")
        if not nome or not nome.replace("_", "").isalnum():
            raise CadHistoryError("nome inválido (use letras, números e _)")
        if nome in self.nomes:
            raise CadHistoryError(f"o nome '{nome}' já existe")
        self.nomes[nome] = {"tipo": tipo, "passo": self.cursor if passo is None else int(passo), "seletor": seletor}
        try:
            self.rebuild(); self.entidades(nome)
        except Exception:
            del self.nomes[nome]; raise

    def esquecer(self, nome):
        self.nomes.pop(nome, None); self.rebuild()

    def entidades(self, nome):
        """Entidades (TopoDS) que o nome designa AGORA (após todas as operações ativas até o cursor)."""
        ras = self._rastrear()[1]
        return list(ras.obter(nome, self.nomes[nome]["tipo"]))

    # --- V4.1b: variáveis e restrições
    def definir(self, nome, valor):
        if not nome.replace("_", "").isalnum() or nome in _CONST or nome in _FUN or nome == "op":
            raise CadHistoryError("nome de variável inválido ou reservado")
        old = self.vars.get(nome); self.vars[nome] = float(valor)
        try: self.rebuild()
        except Exception:
            (self.vars.__setitem__(nome, old) if old is not None else self.vars.pop(nome, None)); raise

    def ajustar(self, variavel, metrica, alvo, lo, hi, tol=1e-6, max_iter=80):
        """V5.3 — procura (bisseção) o valor de `variavel` em [lo, hi] que leva `metrica` ('volume', 'dx', 'dy' ou 'dz') ao `alvo`.
        Não é um solver paramétrico geral: UMA variável, métrica MONÓTONA na faixa (se `alvo` não estiver entre os valores nas pontas, recusa).
        As restrições ficam suspensas durante a busca e são verificadas ao aplicar o resultado; em qualquer erro nada muda."""
        if variavel not in self.vars:
            raise CadHistoryError(f"variável '{variavel}' não existe (defina-a antes e use-a em '=…' nos parâmetros)")
        if metrica not in ("volume", "dx", "dy", "dz"):
            raise CadHistoryError("métrica deve ser 'volume', 'dx', 'dy' ou 'dz'")
        if not lo < hi:
            raise CadHistoryError("faixa inválida: lo deve ser menor que hi")
        original, restr = self.vars[variavel], self.restricoes

        def f(x):
            self.vars[variavel] = float(x)
            try:
                forma = self.rebuild_sem_restricoes()
            except CadHistoryError as exc:
                raise CadHistoryError(f"a geometria falha com {variavel} = {x:g}: {exc}")
            if metrica == "volume":
                return exact_volume(forma) - alvo
            b = _bbox(forma)
            return (b[3 + "xyz".index(metrica[1])] - b[:3]["xyz".index(metrica[1])]) - alvo

        try:
            self.restricoes = []
            fl, fh = f(lo), f(hi)
            if abs(fl) <= tol: x = lo
            elif abs(fh) <= tol: x = hi
            elif fl * fh > 0:
                raise CadHistoryError(f"o alvo {metrica} = {alvo:g} não está entre os valores nas pontas da faixa ({metrica} = {fl + alvo:g} em {lo:g} e {fh + alvo:g} em {hi:g})")
            else:
                a_, b_ = float(lo), float(hi)
                x = 0.5 * (a_ + b_)
                for _ in range(max_iter):
                    x = 0.5 * (a_ + b_); fx = f(x)
                    if abs(fx) <= tol or (b_ - a_) < 1e-12: break
                    if fl * fx < 0: b_ = x
                    else: a_, fl = x, fx
            obtido = f(x) + alvo
        except Exception:
            self.vars[variavel] = original; self.restricoes = restr; raise
        self.restricoes = restr
        self.vars[variavel] = original
        self.definir(variavel, x)                                   # aplica e verifica restrições; reverte sozinho se violar
        return {"variavel": variavel, "valor": x, "metrica": metrica, "obtido": obtido, "alvo": alvo}

    def ajustar_multi(self, variaveis, alvos, tol=1e-5, max_nfev=60):
        """V6.2 — ajuste de VÁRIAS variáveis a VÁRIOS alvos por mínimos quadrados (scipy.least_squares, região de confiança, derivadas por diferenças finitas).
        `variaveis`: {nome: (lo, hi)}; `alvos`: lista de (metrica, valor) com metrica em volume/dx/dy/dz. Resíduos normalizados pelo alvo (|alvo|, ou 1 se 0).
        NÃO prova unicidade: com menos alvos que variáveis há infinitas soluções (devolve a mais próxima do ponto inicial que o solver achou); com mais, é ajuste.
        Devolve `convergiu` e o resíduo relativo máximo por alvo; só aplica se TODOS os resíduos ficarem <= `tol` — senão levanta e nada muda.
        Restrições ficam suspensas durante a busca e são verificadas ao aplicar."""
        from scipy.optimize import least_squares
        if not variaveis or not alvos:
            raise CadHistoryError("informe ao menos uma variável e um alvo")
        for v in variaveis:
            if v not in self.vars:
                raise CadHistoryError(f"variável '{v}' não existe")
        for m, _ in alvos:
            if m not in ("volume", "dx", "dy", "dz"):
                raise CadHistoryError("métrica deve ser 'volume', 'dx', 'dy' ou 'dz'")
        nomes = list(variaveis)
        for v in nomes:
            lo, hi = variaveis[v]
            if not lo < hi:
                raise CadHistoryError(f"faixa inválida para {v}")
        originais, restr = dict(self.vars), self.restricoes

        def medir(forma, m):
            if m == "volume":
                return exact_volume(forma)
            b = _bbox(forma); i = "xyz".index(m[1])
            return b[3 + i] - b[i]

        def res(x):
            for v, xv in zip(nomes, x):
                self.vars[v] = float(xv)
            try:
                forma = self.rebuild_sem_restricoes()
            except CadHistoryError as exc:
                raise CadHistoryError("a geometria falha com " + ", ".join(f"{v} = {xv:g}" for v, xv in zip(nomes, x)) + f": {exc}")
            return [(medir(forma, m) - a) / (abs(a) or 1.0) for m, a in alvos]

        try:
            self.restricoes = []
            x0 = [min(max(originais[v], variaveis[v][0]), variaveis[v][1]) for v in nomes]
            r = least_squares(res, x0, bounds=([variaveis[v][0] for v in nomes], [variaveis[v][1] for v in nomes]), xtol=1e-12, ftol=1e-12, gtol=1e-12, max_nfev=max_nfev, diff_step=1e-6)
            resid = [abs(q) for q in res(r.x)]
        except Exception:
            self.vars = originais; self.restricoes = restr; raise
        self.restricoes = restr
        self.vars = dict(originais)
        if max(resid) > tol:
            raise CadHistoryError(f"o ajuste não atingiu a tolerância (resíduo relativo máx {max(resid):.2e} > {tol:g}); alvos possivelmente incompatíveis com as faixas — nada foi alterado")
        for v, xv in zip(nomes, r.x):
            self.vars[v] = float(xv)
        try:
            self.rebuild()
        except Exception:
            self.vars = dict(originais); raise
        return {"valores": {v: float(xv) for v, xv in zip(nomes, r.x)}, "residuos_relativos": resid, "convergiu": True, "avaliacoes": int(r.nfev),
                "determinacao": ("sub-determinado" if len(alvos) < len(nomes) else "sobre-determinado" if len(alvos) > len(nomes) else "determinado")}

    def rebuild_sem_restricoes(self):
        s, _ = self._rastrear()
        if not BRepCheck_Analyzer(s).IsValid(): raise CadHistoryError("sólido resultante inválido")
        return s

    def restringir(self, expressao):
        self.restricoes.append(expressao)
        try: self.rebuild()
        except Exception: self.restricoes.pop(); raise

    def _valor(self, i, chave, pilha=()):
        if not (0 <= i < len(self.ops)): raise CadHistoryError(f"op[{i}] não existe")
        if (i, chave) in pilha: raise CadHistoryError(f"referência circular em op[{i}].{chave}")
        if chave not in self.ops[i]["params"]: raise CadHistoryError(f"op[{i}] não tem o parâmetro '{chave}'")
        v = self.ops[i]["params"][chave]
        if isinstance(v, str) and v.startswith("="):
            return _avaliar_expr(v, self.vars, lambda j, c: self._valor(j, c, pilha + ((i, chave),)))
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise CadHistoryError(f"op[{i}].{chave} não é numérico")
        return float(v)

    def _params(self, i):
        out = {}
        for k, v in self.ops[i]["params"].items():
            out[k] = self._valor(i, k) if isinstance(v, str) and v.startswith("=") else v
        return out

    def _checar_restricoes(self, shape):
        if not self.restricoes: return
        extra = {}
        if any(w in r for r in self.restricoes for w in ("volume", "dx", "dy", "dz")):
            b = _bbox(shape); extra = {"volume": exact_volume(shape), "dx": b[3] - b[0], "dy": b[4] - b[1], "dz": b[5] - b[2]}
        vs = {**self.vars, **extra}
        for r in self.restricoes:
            ok = _avaliar_expr(r, vs, lambda j, c: self._valor(j, c))
            if ok is not True and ok is not False:
                raise CadHistoryError(f"restrição '{r}' não é uma comparação")
            if not ok:
                raise CadHistoryError(f"restrição violada: {r}")

    # --- reconstrução
    def _rastrear(self, upto=None):
        global _RASTREIO
        n = self.cursor if upto is None else upto
        ras = Rastreio(); anterior = _RASTREIO; _RASTREIO = ras

        def ligar(passo, forma):
            for nome, d in self.nomes.items():
                if d["passo"] == passo and nome not in ras.vivos:
                    ras.vivos[nome] = _resolver_seletor(forma, d["tipo"], d["seletor"]); ras.tipo[nome] = d["tipo"]
        try:
            s = self.base
            ligar(0, s)
            for i, op in enumerate(self.ops[:n]):
                if op["enabled"]:
                    s = _apply(s, {"type": op["type"], "params": self._params(i)})
                ligar(i + 1, s)
            return s, ras
        finally:
            _RASTREIO = anterior

    def rebuild(self, upto=None):
        s, _ = self._rastrear(upto)
        if not BRepCheck_Analyzer(s).IsValid(): raise CadHistoryError("sólido resultante inválido")
        if upto is None:
            self._checar_restricoes(s)
        return s

    @property
    def shape(self): return self.rebuild()
    def volume(self): return exact_volume(self.shape)

    # --- persistência
    def to_dict(self): return {"base_ref": self.base_ref, "ops": self.ops, "cursor": self.cursor,
                               "nomes": self.nomes, "vars": self.vars, "restricoes": self.restricoes}

    @classmethod
    def from_dict(cls, d, base_shape):
        h = cls(base_shape, d["base_ref"]); h.ops = d["ops"]; h.cursor = d["cursor"]
        h.nomes = d.get("nomes", {}); h.vars = d.get("vars", {}); h.restricoes = d.get("restricoes", []); return h
