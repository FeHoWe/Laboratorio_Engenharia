"""Hub de produtos NEXUS + diálogo do NEXUS INTELLIGENCE."""
from __future__ import annotations

from PySide6.QtWidgets import (QComboBox, QDialog, QHBoxLayout, QInputDialog, QLabel, QListWidget, QMessageBox, QPushButton, QTextEdit, QVBoxLayout)

from core import products as P

_COR = {P.PRONTO: "✅", P.PARCIAL: "🟡", P.PLANEJADO: "⬜"}


class HubDialog(QDialog):
    """Lista os 5 produtos; cada capacidade abre a função real da janela principal. Estado honesto: PRONTO/PARCIAL/PLANEJADO."""

    def __init__(self, window) -> None:
        super().__init__(window)
        self.window_ = window
        self.setWindowTitle("NEXUS — Produtos"); self.resize(760, 520)
        root = QHBoxLayout(self)
        self.lista = QListWidget(); root.addWidget(self.lista, 1)
        for p in P.PRODUTOS:
            self.lista.addItem(f"{_COR[p.estado()] if p.estado() != P.PARCIAL else '🟡'}  {p.nome}")
        right = QVBoxLayout(); root.addLayout(right, 2)
        self.titulo = QLabel(); self.titulo.setWordWrap(True); right.addWidget(self.titulo)
        self.caps = QListWidget(); right.addWidget(self.caps, 1)
        self.b_open = QPushButton("Abrir capacidade selecionada"); self.b_open.clicked.connect(self.abrir); right.addWidget(self.b_open)
        self.lac = QTextEdit(); self.lac.setReadOnly(True); self.lac.setMaximumHeight(110); right.addWidget(self.lac)
        self.lista.currentRowChanged.connect(self._sel); self.lista.setCurrentRow(0)

    def _sel(self, i: int) -> None:
        if i < 0:
            return
        p = P.PRODUTOS[i]
        self.titulo.setText(f"<b>{p.nome}</b> — {p.missao}")
        self.caps.clear()
        for c in p.capacidades:
            self.caps.addItem(f"{_COR[c.estado]} {c.rotulo}" + (f"   [{c.nota}]" if c.nota else ""))
        self.lac.setPlainText("Limites declarados:\n" + "\n".join(f"- {x}" for x in p.lacunas))

    def abrir(self) -> None:
        p, j = P.PRODUTOS[self.lista.currentRow()], self.caps.currentRow()
        if j < 0:
            return
        c = p.capacidades[j]
        if not c.acao:
            QMessageBox.information(self, "NEXUS", f"'{c.rotulo}' ainda é {c.estado} — não existe nesta versão."); return
        act = self.window_.actions_by_key.get(c.acao)
        if act is None:
            QMessageBox.warning(self, "NEXUS", f"Ação '{c.acao}' indisponível."); return
        self.accept()
        act.trigger()


class IntelligenceDialog(QDialog):
    """NEXUS INTELLIGENCE: pareceres por regras sobre resultados de projetos e glossário. Não é IA generativa."""

    def __init__(self, window, store=None) -> None:
        super().__init__(window)
        self.setWindowTitle("NEXUS INTELLIGENCE — assistente técnico (regras auditáveis)"); self.resize(720, 620)
        from interface.solvers_dialog import PROJECTS_DIR
        from modules.workspace import ProjectStore
        self.store = store or ProjectStore(PROJECTS_DIR)
        v = QVBoxLayout(self)
        v.addWidget(QLabel("Interpreta resultados e revisa projetos SEM inventar números: cada alerta cita o campo de origem. Não é IA generativa."))
        self.proj = QComboBox(); self.proj.addItems(self.store.list()); v.addWidget(self.proj)
        r = QHBoxLayout()
        for t, f in (("Revisar projeto", self.revisar), ("Interpretar último resultado do projeto", self.interpretar), ("Comparar os dois últimos resultados", self.comparar),
                     ("Explicar termo…", self.termo)):
            b = QPushButton(t); b.clicked.connect(f); r.addWidget(b)
        v.addLayout(r)
        self.out = QTextEdit(); self.out.setReadOnly(True); v.addWidget(self.out)

    def _proj(self):
        n = self.proj.currentText()
        if not n:
            self.out.setPlainText("Crie um projeto em 'Solvers, vitrine e projetos…' e anexe resultados."); return None
        return self.store.open(n)

    def revisar(self) -> None:
        from modules import intelligence as I
        p = self._proj()
        if p:
            self.out.setPlainText(I.revisar_projeto(p).texto())

    def interpretar(self) -> None:
        from modules import intelligence as I
        p = self._proj()
        if p:
            self.out.setPlainText(I.interpretar(p["results"][-1]).texto() if p["results"] else "O projeto não tem resultados anexados.")

    def comparar(self) -> None:
        from modules import intelligence as I
        p = self._proj()
        if p:
            r = p["results"]
            self.out.setPlainText(I.comparar(r[-2], r[-1]).texto() if len(r) >= 2 else "São necessários ao menos dois resultados.")

    def termo(self) -> None:
        from modules import intelligence as I
        t, ok = QInputDialog.getText(self, "Glossário", "Termo (ex.: von Mises, Cp, y+, Reynolds):")
        if ok and t.strip():
            self.out.setPlainText(I.explicar(t))
