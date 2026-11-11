"""Diálogo do NEXUS ENGINEERING ARSENAL (V2.5): navegar, versionar, comparar e inserir componentes reutilizáveis."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (QComboBox, QDialog, QHBoxLayout, QInputDialog, QLabel, QListWidget, QListWidgetItem,
                               QMessageBox, QPushButton, QTextEdit, QVBoxLayout)

from modules.arsenal import Arsenal, ArsenalError
from samples.library import PARTS

ARSENAL_PATH = Path.home() / ".nexus_engineering_lab" / "arsenal.db"


def open_arsenal() -> Arsenal:
    ARSENAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    return Arsenal(ARSENAL_PATH)


class ArsenalDialog(QDialog):
    def __init__(self, window, arsenal: Arsenal | None = None) -> None:
        super().__init__(window)
        self.window_ref = window
        self.arsenal = arsenal or open_arsenal()
        self.setWindowTitle("NEXUS Engineering Arsenal")
        self.resize(760, 520)
        root = QVBoxLayout(self)
        top = QHBoxLayout()
        self.cat = QComboBox()
        self.cat.addItem("(todas)")
        self.cat.addItems(self.arsenal.categories())
        self.cat.currentIndexChanged.connect(self._fill)
        b_cat = QPushButton("Nova categoria…")
        b_cat.clicked.connect(self._new_cat)
        top.addWidget(QLabel("Categoria:"))
        top.addWidget(self.cat, 1)
        top.addWidget(b_cat)
        root.addLayout(top)
        mid = QHBoxLayout()
        self.items = QListWidget()
        self.items.currentItemChanged.connect(self._show)
        self.vers = QListWidget()
        mid.addWidget(self.items, 2)
        mid.addWidget(self.vers, 1)
        root.addLayout(mid, 1)
        self.info = QTextEdit()
        self.info.setReadOnly(True)
        root.addWidget(self.info, 1)
        row = QHBoxLayout()
        for text, fn in (("Salvar peça da biblioteca no Arsenal…", self._save_from_library), ("Inserir na montagem", self._insert),
                         ("Comparar com versão anterior", self._compare), ("Restaurar versão selecionada", self._restore),
                         ("Duplicar (variante)", self._dup), ("Exportar…", self._export), ("Importar…", self._import)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        root.addLayout(row)
        self._fill()

    def _cid(self):
        it = self.items.currentItem()
        return it.data(256) if it else None

    def _ver(self):
        it = self.vers.currentItem()
        return it.data(256) if it else None

    def _fill(self) -> None:
        self.items.clear()
        cat = self.cat.currentText()
        for c in self.arsenal.list_components(None if cat == "(todas)" else cat):
            it = QListWidgetItem(f"{c['id']}  {c['name']}  v{c['latest']}  [{c['category']}]")
            it.setData(256, c["id"])
            self.items.addItem(it)

    def _show(self) -> None:
        cid = self._cid()
        self.vers.clear()
        if not cid:
            return
        for v in self.arsenal.versions(cid):
            it = QListWidgetItem(f"v{v['version']} — {v['change']}")
            it.setData(256, v["version"])
            self.vers.addItem(it)
        self.vers.setCurrentRow(self.vers.count() - 1)
        c = self.arsenal.get(cid)
        self.info.setPlainText(
            f"{c['id']}  {c['name']}  (v{c['version']})\nCategoria: {c['category']}\nMaterial: {c['material_label']}\n"
            f"Receita: {c['part_key'] or c['step_path']}\nParâmetros: {c['params']}\nInterfaces: {c['interfaces'] or 'nenhuma declarada → COMPATIBILIDADE NÃO VERIFICADA'}\n"
            f"Referências: {c['references'] or 'PROPRIEDADE NÃO INFORMADA'}\n"
            + (f"Variante de {c['parent'][0]} v{c['parent'][1]}\n" if c["parent"] else ""))

    def _new_cat(self) -> None:
        name, ok = QInputDialog.getText(self, "Nova categoria", "Nome:")
        if ok and name.strip():
            self.arsenal.add_category(name)
            self.cat.addItem(name.strip())

    def _save_from_library(self) -> None:
        from interface.library_dialog import LibraryDialog
        dlg = LibraryDialog(self.window_ref)
        dlg.btn_add.setText("Salvar no Arsenal")
        dlg.btn_new.hide()
        dlg.btn_add.clicked.disconnect()

        def save():
            key = dlg.current_key()
            if not key:
                return
            name, ok = QInputDialog.getText(dlg, "Nome do componente", "Nome:", text=PARTS[key].title)
            if not ok or not name.strip():
                return
            cats = self.arsenal.categories()
            cat, ok = QInputDialog.getItem(dlg, "Categoria", "Categoria:", cats, 0, False)
            if ok:
                self.arsenal.add_component(name.strip(), cat, {"part_key": key, "params": dlg.values()})
                dlg.accept()
        dlg.btn_add.clicked.connect(save)
        dlg.exec()
        self._fill()

    def _insert(self) -> None:
        cid = self._cid()
        if not cid:
            return
        inst = self.arsenal.instantiate(cid, self._ver())
        if not inst["part_key"]:
            QMessageBox.information(self, "Arsenal", "Componentes por STEP guardado ainda não são inseridos por este botão.")
            return
        comp = self.window_ref.add_library_part(inst["part_key"], inst["params"])
        self.window_ref.project.log("Arsenal", f"Inserido {inst['origin']}")
        self.accept()
        return comp

    def _compare(self) -> None:
        cid, v = self._cid(), self._ver()
        vs = [x["version"] for x in self.arsenal.versions(cid)] if cid else []
        if not cid or v not in vs or vs.index(v) == 0:
            return
        diffs = self.arsenal.compare(cid, vs[vs.index(v) - 1], v)
        self.info.setPlainText("\n".join(f"{d['campo']}: {d['de']} → {d['para']}" for d in diffs) or "Sem diferenças.")

    def _restore(self) -> None:
        try:
            self.arsenal.restore(self._cid(), self._ver())
        except ArsenalError as exc:
            QMessageBox.warning(self, "Arsenal", str(exc))
        self._show()

    def _export(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        cid = self._cid()
        if not cid:
            return
        p, _ = QFileDialog.getSaveFileName(self, "Exportar componente", f"{cid}.json", "JSON (*.json)")
        if p:
            self.arsenal.export_to_file([cid], p)

    def _import(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        p, _ = QFileDialog.getOpenFileName(self, "Importar do Arsenal", "", "JSON (*.json)")
        if not p:
            return
        try:
            ids = self.arsenal.import_file(p)
        except ArsenalError as exc:
            QMessageBox.warning(self, "Arsenal", str(exc)); return
        QMessageBox.information(self, "Arsenal", f"{len(ids)} componente(s) importado(s) com novos IDs: {', '.join(ids)}")
        self._fill()

    def _dup(self) -> None:
        cid = self._cid()
        if not cid:
            return
        name, ok = QInputDialog.getText(self, "Variante", "Nome da variante:")
        if ok and name.strip():
            self.arsenal.duplicate(cid, name.strip())
            self._fill()
