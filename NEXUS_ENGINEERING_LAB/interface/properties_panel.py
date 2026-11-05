"""Painel direito: Component Inspector + configurações do componente.

Regra de honestidade da interface: um campo só é EDITÁVEL se a edição realmente
altera o modelo. Hoje isso vale para: nome, material e visibilidade. Dimensões,
posição e rotação são exibidas como somente leitura (a edição geométrica chega
na V1.5, quando existir o editor paramétrico) — por isso não há campos de edição
falsos aqui.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QGroupBox, QLabel, QLineEdit, QScrollArea,
                               QVBoxLayout, QWidget)

from interface import styles
from modules.component_inspector import InspectionReport

NO_MATERIAL = "— sem material —"
NEW_MATERIAL = "Novo material personalizado…"
PICK_MATERIAL = "Buscar no banco de materiais…"


def fmt(value: Optional[float], unit: str = "", digits: int = 2) -> str:
    """Número no padrão brasileiro (milhar com ponto, decimal com vírgula)."""
    if value is None:
        return "não disponível"
    text = f"{value:,.{digits}f}".replace(",", "§").replace(".", ",").replace("§", ".")
    return f"{text} {unit}".strip()


def fmt_vec(v: Optional[tuple[float, float, float]], unit: str = "mm", digits: int = 2) -> str:
    if v is None:
        return "não disponível"
    return "X " + fmt(v[0], digits=digits) + "   Y " + fmt(v[1], digits=digits) + "   Z " + fmt(v[2], digits=digits) \
        + (f"  {unit}" if unit else "")


class _Value(QLabel):
    def __init__(self, text: str = "—") -> None:
        super().__init__(text)
        self.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.setWordWrap(True)


class PropertiesPanel(QWidget):
    rename_requested = Signal(str, str)
    material_changed = Signal(str, object)        # (id, nome do material ou None)
    new_material_requested = Signal(str)
    pick_material_requested = Signal(str)
    visibility_changed = Signal(str, bool)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._current_id: Optional[str] = None

        self.header = QLabel("Selecione um componente")
        self.header.setObjectName("section")
        self.header.setWordWrap(True)

        # identificação
        self.name_edit = QLineEdit()
        self.name_edit.editingFinished.connect(self._on_rename)
        self.id_label, self.kind_label, self.geom_label = _Value(), _Value(), _Value()
        ident = QGroupBox("Identificação")
        f = QFormLayout(ident)
        f.addRow("Nome", self.name_edit)
        f.addRow("Identificador", self.id_label)
        f.addRow("Tipo", self.kind_label)
        f.addRow("Tipo geométrico", self.geom_label)

        # dimensões
        self.length, self.width, self.height = _Value(), _Value(), _Value()
        dims = QGroupBox("Dimensões (caixa delimitadora)")
        f = QFormLayout(dims)
        f.addRow("Comprimento (X)", self.length)
        f.addRow("Largura (Y)", self.width)
        f.addRow("Altura (Z)", self.height)

        # geometria
        self.volume, self.area, self.centroid = _Value(), _Value(), _Value()
        self.counts = _Value()
        self.diams = _Value()
        geo = QGroupBox("Informações geométricas")
        f = QFormLayout(geo)
        f.addRow("Volume", self.volume)
        f.addRow("Área superficial", self.area)
        f.addRow("Centro de gravidade", self.centroid)
        f.addRow("Diâmetros (cilindros)", self.diams)
        f.addRow("Sólidos / faces / triângulos", self.counts)

        # material
        self.material_combo = QComboBox()
        self.material_combo.activated.connect(self._on_material_activated)
        self.density, self.mass = _Value(), _Value()
        mat = QGroupBox("Material")
        f = QFormLayout(mat)
        f.addRow("Material", self.material_combo)
        f.addRow("Densidade", self.density)
        f.addRow("Massa", self.mass)

        # posição
        self.position, self.displacement, self.rotation = _Value(), _Value(), _Value()
        pos = QGroupBox("Posição e orientação (somente leitura)")
        f = QFormLayout(pos)
        f.addRow("Posição (centro)", self.position)
        f.addRow("Deslocamento (explosão)", self.displacement)
        f.addRow("Rotação da instância", self.rotation)

        # configuração
        self.visible_check = QCheckBox("Visível na cena 3D")
        self.visible_check.toggled.connect(self._on_visible)
        cfg = QGroupBox("Configurações do componente")
        f = QVBoxLayout(cfg)
        f.addWidget(self.visible_check)

        self.notes = QLabel()
        self.notes.setObjectName("muted")
        self.notes.setWordWrap(True)

        self._sections = [ident, dims, geo, mat, pos, cfg]
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.addWidget(self.header)
        for s in self._sections:
            lay.addWidget(s)
        lay.addWidget(self.notes)
        lay.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(inner)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)
        self.show_report(None, [], 0)

    # -------------------------------------------------------------------- exibição
    def show_report(self, rep: Optional[InspectionReport], material_names: list[str], selected_count: int) -> None:
        self._current_id = rep.id if rep else None
        for s in self._sections:
            s.setVisible(rep is not None)
        if rep is None:
            self.header.setText("Selecione um componente na árvore ou na cena 3D.")
            self.notes.setText("")
            return
        extra = f"  (+{selected_count - 1} selecionado(s))" if selected_count > 1 else ""
        self.header.setText(f"{rep.name}{extra}")

        with QSignalBlocker(self.name_edit):
            self.name_edit.setText(rep.name)
        self.id_label.setText(rep.id)
        kind = rep.node_kind
        if rep.child_count:
            kind += f" — {rep.child_count} filho(s), {rep.part_count} peça(s)"
        self.kind_label.setText(kind)
        self.geom_label.setText(rep.geometry_type)

        if rep.size:
            self.length.setText(fmt(rep.size[0], "mm"))
            self.width.setText(fmt(rep.size[1], "mm"))
            self.height.setText(fmt(rep.size[2], "mm"))
        else:
            for w in (self.length, self.width, self.height):
                w.setText("não disponível")
        self.volume.setText(fmt(rep.volume, "mm³"))
        self.area.setText(fmt(rep.area, "mm²"))
        self.centroid.setText(fmt_vec(rep.centroid) if rep.centroid else "não disponível")
        self.centroid.setToolTip(rep.centroid_note)
        self.diams.setText("\n".join(f"Ø {fmt(d, 'mm')}  (eixo {ax})" for d, ax in rep.diameters[:6])
                           + ("\n…" if len(rep.diameters) > 6 else "") if rep.diameters else "nenhum cilindro")
        parts = [("—" if v is None else str(v)) for v in (rep.n_solids, rep.n_faces, rep.n_triangles)]
        self.counts.setText(" / ".join(parts))

        with QSignalBlocker(self.material_combo):
            self.material_combo.clear()
            self.material_combo.addItem(NO_MATERIAL)
            self.material_combo.addItems(material_names)
            self.material_combo.addItem(PICK_MATERIAL)
            self.material_combo.addItem(NEW_MATERIAL)
            idx = self.material_combo.findText(rep.material) if rep.material else 0
            self.material_combo.setCurrentIndex(max(idx, 0))
        self.density.setText(fmt(rep.density, "g/cm³") if rep.density else "—")
        self.mass.setText(fmt(rep.mass, "g") if rep.mass is not None else (rep.mass_note or "não disponível"))

        self.position.setText(fmt_vec(rep.position))
        self.displacement.setText(fmt_vec(rep.displacement))
        self.rotation.setText("Rx {}°  Ry {}°  Rz {}°".format(*(fmt(a, digits=2) for a in rep.rotation)))

        with QSignalBlocker(self.visible_check):
            self.visible_check.setChecked(rep.visible)
        self.notes.setText("\n".join("• " + n for n in rep.notes))

    def set_visible_state(self, visible: bool) -> None:
        with QSignalBlocker(self.visible_check):
            self.visible_check.setChecked(visible)

    # ------------------------------------------------------------------ callbacks
    def _on_rename(self) -> None:
        if self._current_id and self.name_edit.text().strip():
            self.rename_requested.emit(self._current_id, self.name_edit.text().strip())

    def _on_material_activated(self, index: int) -> None:
        if not self._current_id:
            return
        text = self.material_combo.itemText(index)
        if text == PICK_MATERIAL:
            self.pick_material_requested.emit(self._current_id)
        elif text == NEW_MATERIAL:
            self.new_material_requested.emit(self._current_id)
        else:
            self.material_changed.emit(self._current_id, None if text == NO_MATERIAL else text)

    def _on_visible(self, checked: bool) -> None:
        if self._current_id:
            self.visibility_changed.emit(self._current_id, checked)
