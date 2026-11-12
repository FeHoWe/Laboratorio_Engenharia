"""Biblioteca de peças de engenharia (V2.2): escolhe categoria/peça, edita parâmetros e adiciona à montagem."""
from __future__ import annotations

from PySide6.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                               QPushButton, QVBoxLayout, QWidget)

from samples.library import CATEGORIES, PARTS, parts_in


class LibraryDialog(QDialog):
    def __init__(self, window) -> None:
        super().__init__(window)
        self.window_ref = window
        self.setWindowTitle("Biblioteca de peças")
        self.resize(640, 460)
        root = QVBoxLayout(self)
        top = QHBoxLayout()
        self.cat = QComboBox()
        self.cat.addItems(CATEGORIES)
        self.cat.currentIndexChanged.connect(self._fill_parts)
        top.addWidget(QLabel("Categoria:"))
        top.addWidget(self.cat, 1)
        root.addLayout(top)
        self.parts = QListWidget()
        self.parts.currentItemChanged.connect(self._fill_params)
        root.addWidget(self.parts, 1)
        self.note = QLabel("")
        self.note.setWordWrap(True)
        root.addWidget(self.note)
        self.form_host = QWidget()
        self.form = QFormLayout(self.form_host)
        root.addWidget(self.form_host)
        self.pos = [QDoubleSpinBox() for _ in range(3)]
        for ax, sp in zip("XYZ", self.pos):
            sp.setRange(-100000, 100000)
            sp.setDecimals(1)
            sp.setSuffix(" mm")
            self.form.addRow(f"Posição {ax}", sp)
        self.fields: dict[str, QDoubleSpinBox] = {}
        btns = QHBoxLayout()
        self.btn_add = QPushButton("Adicionar à montagem atual")
        self.btn_new = QPushButton("Criar novo projeto com a peça")
        self.btn_add.clicked.connect(lambda: self._go(False))
        self.btn_new.clicked.connect(lambda: self._go(True))
        btns.addWidget(self.btn_add)
        btns.addWidget(self.btn_new)
        root.addLayout(btns)
        self._param_rows: list[str] = []
        self._fill_parts()

    def _fill_parts(self) -> None:
        self.parts.clear()
        for p in parts_in(self.cat.currentText()):
            it = QListWidgetItem(p.title)
            it.setData(256, p.key)
            self.parts.addItem(it)
        if self.parts.count():
            self.parts.setCurrentRow(0)

    def current_key(self):
        it = self.parts.currentItem()
        return it.data(256) if it else None

    def _fill_params(self) -> None:
        for k in list(self.fields):
            self.form.removeRow(self.fields.pop(k))
        key = self.current_key()
        if not key:
            return
        pd = PARTS[key]
        self.note.setText(pd.note)
        for p in pd.params:
            sp = QDoubleSpinBox()
            sp.setRange(p.lo, p.hi)
            sp.setDecimals(3)
            sp.setValue(p.default)
            sp.setSuffix(f" {p.unit}" if p.unit else "")
            self.form.insertRow(len(self.fields), p.label, sp)
            self.fields[p.key] = sp

    def values(self) -> dict:
        return {k: sp.value() for k, sp in self.fields.items()}

    def _go(self, new_project: bool) -> None:
        key = self.current_key()
        if not key:
            return
        try:
            self.window_ref.add_library_part(key, self.values(), tuple(s.value() for s in self.pos), new_project=new_project)
        except Exception as exc:  # parâmetro inválido etc.
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Não foi possível criar a peça", str(exc))
            return
        self.accept()
