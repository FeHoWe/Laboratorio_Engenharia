"""Identificação e separação de sólidos compostos (requisito 5.5).

Arquivo extra em relação à estrutura sugerida: o requisito 5.5 pede "um módulo",
e ele não pertence nem ao importador nem à explosão.

Princípios:
    * IDENTIFICAR é automático e não altera nada.
    * SEPARAR só acontece quando o usuário pede, e é REVERSÍVEL
      (o objeto original fica guardado em ``split_backup``).
    * Um sólido B-Rep conexo NUNCA é cortado: separamos apenas sólidos
      topologicamente independentes (cada um mantém a geometria exata original,
      sem reconstruir nem aproximar nada). Para malhas, a unidade independente é
      o "corpo conexo" (triângulos ligados por vértices compartilhados).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from core.lazy import lazy_import
trimesh = lazy_import("trimesh")

from core.cad_engine import CadEngine
from core.model import Component, ComponentKind, GeometryKind, IdGenerator, MeshData


@dataclass
class AnalysisReport:
    """Resumo da estrutura de um projeto importado."""

    single_solid: list[str] = field(default_factory=list)
    multi_solid: list[str] = field(default_factory=list)   # ids dos objetos com vários sólidos/corpos
    shells: list[str] = field(default_factory=list)
    meshes: list[str] = field(default_factory=list)
    assemblies: list[str] = field(default_factory=list)
    groups: list[str] = field(default_factory=list)

    @property
    def has_splittable(self) -> bool:
        return bool(self.multi_solid)

    def summary(self) -> str:
        parts = [
            f"{len(self.single_solid)} objeto(s) com um sólido",
            f"{len(self.multi_solid)} objeto(s) com vários sólidos",
            f"{len(self.assemblies)} montagem(ns)",
            f"{len(self.groups)} grupo(s)",
        ]
        if self.shells:
            parts.append(f"{len(self.shells)} objeto(s) só com superfícies")
        if self.meshes:
            parts.append(f"{len(self.meshes)} malha(s)")
        return "; ".join(parts)


def mesh_body_labels(mesh: MeshData) -> np.ndarray:
    """Rótulo de corpo conexo por triângulo (vértices compartilhados ligam triângulos)."""
    tm = trimesh.Trimesh(mesh.vertices, mesh.faces, process=False)
    # vértices coincidentes (STL) precisam ser fundidos para detectar conectividade
    tm.merge_vertices()
    if len(tm.faces) == 0:
        return np.zeros(0, dtype=int)
    return trimesh.graph.connected_component_labels(tm.face_adjacency, node_count=len(tm.faces))


def classify(comp: Component, engine: CadEngine) -> GeometryKind:
    """Classifica a geometria PRÓPRIA do componente (não considera filhos)."""
    if comp.shape is not None:
        n = engine.count_solids(comp.shape)
        if n == 0:
            return GeometryKind.SHELL
        return GeometryKind.SOLID if n == 1 else GeometryKind.MULTI_SOLID
    if comp.mesh is not None and not comp.mesh.is_empty:
        labels = mesh_body_labels(comp.mesh)
        return GeometryKind.MESH if (labels.size == 0 or labels.max() == 0) else GeometryKind.MESH_MULTI
    return GeometryKind.NONE


def analyze_tree(root: Component, engine: CadEngine) -> AnalysisReport:
    """Classifica todos os nós e devolve o resumo. Atualiza ``geometry_kind``."""
    report = AnalysisReport()
    for node in root.walk():
        if node is root:
            continue
        if node.has_geometry:
            node.geometry_kind = classify(node, engine)
            bucket = {
                GeometryKind.SOLID: report.single_solid,
                GeometryKind.MULTI_SOLID: report.multi_solid,
                GeometryKind.MESH_MULTI: report.multi_solid,
                GeometryKind.SHELL: report.shells,
                GeometryKind.MESH: report.meshes,
            }[node.geometry_kind]
            bucket.append(node.id)
        else:
            node.geometry_kind = GeometryKind.NONE
            (report.assemblies if node.kind == ComponentKind.ASSEMBLY else report.groups).append(node.id)
    return report


def can_split(comp: Component) -> bool:
    return comp.has_geometry and comp.geometry_kind in (GeometryKind.MULTI_SOLID, GeometryKind.MESH_MULTI)


def split_into_solids(comp: Component, engine: CadEngine, ids: IdGenerator) -> list[Component]:
    """Converte um objeto composto em um grupo de peças individuais.

    O objeto vira um GRUPO cujos filhos são os sólidos (ou corpos de malha). A
    geometria original é guardada para :func:`undo_split`.
    """
    if not can_split(comp):
        raise ValueError(f"'{comp.name}' não contém vários sólidos independentes.")

    backup = {"shape": comp.shape, "mesh": comp.mesh, "geometry_kind": comp.geometry_kind,
              "kind": comp.kind}
    children: list[Component] = []

    if comp.shape is not None:
        for i, solid in enumerate(engine.solids(comp.shape), start=1):
            children.append(Component(
                id=ids.next(), name=f"{comp.name} · sólido {i}", kind=ComponentKind.PART,
                shape=solid, geometry_kind=GeometryKind.SOLID, placement=comp.placement.copy(),
                material=comp.material, source=comp.source, metadata=dict(comp.metadata)))
    else:
        mesh = comp.mesh
        labels = mesh_body_labels(mesh)
        tm = trimesh.Trimesh(mesh.vertices, mesh.faces, process=False)
        tm.merge_vertices()
        for i, label in enumerate(sorted(set(labels.tolist())), start=1):
            piece = tm.submesh([np.where(labels == label)[0]], append=True)
            children.append(Component(
                id=ids.next(), name=f"{comp.name} · corpo {i}", kind=ComponentKind.PART,
                mesh=MeshData(np.asarray(piece.vertices), np.asarray(piece.faces)),
                geometry_kind=GeometryKind.MESH, placement=comp.placement.copy(),
                material=comp.material, source=comp.source, metadata=dict(comp.metadata)))

    comp.split_backup = backup
    comp.shape = None
    comp.mesh = None
    comp.geometry_kind = GeometryKind.NONE
    comp.kind = ComponentKind.GROUP
    comp.metadata["split_from_composite"] = True
    for child in children:
        comp.add_child(child)
    return children


def undo_split(comp: Component) -> list[str]:
    """Desfaz a separação e devolve os ids removidos."""
    if comp.split_backup is None:
        raise ValueError(f"'{comp.name}' não foi separado (nada a desfazer).")
    removed = [c.id for c in comp.walk() if c is not comp]
    for child in list(comp.children):
        comp.remove_child(child)
    backup = comp.split_backup
    comp.shape = backup["shape"]
    comp.mesh = backup["mesh"]
    comp.geometry_kind = backup["geometry_kind"]
    comp.kind = backup["kind"]
    comp.offset = np.zeros(3)
    comp.metadata.pop("split_from_composite", None)
    comp.split_backup = None
    return removed
