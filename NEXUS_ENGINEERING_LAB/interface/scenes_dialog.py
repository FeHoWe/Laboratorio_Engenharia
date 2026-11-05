"""Gerenciador de cenas salvas: aplicar, renomear, excluir."""
from __future__ import annotations

from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QListWidget, QPushButton, QVBoxLayout)


class ScenesDialog(QDialog):
    def __init__(self, window, parent=None) -> None:
        super().__init__(parent or window)
        self.win = window
        self.setWindowTitle("Cenas salvas")
        self.resize(460, 380)
        self.list = QListWidget()
        self.info = QLabel("")
        self.info.setWordWrap(True)
        self.apply_btn = QPushButton("Aplicar")
        self.save_btn = QPushButton("Salvar cena atual…")
        self.rename_btn = QPushButton("Renomear…")
        self.delete_btn = QPushButton("Excluir")
        close = QPushButton("Fechar")
        close.clicked.connect(self.accept)
        row = QHBoxLayout()
        for b in (self.apply_btn, self.save_btn, self.rename_btn, self.delete_btn):
            row.addWidget(b)
        lay = QVBoxLayout(self)
        lay.addWidget(self.list, 1)
        lay.addWidget(self.info)
        lay.addLayout(row)
        lay.addWidget(close)
        self.list.currentItemChanged.connect(self._show)
        self.list.itemDoubleClicked.connect(lambda _i: self._apply())
        self.apply_btn.clicked.connect(self._apply)
        self.save_btn.clicked.connect(self._save)
        self.rename_btn.clicked.connect(self._rename)
        self.delete_btn.clicked.connect(self._delete)
        self.refill()

    def _name(self):
        it = self.list.currentItem()
        return it.text() if it else None

    def refill(self, select: str | None = None) -> None:
        self.list.clear()
        for n in self.win.project.scenes.names():
            self.list.addItem(n)
        if self.list.count():
            row = self.win.project.scenes.names().index(select) if select in self.win.project.scenes.names() else 0
            self.list.setCurrentRow(row)
        self._show(self.list.currentItem())

    def _show(self, item, _prev=None) -> None:
        has = item is not None
        for b in (self.apply_btn, self.rename_btn, self.delete_btn):
            b.setEnabled(has)
        if not has:
            self.info.setText("Nenhuma cena salva. Monte a vista desejada (câmera, explosão, corte) e use “Salvar cena atual…”.")
            return
        s = self.win.project.scenes.get(item.text())
        sec = "sem corte" if not s.section else f"corte plano {'XYZ'[s.section['axis']]} a {s.section['fraction'] * 100:.0f}%"
        self.info.setText(f"{len(s.offsets)} peça(s) deslocada(s) · {len(s.hidden)} oculta(s) · {sec} · "
                          f"{'holograma' if s.holo else 'sólido'} · criada em {s.created.replace('T', ' ')}")

    def _apply(self) -> None:
        if self._name():
            self.win.apply_scene(self._name())

    def _save(self) -> None:
        name = self.win.save_scene_dialog()
        if name:
            self.refill(name)

    def _rename(self) -> None:
        old = self._name()
        if old and (new := self.win.rename_scene_dialog(old)):
            self.refill(new)

    def _delete(self) -> None:
        if self._name():
            self.win.delete_scene(self._name())
            self.refill()
