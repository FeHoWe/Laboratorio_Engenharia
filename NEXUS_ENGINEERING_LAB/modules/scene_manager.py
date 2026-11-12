"""Cenas salvas — V1.6.

Uma cena é um "instantâneo de exibição" nomeado: câmera, explosão (deslocamentos), visibilidade,
corte de seção, estilo e seleção. Cenas NÃO alteram a geometria; só como o modelo é mostrado.
Ficam dentro do arquivo .nexus. Ids que não existem mais (peça dividida/apagada) são ignorados
ao aplicar, e o resultado informa quantos foram ignorados.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Scene:
    name: str
    camera: dict = field(default_factory=dict)        # position, focal, up (3 floats), scale (parallel), parallel (bool)
    offsets: dict = field(default_factory=dict)       # id -> [x, y, z] (só os não nulos)
    hidden: list = field(default_factory=list)        # ids com visible=False
    section: Optional[dict] = None                    # {"axis": 0-2, "fraction": 0-1, "flip": bool}
    holo: bool = True
    edges: bool = True
    selection: list = field(default_factory=list)
    poses: dict = field(default_factory=dict)         # V1.8: id -> 16 números (matriz 4x4 de exibição, linha a linha)
    kin_deg: Optional[float] = None                   # V1.8: ângulo de entrada da animação, se ativa
    note: str = ""
    created: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Scene":
        known = {k: d[k] for k in cls.__dataclass_fields__ if k in d}
        return cls(**known)


class SceneStore:
    def __init__(self) -> None:
        self._scenes: list[Scene] = []

    def __len__(self) -> int:
        return len(self._scenes)

    def __iter__(self):
        return iter(self._scenes)

    def names(self) -> list[str]:
        return [s.name for s in self._scenes]

    def get(self, name: str) -> Optional[Scene]:
        return next((s for s in self._scenes if s.name == name), None)

    def add(self, scene: Scene, replace: bool = False) -> Scene:
        scene.name = scene.name.strip()
        if not scene.name:
            raise ValueError("A cena precisa de um nome.")
        old = self.get(scene.name)
        if old is not None:
            if not replace:
                raise ValueError(f"Já existe uma cena chamada '{scene.name}'.")
            self._scenes[self._scenes.index(old)] = scene
        else:
            self._scenes.append(scene)
        return scene

    def remove(self, name: str) -> bool:
        s = self.get(name)
        if s is None:
            return False
        self._scenes.remove(s)
        return True

    def rename(self, old: str, new: str) -> None:
        s = self.get(old)
        new = new.strip()
        if s is None:
            raise KeyError(old)
        if not new:
            raise ValueError("A cena precisa de um nome.")
        if new != old and self.get(new) is not None:
            raise ValueError(f"Já existe uma cena chamada '{new}'.")
        s.name = new

    def to_list(self) -> list[dict]:
        return [s.to_dict() for s in self._scenes]

    @classmethod
    def from_list(cls, items: list[dict]) -> "SceneStore":
        st = cls()
        for d in items or []:
            try:
                st._scenes.append(Scene.from_dict(d))
            except (TypeError, KeyError):
                continue          # entrada corrompida não derruba o projeto
        return st
