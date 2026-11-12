"""Resultados de simulação amarrados à VERSÃO da geometria (Master Prompt §9).

- `fingerprint_recipe(part_key, params, ...)` — impressão digital determinística da receita paramétrica (peças da biblioteca/Arsenal).
- `fingerprint_shape(shape)` — impressão digital de um sólido B-Rep importado (volume, área, caixa, nº de faces, centro de massa).
- Todo resultado anexado guarda a impressão digital da geometria usada. Se a geometria muda, o resultado NÃO é apagado:
  ganha o estado OBSOLETO ("referente a versão anterior da geometria") e deixa de contar como vigente.
- `compare` cruza valores numéricos de dois resultados (ex.: versão A × versão B da peça), sinalizando se as geometrias diferem.
"""
from __future__ import annotations

import hashlib
import json
import time


def _h(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, default=repr).encode("utf-8")).hexdigest()[:16]


def fingerprint_recipe(part_key: str, params: dict, arsenal_id: str = "", version: str = "") -> str:
    return _h({"k": part_key, "p": {k: (round(v, 9) if isinstance(v, float) else v) for k, v in params.items()}, "a": arsenal_id, "v": version})


def fingerprint_shape(shape) -> str:
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    vp, sp = GProp_GProps(), GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, vp)
    BRepGProp.SurfaceProperties_s(shape, sp)
    bb = Bnd_Box()
    BRepBndLib.Add_s(shape, bb)
    x0, y0, z0, x1, y1, z1 = bb.CornerMin().X(), bb.CornerMin().Y(), bb.CornerMin().Z(), bb.CornerMax().X(), bb.CornerMax().Y(), bb.CornerMax().Z()
    nf, ex = 0, TopExp_Explorer(shape, TopAbs_FACE)
    while ex.More():
        nf += 1
        ex.Next()
    c = vp.CentreOfMass()
    r = lambda v: round(float(v), 4)                                    # tolerância de 1e-4 mm para ruído numérico
    return _h([r(vp.Mass()), r(sp.Mass()), [r(x0), r(y0), r(z0), r(x1), r(y1), r(z1)], nf, [r(c.X()), r(c.Y()), r(c.Z())]])


class ResultStore:
    """Opera sobre `proj['results']` (lista de dicts) do ProjectStore, sem mudar o esquema existente (campos novos são aditivos)."""

    def __init__(self, proj: dict) -> None:
        self.proj = proj
        self.proj.setdefault("results", [])

    def attach(self, traced, geometry_fp: str, geometry_label: str = "") -> dict:
        d = traced.to_dict()
        d["geometry_fp"] = geometry_fp
        d["geometry_label"] = geometry_label
        d["status_geometria"] = "VIGENTE"
        d["anexado_em"] = time.time()
        self.proj["results"].append(d)
        return d

    def refresh(self, current_fps: dict) -> list[dict]:
        """`current_fps` = {geometry_label: fingerprint atual}. Marca como OBSOLETO tudo cuja geometria mudou; nada é removido."""
        mudou = []
        for r in self.proj["results"]:
            if "geometry_fp" not in r:
                r.setdefault("status_geometria", "SEM_VINCULO")          # resultados antigos (pré-V3.0): não afirmamos validade
                continue
            atual = current_fps.get(r.get("geometry_label"))
            if atual is None:
                continue
            novo = "VIGENTE" if atual == r["geometry_fp"] else "OBSOLETO"
            if novo != r.get("status_geometria"):
                r["status_geometria"] = novo
                if novo == "OBSOLETO":
                    r["obsoleto_motivo"] = "geometria alterada após este resultado — referente à versão anterior"
                mudou.append(r)
        return mudou

    def vigentes(self) -> list[dict]:
        return [r for r in self.proj["results"] if r.get("status_geometria") == "VIGENTE"]

    def obsoletos(self) -> list[dict]:
        return [r for r in self.proj["results"] if r.get("status_geometria") == "OBSOLETO"]


def compare(a: dict, b: dict) -> dict:
    """Compara dois resultados (dicts de TracedResult.to_dict). Só compara chaves numéricas comuns."""
    va, vb = a.get("valores", {}), b.get("valores", {})
    linhas = []
    for k in sorted(set(va) & set(vb)):
        x, y = va[k], vb[k]
        if isinstance(x, (int, float)) and isinstance(y, (int, float)) and not isinstance(x, bool) and not isinstance(y, bool):
            linhas.append({"grandeza": k, "a": x, "b": y, "delta": y - x, "delta_pct": (100 * (y - x) / x) if x else None})
    return {"mesma_geometria": a.get("geometry_fp") == b.get("geometry_fp"), "mesmo_metodo": a.get("metodo") == b.get("metodo"),
            "a_status": a.get("status_geometria"), "b_status": b.get("status_geometria"), "linhas": linhas}
