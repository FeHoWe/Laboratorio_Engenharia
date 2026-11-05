"""Gerenciador da árvore de componentes de um projeto.

Responsabilidades: índice por id, caixas delimitadoras em repouso, malhas de
exibição (cache), visibilidade/isolamento e atribuição de material.
Não conhece interface nem arquivos: apenas o modelo.
"""
from __future__ import annotations

from typing import Iterable, Iterator, Optional

import numpy as np

from core.cad_engine import CadEngine
from core.geometry import BoundingBox
from core.model import Component, IdGenerator, MeshData


class ComponentManager:
    def __init__(self, engine: CadEngine, root: Optional[Component] = None, ids: Optional[IdGenerator] = None) -> None:
        self.engine = engine
        self.ids = ids or IdGenerator()
        self.root: Optional[Component] = None
        self._index: dict[str, Component] = {}
        self._bbox_cache: dict[str, Optional[BoundingBox]] = {}
        self._mesh_cache: dict[str, MeshData] = {}
        if root is not None:
            self.set_root(root)

    # ------------------------------------------------------------------ índice
    def set_root(self, root: Component) -> None:
        self.root = root
        self.reindex()

    def reindex(self) -> None:
        """Reconstrói índice e caches (chamar após alterar a estrutura da árvore)."""
        self._index = {}
        if self.root is not None:
            for node in self.root.walk():
                self.ids.observe(node.id)
                self._index[node.id] = node
        self._bbox_cache = {}
        self._mesh_cache = {k: v for k, v in self._mesh_cache.items() if k in self._index}

    def get(self, component_id: str) -> Component:
        try:
            return self._index[component_id]
        except KeyError:
            raise KeyError(f"Componente inexistente: {component_id}") from None

    def find(self, component_id: str) -> Optional[Component]:
        return self._index.get(component_id)

    def all(self) -> Iterator[Component]:
        return iter(self._index.values())

    def leaves(self, node: Optional[Component] = None) -> list[Component]:
        node = node or self.root
        return list(node.leaves()) if node is not None else []

    def ids_set(self) -> set[str]:
        return set(self._index)

    # -------------------------------------------------------------- geometria
    def own_bbox(self, comp: Component) -> Optional[BoundingBox]:
        """Caixa da geometria própria do componente, na posição ORIGINAL."""
        if comp.shape is not None:
            return self.engine.bbox(comp.shape)
        if comp.mesh is not None and not comp.mesh.is_empty:
            return BoundingBox.from_points(comp.mesh.vertices)
        return None

    def bbox(self, node: Component) -> Optional[BoundingBox]:
        """Caixa delimitadora do nó (e descendentes) em repouso — sem explosão."""
        if node.id in self._bbox_cache:
            return self._bbox_cache[node.id]
        boxes = [self.own_bbox(node)] if node.has_geometry else []
        boxes += [self.bbox(c) for c in node.children]
        result = BoundingBox.union(boxes)
        self._bbox_cache[node.id] = result
        return result

    def displayed_bbox(self, node: Component) -> Optional[BoundingBox]:
        """Caixa considerando os deslocamentos atuais da explosão."""
        boxes = []
        for leaf in node.leaves():
            b = self.own_bbox(leaf)
            if b is not None:
                boxes.append(b.translated(leaf.effective_offset()))
        return BoundingBox.union(boxes)

    def render_mesh(self, comp: Component) -> MeshData:
        """Malha de exibição (B-Rep é triangulado sob demanda e guardado em cache)."""
        if comp.id in self._mesh_cache:
            return self._mesh_cache[comp.id]
        if comp.shape is not None:
            mesh = self.engine.tessellate(comp.shape)
        elif comp.mesh is not None:
            mesh = comp.mesh
        else:
            raise ValueError(f"'{comp.name}' não possui geometria.")
        self._mesh_cache[comp.id] = mesh
        return mesh

    def invalidate(self, comp_id: str) -> None:
        self._mesh_cache.pop(comp_id, None)
        self._bbox_cache = {}

    # -------------------------------------------------------------- visibilidade
    def set_visible(self, component_id: str, visible: bool, recursive: bool = True) -> list[str]:
        node = self.get(component_id)
        nodes = list(node.walk()) if recursive else [node]
        for n in nodes:
            n.visible = visible
        return [n.id for n in nodes]

    def show_all(self) -> list[str]:
        changed = []
        for n in self._index.values():
            if not n.visible:
                n.visible = True
                changed.append(n.id)
        return changed

    def isolate(self, ids: Iterable[str]) -> None:
        """Mostra somente os componentes escolhidos (e seus descendentes)."""
        keep: set[str] = set()
        for cid in ids:
            node = self.get(cid)
            keep.update(n.id for n in node.walk())
            keep.update(a.id for a in node.ancestors())  # contêineres precisam ficar visíveis
        for n in self._index.values():
            n.visible = n.id in keep

    def is_effectively_visible(self, comp: Component) -> bool:
        return comp.visible and all(a.visible for a in comp.ancestors())

    # ----------------------------------------------------------------- material
    def set_material(self, component_id: str, material_name: Optional[str], recursive: bool = True) -> list[str]:
        node = self.get(component_id)
        nodes = list(node.walk()) if recursive else [node]
        changed = []
        for n in nodes:
            if n.has_geometry or not recursive:
                n.material = material_name
                changed.append(n.id)
        return changed

    # ------------------------------------------------------------------ resumos
    def counts(self) -> dict:
        nodes = list(self._index.values())
        return {
            "total": len(nodes),
            "parts": sum(1 for n in nodes if n.has_geometry),
            "groups": sum(1 for n in nodes if n.children),
            "hidden": sum(1 for n in nodes if not n.visible),
        }

    def displaced_ids(self) -> list[str]:
        return [n.id for n in self._index.values() if n.has_geometry and n.is_displaced()]
