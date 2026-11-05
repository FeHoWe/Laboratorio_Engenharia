"""Janela de animação do mecanismo (V1.8): controle de ângulo, reprodução e leituras."""
from __future__ import annotations

from PySide6.QtCore import QElapsedTimer, QPointF, QRectF, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QHBoxLayout, QLabel, QPushButton, QSlider,
                               QVBoxLayout, QWidget)

from modules.kinematics import Mechanism


class ValveDiagram(QWidget):
    """Levantamento, velocidade e aceleração da válvula (cilindro 1) × ângulo, com cursor no ângulo atual."""
    ROWS = (("lift", "Levantamento (mm)", 1.0), ("vel", "Velocidade (m/s)", 1.0), ("acc", "Aceleração (m/s²)", 1.0))

    def __init__(self, data: dict, parent=None) -> None:
        super().__init__(parent)
        self.data, self.rpm, self.angle = data, 3000.0, 0.0
        self.setMinimumHeight(250)

    def set_rpm(self, rpm: float) -> None:
        self.rpm = float(rpm)
        self.update()

    def set_angle(self, deg: float) -> None:
        self.angle = deg
        self.update()

    def _scale(self, key: str) -> float:
        k = self.rpm / self.data["ref_rpm"]
        return {"lift": 1.0, "vel": k, "acc": k * k}[key]

    def paintEvent(self, ev) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#06121c"))
        n, w, h = self.data["n"], self.width(), self.height()
        left, right, top, bot = 92, 8, 6, 16
        rh = (h - top - bot) / len(self.ROWS)
        font = p.font()
        font.setPointSize(8)
        p.setFont(font)
        for i, (key, label, _) in enumerate(self.ROWS):
            box = QRectF(left, top + i * rh + 3, w - left - right, rh - 8)
            series = {c: [v * self._scale(key) for v in self.data[c][key]] for c in ("int", "exh")}
            lo = min(min(s) for s in series.values())
            hi = max(max(s) for s in series.values())
            span = (hi - lo) or 1.0
            lo, hi = lo - 0.05 * span, hi + 0.05 * span
            p.setPen(QPen(QColor("#1d3a4d"), 1))
            p.drawRect(box)
            if lo < 0 < hi:
                y0 = box.bottom() - (0 - lo) / (hi - lo) * box.height()
                p.drawLine(QPointF(box.left(), y0), QPointF(box.right(), y0))
            for col, name in (("int", "#37d6ff"), ("exh", "#ffb347")):
                p.setPen(QPen(QColor(name), 1.4))
                pts = [QPointF(box.left() + j / (n - 1) * box.width(), box.bottom() - (v - lo) / (hi - lo) * box.height())
                       for j, v in enumerate(series[col])]
                p.drawPolyline(pts)
            p.setPen(QColor("#8fb4c8"))
            p.drawText(QRectF(2, box.top(), left - 6, box.height()), Qt.AlignVCenter | Qt.TextWordWrap, f"{label}\n{lo:+.1f} … {hi:+.1f}")
            x = box.left() + (self.angle % 720.0) / 720.0 * box.width()
            p.setPen(QPen(QColor("#ff4d6d"), 1))
            p.drawLine(QPointF(x, box.top()), QPointF(x, box.bottom()))
        p.setPen(QColor("#8fb4c8"))
        p.drawText(QRectF(left, h - bot, w - left, bot), Qt.AlignLeft, f"0° … 720° (virabrequim) · ciano = admissão · laranja = escape · {self.rpm:.0f} rpm")
        p.end()


