"""Janela de verificação de interferência: lista os pares em colisão, seleciona-os na cena e exporta CSV."""
from __future__ import annotations

from PySide6.QtWidgets import (QDialog, QDoubleSpinBox, QFileDialog, QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QApplication)

from modules.interference import find_interferences, to_csv


class InterferenceDialog(QDialog):
    def __init__(self, window) -> None:
        super().__init__(window)
        self.win = window
        self.clashes = []
        self.setWindowTitle("Verificação de interferência (estática)")
        self.resize(760, 460)
        root = QVBoxLayout(self)
        top = QHBoxLayout()
        self.min_vol = QDoubleSpinBox()
        self.min_vol.setRange(0.0, 1e9)
        self.min_vol.setValue(1.0)
        self.min_vol.setSuffix(" mm³ mínimo")
        self.sel_only = QPushButton("Só peças selecionadas")
        self.sel_only.setCheckable(True)
        run = QPushButton("Verificar")
        run.clicked.connect(lambda: self.run())
        exp = QPushButton("Exportar CSV…")
        exp.clicked.connect(lambda: self.export_csv())
        for w in (self.min_vol, self.sel_only, run, exp):
            top.addWidget(w)
        top.addStretch(1)
        root.addLayout(top)
        self.status = QLabel("Verificação estática na pose atual: toque de faces não conta; encaixes propositais também aparecem.")
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Peça A", "Peça B", "Volume (mm³)"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.itemSelectionChanged.connect(self._select)
        root.addWidget(self.table, 1)

    def run(self) -> list:
        ids = set(self.win.selection.selected) if self.sel_only.isChecked() and self.win.selection.selected else None
        if ids is not None:
            ids = {l.id for l in self.win.project.components.leaves() if l.id in self.win._leaf_ids_of(list(ids))}
        self.status.setText("Calculando…")
        QApplication.processEvents()
        self.clashes = find_interferences(self.win.project.components, self.min_vol.value(), ids)
        self.table.setRowCount(len(self.clashes))
        for r, c in enumerate(self.clashes):
            for k, v in enumerate((c.a_name, c.b_name, f"{c.volume:,.1f}")):
                self.table.setItem(r, k, QTableWidgetItem(v))
        self.status.setText(f"{len(self.clashes)} interferência(s) ≥ {self.min_vol.value():g} mm³.")
        return self.clashes

    def _select(self) -> None:
        rows = {i.row() for i in self.table.selectedItems()}
        ids = []
        for r in rows:
            ids += [self.clashes[r].a_id, self.clashes[r].b_id]
        if ids:
            self.win.selection.select(ids, source="api")

    def export_csv(self, path=None):
        if path is None:
            path, _ = QFileDialog.getSaveFileName(self, "Exportar interferências", "interferencias.csv", "CSV (*.csv)")
        if not path:
            return None
        from pathlib import Path
        Path(path).write_text(to_csv(self.clashes), encoding="utf-8")
        return path
