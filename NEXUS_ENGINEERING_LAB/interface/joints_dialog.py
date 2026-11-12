"""Janela das relações de montagem (juntas) inferidas da geometria."""
from __future__ import annotations

from PySide6.QtWidgets import (QDialog, QHBoxLayout, QHeaderView, QLabel, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout)

from modules.joint_finder import JointReport

HEADERS = ["Tipo", "Peça A", "Peça B", "Detalhe"]


class JointsDialog(QDialog):
    def __init__(self, report: JointReport, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Relações de montagem (inferidas)")
        self.resize(1000, 540)
        self.report = report
        note = QLabel("Linhas \"Concêntrica\"/\"Plano contra plano\" são DEDUZIDAS da geometria (coincidência não prova intenção de projeto). "
                      "Linhas \"Gravada (FreeCAD)\" foram LIDAS do arquivo FCStd (leitor não validado com arquivos reais do FreeCAD; não viram restrição). Dê duplo clique numa linha para selecionar as duas peças.")
        note.setWordWrap(True)
        self.summary = QLabel(report.summary())
        self.summary.setWordWrap(True)
        self.orphans = QLabel(("Sem junta: " + ", ".join(report.orphans[:10]) + ("…" if len(report.orphans) > 10 else ""))
                              if report.orphans else "Todas as peças têm ao menos uma junta inferida.")
        self.orphans.setWordWrap(True)
        self.table = QTableWidget(len(report.joints), len(HEADERS))
        self.table.setHorizontalHeaderLabels(HEADERS)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        for r, j in enumerate(report.joints):
            for c, v in enumerate((j.kind, j.a_name, j.b_name, j.detail)):
                self.table.setItem(r, c, QTableWidgetItem(v))
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.export_btn = QPushButton("Exportar CSV…")
        close = QPushButton("Fechar")
        close.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addWidget(self.export_btn)
        row.addStretch(1)
        row.addWidget(close)
        lay = QVBoxLayout(self)
        for w in (note, self.summary, self.orphans):
            lay.addWidget(w)
        lay.addWidget(self.table, 1)
        lay.addLayout(row)