class KinematicsDialog(QDialog):
    angleChanged = Signal(float)
    closedByUser = Signal()

    def __init__(self, mech: Mechanism, parent=None) -> None:
        super().__init__(parent)
        self.mech = mech
        self.setWindowTitle(f"Animação — {mech.name}")
        self.setModal(False)
        self.resize(640, 330 + (290 if mech.extra.get('diagram') else 0))
        note = QLabel("Movimento PRESCRITO (sem dinâmica, forças ou contato). A geometria não é alterada; só a exibição.")
        note.setWordWrap(True)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, int(mech.period_deg))
        self.spin = QDoubleSpinBox()
        self.spin.setRange(0, mech.period_deg)
        self.spin.setDecimals(1)
        self.spin.setSuffix(" °")
        self.play = QPushButton("▶ Reproduzir")
        self.play.setCheckable(True)
        self.speed = QComboBox()
        for label, dps in (("Lento (30°/s)", 30.0), ("Normal (90°/s)", 90.0), ("Rápido (270°/s)", 270.0)):
            self.speed.addItem(label, dps)
        self.speed.setCurrentIndex(1)
        self.loop = QCheckBox("Repetir")
        self.loop.setChecked(True)
        self.reset_btn = QPushButton("Zerar (θ = 0)")
        self.info = QLabel("")
        self.info.setStyleSheet("font-family: Consolas, monospace;")
        self.info.setWordWrap(True)
        notes = QLabel("• " + "\n• ".join(mech.notes))
        notes.setWordWrap(True)
        notes.setStyleSheet("color: #8fb4c8; font-size: 11px;")
        row = QHBoxLayout()
        for w in (QLabel(mech.input_label + ":"), self.spin, self.play, self.speed, self.loop, self.reset_btn):
            row.addWidget(w)
        lay = QVBoxLayout(self)
        for w in (note, self.slider):
            lay.addWidget(w)
        lay.addLayout(row)
        lay.addWidget(self.info)
        self.diagram = None
        if mech.extra.get("diagram"):
            self.diagram = ValveDiagram(mech.extra["diagram"])
            self.rpm = QDoubleSpinBox()
            self.rpm.setRange(500, 12000)
            self.rpm.setSingleStep(500)
            self.rpm.setDecimals(0)
            self.rpm.setValue(3000)
            self.rpm.setSuffix(" rpm")
            self.rpm.valueChanged.connect(self.diagram.set_rpm)
            hr = QHBoxLayout()
            hr.addWidget(QLabel("Diagrama de válvulas (cil. 1) — rotação:"))
            hr.addWidget(self.rpm)
            hr.addStretch(1)
            lay.addLayout(hr)
            lay.addWidget(self.diagram)
        lay.addWidget(notes)
        self._clock = QElapsedTimer()
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)
        self.slider.valueChanged.connect(lambda v: self.set_angle(float(v)))
        self.spin.valueChanged.connect(self.set_angle)
        self.play.toggled.connect(self._toggle)
        self.reset_btn.clicked.connect(lambda: self.set_angle(0.0))
        self._angle = 0.0

    @property
    def angle(self) -> float:
        return self._angle

    def set_angle(self, deg: float, emit: bool = True) -> None:
        deg = float(deg) % self.mech.period_deg if deg >= self.mech.period_deg and self.loop.isChecked() else \
            min(max(float(deg), 0.0), self.mech.period_deg)
        self._angle = deg
        for w, v in ((self.slider, int(round(deg))), (self.spin, deg)):
            w.blockSignals(True)
            w.setValue(v)
            w.blockSignals(False)
        self.info.setText(self.mech.readout(deg) if self.mech.readout else f"{deg:.1f}°")
        if self.diagram is not None:
            self.diagram.set_angle(deg)
        if emit:
            self.angleChanged.emit(deg)

    def _toggle(self, on: bool) -> None:
        self.play.setText("⏸ Pausar" if on else "▶ Reproduzir")
        if on:
            self._clock.start()
            self._timer.start()
        else:
            self._timer.stop()

    def _tick(self) -> None:
        dt = self._clock.restart() / 1000.0
        new = self._angle + dt * float(self.speed.currentData())
        if new >= self.mech.period_deg and not self.loop.isChecked():
            self.set_angle(self.mech.period_deg)
            self.play.setChecked(False)
            return
        self.set_angle(new)

    def closeEvent(self, ev) -> None:
        self._timer.stop()
        self.closedByUser.emit()
        super().closeEvent(ev)
