"""Editor paramétrico com histórico (V2.6): peça da biblioteca ou STEP → operações reaplicáveis → exportar STEP."""
from __future__ import annotations
from PySide6.QtWidgets import (QComboBox, QDialog, QFileDialog, QHBoxLayout, QInputDialog, QLabel, QListWidget, QMessageBox,
                               QPushButton, QVBoxLayout)
from modules.cad_history import BOOL_MODES, BOOL_TOOLS, CadHistory, CadHistoryError, OPS, load_step
from samples.library import PARTS


class CadHistoryDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Editor paramétrico com histórico"); self.resize(560, 520)
        self.hist: CadHistory | None = None
        v = QVBoxLayout(self)
        v.addWidget(QLabel("Base: peça da biblioteca ou STEP. O resultado é regenerado reaplicando as operações (receita)."))
        self.part = QComboBox(); [self.part.addItem(p.title, p.key) for p in PARTS.values()]
        r = QHBoxLayout(); r.addWidget(self.part)
        b = QPushButton("Usar peça (parâmetros padrão)"); b.clicked.connect(self.use_part); r.addWidget(b)
        b = QPushButton("Abrir STEP…"); b.clicked.connect(self.open_step); r.addWidget(b); v.addLayout(r)
        self.lst = QListWidget(); v.addWidget(self.lst)
        r = QHBoxLayout()
        for txt, fn in (("Adicionar…", self.add), ("Editar parâmetro…", self.edit), ("Suprimir/ativar", self.toggle), ("Desfazer", self.undo), ("Refazer", self.redo)):
            b = QPushButton(txt); b.clicked.connect(fn); r.addWidget(b)
        v.addLayout(r)
        self.info = QLabel(""); v.addWidget(self.info)
        b = QPushButton("Exportar resultado como STEP…"); b.clicked.connect(self.export); v.addWidget(b)

    def _need(self) -> bool:
        if self.hist is None:
            QMessageBox.information(self, "Editor", "Escolha uma peça ou STEP."); return False
        return True

    def refresh(self) -> None:
        self.lst.clear()
        if not self.hist: return
        for i, o in enumerate(self.hist.ops):
            st = "" if o["enabled"] else " [suprimida]"
            cur = "▶ " if i < self.hist.cursor else "   (desfeita) "
            self.lst.addItem(f"{cur}{i}: {o['type']} {o['params']}{st}")
        try:
            self.info.setText(f"Volume atual: {self.hist.volume():.3f} mm³ (base: {self.hist.base_ref})")
        except CadHistoryError as e:
            self.info.setText(f"ERRO: {e}")

    def use_part(self) -> None:
        k = self.part.currentData(); self.hist = CadHistory(PARTS[k].make(), f"biblioteca:{k}"); self.refresh()

    def open_step(self) -> None:
        p, _ = QFileDialog.getOpenFileName(self, "Abrir STEP", "", "STEP (*.step *.stp)")
        if p:
            try: self.hist = CadHistory(load_step(p), f"step:{p}")
            except CadHistoryError as e: QMessageBox.warning(self, "STEP", str(e))
            self.refresh()

    def add(self) -> None:
        if not self._need(): return
        t, ok = QInputDialog.getItem(self, "Operação", "Tipo:", list(OPS), 0, False)
        if not ok: return
        if t == "sketch_extrude":
            from interface.sketch_dialog import SketchDialog
            SketchDialog(self, self.hist).exec(); self.refresh(); return
        params = {}
        if t == "boolean":
            m, ok = QInputDialog.getItem(self, "Booleana", "Operação:", list(BOOL_MODES), 0, False)
            if not ok: return
            tool, ok = QInputDialog.getItem(self, "Booleana", "Ferramenta:", list(BOOL_TOOLS), 0, False)
            if not ok: return
            params.update(mode=m, tool=tool)
            if tool == "step":
                pth, _ = QFileDialog.getOpenFileName(self, "STEP da ferramenta", "", "STEP (*.step *.stp)")
                if not pth: return
                params["path"] = pth
            if tool == "cylinder":
                params["axis"], ok = QInputDialog.getItem(self, "Cilindro", "Eixo:", ["x", "y", "z"], 2, False)
                if not ok: return
        for k in [k for k in OPS[t] if k not in params]:
            v, ok = QInputDialog.getDouble(self, t, k, 0.0, -1e9, 1e9, 4)
            if not ok: return
            params[k] = v
        if t in ("fillet", "chamfer"):
            params["edges"], ok = QInputDialog.getItem(self, t, "Arestas:", ["all", "axis:x", "axis:y", "axis:z"], 0, False)
        try: self.hist.add(t, **params)
        except Exception as e: QMessageBox.warning(self, "Operação", str(e))
        self.refresh()

    def edit(self) -> None:
        if not self._need() or self.lst.currentRow() < 0: return
        i = self.lst.currentRow(); keys = [k for k, v in self.hist.ops[i]["params"].items() if not isinstance(v, (str, dict))]
        k, ok = QInputDialog.getItem(self, "Parâmetro", "Qual:", keys, 0, False)
        if not ok: return
        v, ok = QInputDialog.getDouble(self, k, "Novo valor:", float(self.hist.ops[i]["params"][k]), -1e9, 1e9, 4)
        if ok:
            try: self.hist.set_param(i, k, v)
            except Exception as e: QMessageBox.warning(self, "Parâmetro", str(e))
        self.refresh()

    def toggle(self) -> None:
        if self._need() and self.lst.currentRow() >= 0:
            i = self.lst.currentRow()
            try: self.hist.suppress(i, self.hist.ops[i]["enabled"])
            except Exception as e: QMessageBox.warning(self, "Operação", str(e))
            self.refresh()

    def undo(self) -> None:
        if self._need(): self.hist.undo(); self.refresh()

    def redo(self) -> None:
        if self._need(): self.hist.redo(); self.refresh()

    def export(self) -> None:
        if not self._need(): return
        p, _ = QFileDialog.getSaveFileName(self, "Exportar STEP", "editado.step", "STEP (*.step)")
        if p:
            from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
            w = STEPControl_Writer(); w.Transfer(self.hist.shape, STEPControl_AsIs); w.Write(p)
