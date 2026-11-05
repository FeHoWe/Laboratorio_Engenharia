"""Barras de ferramentas: principal (arquivo/vistas) e controles da explosão."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QLabel, QSlider, QToolBar, QWidget)

from interface import styles
from modules.explode_engine import ExplodeParams

# (rótulo, modo do ExplodeEngine)
EXPLODE_MODES = [
    ("Radial (do centro)", "radial"),
    ("Eixo X", "axis_x"),
    ("Eixo Y", "axis_y"),
    ("Eixo Z", "axis_z"),
    ("Direção personalizada", "custom"),
]
SLIDER_MAX = 300           # 300 -> fator 3,00
DEFAULT_FACTOR = 1.0


def build_main_toolbar(window: QWidget, actions: dict[str, QAction]) -> QToolBar:
    bar = QToolBar("Principal")
    bar.setObjectName("toolbar_main")
    bar.setMovable(False)
    bar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
    layout = [
        ["import", "open", "save"], None,
        ["fit", "view_front", "view_top", "view_right", "view_iso", "perspective"], None,
        ["hide", "isolate", "show_all"],
    ]
    for group in layout:
        if group is None:
            bar.addSeparator()
            continue
        for key in group:
            bar.addAction(actions[key])
    return bar


class ExplodeToolBar(QToolBar):
    """Controles de explosão: modo/direção, distância, animação e comandos."""

    explode_all_requested = Signal()
    explode_group_requested = Signal()
    separate_part_requested = Signal()
    restore_requested = Signal()
    params_changed = Signal()          # modo, direção ou distância mudaram

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("Explosão", parent)
        self.setObjectName("toolbar_explode")
        self.setMovable(False)
        self.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        title = QLabel("EXPLOSÃO")
        title.setObjectName("section")
        self.addWidget(title)

        self.mode_combo = QComboBox()
        for label, mode in EXPLODE_MODES:
            self.mode_combo.addItem(label, mode)
        self.mode_combo.setToolTip("Direção do deslocamento")
        self.mode_combo.currentIndexChanged.connect(self._on_mode)
        self.addWidget(self.mode_combo)

        self.dir_spins: list[QDoubleSpinBox] = []
        self._dir_actions: list[QAction] = []   # em QToolBar, esconde-se a ação, não o widget
        for axis, default in zip("XYZ", (0.0, 0.0, 1.0)):
            spin = QDoubleSpinBox()
            spin.setRange(-1000, 1000)
            spin.setDecimals(2)
            spin.setValue(default)
            spin.setPrefix(axis + " ")
            spin.setFixedWidth(78)
            spin.setToolTip(f"Componente {axis} da direção personalizada")
            spin.valueChanged.connect(lambda _=0: self.params_changed.emit())
            self.dir_spins.append(spin)
            self._dir_actions.append(self.addWidget(spin))
        self._on_mode()

        self.addWidget(QLabel("Distância"))
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, SLIDER_MAX)
        self.slider.setValue(int(DEFAULT_FACTOR * 100))
        self.slider.setFixedWidth(150)
        self.slider.setToolTip("Distância de separação (relativa ao tamanho da montagem)")
        self.slider.valueChanged.connect(self._on_slider)
        self.addWidget(self.slider)
        self.value_label = QLabel()
        self.value_label.setMinimumWidth(38)
        self.addWidget(self.value_label)
        self._on_slider(self.slider.value())

        self.animate_check = QCheckBox("Animar")
        self.animate_check.setChecked(True)
        self.addWidget(self.animate_check)
        self.addSeparator()

        self.act_all = self._action("explode", "Explodir tudo", "Explodir a montagem completa",
                                    self.explode_all_requested)
        self.act_group = self._action("group_explode", "Explodir grupo",
                                      "Explodir somente o grupo/montagem selecionado",
                                      self.explode_group_requested)
        self.act_part = self._action("separate", "Separar peça", "Separar a peça selecionada",
                                     self.separate_part_requested)
        self.act_restore = self._action("restore", "Restaurar", "Restaurar a montagem original",
                                        self.restore_requested)

    def _action(self, icon: str, text: str, tip: str, signal: Signal) -> QAction:
        act = QAction(styles.make_icon(icon), text, self)
        act.setToolTip(tip)
        act.triggered.connect(lambda _=False: signal.emit())
        self.addAction(act)
        return act

    # -------------------------------------------------------------------- estado
    def _on_mode(self) -> None:
        custom = self.mode_combo.currentData() == "custom"
        for act in self._dir_actions:
            act.setVisible(custom)
        self.params_changed.emit()

    def _on_slider(self, value: int) -> None:
        self.value_label.setText(f"{value / 100:.2f}×")
        self.params_changed.emit()

    @property
    def animate(self) -> bool:
        return self.animate_check.isChecked()

    def params(self) -> ExplodeParams:
        mode = self.mode_combo.currentData()
        direction = tuple(s.value() for s in self.dir_spins) if mode == "custom" else None
        return ExplodeParams(factor=self.slider.value() / 100.0, mode=mode, direction=direction)


class SectionToolBar(QToolBar):
    """Corte de seção: liga/desliga, eixo, posição e lado mantido. Só altera a exibição."""

    params_changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("Corte", parent)
        self.setObjectName("toolbar_section")
        self.setMovable(False)
        title = QLabel("CORTE")
        title.setObjectName("section")
        self.addWidget(title)
        self.enable_check = QCheckBox("Ativar")
        self.addWidget(self.enable_check)
        self.axis_combo = QComboBox()
        for label, axis in (("Plano X", 0), ("Plano Y", 1), ("Plano Z", 2)):
            self.axis_combo.addItem(label, axis)
        self.axis_combo.setCurrentIndex(1)
        self.addWidget(self.axis_combo)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 1000)
        self.slider.setValue(500)
        self.slider.setFixedWidth(220)
        self.slider.setToolTip("Posição do plano de corte dentro da caixa do modelo")
        self.addWidget(self.slider)
        self.pos_label = QLabel("50%")
        self.pos_label.setMinimumWidth(36)
        self.addWidget(self.pos_label)
        self.flip_check = QCheckBox("Inverter lado")
        self.addWidget(self.flip_check)
        self.holo_check = QCheckBox("Holograma")
        self.holo_check.setChecked(True)
        self.holo_check.setToolTip("Estilo de bancada holográfica (desligado: sólido técnico)")
        self.addSeparator()
        self.addWidget(self.holo_check)
        for w in (self.enable_check, self.flip_check):
            w.toggled.connect(lambda _=False: self.params_changed.emit())
        self.axis_combo.currentIndexChanged.connect(lambda _=0: self.params_changed.emit())
        self.slider.valueChanged.connect(self._on_slider)

    def _on_slider(self, v: int) -> None:
        self.pos_label.setText(f"{v / 10:.0f}%")
        self.params_changed.emit()

    @property
    def enabled(self) -> bool:
        return self.enable_check.isChecked()

    @property
    def axis(self) -> int:
        return int(self.axis_combo.currentData())

    @property
    def fraction(self) -> float:
        return self.slider.value() / 1000.0

    @property
    def flip(self) -> bool:
        return self.flip_check.isChecked()
