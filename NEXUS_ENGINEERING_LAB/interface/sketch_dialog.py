"""Editor de sketch 2D: perfis (retângulo, círculo, polígono) → extrusão (adicionar/cortar) no histórico paramétrico."""
from __future__ import annotations
from core.i18n import tr

from PySide6.QtWidgets import (QLineEdit, QComboBox, QDialog, QDoubleSpinBox, QHBoxLayout, QInputDialog, QLabel, QListWidget, QMessageBox, QPushButton, QVBoxLayout)

from modules.sketch2d import Sketch, SketchError


def _fmt(e: dict) -> str:
    if e["t"] == "rect":
        return f"retângulo ({e['x0']:g},{e['y0']:g}) → ({e['x1']:g},{e['y1']:g})"
    if e["t"] == "circle":
        return f"círculo c=({e['cx']:g},{e['cy']:g}) r={e['r']:g}"
    return "polígono " + " ".join(f"({x:g},{y:g})" for x, y in e["pts"])


class SketchDialog(QDialog):
    def __init__(self, parent=None, history=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Sketch 2D → extrusão"); self.resize(520, 480)
        self.sk = Sketch("XY", 0.0)
        self.history = history
        v = QVBoxLayout(self)
        r = QHBoxLayout()
        self.plane = QComboBox(); self.plane.addItems(["XY", "XZ", "YZ"]); r.addWidget(QLabel("Plano")); r.addWidget(self.plane)
        self.offset = QDoubleSpinBox(); self.offset.setRange(-1e6, 1e6); self.offset.setDecimals(3); r.addWidget(QLabel("deslocamento")); r.addWidget(self.offset)
        v.addLayout(r)
        self.lst = QListWidget(); v.addWidget(self.lst)
        r = QHBoxLayout()
        for t, f in (("+ Retângulo", self.add_rect), ("+ Círculo", self.add_circle), ("+ Polígono", self.add_poly), ("Editar nº…", self.edit_dim), ("Excluir", self.remove)):
            b = QPushButton(t); b.clicked.connect(f); r.addWidget(b)
        v.addLayout(r)
        self.info = QLabel(""); v.addWidget(self.info)
        r = QHBoxLayout()
        self.dist = QDoubleSpinBox(); self.dist.setRange(-1e6, 1e6); self.dist.setDecimals(3); self.dist.setValue(10.0)
        self.mode = QComboBox(); self.mode.addItems(["add", "cut"])
        r.addWidget(QLabel("extrusão")); r.addWidget(self.dist); r.addWidget(self.mode)
        b = QPushButton("Aplicar ao histórico"); b.clicked.connect(self.apply); r.addWidget(b)
        v.addLayout(r)
        r = QHBoxLayout()                                                      # V4.1b: revolução em torno de um eixo do plano do esboço
        self.ang = QDoubleSpinBox(); self.ang.setRange(1, 360); self.ang.setDecimals(2); self.ang.setValue(360.0)
        self.eixo = [QDoubleSpinBox() for _ in range(4)]
        for w, val in zip(self.eixo, (0, 0, 0, 1)):
            w.setRange(-1e6, 1e6); w.setDecimals(3); w.setValue(val)
        r.addWidget(QLabel("revolução [°]")); r.addWidget(self.ang); r.addWidget(QLabel("eixo u0 v0 u1 v1"))
        for w in self.eixo: r.addWidget(w)
        b = QPushButton("Revolucionar"); b.clicked.connect(self.apply_revolve); r.addWidget(b)
        v.addLayout(r)
        r = QHBoxLayout()                                                      # V4.2: varredura ao longo de uma poligonal 3D
        self.caminho = QLineEdit("0,0,0; 0,0,20"); r.addWidget(QLabel("caminho x,y,z; …")); r.addWidget(self.caminho)
        b = QPushButton("Varrer"); b.clicked.connect(self.apply_sweep); r.addWidget(b)
        v.addLayout(r)
        self.refresh()

    def _sync(self) -> None:
        self.sk.plane, self.sk.offset = self.plane.currentText(), self.offset.value()

    def _nums(self, titulo: str, nomes: list):
        vals = []
        for n in nomes:
            x, ok = QInputDialog.getDouble(self, titulo, n, 0.0, -1e6, 1e6, 4)
            if not ok:
                return None
            vals.append(x)
        return vals

    def _try(self, **e) -> None:
        try:
            self.sk.add(**e)
        except SketchError as ex:
            QMessageBox.warning(self, tr("Sketch"), str(ex))
        self.refresh()

    def add_rect(self) -> None:
        v = self._nums("Retângulo", ["x0", "y0", "x1", "y1"])
        if v:
            self._try(t="rect", x0=v[0], y0=v[1], x1=v[2], y1=v[3])

    def add_circle(self) -> None:
        v = self._nums("Círculo", ["cx", "cy", "raio"])
        if v:
            self._try(t="circle", cx=v[0], cy=v[1], r=v[2])

    def add_poly(self) -> None:
        txt, ok = QInputDialog.getText(self, tr("Polígono"), tr("Pontos x,y separados por ';' (ex.: 0,0; 10,0; 10,5):"))
        if not ok:
            return
        try:
            pts = [[float(a) for a in p.split(",")] for p in txt.split(";") if p.strip()]
            assert all(len(p) == 2 for p in pts)
        except (ValueError, AssertionError):
            QMessageBox.warning(self, tr("Sketch"), tr("Formato inválido. Use: x,y; x,y; x,y")); return
        self._try(t="poly", pts=pts)

    def edit_dim(self) -> None:
        i = self.lst.currentRow()
        if i < 0:
            return
        e = self.sk.entities[i]
        keys = [k for k, x in e.items() if isinstance(x, (int, float))]
        if not keys:
            QMessageBox.information(self, tr("Sketch"), tr("Polígono: exclua e recrie com os novos pontos.")); return
        k, ok = QInputDialog.getItem(self, tr("Parâmetro"), tr("Qual:"), keys, 0, False)
        if not ok:
            return
        x, ok = QInputDialog.getDouble(self, k, tr("Novo valor:"), float(e[k]), -1e6, 1e6, 4)
        if ok:
            try:
                self.sk.modify(i, **{k: x})
            except SketchError as ex:
                QMessageBox.warning(self, tr("Sketch"), str(ex))
        self.refresh()

    def remove(self) -> None:
        if self.lst.currentRow() >= 0:
            self.sk.delete(self.lst.currentRow()); self.refresh()

    def refresh(self) -> None:
        self._sync(); self.lst.clear(); self.lst.addItems([_fmt(e) for e in self.sk.entities])
        try:
            self.info.setText(f"Área líquida: {self.sk.area():.4f} (unidades²) — furos por aninhamento" if self.sk.entities else "Adicione perfis.")
        except SketchError as ex:
            self.info.setText(f"⚠ {ex}")

    def apply_sweep(self) -> None:
        self._sync()
        try:
            self.sk.validate()
            caminho = [[float(c) for c in p.split(",")] for p in self.caminho.text().split(";") if p.strip()]
        except (SketchError, ValueError) as ex:
            QMessageBox.warning(self, tr("Sketch"), str(ex)); return
        if self.history is None:
            QMessageBox.information(self, tr("Sketch"), tr("Abra uma peça no histórico paramétrico primeiro.")); return
        try:
            self.history.add("sketch_sweep", sketch=self.sk.to_dict(), path=caminho, mode=self.mode.currentText())
        except Exception as ex:
            QMessageBox.warning(self, tr("Varredura"), str(ex)); return
        self.accept()

    def apply_revolve(self) -> None:
        self._sync()
        try:
            self.sk.validate()
        except SketchError as ex:
            QMessageBox.warning(self, tr("Sketch"), str(ex)); return
        if self.history is None:
            QMessageBox.information(self, tr("Sketch"), tr("Abra uma peça no histórico paramétrico primeiro.")); return
        try:
            self.history.add("sketch_revolve", sketch=self.sk.to_dict(), angle_deg=self.ang.value(), axis=[w.value() for w in self.eixo], mode=self.mode.currentText())
        except Exception as ex:
            QMessageBox.warning(self, tr("Revolução"), str(ex)); return
        self.accept()

    def apply(self) -> None:
        self._sync()
        try:
            self.sk.validate()
        except SketchError as ex:
            QMessageBox.warning(self, tr("Sketch"), str(ex)); return
        if self.history is None:
            QMessageBox.information(self, tr("Sketch"), tr("Abra uma peça no histórico paramétrico primeiro.")); return
        try:
            self.history.add("sketch_extrude", sketch=self.sk.to_dict(), distance=self.dist.value(), mode=self.mode.currentText())
        except Exception as ex:
            QMessageBox.warning(self, tr("Extrusão"), str(ex)); return
        self.accept()
