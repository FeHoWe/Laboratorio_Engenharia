"""Painel esquerdo: árvore hierárquica, lista de peças e grupos de montagem.

Os três modos exibem o MESMO modelo e compartilham o :class:`SelectionManager`.
O painel não altera o modelo: pede ações à janela principal por sinais.
"""
from __future__ import annotations

from typing import Iterable, Optional

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (QAbstractItemView, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu,
                               QTabWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from core.model import Component, ComponentKind
from core.project_manager import Project
from interface import styles
from modules.selection_manager import SelectionManager

ID_ROLE = Qt.UserRole
_KIND_ICON = {ComponentKind.PART: "part", ComponentKind.ASSEMBLY: "assembly", ComponentKind.GROUP: "group"}
SEPARATED_MARK = "↗"


def _visibility_state(node: Component) -> Qt.CheckState:
    nodes = [n for n in node.walk() if n.has_geometry] or [node]
    visible = [n.visible for n in nodes]
    if all(visible):
        return Qt.Checked
    if not any(visible):
        return Qt.Unchecked
    return Qt.PartiallyChecked


def _has_displaced(node: Component) -> bool:
    return any(l.is_displaced() for l in node.leaves())


class ComponentPanel(QWidget):
    """Abas: Árvore | Peças | Grupos, com busca por nome."""

    action_requested = Signal(str, list)        # (ação, ids selecionados)
    visibility_toggled = Signal(str, bool)      # (id, visível)

    def __init__(self, selection: SelectionManager, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.selection = selection
        self.project: Optional[Project] = None

        self.search = QLineEdit(placeholderText="Buscar componente…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._apply_filter)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Componente", ""])
        self.tree.setColumnWidth(0, 230)
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0, self.tree.header().ResizeMode.Stretch)
        self.tree.setColumnWidth(1, 22)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.setAnimated(True)

        self.parts = QListWidget()
        self.parts.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.parts.setContextMenuPolicy(Qt.CustomContextMenu)
        self.groups = QListWidget()
        self.groups.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.groups.setContextMenuPolicy(Qt.CustomContextMenu)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.tree, "Árvore")
        self.tabs.addTab(self.parts, "Peças")
        self.tabs.addTab(self.groups, "Grupos")

        self.summary = QLabel("Nenhum projeto aberto")
        self.summary.setObjectName("muted")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(self.search)
        layout.addWidget(self.tabs, 1)
        layout.addWidget(self.summary)

        self._items: dict[str, QTreeWidgetItem] = {}
        self._part_items: dict[str, QListWidgetItem] = {}
        self._group_items: dict[str, QListWidgetItem] = {}

        self.tree.itemSelectionChanged.connect(lambda: self._on_selection_changed(self.tree, "tree"))
        self.parts.itemSelectionChanged.connect(lambda: self._on_selection_changed(self.parts, "list"))
        self.groups.itemSelectionChanged.connect(lambda: self._on_selection_changed(self.groups, "groups"))
        self.tree.itemChanged.connect(self._on_tree_item_changed)
        self.parts.itemChanged.connect(self._on_list_item_changed)
        for w in (self.tree, self.parts, self.groups):
            w.customContextMenuRequested.connect(lambda pos, w=w: self._context_menu(w, pos))
        self.selection.subscribe(self._on_external_selection)

    # ------------------------------------------------------------------ população
    def populate(self, project: Optional[Project]) -> None:
        """Reconstrói os três modos a partir do modelo."""
        self.project = project
        blockers = [QSignalBlocker(w) for w in (self.tree, self.parts, self.groups)]
        self.tree.clear()
        self.parts.clear()
        self.groups.clear()
        self._items.clear()
        self._part_items.clear()
        self._group_items.clear()
        if project is not None and project.components.root is not None:
            root = project.components.root
            self._add_tree_node(root, None)
            self.tree.expandToDepth(2)
            for leaf in project.components.leaves():
                item = QListWidgetItem(styles.make_icon("part", size=16), leaf.name)
                item.setData(ID_ROLE, leaf.id)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked if leaf.visible else Qt.Unchecked)
                self.parts.addItem(item)
                self._part_items[leaf.id] = item
            for node in root.walk():
                if node.children:
                    item = QListWidgetItem(styles.make_icon(_KIND_ICON[node.kind], size=16),
                                           f"{node.name}  ({sum(1 for _ in node.leaves())} peças)")
                    item.setData(ID_ROLE, node.id)
                    self.groups.addItem(item)
                    self._group_items[node.id] = item
        del blockers
        self.refresh_states()
        self._apply_filter(self.search.text())

    def _add_tree_node(self, node: Component, parent_item: Optional[QTreeWidgetItem]) -> None:
        item = QTreeWidgetItem(parent_item) if parent_item else QTreeWidgetItem(self.tree)
        item.setText(0, node.name)
        item.setIcon(0, styles.make_icon(_KIND_ICON[node.kind], size=16))
        item.setData(0, ID_ROLE, node.id)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(0, Qt.Checked)
        self._items[node.id] = item
        for child in node.children:
            self._add_tree_node(child, item)

    def refresh_states(self) -> None:
        """Atualiza visibilidade, marcador de peça separada e resumo (sem reconstruir)."""
        if self.project is None or self.project.components.root is None:
            self.summary.setText("Nenhum projeto aberto")
            return
        comps = self.project.components
        blockers = [QSignalBlocker(w) for w in (self.tree, self.parts, self.groups)]
        for cid, item in self._items.items():
            node = comps.find(cid)
            if node is None:
                continue
            item.setCheckState(0, _visibility_state(node))
            item.setText(0, node.name)
            displaced = _has_displaced(node)
            item.setText(1, SEPARATED_MARK if displaced else "")
            item.setForeground(1, QBrush(QColor(styles.ACCENT)))
            item.setToolTip(1, "Componente separado da posição original (explosão)" if displaced else "")
            dim = not comps.is_effectively_visible(node)
            item.setForeground(0, QBrush(QColor(styles.MUTED if dim else styles.TEXT)))
        for cid, item in self._part_items.items():
            node = comps.find(cid)
            if node is not None:
                item.setCheckState(Qt.Checked if node.visible else Qt.Unchecked)
                item.setText(node.name + (f"   {SEPARATED_MARK}" if node.is_displaced() else ""))
        del blockers
        c = comps.counts()
        displaced_n = len(comps.displaced_ids())
        extra = f" · {displaced_n} separada(s)" if displaced_n else ""
        extra += f" · {c['hidden']} oculto(s)" if c["hidden"] else ""
        self.summary.setText(f"{c['parts']} peça(s) · {c['groups']} grupo(s){extra}")

    # --------------------------------------------------------------------- filtro
    def _apply_filter(self, text: str) -> None:
        text = text.strip().lower()
        for i in range(self.tree.topLevelItemCount()):
            self._filter_item(self.tree.topLevelItem(i), text)
        for lst in (self.parts, self.groups):
            for i in range(lst.count()):
                it = lst.item(i)
                it.setHidden(bool(text) and text not in it.text().lower())

    def _filter_item(self, item: QTreeWidgetItem, text: str) -> bool:
        child_match = False
        for i in range(item.childCount()):
            child_match |= self._filter_item(item.child(i), text)
        match = not text or text in item.text(0).lower() or child_match
        item.setHidden(not match)
        if text and child_match:
            item.setExpanded(True)
        return match

    # ------------------------------------------------------------------- seleção
    def _selected_ids(self, widget) -> list[str]:
        if widget is self.tree:
            return [it.data(0, ID_ROLE) for it in self.tree.selectedItems()]
        return [it.data(ID_ROLE) for it in widget.selectedItems()]

    def _on_selection_changed(self, widget, source: str) -> None:
        self.selection.select(self._selected_ids(widget), source=source)

    def _on_external_selection(self, ids: list[str], source: str) -> None:
        """Seleção vinda do 3D (ou de outra aba): espelha na árvore e nas listas."""
        wanted = set(ids)
        if source != "tree":
            self._mirror(self.tree, {i: it for i, it in self._items.items()}, wanted, tree=True)
        if source != "list":
            self._mirror(self.parts, self._part_items, wanted)
        if source != "groups":
            self._mirror(self.groups, self._group_items, wanted)

    def _mirror(self, widget, items: dict, wanted: set[str], tree: bool = False) -> None:
        with QSignalBlocker(widget):
            widget.clearSelection()
            last = None
            for cid in wanted:
                item = items.get(cid)
                if item is not None:
                    item.setSelected(True)
                    last = item
            if last is not None:
                widget.scrollToItem(last)

    # ---------------------------------------------------------------- visibilidade
    def _on_tree_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if column != 0:
            return
        state = item.checkState(0)
        if state == Qt.PartiallyChecked:
            return
        self.visibility_toggled.emit(item.data(0, ID_ROLE), state == Qt.Checked)

    def _on_list_item_changed(self, item: QListWidgetItem) -> None:
        self.visibility_toggled.emit(item.data(ID_ROLE), item.checkState() == Qt.Checked)

    # ------------------------------------------------------------------ menu de contexto
    def _context_menu(self, widget, pos) -> None:
        ids = self.selection.selected
        under = widget.itemAt(pos)
        if under is not None and not ids:
            ids = [under.data(0, ID_ROLE) if widget is self.tree else under.data(ID_ROLE)]
        if not ids or self.project is None:
            return
        comps = self.project.components
        nodes = [comps.find(i) for i in ids if comps.find(i)]
        if not nodes:
            return
        menu = QMenu(self)
        first = nodes[0]
        add = lambda text, action, icon=None, enabled=True: self._add_action(menu, text, action, ids, icon, enabled)
        add("Ocultar", "hide", "eye")
        add("Mostrar", "show")
        add("Isolar", "isolate", "isolate")
        add("Mostrar tudo", "show_all")
        menu.addSeparator()
        if first.children:
            add("Explodir este grupo", "explode_group", "group_explode")
        if first.has_geometry:
            add("Separar peça", "separate_part", "separate")
        menu.addSeparator()
        from modules.solid_analyzer import can_split
        add("Separar sólidos compostos", "split", enabled=any(can_split(n) for n in nodes))
        add("Desfazer separação de sólidos", "undo_split",
            enabled=any(n.split_backup is not None for n in nodes))
        menu.addSeparator()
        add("Agrupar selecionados…", "group", enabled=len(nodes) >= 2)
        add("Desagrupar", "ungroup", enabled=bool(first.children and not first.has_geometry
                                                  and first.parent is not None))
        menu.addSeparator()
        add("Definir material…", "material")
        add("Renomear…", "rename")
        add("Ajustar vista à seleção", "fit_selection", "fit")
        menu.exec(widget.viewport().mapToGlobal(pos))

    def _add_action(self, menu: QMenu, text: str, action: str, ids: list[str],
                    icon: Optional[str], enabled: bool) -> None:
        act = menu.addAction(styles.make_icon(icon, size=16) if icon else None, text) if icon else menu.addAction(text)
        act.setEnabled(enabled)
        act.triggered.connect(lambda _=False, a=action: self.action_requested.emit(a, list(ids)))
