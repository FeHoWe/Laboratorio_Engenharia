"""Interface da segurança de projeto (V4.0): versões, comparação e recuperação após encerramento inesperado."""
from __future__ import annotations

from PySide6.QtWidgets import (QDialog, QHBoxLayout, QInputDialog, QLabel, QListWidget, QListWidgetItem,
                               QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout)

from core.i18n import tr
from core.project_manager import ProjectError
from core import project_safety as ps


def formatar_comparacao(c: dict) -> str:
    """Texto legível do resultado de `project_safety.comparar`."""
    if c.get("iguais"):
        return tr("Os projetos são iguais.")
    nomes = [("adicionados", tr("Adicionados")), ("removidos", tr("Removidos")), ("renomeados", tr("Renomeados")),
             ("material", tr("Material alterado")), ("geometria", tr("Geometria alterada")),
             ("posicao", tr("Posição alterada")), ("pai", tr("Movidos na árvore"))]
    linhas = []
    for k, rot in nomes:
        v = c.get(k)
        if v:
            linhas.append(f"{rot} ({len(v)}):")
            linhas += [f"   • {x}" for x in v]
    return "\n".join(linhas) or tr("Os projetos são iguais.")


class VersoesDialog(QDialog):
    def __init__(self, window) -> None:
        super().__init__(window)
        self.w = window
        self.setWindowTitle(tr("Versões do projeto"))
        self.resize(640, 420)
        lay = QVBoxLayout(self)
        self.lista = QListWidget()
        self.saida = QPlainTextEdit(); self.saida.setReadOnly(True)
        lay.addWidget(QLabel(tr("Versões registradas deste projeto (pasta 'versions' ao lado do arquivo):")))
        lay.addWidget(self.lista, 2)
        lay.addWidget(self.saida, 2)
        row = QHBoxLayout()
        self.b_cmp = QPushButton(tr("Comparar com o arquivo atual"))
        self.b_rest = QPushButton(tr("Restaurar esta versão"))
        b_close = QPushButton(tr("Fechar"))
        for b in (self.b_cmp, self.b_rest, b_close):
            row.addWidget(b)
        lay.addLayout(row)
        self.b_cmp.clicked.connect(self.comparar)
        self.b_rest.clicked.connect(self.restaurar)
        b_close.clicked.connect(self.accept)
        self.recarregar()

    def recarregar(self) -> None:
        self.lista.clear()
        p = self.w.project.path
        for v in (ps.listar_versoes(p) if p else []):
            it = QListWidgetItem(f"{v['carimbo']}  {v['nota']}")
            it.setData(256, v)
            self.lista.addItem(it)
        ok = self.lista.count() > 0
        self.b_cmp.setEnabled(ok); self.b_rest.setEnabled(ok)
        if not ok:
            self.saida.setPlainText(tr("Nenhuma versão registrada."))

    def _sel(self):
        it = self.lista.currentItem() or (self.lista.item(0) if self.lista.count() else None)
        return it.data(256) if it else None

    def comparar(self) -> str:
        v = self._sel()
        if v is None:
            return ""
        try:
            txt = formatar_comparacao(ps.comparar(v["arquivo"], self.w.project.path))
        except ProjectError as exc:
            txt = str(exc)
        self.saida.setPlainText(txt)
        return txt

    def restaurar(self, confirmar: bool = True) -> bool:
        v = self._sel()
        if v is None:
            return False
        if confirmar and QMessageBox.question(
                self, tr("Restaurar versão"),
                tr("O arquivo atual será guardado em 'backups' e substituído pela versão escolhida. Continuar?")) != QMessageBox.Yes:
            return False
        try:
            ps.restaurar_versao(self.w.project.path, v["arquivo"])
            self.w.open_project(str(self.w.project.path))
        except ProjectError as exc:
            QMessageBox.critical(self, tr("Falha ao salvar"), str(exc))
            return False
        self.accept()
        return True


def registrar_versao(window, nota: str | None = None) -> bool:
    if window.project.path is None or window.project.dirty:
        if QMessageBox.question(window, tr("Registrar versão"),
                                tr("Salve o projeto antes de registrar uma versão. Salvar agora?")) != QMessageBox.Yes:
            return False
        if not window.save_project():
            return False
    if nota is None:
        nota, ok = QInputDialog.getText(window, tr("Registrar versão"), tr("Nota da versão (opcional):"))
        if not ok:
            return False
    try:
        dst = ps.salvar_versao(window.project.path, nota)
    except ProjectError as exc:
        QMessageBox.critical(window, tr("Falha ao salvar"), str(exc))
        return False
    window.console.log("ok", f"Versão registrada: {dst.name}")
    return True


def verificar_recuperacao(window, decidir=None) -> int:
    """Oferece abrir sessões deixadas por um encerramento inesperado. `decidir(p)` -> "abrir"|"descartar"|"manter" (testes)."""
    n = 0
    for p in ps.pendentes():
        if decidir is None:
            ans = QMessageBox.question(
                window, tr("Recuperar projeto"),
                f"{tr('O NEXUS foi encerrado inesperadamente com alterações não salvas.')}\n\n"
                f"{p.nome} — {p.hora}\n\n{tr('Recuperar agora? (Não = descartar)')}",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Ignore, QMessageBox.Yes)
            acao = {QMessageBox.Yes: "abrir", QMessageBox.No: "descartar"}.get(ans, "manter")
        else:
            acao = decidir(p)
        if acao == "abrir":
            proj = ps.abrir_pendente(window.project_manager, p)
            window._set_project(proj)
            ps.descartar_pendente(p)
            window.console.log("ok", f"Projeto recuperado: {proj.name}")
            n += 1
        elif acao == "descartar":
            ps.descartar_pendente(p)
    return n
