"""Diálogo de infraestrutura V2.6: status dos solvers, vitrine do Arsenal, projetos do usuário."""
from __future__ import annotations
from pathlib import Path
from PySide6.QtWidgets import QDialog, QLabel, QListWidget, QMessageBox, QPushButton, QVBoxLayout, QInputDialog
from modules import solver_registry as sr
from modules.workspace import ProjectStore, seed_showcase
from interface.arsenal_dialog import open_arsenal

PROJECTS_DIR = Path.home() / ".nexus_engineering_lab" / "projetos"


def solver_report() -> str:
    lines = []
    for n, s in sr.detect_all().items():
        lines.append(f"{n}: {s.estado}" + (f"  [{s.versao}] {s.caminho}" if s.instalado else f"  — {s.instrucao}"))
    lines.append("NEXUS-Tet4 (FEA 3D próprio): PRONTO — malhas de caixa, material informado pelo usuário")
    return "\n".join(lines)


class SolversDialog(QDialog):
    def __init__(self, window) -> None:
        super().__init__(window)
        self.setWindowTitle("Solvers, vitrine e projetos")
        self.resize(640, 460)
        self.store = ProjectStore(PROJECTS_DIR)
        v = QVBoxLayout(self)
        self.status = QLabel(solver_report()); self.status.setWordWrap(True); v.addWidget(self.status)
        dg = QPushButton("Diagnóstico completo do ambiente (somente leitura)…"); dg.clicked.connect(self.diag); v.addWidget(dg)
        b = QPushButton("Popular Arsenal com a vitrine (peças paramétricas, sem material)"); b.clicked.connect(self.seed); v.addWidget(b)
        f = QPushButton("Estudo FEA 3D de peça (NEXUS-Tet4)…"); f.clicked.connect(self.fea); v.addWidget(f)
        c = QPushButton("Editor paramétrico com histórico (peça/STEP)…"); c.clicked.connect(self.cad); v.addWidget(c)
        self.lst = QListWidget(); v.addWidget(QLabel("Projetos do usuário:")); v.addWidget(self.lst)
        n = QPushButton("Novo projeto…"); n.clicked.connect(self.new); v.addWidget(n)
        d = QPushButton("Excluir projeto selecionado…"); d.clicked.connect(self.delete); v.addWidget(d)
        self.reload()

    def reload(self):
        self.lst.clear(); self.lst.addItems(self.store.list())

    def diag(self):
        from core import doctor
        QMessageBox.information(self, "Diagnóstico do ambiente", doctor.report_text())

    def cad(self):
        from interface.cad_history_dialog import CadHistoryDialog
        CadHistoryDialog(self).exec()

    def fea(self):
        from interface.fea_dialog import FeaDialog
        FeaDialog(self).exec()

    def seed(self):
        a = open_arsenal(); ids = seed_showcase(a); a.close()
        QMessageBox.information(self, "Arsenal", f"{len(ids)} peça(s) adicionada(s).")

    def new(self):
        name, ok = QInputDialog.getText(self, "Novo projeto", "Nome:")
        if ok and name.strip():
            try: self.store.create(name.strip())
            except Exception as e: QMessageBox.warning(self, "Projeto", str(e))
            self.reload()

    def delete(self):
        it = self.lst.currentItem()
        if it and QMessageBox.question(self, "Excluir", f"Excluir '{it.text()}' definitivamente?") == QMessageBox.Yes:
            self.store.delete(it.text(), confirm=True); self.reload()
