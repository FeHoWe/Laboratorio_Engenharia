"""Modelo de dados do NEXUS: a árvore de componentes.

Decisão de arquitetura (arquivo extra em relação à estrutura sugerida):
    ``model.py`` concentra as classes de dados puras, para que geometria,
    importação, explosão, interface e salvamento compartilhem o MESMO vocabulário
    sem se importarem entre si.

Ideia central — a geometria NUNCA é alterada pela explosão:
    * ``shape`` / ``mesh`` guardam a geometria original, já no espaço do mundo
      (a posição de cada instância da montagem é "assada" na geometria).
    * ``offset`` é um deslocamento próprio do componente, aplicado somente na
      exibição. Restaurar a montagem = zerar todos os ``offset``.
    * O deslocamento efetivo de uma peça é a soma dos ``offset`` dos seus
      ancestrais mais o próprio (mover um grupo move todos os seus filhos).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterator, Optional

import numpy as np


class ComponentKind(str, Enum):
    ASSEMBLY = "assembly"  # montagem vinda do arquivo (ex.: STEP com instâncias)
    GROUP = "group"        # agrupamento (FreeCAD, objetos OBJ, criado pelo usuário)
    PART = "part"          # peça com geometria própria


class GeometryKind(str, Enum):
    NONE = "none"              # nós sem geometria própria (montagens e grupos)
    SOLID = "solid"            # BRep com exatamente 1 sólido
    MULTI_SOLID = "multi_solid"  # BRep com vários sólidos independentes
    SHELL = "shell"            # BRep sem sólidos (cascas/superfícies)
    MESH = "mesh"              # malha com 1 corpo conexo
    MESH_MULTI = "mesh_multi"  # malha com vários corpos desconexos

    @property
    def label(self) -> str:
        return {
            "none": "Sem geometria própria",
            "solid": "Sólido B-Rep",
            "multi_solid": "Objeto com vários sólidos (B-Rep)",
            "shell": "Cascas/superfícies B-Rep (sem sólido)",
            "mesh": "Malha triangular",
            "mesh_multi": "Malha com vários corpos desconexos",
        }[self.value]


@dataclass
class MeshData:
    """Malha triangular: ``vertices`` (N,3) float64 e ``faces`` (M,3) int64."""

    vertices: np.ndarray
    faces: np.ndarray
    normals: Optional[np.ndarray] = None  # (N,3) — opcional

    def __post_init__(self) -> None:
        self.vertices = np.asarray(self.vertices, dtype=np.float64).reshape(-1, 3)
        self.faces = np.asarray(self.faces, dtype=np.int64).reshape(-1, 3)

    @property
    def is_empty(self) -> bool:
        return len(self.faces) == 0


class IdGenerator:
    """Gera identificadores estáveis e legíveis (C0001, C0002, ...)."""

    def __init__(self, start: int = 0) -> None:
        self._n = start

    def next(self) -> str:
        self._n += 1
        return f"C{self._n:04d}"

    def observe(self, existing_id: str) -> None:
        """Garante que novos ids não colidam com ids carregados de um projeto."""
        if existing_id.startswith("C") and existing_id[1:].isdigit():
            self._n = max(self._n, int(existing_id[1:]))

    @property
    def counter(self) -> int:
        return self._n


@dataclass
class Component:
    """Um nó da árvore do projeto (montagem, grupo ou peça)."""

    id: str
    name: str
    kind: ComponentKind = ComponentKind.PART
    children: list["Component"] = field(default_factory=list)
    parent: Optional["Component"] = field(default=None, repr=False, compare=False)

    # Geometria original (espaço do mundo). Apenas peças têm shape OU mesh.
    shape: Any = field(default=None, repr=False, compare=False)  # OCP TopoDS_Shape
    mesh: Optional[MeshData] = field(default=None, repr=False, compare=False)
    geometry_kind: GeometryKind = GeometryKind.NONE

    # Transformação acumulada da instância no arquivo de origem (metadado).
    placement: np.ndarray = field(default_factory=lambda: np.eye(4))

    visible: bool = True
    material: Optional[str] = None
    offset: np.ndarray = field(default_factory=lambda: np.zeros(3))

    # Geometria importada não tem histórico de construção (ver docs/ARQUITETURA.md).
    parametric: bool = False
    source: str = ""                      # arquivo/objeto de origem
    metadata: dict = field(default_factory=dict)
    split_backup: Optional[dict] = field(default=None, repr=False, compare=False)

    # ------------------------------------------------------------------ árvore
    @property
    def is_leaf(self) -> bool:
        return not self.children

    @property
    def has_geometry(self) -> bool:
        return self.shape is not None or (self.mesh is not None and not self.mesh.is_empty)

    def add_child(self, child: "Component", index: Optional[int] = None) -> "Component":
        child.parent = self
        if index is None:
            self.children.append(child)
        else:
            self.children.insert(index, child)
        return child

    def remove_child(self, child: "Component") -> None:
        self.children.remove(child)
        child.parent = None

    def ancestors(self) -> Iterator["Component"]:
        node = self.parent
        while node is not None:
            yield node
            node = node.parent

    def depth(self) -> int:
        return sum(1 for _ in self.ancestors())

    def walk(self) -> Iterator["Component"]:
        """Percorre este nó e todos os descendentes (pré-ordem)."""
        yield self
        for c in self.children:
            yield from c.walk()

    def leaves(self) -> Iterator["Component"]:
        """Descendentes com geometria própria (peças)."""
        for n in self.walk():
            if n.has_geometry:
                yield n

    def effective_offset(self) -> np.ndarray:
        """Deslocamento total de exibição (ancestrais + próprio)."""
        total = np.array(self.offset, dtype=np.float64)
        for a in self.ancestors():
            total = total + a.offset
        return total

    def is_displaced(self, tol: float = 1e-9) -> bool:
        return bool(np.linalg.norm(self.effective_offset()) > tol)
