"""Gerenciador de seleção compartilhado entre a árvore e a visualização 3D.

Árvore e viewport não se conhecem: ambos falam com este objeto. Cada mudança
informa a ORIGEM (``source``) para que quem originou a seleção não reaja ao
próprio eco (evita laços infinitos entre árvore e 3D).
"""
from __future__ import annotations

from typing import Callable, Iterable

Listener = Callable[[list[str], str], None]


class SelectionManager:
    def __init__(self) -> None:
        self._selected: list[str] = []
        self._listeners: list[Listener] = []

    @property
    def selected(self) -> list[str]:
        return list(self._selected)

    @property
    def primary(self) -> str | None:
        """Último componente selecionado (alvo do Component Inspector)."""
        return self._selected[-1] if self._selected else None

    def subscribe(self, listener: Listener) -> None:
        self._listeners.append(listener)

    def select(self, ids: Iterable[str] | str | None, source: str = "api", additive: bool = False) -> None:
        if ids is None:
            new: list[str] = []
        elif isinstance(ids, str):
            new = [ids]
        else:
            new = list(dict.fromkeys(ids))
        if additive:
            new = list(dict.fromkeys(self._selected + new))
        if new == self._selected:
            return
        self._selected = new
        for listener in list(self._listeners):
            listener(list(self._selected), source)

    def clear(self, source: str = "api") -> None:
        self.select(None, source)

    def toggle(self, component_id: str, source: str = "api") -> None:
        if component_id in self._selected:
            self.select([i for i in self._selected if i != component_id], source)
        else:
            self.select([component_id], source, additive=True)

    def prune(self, valid_ids: set[str], source: str = "api") -> None:
        """Remove da seleção ids que deixaram de existir (ex.: após dividir sólidos)."""
        self.select([i for i in self._selected if i in valid_ids], source)
