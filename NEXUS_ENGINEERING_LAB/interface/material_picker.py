"""Seletor de materiais com busca e filtro por categoria (banco SQL de densidades)."""
from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QVBoxLayout)

from modules.material_manager import MaterialLibrary

ALL = "Todas as categorias"


class MaterialPicker(QDialog):
    def __init__(self, library: MaterialLibrary, parent=None, current: Optional[str] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Banco de materiais")
        self.resize(560, 520)
        self.library = library
        self.selected: Optional[str] = None

        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar (ex.: 6061, inox, nylon, óleo, carvalho)…")
        self.category = QComboBox()
        self.category.addItem(ALL)
        self.category.addItems(library.categories())
        self.list = QListWidget()
        self.info = QLabel("")
        self.info.setWordWrap(True)
        self.info.setOpenExternalLinks(True)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addWidget(self.search)
        lay.addWidget(self.category)
        lay.addWidget(self.list, 1)
        lay.addWidget(self.info)
        lay.addWidget(self.buttons)

        self.search.textChanged.connect(self._fill)
        self.category.currentIndexChanged.connect(self._fill)
        self.list.currentItemChanged.connect(self._show_info)
        self.list.itemDoubleClicked.connect(lambda _i: self.accept())
        self._fill()
        if current:
            for i in range(self.list.count()):
                if self.list.item(i).data(256) == current:
                    self.list.setCurrentRow(i)
                    break

    def _fill(self) -> None:
        text = self.search.text()
        cat = self.category.currentText()
        found = self.library.search(text)
        if cat != ALL:
            found = [m for m in found if (m.category or "Nativos") == cat]
        self.list.clear()
        for m in found:
            item = QListWidgetItem(f"{m.name}    —    {m.density_g_cm3:g} g/cm³")
            item.setData(256, m.name)
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)
        else:
            self.info.setText("Nenhum material encontrado.")
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(self.list.count() > 0)

    def _show_info(self, item, _prev=None) -> None:
        if item is None:
            return
        m = self.library.get(item.data(256))
        if m is None:
            return
        parts = [f"<b>{m.name}</b> — {m.density_g_cm3:g} g/cm³ ({m.density_g_cm3 * 1000:.0f} kg/m³)"]
        if m.density_min is not None and m.density_max is not None and m.density_max > m.density_min:
            parts.append(f"Faixa publicada: {m.density_min:g} – {m.density_max:g} g/cm³ (usa o ponto médio)")
        if m.source:
            link = f'<a href="{m.source_url}">{m.source}</a>' if m.source_url else m.source
            parts.append(f"Fonte: {link}")
        else:
            parts.append("Valor nominal nativo do NEXUS")
        if m.note:
            parts.append(f"Obs.: {m.note}")
        self.info.setText("<br>".join(parts))

    def accept(self) -> None:
        item = self.list.currentItem()
        self.selected = item.data(256) if item else None
        super().accept()
