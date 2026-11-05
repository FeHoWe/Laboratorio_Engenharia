"""Relações de montagem (juntas) INFERIDAS da geometria — V1.7.

STEP/STL/OBJ não trazem juntas (mates). Este módulo as DEDUZ da geometria exata:
    * Concêntrica (eixo/furo): duas superfícies cilíndricas com eixos coincidentes, raios que diferem
      menos que ``max_gap`` e partes que se sobrepõem ao longo do eixo.
    * Plano contra plano: faces planas de normais opostas (para fora), coplanares (``tol``) e cujas
      caixas se sobrepõem com área > 0 (aproximação: duas faces coplanares com buraco no meio
      podem ser contadas mesmo sem tocar de fato).
Tudo é rotulado "inferido": uma coincidência geométrica não prova intenção de projeto (ex.: um pino
e um furo podem estar alinhados sem estarem montados). Não há restrições cinemáticas nem simulação.
Juntas gravadas por CADs (ex.: Assembly do FreeCAD) NÃO são lidas.
"""
from __future__ import annotations

import csv
import itertools
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

from core.component_manager import ComponentManager
from core.geometry import BoundingBox

KIND_CONCENTRIC = "Concêntrica (eixo/furo)"
KIND_PLANAR = "Plano contra plano"


@dataclass
class Joint:
    kind: str
    a_id: str
    b_id: str
    a_name: str
    b_name: str
    detail: str                         # texto curto para a tabela
    gap: Optional[float] = None         # folga radial (mm) ou distância ao plano (mm)
    axis: Optional[tuple] = None
    radius_a: Optional[float] = None
    radius_b: Optional[float] = None
    inferred: bool = True


@dataclass
class JointReport:
    joints: list[Joint]
    parts: int
    pairs_checked: int
    orphans: list[str]                  # peças sem nenhuma junta inferida
    clusters: list[list[str]]           # grupos de peças ligadas (nomes), maiores primeiro

    def summary(self) -> str:
        k = {}
        for j in self.joints:
            k[j.kind] = k.get(j.kind, 0) + 1
        parts = "; ".join(f"{n} {kind.lower()}" for kind, n in k.items()) or "nenhuma"
        return (f"{len(self.joints)} junta(s) inferida(s) ({parts}) entre {self.parts} peças · "
                f"{len(self.orphans)} peça(s) sem junta · {len(self.clusters)} conjunto(s) ligado(s)")


def _overlap_along(a: BoundingBox, b: BoundingBox, axis: np.ndarray, margin: float) -> bool:
    def proj(box):
        corners = np.array(list(itertools.product(*zip(box.min, box.max))))
        s = corners @ axis
        return s.min(), s.max()
    a0, a1 = proj(a)
    b0, b1 = proj(b)
    return a0 <= b1 + margin and b0 <= a1 + margin


def _axis_distance(p1, d1, p2) -> float:
    """Distância de p2 à reta (p1, d1)."""
    v = p2 - p1
    return float(np.linalg.norm(v - np.dot(v, d1) * d1))


