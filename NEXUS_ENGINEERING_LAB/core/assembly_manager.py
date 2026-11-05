"""Gerenciamento da montagem: estado de explosão, restauração e agrupamento.

Faz a ponte entre o algoritmo puro (:mod:`modules.explode_engine`) e o modelo:
aplica deslocamentos, garante a restauração exata e permite ao usuário criar
agrupamentos próprios (ex.: "Trem de válvulas").

"Relações de montagem": o STEP/FCStd preserva hierarquia e a posição (matriz) de
cada instância — o NEXUS guarda ambos em ``Component.placement`` e na árvore.
Restrições cinemáticas (mates, juntas) normalmente NÃO existem em STEP/FCStd e
portanto não são inventadas aqui; a explosão apenas desloca, nunca altera
posição original, o que permite reconstruir a montagem exatamente.
"""
from __future__ import annotations

from typing import Iterable, Optional

import numpy as np

from core.component_manager import ComponentManager
from core.model import Component, ComponentKind, GeometryKind
from modules.explode_engine import ExplodeEngine, ExplodeParams


class AssemblyManager:
    def __init__(self, components: ComponentManager) -> None:
        self.components = components
        self.engine = ExplodeEngine(components.bbox)

    # --------------------------------------------------------------- estado
    @property
    def root(self) -> Component:
        assert self.components.root is not None, "Projeto sem componentes"
        return self.components.root

    def current_offsets(self) -> dict[str, np.ndarray]:
        return {n.id: np.array(n.offset) for n in self.root.walk()}

    def apply_offsets(self, offsets: dict[str, np.ndarray]) -> list[str]:
        """Grava offsets nos componentes; devolve ids cujo deslocamento mudou."""
        changed = []
        for cid, off in offsets.items():
            node = self.components.find(cid)
            if node is None:
                continue
            new = np.asarray(off, dtype=np.float64)
            if not np.allclose(node.offset, new, atol=1e-12):
                node.offset = new.copy()
                changed.append(cid)
        return changed

    def is_exploded(self) -> bool:
        return any(np.linalg.norm(n.offset) > 1e-9 for n in self.root.walk())

    # ---------------------------------------------------- alvos de explosão
    def target_explode_all(self, params: ExplodeParams) -> dict[str, np.ndarray]:
        return self.engine.explode_all(self.root, params)

    def target_explode_group(self, group_id: str, params: ExplodeParams) -> dict[str, np.ndarray]:
        group = self.components.get(group_id)
        if not group.children:
            raise ValueError(f"'{group.name}' não é um grupo/montagem; use 'Separar peça'.")
        return self.engine.explode_group(self.root, group, params)

    def target_separate_part(self, part_id: str, params: ExplodeParams) -> dict[str, np.ndarray]:
        part = self.components.get(part_id)
        if part is self.root:
            raise ValueError("A raiz do projeto não pode ser separada de si mesma.")
        return self.engine.separate_part(self.root, part, params)

    def target_restore(self) -> dict[str, np.ndarray]:
        return self.engine.restore(self.root)

    def restore(self) -> list[str]:
        """Restaura imediatamente a montagem original (sem animação)."""
        return self.apply_offsets(self.target_restore())

    def verify_restored(self, tol: float = 1e-9) -> bool:
        """Garante que a montagem voltou à posição original (todos os offsets nulos)."""
        return all(np.linalg.norm(n.offset) <= tol for n in self.root.walk())

    # -------------------------------------------------------------- agrupamento
    def group_components(self, ids: Iterable[str], name: str) -> Component:
        """Cria um grupo contendo os componentes escolhidos (geometria intacta).

        O grupo nasce na posição do primeiro componente escolhido. A posição
        mundial das peças não muda, pois os deslocamentos são relativos ao mundo.
        """
        nodes = [self.components.get(i) for i in dict.fromkeys(ids)]
        if len(nodes) < 2:
            raise ValueError("Selecione ao menos dois componentes para agrupar.")
        root = self.root
        if root in nodes:
            raise ValueError("A raiz do projeto não pode ser agrupada.")
        # evita agrupar um nó junto com seu próprio descendente
        selected = {n.id for n in nodes}
        nodes = [n for n in nodes if not any(a.id in selected for a in n.ancestors())]
        if len(nodes) < 2:
            raise ValueError("Os componentes escolhidos já pertencem uns aos outros.")

        if self.is_exploded():
            raise ValueError("Restaure a montagem antes de agrupar componentes "
                             "(os deslocamentos da explosão dependem da hierarquia).")

        first_parent = nodes[0].parent or root
        index = first_parent.children.index(nodes[0])
        group = Component(id=self.components.ids.next(), name=name.strip() or "Grupo",
                          kind=ComponentKind.GROUP, geometry_kind=GeometryKind.NONE)
        for n in nodes:
            n.parent.remove_child(n)  # type: ignore[union-attr]
        first_parent.add_child(group, index=min(index, len(first_parent.children)))
        for n in nodes:
            group.add_child(n)
        self.components.reindex()
        return group

    def ungroup(self, group_id: str) -> list[str]:
        """Desfaz um grupo, devolvendo os filhos ao pai original."""
        group = self.components.get(group_id)
        if group.parent is None:
            raise ValueError("A raiz do projeto não pode ser desagrupada.")
        if group.has_geometry:
            raise ValueError(f"'{group.name}' é uma peça, não um grupo.")
        if self.is_exploded():
            raise ValueError("Restaure a montagem antes de desagrupar.")
        parent = group.parent
        index = parent.children.index(group)
        kids = list(group.children)
        for k in kids:
            group.remove_child(k)
        parent.remove_child(group)
        for offset, k in enumerate(kids):
            parent.add_child(k, index=index + offset)
        self.components.reindex()
        return [k.id for k in kids]
