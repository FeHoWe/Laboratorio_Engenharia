"""Janela da lista de materiais (BOM) com massa total e exportação CSV/XLSX."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QHeaderView, QLabel, QPushButton,
                               QTableWidget, QTableWidgetItem, QVBoxLayout)

from modules.bom import HEADERS, BomReport


class BomDialog(QDialog):
    def __init__(self, report: BomReport, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Lista de materiais (BOM) e massa")
        self.resize(1100, 560)
        self.report = report
        self.export_csv_btn = QPushButton("Exportar CSV…")
        self.export_xlsx_btn = QPushButton("Exportar XLSX…")
        close = QPushButton("Fechar")
        close.clicked.connect(self.accept)

        self.summary = QLabel(report.summary())
        self.summary.setWordWrap(True)
        extra = []
        if report.center_of_mass:
            x, y, z = report.center_of_mass
            extra.append(f"Centro de massa{'' if report.complete else ' (parcial)'}: "
                         f"X {x:.1f}  Y {y:.1f}  Z {z:.1f} mm (posição original, sem explosão)")
        if report.by_material:
            extra.append("Maiores massas: " + "; ".join(f"{m} {g/1000:.3f} kg" for m, _n, g in report.by_material[:3]))
        if report.missing:
            extra.append("Sem material/volume: " + ", ".join(report.missing[:6]) + ("…" if len(report.missing) > 6 else ""))
        self.extra = QLabel("\n".join(extra))
        self.extra.setWordWrap(True)

        self.table = QTableWidget(len(report.lines), len(HEADERS))
        self.table.setHorizontalHeaderLabels(HEADERS)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        for r, ln in enumerate(report.lines):
            vals = [ln.item, ln.name, ln.group, ln.qty, ln.material or "—",
                    "" if ln.density is None else f"{ln.density:.3f}",
                    "" if ln.volume_cm3 is None else f"{ln.volume_cm3:.2f}",
                    "" if ln.mass_unit_g is None else f"{ln.mass_unit_g:.1f}",
                    "" if ln.mass_total_g is None else f"{ln.mass_total_g:.1f}",
                    "" if ln.pct is None else f"{ln.pct:.1f}", ln.note]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(str(v))
                if c in (0, 3, 5, 6, 7, 8, 9):
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(r, c, it)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)

        row = QHBoxLayout()
        row.addWidget(self.export_csv_btn)
        row.addWidget(self.export_xlsx_btn)
        row.addStretch(1)
        row.addWidget(close)
        lay = QVBoxLayout(self)
        lay.addWidget(self.summary)
        lay.addWidget(self.extra)
        lay.addWidget(self.table, 1)
        lay.addLayout(row)