class JointFinder:
    def __init__(self, components: ComponentManager) -> None:
        self.components = components
        self.engine = components.engine

    def find(self, max_gap: float = 1.0, tol: float = 0.02, axis_tol: float = 0.05,
             min_cyl_area: float = 20.0, only_visible: bool = False) -> JointReport:
        leaves = [l for l in self.components.leaves()
                  if l.shape is not None and (not only_visible or l.visible)]
        faces = {l.id: self.engine.analytic_faces(l.shape) for l in leaves}
        boxes = {l.id: self.components.bbox(l) for l in leaves}
        joints: list[Joint] = []
        checked = 0
        margin = max(max_gap, tol) + 0.01
        for a, b in itertools.combinations(leaves, 2):
            ba, bb = boxes[a.id], boxes[b.id]
            if ba is None or bb is None:
                continue
            if np.any(ba.min > bb.max + margin) or np.any(bb.min > ba.max + margin):
                continue
            checked += 1
            joints += self._concentric(a, b, faces, boxes, max_gap, axis_tol, min_cyl_area, margin)
            joints += self._planar(a, b, faces, boxes, tol, margin)
        # agrupamento (componentes conexos)
        parent = {l.id: l.id for l in leaves}

        def root(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        for j in joints:
            parent[root(j.a_id)] = root(j.b_id)
        groups: dict[str, list[str]] = {}
        names = {l.id: l.name for l in leaves}
        for l in leaves:
            groups.setdefault(root(l.id), []).append(l.id)
        linked = {x for j in joints for x in (j.a_id, j.b_id)}
        clusters = sorted(([names[i] for i in ids] for ids in groups.values() if len(ids) > 1), key=len, reverse=True)
        return JointReport(self.declared() + joints, len(leaves), checked,
                           [names[l.id] for l in leaves if l.id not in linked], clusters)

    def declared(self) -> list[Joint]:
        """Juntas gravadas no arquivo de origem (FCStd), ligadas às peças pelo nome interno do objeto."""
        from modules.declared_joints import JOINT_LABELS, KIND_DECLARED, DeclaredJoint, resolve_name
        root = self.components.root
        raw = root.metadata.get("fc_joints") if root is not None else None
        if not raw:
            return []
        by_name = {n.metadata["fc_name"]: n for n in self.components.root.walk() if n.metadata.get("fc_name")}
        out: list[Joint] = []
        for d in raw:
            dj = DeclaredJoint.from_dict(d)
            a, b = resolve_name(dj.obj1, dj.sub1, by_name), resolve_name(dj.obj2, dj.sub2, by_name)
            tipo = JOINT_LABELS.get(dj.joint_type, dj.joint_type) + (" (tipo pela ordem padrão do FreeCAD 1.0)" if dj.type_assumed else "")
            det = f"{dj.label}: {tipo}; {dj.obj1}.{dj.sub1} ↔ {dj.obj2}.{dj.sub2}"
            if a is None or b is None:
                det += " — peça(s) não encontrada(s) no modelo importado"
            out.append(Joint(f"{KIND_DECLARED}: {JOINT_LABELS.get(dj.joint_type, dj.joint_type)}",
                             a.id if a else "", b.id if b else "", a.name if a else dj.obj1, b.name if b else dj.obj2,
                             det, inferred=False))
        return out

    # ---------------------------------------------------------------- concêntricas
    def _concentric(self, a, b, faces, boxes, max_gap, axis_tol, min_area, margin) -> list[Joint]:
        best: dict[tuple, Joint] = {}
        for ca in faces[a.id][0]:
            if ca.area < min_area:
                continue
            for cb in faces[b.id][0]:
                if cb.area < min_area:
                    continue
                if abs(float(np.dot(ca.axis, cb.axis))) < 0.9999:
                    continue
                if _axis_distance(ca.point, ca.axis, cb.point) > axis_tol:
                    continue
                gap = abs(ca.radius - cb.radius)
                if gap > max_gap:
                    continue
                if not _overlap_along(boxes[a.id], boxes[b.id], ca.axis, margin):
                    continue
                inner, outer = (a, b) if ca.radius <= cb.radius else (b, a)
                r_in, r_out = sorted((ca.radius, cb.radius))
                kind_txt = ("coincidentes (ajuste justo)" if gap < 1e-3 else
                            f"folga radial {gap:.3f} mm")
                key = (round(r_in, 2), round(r_out, 2), tuple(np.round(np.abs(ca.axis), 3)))
                if key in best:
                    continue
                best[key] = Joint(KIND_CONCENTRIC, a.id, b.id, a.name, b.name,
                                  f"Ø {2 * r_in:.2f} em Ø {2 * r_out:.2f} mm — {kind_txt}; "
                                  f"eixo {_axis_name(ca.axis)}; interno: {inner.name}",
                                  gap=gap, axis=tuple(float(x) for x in ca.axis), radius_a=ca.radius, radius_b=cb.radius)
        # uma junta por par e conjunto de raios; limita ruído (muitas faces iguais) a 3 por par
        return sorted(best.values(), key=lambda j: j.gap)[:3]

    # ---------------------------------------------------------------- planas
    def _planar(self, a, b, faces, boxes, tol, margin, min_overlap: float = 0.5) -> list[Joint]:
        found: Optional[Joint] = None
        for pa in faces[a.id][1]:
            for pb in faces[b.id][1]:
                if float(np.dot(pa.normal, pb.normal)) > -0.9999:
                    continue
                d = abs(float(np.dot(pb.point - pa.point, pa.normal)))
                if d > tol:
                    continue
                if pa.bounds is None or pb.bounds is None:
                    continue
                # contato real: as caixas das duas faces (coplanares) se sobrepõem com área > 0
                lo = np.maximum(pa.bounds[0], pb.bounds[0])
                hi = np.minimum(pa.bounds[1], pb.bounds[1])
                ext = hi - lo
                if np.any(ext < -tol) or np.sum(ext > min_overlap) < 2:
                    continue
                if found is None or d < found.gap:
                    found = Joint(KIND_PLANAR, a.id, b.id, a.name, b.name,
                                  f"faces coplanares (normal {_axis_name(pa.normal)}), distância {d:.4f} mm",
                                  gap=d, axis=tuple(float(x) for x in pa.normal))
        return [found] if found else []


def _axis_name(v) -> str:
    v = np.asarray(v, dtype=float)
    i = int(np.argmax(np.abs(v)))
    if abs(v[i]) > 0.9999:
        return "XYZ"[i]
    return f"({v[0]:.2f}, {v[1]:.2f}, {v[2]:.2f})"


def export_csv(report: JointReport, path: str | Path) -> Path:
    path = Path(path)
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["Tipo", "Peça A", "Peça B", "Detalhe", "Folga/distância (mm)", "Origem"])
        for j in report.joints:
            w.writerow([j.kind, j.a_name, j.b_name, j.detail, "" if j.gap is None else f"{j.gap:.4f}",
                        "inferida da geometria" if j.inferred else "gravada no arquivo FCStd"])
        w.writerow([])
        w.writerow([report.summary()])
    return path
