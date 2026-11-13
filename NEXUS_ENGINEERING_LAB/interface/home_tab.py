"""NEXUS HOME (V5.0) — tela inicial por ambientes: estado do projeto, atalhos para cada ambiente e verificação de consistência.

Só reúne o que já existe (nenhum cálculo novo aqui, exceto a verificação de consistência sob demanda). O resumo é barato: contagens do projeto,
sem recalcular volumes/massas — a massa só aparece na verificação, quando o usuário a pede.
"""
from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from core.i18n import tr

# (título do ambiente, descrição, [(rótulo do botão, método da janela principal)])
AMBIENTES = [
    ("CAD", "Importar, editar com histórico, nomes, variáveis e restrições.",
     [("Importar modelo", "import_model"), ("Editor paramétrico", "show_solvers"), ("Biblioteca de peças", "show_library")]),
    ("Montagem e materiais", "Árvore, explosão, juntas, materiais e lista de materiais.",
     [("Lista de materiais (BOM)", "show_bom"), ("Interferência", "show_interference")]),
    ("Estrutural e CFD", "FEA 3D, casos não lineares e CFD (solvers reais, quando instalados).",
     [("Solvers e estudos", "show_solvers"), ("FEA não linear", "show_nlfea"), ("Hub de engenharia", "show_hub")]),
    ("Veículo e F1", "Pneu, suspensão, volta, telemetria e comparação A/B.",
     [("NEXUS VEHICLE", "show_vehgeo"), ("Ferramentas F1", "show_f1tools"), ("Estudos avançados", "show_estudos_avancados")]),
    ("Intelligence", "Pareceres por regras (não é IA generativa).",
     [("Parecer de resultados", "show_intelligence")]),
]


class HomeTab(QWidget):
    def __init__(self, window) -> None:
        super().__init__()
        self.w = window
        v = QVBoxLayout(self)
        self.titulo = QLabel(); self.titulo.setStyleSheet("font-size:20px;font-weight:600"); v.addWidget(self.titulo)
        self.resumo = QLabel(); self.resumo.setWordWrap(True); v.addWidget(self.resumo)
        grade = QGridLayout(); v.addLayout(grade)
        self.botoes: dict[str, QPushButton] = {}
        for i, (nome, desc, acoes) in enumerate(AMBIENTES):
            g = QGroupBox(tr(nome)); lay = QVBoxLayout(g)
            d = QLabel(tr(desc)); d.setWordWrap(True); lay.addWidget(d)
            for rot, metodo in acoes:
                b = QPushButton(tr(rot)); b.clicked.connect(lambda _=False, m=metodo: getattr(self.w, m)())
                lay.addWidget(b); self.botoes[metodo] = b
            grade.addWidget(g, i // 2, i % 2)
        for rot, fn in (("Verificar consistência do projeto", self.verificar), ("Diagnóstico técnico (calculado, interpretação, hipótese, recomendação)", self.diagnosticar), ("Relatório técnico (PDF, Markdown ou JSON)…", self.relatorio), ("Versões do projeto…", lambda: self.w.mostrar_versoes()),
                        ("Registrar versão…", lambda: self.w.registrar_versao())):
            b = QPushButton(tr(rot)); b.clicked.connect(lambda _=False, f=fn: f()); v.addWidget(b)
            if fn == self.verificar:
                self.b_verificar = b
        self.recentes = QComboBox(); v.addWidget(QLabel(tr("Projetos recentes")))
        h = QHBoxLayout(); h.addWidget(self.recentes, 1)
        self.b_recente = QPushButton(tr("Abrir projeto recente")); self.b_recente.clicked.connect(self.abrir_recente); h.addWidget(self.b_recente); v.addLayout(h)
        v.addWidget(QLabel(tr("Atividade recente")))
        self.atividade = QPlainTextEdit(); self.atividade.setReadOnly(True); self.atividade.setMaximumHeight(110); v.addWidget(self.atividade)
        self.saida = QPlainTextEdit(); self.saida.setReadOnly(True); v.addWidget(self.saida, 1)
        self.atualizar()

    def atualizar(self) -> None:
        p = self.w.project
        c = p.components.counts()
        folhas = p.components.leaves()
        com_mat = sum(1 for x in folhas if x.material)
        linhas = [f"{c['parts']} peça(s) · {c['groups']} grupo(s) · {c['hidden']} oculta(s) · {len(p.components.displaced_ids())} deslocada(s)",
                  f"Materiais atribuídos: {com_mat} de {len(folhas)} peça(s)" + ("" if not folhas or com_mat == len(folhas) else " — a massa total será PARCIAL"),
                  f"Arquivo: {p.path if p.path else '(ainda não salvo)'}" + ("   ·   alterações NÃO salvas" if p.dirty else "")]
        try:
            from core import project_safety as ps
            if p.path:
                linhas.append(f"Versões registradas: {len(ps.listar_versoes(p.path))}")
        except Exception:  # noqa: BLE001 - o resumo jamais deve quebrar a janela
            pass
        self._atualizar_recentes()
        self.titulo.setText(f"{p.name}")
        self.resumo.setText("\n".join(linhas))

    def _atualizar_recentes(self) -> None:
        from core import atividade
        self.recentes.clear()
        for c in atividade.projetos_recentes():
            self.recentes.addItem(c, c)
        self.b_recente.setEnabled(self.recentes.count() > 0)
        self.atividade.setPlainText("\n".join(f"{d['t']}  [{d['tipo']}]  {d['texto']}" for d in atividade.ultimos(12)) or tr("(sem atividade registrada ainda)"))

    def abrir_recente(self) -> bool:
        c = self.recentes.currentData()
        return bool(c) and self.w.open_project(c)

    def diagnosticar(self) -> str:
        """AI Engineer determinístico: cinco blocos separados, números só de módulos; compara com o último levantamento da Home para apontar o que refazer."""
        from modules import ai_engenheiro, gemeo_digital
        d = ai_engenheiro.diagnostico(self.w.project, getattr(self.w, "estudos_diagnostico", []), getattr(self, "_estado_anterior", None))
        self._estado_anterior = gemeo_digital.levantar(self.w.project)
        txt = ai_engenheiro.texto(d)
        self.saida.setPlainText(txt)
        return txt

    def relatorio(self, caminho: str | None = None) -> str:
        """Relatório técnico de 14 seções do projeto aberto + estudos da sessão (`estudos_diagnostico`). Seções sem dado dizem 'Não informado'."""
        from PySide6.QtWidgets import QFileDialog
        from modules import relatorio_tecnico
        if not caminho:
            caminho, _ = QFileDialog.getSaveFileName(self, tr("Relatório técnico"), "", "PDF (*.pdf);;Markdown (*.md);;JSON (*.json)")
        if not caminho:
            return ""
        try:
            rel = relatorio_tecnico.montar(self.w.project, "", getattr(self.w, "estudos_diagnostico", []))
            p = relatorio_tecnico.exportar(rel, caminho)
            msg = f"Relatório técnico gravado em {p} ({len(relatorio_tecnico.SECOES)} seções)."
        except Exception as e:  # noqa: BLE001
            msg = f"Não foi possível gerar o relatório: {e}"
        self.saida.setPlainText(msg)
        return msg

    def verificar(self, clashes=None) -> str:
        from modules.intelligence import verificar_projeto
        txt = verificar_projeto(self.w.project, clashes).texto()
        self.saida.setPlainText(txt)
        return txt
