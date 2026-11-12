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
                     ("Explicar termo…", self.termo), ("Perguntar à IA (opcional)…", self.perguntar)):
            b = QPushButton(t); b.clicked.connect(f); r.addWidget(b)
        v.addLayout(r)
        r2 = QHBoxLayout()
        for t, f in (("Relatório PDF de resultados…", lambda: self.relatorio(False)), ("Laudo simplificado PDF…", lambda: self.relatorio(True)), ("Selos de referência", self.selos), ("Fadiga do último resultado FEA…", self.fadiga_fea)):
            b = QPushButton(t); b.clicked.connect(f); r2.addWidget(b)
        v.addLayout(r2)
        self.out = QTextEdit(); self.out.setReadOnly(True); v.addWidget(self.out)

    def _proj(self):
        n = self.proj.currentText()
        if not n:
            self.out.setPlainText("Crie um projeto em 'Solvers, vitrine e projetos…' e anexe resultados."); return None
        return self.store.open(n)

    def relatorio(self, laudo: bool, caminho: str | None = None, peca: str | None = None) -> None:
        from modules import report_resultados as RR
        p = self._proj()
        if not p: return
        if not p["results"]:
            self.out.setPlainText("O projeto não tem resultados anexados."); return
        if laudo and peca is None:
            peca, ok = QInputDialog.getText(self, "Laudo", "Nome/código da peça:")
            if not ok: return
        if caminho is None:
            from PySide6.QtWidgets import QFileDialog
            caminho, _ = QFileDialog.getSaveFileName(self, "Salvar PDF", "laudo.pdf" if laudo else "relatorio_resultados.pdf", "PDF (*.pdf)")
            if not caminho: return
        try:
            RR.gerar(p["results"], caminho, versao=getattr(self.parent(), "APP_VERSION", ""), laudo=laudo, peca=peca or "")
        except Exception as e:  # noqa: BLE001
            self.out.setPlainText(f"Falha ao gerar o PDF: {type(e).__name__}: {e}"); return
        self.out.setPlainText(f"PDF gerado: {caminho}\n(contém a classe original de cada resultado; não valida nada)")

    def fadiga_fea(self, valores: dict | None = None) -> None:
        """Fadiga a partir do pico de von Mises do último resultado FEA do projeto. Su, Sy, Se' corrigido e R são DIGITADOS (nada é atribuído)."""
        from modules import fatigue as fa, fatigue_fea as ff
        from modules.result_trace import TracedResult
        p = self._proj()
        if not p: return
        fea = [r for r in p["results"] if r.get("classe") in ("SIMULACAO_NUMERICA", "VALIDADO") and ("vm_max_MPa" in (r.get("valores") or {}) or "vm_nodal_max_MPa" in (r.get("valores") or {}))]
        if not fea:
            self.out.setPlainText("O projeto não tem resultado de FEA com tensão de von Mises."); return
        if valores is None:
            nomes = (("R = σmin/σmax", -1.0), ("Su [MPa]", 600.0), ("Sy [MPa]", 400.0), ("Se corrigido [MPa]", 200.0))
            vals = []
            for t, d in nomes:
                v, ok = QInputDialog.getDouble(self, "Fadiga (valores iniciais ILUSTRATIVOS — digite os do SEU material)", t, d, -1e6, 1e6, 3)
                if not ok: return
                vals.append(v)
            valores = dict(R=vals[0], su=vals[1], sy=vals[2], se=vals[3])
        r = fea[-1]; tr = TracedResult(r["nome"], r["classe"], r["metodo"], r.get("valores") or {}, r.get("entradas") or {}, solver=r.get("solver", ""), solver_versao=r.get("solver_versao", ""),
                                       validacao_ref=r.get("validacao_ref", ""))
        try:
            res = ff.avaliar(tr, valores["R"], fa.FatigueMaterial("usuario", su=valores["su"], sy=valores["sy"], se_prime=valores["se"]), valores["se"])
        except ValueError as e:
            self.out.setPlainText(f"ERRO: {e}"); return
        cs = res["coef_seguranca"]
        self.out.setPlainText(f"σmax = {res['sigma_max_MPa']:.1f} MPa (de {res['origem_tensao']}) · σa = {res['sigma_a_MPa']:.1f} · σm = {res['sigma_m_MPa']:.1f}\n" +
                              "\n".join(f"  {k}: {v:.3f}" for k, v in cs.items()) + f"\nVida: {'infinita (abaixo do limite de fadiga)' if res['vida_infinita'] else format(res['ciclos'], '.3g') + ' ciclos'}\n\n" +
                              "\n".join("⚠ " + a for a in res["avisos"]))

    def selos(self) -> None:
        from modules import referencias as R
        r = R.rodar()
        self.out.setPlainText("\n".join(f"[{c['estado']}] {c['modulo']}: {c['caso']}" for c in r["casos"]) + "\n\nSelos: " +
                              "; ".join(f"{m}: {e}" for m, e in r["selos"].items()) + "\n" + r["aviso"])

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

    confirmar_envio = staticmethod(lambda w: QMessageBox.question(
        w, "Enviar para a IA?", "A pergunta e o parecer do NEXUS (valores do resultado) serão ENVIADOS pela internet à API da Anthropic. Continuar?") == QMessageBox.Yes)

    def perguntar(self) -> None:
        from modules import intelligence as I, intelligence_llm as L
        p = self._proj()
        if not p:
            return
        q, ok = QInputDialog.getText(self, "Pergunta", "Pergunte sobre o último resultado (ou sobre o projeto):")
        if not ok or not q.strip():
            return
        parecer = I.interpretar(p["results"][-1]) if p["results"] else I.revisar_projeto(p)
        if not self.confirmar_envio(self):
            self.out.setPlainText("Envio cancelado. Nada foi enviado."); return
        try:
            r = L.perguntar(q.strip(), parecer, cliente=getattr(self, "cliente_ia", None))
        except Exception as e:
            self.out.setPlainText(f"Falha ao consultar a IA: {type(e).__name__}: {e}"); return
        if not r["disponivel"]:
            self.out.setPlainText(f"IA generativa indisponível: {r['motivo']}.\n\nO assistente por regras segue funcionando (botões acima)."); return
        cab = "✔ Resposta verificada (todos os números vêm dos resultados do NEXUS)" if r["aprovada"] else "⚠ " + r["aviso"] + "\nNúmeros sem lastro: " + ", ".join(r["numeros_sem_fundamento"])
        self.out.setPlainText(cab + "\n\n" + r["resposta"] + "\n\n[IA generativa opcional; apoia a decisão, não a substitui]")

    def termo(self) -> None:
        from modules import intelligence as I
        t, ok = QInputDialog.getText(self, "Glossário", "Termo (ex.: von Mises, Cp, y+, Reynolds):")
        if ok and t.strip():
            self.out.setPlainText(I.explicar(t))
