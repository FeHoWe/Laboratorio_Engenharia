"""Janela principal do NEXUS ENGINEERING LAB.

Esta classe só COORDENA: cada painel mostra uma parte do modelo e cada ação de
menu chama um módulo de domínio (importer, assembly_manager, exporter...).
Regras de negócio não ficam aqui.
"""
from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
from PySide6.QtCore import QObject, QSignalBlocker, QThread, Qt, Signal, Slot
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import (QApplication, QDialog, QDialogButtonBox, QFileDialog, QInputDialog, QLabel,
                               QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QDockWidget)

from core.cad_engine import CadEngine, environment_report
from core.project_manager import PROJECT_FILTER, Project, ProjectError, ProjectManager
from interface import styles
from interface.bom_dialog import BomDialog
from interface.joints_dialog import JointsDialog
from interface.scenes_dialog import ScenesDialog
from interface.component_tree import ComponentPanel
from interface.material_picker import MaterialPicker
from interface.properties_panel import PropertiesPanel
from interface.toolbar import ExplodeToolBar, SectionToolBar, build_main_toolbar
from interface.viewport import OffsetAnimator, VIEW_LABELS, Viewport
from modules.component_inspector import ComponentInspector
from modules.exporter import EXPORT_FILTER, ExportError, Exporter
from modules.measure_engine import MeasureEngine, axis_label
from modules.importer import FILE_DIALOG_FILTER, ImportFailure, ImportResult, ProjectImporter
from modules.selection_manager import SelectionManager
from modules.solid_analyzer import analyze_tree, can_split, split_into_solids, undo_split

APP_NAME = "NEXUS ENGINEERING LAB"
APP_VERSION = "3.6"


# --------------------------------------------------------------- console inferior
class ConsolePanel(QPlainTextEdit):
    """Mensagens de status, processamento, erros e resultados."""

    COLORS = {"info": styles.TEXT, "ok": styles.OK, "warn": styles.WARN, "error": styles.ERROR}
    TAGS = {"info": "INFO", "ok": " OK ", "warn": "AVISO", "error": "ERRO"}

    def __init__(self) -> None:
        super().__init__()
        self.setReadOnly(True)
        self.setMaximumBlockCount(2000)
        self.messages: list[tuple[str, str]] = []

    def log(self, level: str, message: str) -> None:
        self.messages.append((level, message))
        stamp = datetime.now().strftime("%H:%M:%S")
        color = self.COLORS.get(level, styles.TEXT)
        self.appendHtml(f'<span style="color:{styles.MUTED}">{stamp}</span> '
                        f'<span style="color:{color}"><b>{self.TAGS.get(level, "INFO")}</b> '
                        f'{html.escape(message)}</span>')


# ------------------------------------------------------------ importação em thread
from samples.projects import all_projects  # noqa: E402


class ImportWorker(QObject):
    done = Signal(object)    # ImportResult
    failed = Signal(str)

    def __init__(self, importer: ProjectImporter, path: str) -> None:
        super().__init__()
        self.importer, self.path = importer, path

    @Slot()
    def run(self) -> None:
        try:
            self.done.emit(self.importer.import_file(self.path))
        except ImportFailure as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # nunca deixar a thread morrer em silêncio
            self.failed.emit(f"Erro inesperado: {exc}")


class MainWindow(QMainWindow):
    def __init__(self, config: Optional[dict] = None, engine: Optional[CadEngine] = None) -> None:
        super().__init__()
        self.config = config or {}
        self.engine = engine or CadEngine()
        self.project_manager = ProjectManager(self.engine)
        self.exporter = Exporter(self.engine)
        self.selection = SelectionManager()
        self.mechanism = None
        self.kin_deg = None
        self._kin_dialog = None
        self.project: Project = self.project_manager.new_project("Novo projeto")
        self.inspector = ComponentInspector(self.project.components, self.project.materials)
        self.busy = False
        self.last_measurement = None
        self.last_angle = None
        self._last_explode: Optional[tuple[str, list[str]]] = None
        self._anim_label = ""
        self._thread: Optional[QThread] = None
        self._worker: Optional[ImportWorker] = None
        self._pending_import: Optional[tuple[Project, Optional[bool]]] = None

        self.resize(1480, 880)
        self.setStyleSheet(styles.stylesheet())

        self.viewport = Viewport()
        from PySide6.QtWidgets import QTabWidget
        from interface.fatigue_tab import FatigueTab
        self.fatigue_tab = FatigueTab(self.project.materials, self._primary_name)
        self.central_tabs = QTabWidget()  # noqa
        self.central_tabs.setObjectName("central_tabs")
        self.central_tabs.addTab(self.viewport, "Bancada 3D")
        self.central_tabs.addTab(self.fatigue_tab, "Simulação de fadiga")
        from interface.lab_tab import LabTab
        self.lab_tab = LabTab(self._primary_name)
        self.central_tabs.addTab(self.lab_tab, "Laboratório de testes")
        self.setCentralWidget(self.central_tabs)
        self.panel = ComponentPanel(self.selection)
        self.props = PropertiesPanel()
        self.console = ConsolePanel()
        self.animator = OffsetAnimator(self)

        self._create_actions()
        self._create_menus()
        self._create_docks_and_toolbars()
        self._create_statusbar()
        self._connect()
        self._set_project(self.project, rebuild=True)
        self.console.log("info", f"{APP_NAME} {APP_VERSION} pronto. Backend CAD: {self.engine.backend_name}.")
        self.console.log("info", "Importe um modelo (Ctrl+I) ou abra um projeto (Ctrl+O).")

    # ============================================================= criação da UI
    def _act(self, key: str, text: str, slot=None, shortcut: Optional[str] = None, icon: Optional[str] = None,
             tip: Optional[str] = None, checkable: bool = False, enabled: bool = True) -> QAction:
        action = QAction(styles.make_icon(icon) if icon else None, text, self) if icon else QAction(text, self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        if tip:
            action.setToolTip(tip)
            action.setStatusTip(tip)
        action.setCheckable(checkable)
        action.setEnabled(enabled)
        if slot is not None:
            (action.toggled if checkable else action.triggered).connect(slot)
        self.actions_by_key[key] = action
        return action

    def _create_actions(self) -> None:
        self.actions_by_key: dict[str, QAction] = {}
        a = self._act
        # arquivo
        a("new", "Novo projeto", self.new_project, "Ctrl+N")
        a("sample_engine", "Abrir exemplo: motor 4 cilindros", lambda: self.open_sample_engine())
        a("import", "Importar", lambda: self.import_model(), "Ctrl+I", "import", "Importar modelo CAD (STEP, STL, OBJ, FCStd)")
        a("open", "Abrir", lambda: self.open_project(), "Ctrl+O", "open", "Abrir projeto NEXUS (.nexus)")
        a("save", "Salvar", self.save_project, "Ctrl+S", "save", "Salvar projeto")
        a("save_as", "Salvar como…", self.save_project_as, "Ctrl+Shift+S")
        a("export", "Exportar modelo…", lambda: self.export_model(), "Ctrl+Shift+E")
        a("quit", "Sair", self.close, "Ctrl+Q")
        # editar
        a("select_all", "Selecionar todas as peças", self.select_all_parts, "Ctrl+A")
        a("clear_selection", "Limpar seleção", lambda: self.selection.clear("menu"), "Esc")
        a("rename", "Renomear…", self.rename_selected, "F2")
        a("history", "Histórico de alterações…", self.show_history)
        # vista
        a("fit", "Ajustar", self.fit_view, "Home", "fit", "Centralizar o projeto na janela")
        a("fit_selection", "Ajustar à seleção", self.fit_selection)
        for key, shortcut in (("front", "Ctrl+1"), ("back", "Ctrl+2"), ("left", "Ctrl+3"),
                              ("right", "Ctrl+4"), ("top", "Ctrl+5"), ("bottom", "Ctrl+6"), ("iso", "Ctrl+0")):
            icon = {"front": "view_front", "top": "view_top", "right": "view_right", "iso": "view_iso"}.get(key)
            a(f"view_{key}", {"front": "Frontal", "top": "Superior", "right": "Direita", "iso": "Iso"}.get(key, VIEW_LABELS[key]),
              lambda _=False, k=key: self.set_view(k), shortcut, icon, f"Vista {VIEW_LABELS[key].lower()}")
        a("perspective", "Perspectiva", self.toggle_perspective, "Ctrl+P", "perspective",
          "Alternar entre perspectiva e vista ortográfica", checkable=True)
        self.actions_by_key["perspective"].setChecked(True)
        a("edges", "Mostrar arestas", self.toggle_edges, None, None, None, checkable=True)
        self.actions_by_key["edges"].setChecked(True)
        # montagem
        a("split", "Separar sólidos compostos", lambda: self.split_composites(), None, None,
          "Converte objetos com vários sólidos em componentes individuais (reversível)")
        a("undo_split", "Desfazer separação de sólidos", lambda: self.undo_split_selected())
        a("group", "Agrupar seleção…", lambda: self.group_selected())
        a("ungroup", "Desagrupar", lambda: self.ungroup_selected())
        # explosão
        a("explode_all", "Explodir montagem completa", lambda: self.explode_all(), "Ctrl+E")
        a("explode_group", "Explodir grupo selecionado", lambda: self.explode_group())
        a("separate_part", "Separar peça selecionada", lambda: self.separate_part())
        a("restore", "Restaurar montagem", lambda: self.restore_assembly(), "Ctrl+R")
        # componentes
        a("hide", "Ocultar", lambda: self.hide_selected(), "Ctrl+H", "eye", "Ocultar componentes selecionados")
        a("show", "Mostrar", lambda: self.show_selected(), "Ctrl+Shift+H")
        a("isolate", "Isolar", lambda: self.isolate_selected(), "Ctrl+Shift+I", "isolate", "Mostrar somente a seleção")
        a("show_all", "Mostrar tudo", lambda: self.show_all(), "Ctrl+Alt+H", None, "Reexibir todos os componentes")
        a("material", "Definir material…", lambda: self.assign_material())
        a("typical_materials", "Aplicar materiais típicos ao exemplo do motor",
          lambda: self.apply_typical_materials(), tip="Sugestão didática, só para o exemplo; você pode trocar depois")
        a("scene_save", "Salvar cena atual…", lambda: self.save_scene_dialog(), "Ctrl+K", None,
          "Guarda câmera, explosão, visibilidade e corte com um nome")
        a("scene_manage", "Gerenciar cenas…", lambda: ScenesDialog(self).exec(), "Ctrl+Shift+K")
        a("report_pdf", "Relatório PDF do projeto…", lambda: self.export_report_dialog(), "Ctrl+Shift+R", None,
          "PDF com vista geral, BOM, materiais e uma página por componente")
        a("joints", "Relações de montagem (juntas inferidas)…", lambda: self.show_joints(), "Ctrl+J", None,
          "Deduz juntas concêntricas e plano-a-plano da geometria (não lê mates de CADs)")
        a("fatigue", "Simulação de fadiga (aba)…", lambda: self.open_fatigue(), "Ctrl+Shift+F", None,
          "Abre a aba de fadiga: S-N, Goodman/Gerber, dano de Miner e mola helicoidal (análise analítica, dados digitados por você)")
        for _p in all_projects():
            a(f"proj_{_p.key}", _p.title, (lambda *_, k=_p.key: self.open_predefined(k)), None, None, _p.description + " — " + _p.note)
        a("library", "Biblioteca de peças de engenharia…", lambda: self.show_library(), "Ctrl+L", None,
          "Parafusos, rolamentos, engrenagens, perfis, molas… (B-rep real, parâmetros editáveis) para montar seus próprios projetos")
        a("arsenal", "NEXUS Engineering Arsenal (componentes versionados)…", lambda: self.show_arsenal(), "Ctrl+Shift+A", None,
          "Biblioteca central de componentes reutilizáveis: IDs NEXUS-COMP, versões, comparar/restaurar, variantes e compatibilidade")
        a("solvers", "Solvers, vitrine e projetos…", lambda: self.show_solvers(), "Ctrl+Shift+S", None,
          "Status de OpenFOAM/CalculiX/Gmsh (NÃO INSTALADO se ausentes), vitrine do Arsenal e projetos do usuário")
        a("hub", "NEXUS — Produtos (CAD, Structural, Aerodynamics, Vehicle, Intelligence)…", lambda: self.show_hub(), "Ctrl+Shift+H", None,
          "Mapa dos cinco produtos do NEXUS e das funções reais de cada um, com estado honesto (pronto/parcial/planejado)")
        a("intelligence", "NEXUS INTELLIGENCE — interpretar resultados e revisar projeto…", lambda: self.show_intelligence(), "Ctrl+Shift+I", None,
          "Assistente técnico por regras: parecer sobre resultados, revisão de projeto, comparação e glossário (não inventa números)")
        a("vehgeo", "NEXUS VEHICLE — Pneu combinado e suspensão…", lambda: self.show_vehgeo(), None, None,
          "Força combinada Fx–Fy do pneu (escova) e cinemática de suspensão duplo-A (camber, bitola, centro de rolagem)")
        a("nlfea", "NEXUS STRUCTURAL — Plasticidade, multimaterial e contato…", lambda: self.show_nlfea(), None, None,
          "Barra elastoplástica, barras em série e blocos em contato no CalculiX real, com a solução analítica ao lado")
        a("clearfield", "Limpar mapa de tensões/pressão do visualizador", lambda: self.clear_field_map(), None, None,
          "Remove o mapa de cores (FEA/CFD) exibido no visualizador 3D e devolve as peças")
        a("f1tools", "Engenharia F1 (regulamento, massa/CG, volta)…", lambda: self.show_f1tools(), "Ctrl+Alt+F", None,
          "Conformidade geométrica com limites públicos do regulamento, massa/CG/inércia e simulação de volta quase-estacionária (estudo, não homologação)")
        a("f1sim", "Simulador F1 completo (volta, pneus, estratégia, telemetria, áudio, análise)…", lambda: self.show_f1sim(), "Ctrl+Alt+S", None,
          "NEXUS F1: simulador quase-estático por circuito, pneus, estratégia de pit stop, comparação A/B/C, análise estilo i2/OptimumLap e som sintetizado do motor (dados sintéticos, parâmetros estimados)")
        a("lab", "Laboratório de testes (aba)…", lambda: self.open_lab(), "Ctrl+Shift+L", None,
          "Aerodinâmica, desempenho e testes estruturais analíticos (não é CFD nem FEA)")
        a("kinematics", "Animar mecanismo (motor de exemplo)…", lambda: self.open_kinematics(), "Ctrl+M", None,
          "Gira virabrequim, mexe bielas/pistões, comandos e válvulas (movimento prescrito, só exibição)")
        a("interference", "Verificação de interferência (estática)…", lambda: self.show_interference(), "Ctrl+Shift+I", None,
          "Acha pares de peças que se sobrepõem (interseção booleana exata), lista, seleciona na cena e exporta CSV")
        a("bom", "Lista de materiais (BOM) e massa…", lambda: self.show_bom(), "Ctrl+B", None,
          "Massa por componente, total e exportação CSV/XLSX")
        # análise
        a("inspector", "Component Inspector", self.toggle_inspector, "Ctrl+Shift+P", "inspect", checkable=True)
        self.actions_by_key["inspector"].setChecked(True)
        a("identify_solids", "Identificar sólidos compostos", self.identify_solids)
        a("measure", "Medir distância entre 2 componentes", self.measure_selected, "Ctrl+M", None,
          "Selecione exatamente duas peças e meça a menor distância entre elas")
        a("measure_angle", "Medir ângulo entre 2 componentes", self.measure_angle, "Ctrl+Shift+M", None,
          "Ângulo entre os eixos dos cilindros (ou normais das maiores faces planas)")
        a("diameters", "Listar diâmetros do componente", self.list_diameters)
        a("clear_measure", "Limpar medição", self.clear_measurement)
        a("stats", "Estatísticas do projeto", self.show_stats)
        # simulação (ainda não existe: ações desabilitadas e rotuladas com a versão prevista)
        a("sim_motion", "Simulação de mecanismos e movimentos — V2.1", enabled=False,
          tip="Planejado para a V2.1; não disponível nesta versão")
        a("sim_materials", "Análise de materiais e propriedades físicas — V2.2", enabled=False,
          tip="Planejado para a V2.2; não disponível nesta versão")
        a("sim_fem", "Análise estrutural e elementos finitos — V3.0", enabled=False,
          tip="Planejado para a V3.0; não disponível nesta versão")
        a("sim_thermal", "Temperatura e vibrações — V3.1", enabled=False,
          tip="Planejado para a V3.1; não disponível nesta versão")
        # ferramentas / ajuda
        a("environment", "Verificar ambiente…", self.show_environment)
        a("assistant", "Engineering Assistant — V4.0", enabled=False,
          tip="Planejado para a V4.0; nenhuma IA é simulada nesta versão")
        a("about", "Sobre o NEXUS", self.show_about)
        a("quick_guide", "Guia rápido de uso", self.show_quick_guide)

    def _create_menus(self) -> None:
        A = self.actions_by_key
        bar = self.menuBar()
        m = bar.addMenu("File")
        pm = m.addMenu("Projetos predefinidos")
        for _p in all_projects():
            pm.addAction(A[f"proj_{_p.key}"])
        for k in ("new", "import", "open", "sample_engine", None, "save", "save_as", None, "export", "report_pdf", None, "quit"):
            m.addSeparator() if k is None else m.addAction(A[k])
        m = bar.addMenu("Edit")
        for k in ("select_all", "clear_selection", None, "rename", None, "history"):
            m.addSeparator() if k is None else m.addAction(A[k])
        m = bar.addMenu("View")
        for k in ("fit", "fit_selection", None):
            m.addSeparator() if k is None else m.addAction(A[k])
        views = m.addMenu("Vistas")
        group = QActionGroup(self)
        for k in ("front", "back", "left", "right", "top", "bottom", "iso"):
            views.addAction(A[f"view_{k}"])
        m.addAction(A["perspective"])
        m.addAction(A["edges"])
        self.view_menu = m
        m = bar.addMenu("Assembly")
        for k in ("split", "undo_split", None, "group", "ungroup", None, "restore"):
            m.addSeparator() if k is None else m.addAction(A[k])
        m = bar.addMenu("Explode")
        for k in ("explode_all", "explode_group", "separate_part", None, "restore"):
            m.addSeparator() if k is None else m.addAction(A[k])
        m = bar.addMenu("Components")
        for k in ("hide", "show", "isolate", "show_all", None, "material", "typical_materials", "rename"):
            m.addSeparator() if k is None else m.addAction(A[k])
        m = bar.addMenu("Analyze")
        for k in ("inspector", "identify_solids", "bom", "joints", "interference", "kinematics", "fatigue", "lab", "library", "arsenal", "f1tools", "f1sim", "hub", "intelligence", "vehgeo", "nlfea", "solvers", "clearfield", None, "measure", "measure_angle", "diameters", "clear_measure", None, "stats"):
            if k is None:
                m.addSeparator()
                continue
            m.addAction(A[k])
        self.scenes_menu = bar.addMenu("Scenes")
        self.scenes_menu.aboutToShow.connect(self._fill_scenes_menu)
        m = bar.addMenu("Simulation")
        for k in ("sim_motion", "sim_materials", "sim_fem", "sim_thermal"):
            m.addAction(A[k])
        m = bar.addMenu("Tools")
        for k in ("environment", "assistant"):
            m.addAction(A[k])
        m = bar.addMenu("Help")
        for k in ("quick_guide", "about"):
            m.addAction(A[k])

    def _create_docks_and_toolbars(self) -> None:
        self.main_toolbar = build_main_toolbar(self, self.actions_by_key)
        self.addToolBar(Qt.TopToolBarArea, self.main_toolbar)
        self.addToolBarBreak(Qt.TopToolBarArea)
        self.explode_bar = ExplodeToolBar()
        self.addToolBar(Qt.TopToolBarArea, self.explode_bar)
        self.addToolBarBreak(Qt.TopToolBarArea)
        self.section_bar = SectionToolBar()
        self.addToolBar(Qt.TopToolBarArea, self.section_bar)

        def dock(title, widget, area, name):
            d = QDockWidget(title, self)
            d.setObjectName(name)
            d.setWidget(widget)
            d.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable
                          | QDockWidget.DockWidgetClosable)
            self.addDockWidget(area, d)
            return d

        self.dock_left = dock("Componentes", self.panel, Qt.LeftDockWidgetArea, "dock_components")
        self.dock_right = dock("Propriedades", self.props, Qt.RightDockWidgetArea, "dock_properties")
        self.dock_bottom = dock("Status e mensagens", self.console, Qt.BottomDockWidgetArea, "dock_console")
        self.dock_left.setMinimumWidth(290)
        self.dock_right.setMinimumWidth(330)
        self.dock_bottom.setMinimumHeight(110)
        self.resizeDocks([self.dock_left, self.dock_right], [310, 350], Qt.Horizontal)
        self.resizeDocks([self.dock_bottom], [150], Qt.Vertical)
        for d in (self.dock_left, self.dock_right, self.dock_bottom):
            self.view_menu.addAction(d.toggleViewAction())
        self.dock_right.visibilityChanged.connect(
            lambda v: self.actions_by_key["inspector"].setChecked(self.dock_right.isVisible()))

    def _create_statusbar(self) -> None:
        sb = self.statusBar()
        self.state_label = QLabel("Montada")
        self.select_label = QLabel("")
        self.select_label.setObjectName("muted")
        self.progress = QProgressBar()
        self.progress.setFixedWidth(220)
        self.progress.setVisible(False)
        sb.addWidget(self.state_label)
        sb.addWidget(self.select_label, 1)
        sb.addPermanentWidget(self.progress)

    def _connect(self) -> None:
        self.selection.subscribe(self._on_selection_changed)
        self.viewport.pick_requested.connect(self._on_pick)
        self.panel.action_requested.connect(self._on_panel_action)
        self.panel.visibility_toggled.connect(self._set_visible)
        self.props.rename_requested.connect(self._rename)
        self.props.material_changed.connect(self._set_material)
        self.props.new_material_requested.connect(self._new_material)
        self.props.pick_material_requested.connect(self._pick_material)
        self.props.visibility_changed.connect(self._set_visible)
        self.animator.frame.connect(self._on_anim_frame)
        self.animator.finished.connect(self._on_anim_finished)
        self.section_bar.params_changed.connect(self._apply_section)
        self.section_bar.holo_check.toggled.connect(self.set_holo)
        eb = self.explode_bar
        eb.explode_all_requested.connect(self.explode_all)
        eb.explode_group_requested.connect(self.explode_group)
        eb.separate_part_requested.connect(self.separate_part)
        eb.restore_requested.connect(self.restore_assembly)
        eb.params_changed.connect(self._on_explode_params_changed)

    # ================================================================== projeto
    @property
    def scene(self):
        return self.viewport.scene

    def _set_project(self, project: Project, rebuild: bool = True, fit: bool = True) -> None:
        self.animator.stop()
        self.project = project
        self.inspector = ComponentInspector(project.components, project.materials)
        self._last_explode = None
        self.selection.clear("api")
        self.scene.set_section(None)
        if hasattr(self, 'section_bar'):
            self.section_bar.enable_check.setChecked(False)
        if rebuild:
            self._rebuild_scene(fit=fit)
        self.panel.populate(project)
        self._update_title()
        self._update_state_labels()
        self._refresh_inspector()

    def _rebuild_scene(self, fit: bool = False) -> None:
        self._begin_busy("Construindo a cena 3D…")
        try:
            def progress(i: int, n: int, name: str) -> None:
                self.progress.setMaximum(max(n, 1))
                self.progress.setValue(i)
                if i % 8 == 0:
                    QApplication.processEvents()
            if self._kin_dialog is not None:
                self._kin_dialog.close()
            self.kin_deg, self.mechanism = None, None
            failures = self.scene.build(self.project.components, progress)
            for f in failures:
                self.console.log("warn", f"Peça não exibida — {f}")
            if fit:
                self.scene.set_view("iso")
            self.viewport.refresh()
        finally:
            self._end_busy()

    def _begin_busy(self, message: str) -> None:
        self.busy = True
        self.statusBar().showMessage(message)
        self.progress.setValue(0)
        self.progress.setVisible(True)
        QApplication.setOverrideCursor(Qt.BusyCursor)

    def _end_busy(self) -> None:
        self.busy = False
        self.progress.setVisible(False)
        self.statusBar().clearMessage()
        QApplication.restoreOverrideCursor()

    def _update_title(self) -> None:
        self.setWindowTitle(f"{self.project.title} — {APP_NAME}")

    def _update_state_labels(self) -> None:
        comps = self.project.components
        displaced = comps.displaced_ids()
        self.state_label.setText(f"Explodida · {len(displaced)} peça(s) separada(s)" if displaced else "Montada")
        c = comps.counts()
        self._update_hud() if hasattr(self, 'section_bar') else None
        self.select_label.setText(f"{c['parts']} peça(s)" + (f" · seleção: {len(self.selection.selected)}"
                                                           if self.selection.selected else ""))

    def _maybe_save(self) -> bool:
        """Pergunta o que fazer com alterações não salvas. False = cancelar a operação."""
        if not self.project.dirty or not self.project.components.leaves():
            return True
        ans = QMessageBox.question(
            self, "Alterações não salvas",
            f"O projeto '{self.project.name}' tem alterações não salvas. Salvar antes de continuar?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save)
        if ans == QMessageBox.Cancel:
            return False
        if ans == QMessageBox.Save:
            return self.save_project()
        return True

    # ---- novo / abrir / salvar
    def new_project(self) -> None:
        if not self._maybe_save():
            return
        self._set_project(self.project_manager.new_project("Novo projeto"))
        self.console.log("ok", "Novo projeto criado.")

    def open_project(self, path: Optional[str] = None) -> bool:
        if path is None:
            if not self._maybe_save():
                return False
            path, _ = QFileDialog.getOpenFileName(self, "Abrir projeto NEXUS", "", PROJECT_FILTER)
            if not path:
                return False
        self._begin_busy("Abrindo projeto…")
        try:
            project = self.project_manager.open(path)
        except ProjectError as exc:
            self._end_busy()
            self.console.log("error", str(exc))
            QMessageBox.critical(self, "Não foi possível abrir", str(exc))
            return False
        self._end_busy()
        self._set_project(project)
        self.console.log("ok", f"Projeto '{project.name}' aberto ({len(project.components.leaves())} peças).")
        return True

    def save_project(self) -> bool:
        if self.project.path is None:
            return self.save_project_as()
        return self._save_to(None)

    def save_project_as(self, path: Optional[str] = None) -> bool:
        if path is None:
            suggestion = str(Path("projects") / f"{self.project.name}.nexus")
            path, _ = QFileDialog.getSaveFileName(self, "Salvar projeto como", suggestion, PROJECT_FILTER)
            if not path:
                return False
        return self._save_to(path)

    def _save_to(self, path: Optional[str]) -> bool:
        try:
            saved = self.project_manager.save(self.project, path)
        except ProjectError as exc:
            self.console.log("error", str(exc))
            QMessageBox.critical(self, "Falha ao salvar", str(exc))
            return False
        self._update_title()
        self.console.log("ok", f"Projeto salvo em {saved}.")
        return True

    # ---- importar
    def import_model(self, path: Optional[str] = None, background: bool = True,
                     ask_split: Optional[bool] = None) -> None:
        """Importa um modelo CAD criando um NOVO projeto com o conteúdo do arquivo.

        ``ask_split``: None = perguntar ao usuário; True/False = decidir sem perguntar.
        """
        self.scene.project_key = self.__dict__.pop("_predef_next", None)   # aparência visual por projeto predefinido
        if self.busy:
            self.console.log("warn", "Aguarde o término da operação em andamento.")
            return
        if path is None:
            if not self._maybe_save():
                return
            path, _ = QFileDialog.getOpenFileName(self, "Importar modelo CAD", "", FILE_DIALOG_FILTER)
            if not path:
                return
        stem = Path(path).stem
        project = self.project_manager.new_project(stem)
        project.source_files.append(str(path))
        importer = ProjectImporter(self.engine, project.ids)
        self.console.log("info", f"Importando '{Path(path).name}'…")
        self._begin_busy(f"Importando {Path(path).name}…")
        self.progress.setMaximum(0)  # indeterminado
        self._pending_import = (project, ask_split)
        worker = ImportWorker(importer, str(path))
        if not background:
            worker.done.connect(self._on_import_done)
            worker.failed.connect(self._on_import_failed)
            worker.run()
            return
        self._thread = QThread(self)
        self._worker = worker
        worker.moveToThread(self._thread)
        self._thread.started.connect(worker.run)
        worker.done.connect(self._on_import_done)
        worker.failed.connect(self._on_import_failed)
        worker.done.connect(self._thread.quit)
        worker.failed.connect(self._thread.quit)
        self._thread.start()

    @Slot(str)
    def _on_import_failed(self, message: str) -> None:
        self._end_busy()
        self._pending_import = None
        self.console.log("error", message)
        QMessageBox.critical(self, "Falha na importação", message)

    @Slot(object)
    def _on_import_done(self, result: ImportResult) -> None:
        project, ask_split = self._pending_import
        self._pending_import = None
        self._end_busy()
        project.set_root(result.root)
        project.name = Path(result.path).stem
        project.log("Modelo importado", f"{Path(result.path).name} ({result.format}) — {result.report.summary()}")
        self.console.log("ok", f"{Path(result.path).name} importado ({result.format}): {result.report.summary()}.")
        for w in result.warnings:
            self.console.log("warn", w)
        self._set_project(project)
        if result.report.has_splittable:
            n = len(result.report.multi_solid)
            if ask_split is None:
                ask_split = QMessageBox.question(
                    self, "Objetos com vários sólidos",
                    f"{n} objeto(s) importado(s) contém(êm) vários sólidos independentes.\n\n"
                    "Separar em componentes individuais agora? (Pode ser desfeito depois.)",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes) == QMessageBox.Yes
            if ask_split:
                self.split_composites()
            else:
                self.console.log("info", f"{n} objeto(s) composto(s) mantido(s) unido(s); "
                                         "use Assembly ▸ Separar sólidos compostos quando quiser.")

    def open_sample_engine(self, ask_split: Optional[bool] = False, background: bool = True) -> None:
        """Gera (se preciso) e importa o motor 4 cilindros de exemplo."""
        from samples.motor_4_cilindros import write
        target = Path(__file__).resolve().parent.parent / "samples" / "motor_4_cilindros.step"
        if not target.exists():
            self._begin_busy("Gerando o motor de exemplo…")
            try:
                write(target)
            except Exception as exc:
                self._end_busy()
                self.console.log("error", f"Não foi possível gerar o exemplo: {exc}")
                return
            self._end_busy()
        if self._maybe_save():
            self.import_model(str(target), ask_split=ask_split, background=background)

    # ---- exportar
    def export_model(self, path: Optional[str] = None, include_explosion: Optional[bool] = None) -> bool:
        if not self.project.components.leaves():
            self.console.log("warn", "Não há geometria para exportar.")
            return False
        if path is None:
            path, _ = QFileDialog.getSaveFileName(self, "Exportar modelo", f"exports/{self.project.name}.step",
                                                  EXPORT_FILTER)
            if not path:
                return False
        if include_explosion is None:
            include_explosion = False
            if self.project.assembly.is_exploded():
                include_explosion = QMessageBox.question(
                    self, "Exportar", "A montagem está explodida. Exportar a vista explodida?\n"
                    "(Não = exportar na posição original.)",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes
        try:
            res = self.exporter.export(self.project, path, include_explosion=include_explosion)
        except ExportError as exc:
            self.console.log("error", str(exc))
            QMessageBox.critical(self, "Falha ao exportar", str(exc))
            return False
        self.project.log("Modelo exportado", f"{res.path.name} ({res.format}, {res.exported} peças)")
        self.console.log("ok", f"Exportado {res.exported} peça(s) para {res.path} ({res.format}).")
        if res.skipped:
            self.console.log("warn", "Não exportadas (malhas não viram STEP): " + ", ".join(res.skipped[:8]))
        self._update_title()
        return True

    # =============================================================== seleção/3D
    def _leaf_ids_of(self, ids: list[str]) -> set[str]:
        comps = self.project.components
        out: set[str] = set()
        for i in ids:
            node = comps.find(i)
            if node is not None:
                out.update(l.id for l in node.leaves())
        return out

    def _on_selection_changed(self, ids: list[str], source: str) -> None:
        self.scene.clear_measure_line()
        self.scene.set_highlight(self._leaf_ids_of(ids))
        self.viewport.refresh()
        self._refresh_inspector()
        self._update_state_labels()

    def _on_pick(self, comp_id: Optional[str], additive: bool) -> None:
        if comp_id is None:
            if not additive:
                self.selection.clear("viewport")
            return
        if additive:
            self.selection.toggle(comp_id, "viewport")
        else:
            self.selection.select(comp_id, source="viewport")

    def _refresh_inspector(self) -> None:
        comps = self.project.components
        pid = self.selection.primary
        node = comps.find(pid) if pid else None
        if node is None:
            self.props.show_report(None, [], 0)
            return
        try:
            rep = self.inspector.inspect(node)
        except Exception as exc:
            self.console.log("error", f"Inspector: {exc}")
            self.props.show_report(None, [], 0)
            return
        self.props.show_report(rep, self.project.materials.quick_names(rep.material if rep else None), len(self.selection.selected))

    def select_all_parts(self) -> None:
        self.selection.select([l.id for l in self.project.components.leaves()], source="menu")

    def _selected_nodes(self):
        comps = self.project.components
        return [n for n in (comps.find(i) for i in self.selection.selected) if n is not None]

    # ---- câmera
    def fit_view(self) -> None:
        self.scene.fit()
        self.viewport.refresh()

    def fit_selection(self) -> None:
        if not self.scene.fit_to(self.scene.highlighted):
            self.fit_view()
            return
        self.viewport.refresh()

    def set_view(self, name: str) -> None:
        self.scene.set_view(name)
        self.viewport.refresh()

    def toggle_perspective(self, checked: bool) -> None:
        self.scene.set_perspective(checked)
        self.actions_by_key["perspective"].setText("Perspectiva" if checked else "Ortográfica")
        self.viewport.refresh()

    def toggle_edges(self, checked: bool) -> None:
        self.scene.set_edges_visible(checked, self.project.components)
        self.viewport.refresh()

    def toggle_inspector(self, checked: bool) -> None:
        if hasattr(self, "dock_right"):      # o sinal dispara durante a criação das ações
            self.dock_right.setVisible(checked)

    # ============================================================ visibilidade
    def _after_visibility_change(self, detail: str) -> None:
        self.scene.sync_visibility(self.project.components)
        self.panel.refresh_states()
        self.project.log("Visibilidade", detail)
        self._update_title()
        self._refresh_inspector()
        self.viewport.refresh()

    def _set_visible(self, comp_id: str, visible: bool) -> None:
        node = self.project.components.find(comp_id)
        if node is None or all(n.visible == visible for n in node.walk()):
            return
        self.project.components.set_visible(comp_id, visible)
        self._after_visibility_change(f"{'Exibido' if visible else 'Oculto'}: {node.name}")

    def hide_selected(self) -> None:
        for n in self._selected_nodes():
            self.project.components.set_visible(n.id, False)
        self._after_visibility_change("Ocultar seleção")

    def show_selected(self) -> None:
        for n in self._selected_nodes():
            self.project.components.set_visible(n.id, True)
            for a in n.ancestors():
                a.visible = True
        self._after_visibility_change("Mostrar seleção")

    def isolate_selected(self) -> None:
        if not self.selection.selected:
            self.console.log("warn", "Selecione ao menos um componente para isolar.")
            return
        self.project.components.isolate(self.selection.selected)
        self._after_visibility_change("Isolar seleção")
        self.fit_selection()

    def show_all(self) -> None:
        self.project.components.show_all()
        self._after_visibility_change("Mostrar tudo")

    # ============================================================ edição
    def rename_selected(self) -> None:
        pid = self.selection.primary
        node = self.project.components.find(pid) if pid else None
        if node is None:
            self.console.log("warn", "Selecione um componente para renomear.")
            return
        text, ok = QInputDialog.getText(self, "Renomear", "Novo nome:", text=node.name)
        if ok and text.strip():
            self._rename(node.id, text.strip())

    def _rename(self, comp_id: str, name: str) -> None:
        node = self.project.components.find(comp_id)
        if node is None or node.name == name:
            return
        old, node.name = node.name, name
        if node is self.project.components.root:
            self.project.name = name
        self.project.log("Renomeado", f"{old} → {name}")
        self.panel.refresh_states()
        self._update_title()
        self._refresh_inspector()

    def assign_material(self) -> None:
        nodes = self._selected_nodes()
        if not nodes:
            self.console.log("warn", "Selecione componentes para definir o material.")
            return
        self._pick_material(nodes[0].id, apply_to=[n.id for n in nodes])

    def _pick_material(self, comp_id: str, apply_to: Optional[list] = None) -> None:
        """Abre o banco de materiais (busca + categorias) e aplica a escolha."""
        current = self.project.components.get(comp_id).material if self.project.components.get(comp_id) else None
        dlg = MaterialPicker(self.project.materials, self, current)
        if not dlg.exec() or not dlg.selected:
            self._refresh_inspector()
            return
        for cid in (apply_to or [comp_id]):
            self._set_material(cid, dlg.selected)

    def _new_material(self, comp_id: str) -> None:
        name, ok = QInputDialog.getText(self, "Novo material", "Nome do material:")
        if not ok or not name.strip():
            self._refresh_inspector()
            return
        density, ok = QInputDialog.getDouble(self, "Novo material", "Densidade (g/cm³):", 7.85, 0.001, 30.0, 3)
        if not ok:
            self._refresh_inspector()
            return
        try:
            self.project.materials.add_custom(name, density)
        except ValueError as exc:
            self.console.log("error", str(exc))
            self._refresh_inspector()
            return
        self._set_material(comp_id, name.strip())

    def _set_material(self, comp_id: str, material: Optional[str]) -> None:
        node = self.project.components.find(comp_id)
        if node is None:
            return
        changed = self.project.components.set_material(comp_id, material)
        if changed:
            self.project.log("Material", f"{node.name}: {material or 'sem material'} ({len(changed)} peça(s))")
            self.console.log("ok", f"Material '{material or 'nenhum'}' aplicado a {len(changed)} peça(s).")
        self._update_title()
        self._refresh_inspector()

    def apply_typical_materials(self) -> int:
        """Aplica materiais típicos às peças de um projeto predefinido (somente por pedido do usuário)."""
        from samples.projects import project_for_name, get
        pdef = project_for_name(self.project.name) or get("motor")
        done = 0
        for leaf in self.project.components.leaves():
            mat = pdef.material_for(leaf.name)
            if mat and self.project.materials.get(mat) and leaf.material != mat:
                self.project.components.set_material(leaf.id, mat)
                done += 1
        if done:
            self.project.log("Material", f"Materiais típicos de '{pdef.title}' aplicados a {done} peça(s)")
            self.console.log("ok", f"Materiais típicos aplicados a {done} peça(s). Peças sem correspondência ficam sem material (ex.: compósitos).")
        else:
            self.console.log("warn", "Nenhuma peça com nome de projeto predefinido encontrada.")
        self._update_title()
        self._refresh_inspector()
        return done

    # ============================================================== projetos predefinidos e biblioteca (V2.2)
    def open_predefined(self, key: str, ask_split: Optional[bool] = False, background: bool = True) -> None:
        """Gera (se preciso) o STEP do projeto predefinido e o importa."""
        from samples.projects import get
        pdef = get(key)
        if not pdef.step_path.exists():
            self._begin_busy(f"Gerando '{pdef.title}'…")
            try:
                pdef.ensure_step()
            except Exception as exc:
                self._end_busy()
                self.console.log("error", f"Não foi possível gerar o projeto: {exc}")
                return
            self._end_busy()
        self.console.log("info", pdef.note)
        if self._maybe_save():
            self._predef_next = key
            self.import_model(str(pdef.step_path), ask_split=ask_split, background=background)

    def show_arsenal(self) -> None:
        from interface.arsenal_dialog import ArsenalDialog
        ArsenalDialog(self).exec()

    def show_hub(self) -> None:
        from interface.hub_dialog import HubDialog
        HubDialog(self).exec()

    def show_nlfea(self) -> None:
        from interface.nl_dialog import NLDialog
        NLDialog(self).exec()

    def show_vehgeo(self) -> None:
        from interface.vehicle_geo_dialog import VehicleGeoDialog
        VehicleGeoDialog(self).exec()

    def show_intelligence(self) -> None:
        from interface.hub_dialog import IntelligenceDialog
        IntelligenceDialog(self).exec()

    def clear_field_map(self) -> None:
        """Remove o mapa de cores (FEA/CFD) e restaura as peças."""
        self.viewport.clear_field()

    def show_solvers(self) -> None:
        from interface.solvers_dialog import SolversDialog
        SolversDialog(self).exec()

    def show_f1sim(self) -> None:
        """Abre o NEXUS F1 (janela própria); mantém referência para não ser coletada."""
        from nexus_f1.ui.main_window import MainWindow as F1Window
        from nexus_f1.ui.style import QSS
        w = F1Window()
        w.setStyleSheet(QSS)
        w.setAttribute(Qt.WA_DeleteOnClose, True)
        self._f1sim = w
        w.show()

    def show_f1tools(self) -> None:
        from interface.f1_dialog import F1Dialog
        F1Dialog(self).exec()

    def show_library(self) -> None:
        from interface.library_dialog import LibraryDialog
        LibraryDialog(self).exec()

    def add_library_part(self, key: str, params: Optional[dict] = None, pos=(0.0, 0.0, 0.0), new_project: bool = False):
        """Cria uma peça da biblioteca e a insere na montagem atual (ou num projeto novo). Retorna o componente criado."""
        import tempfile
        from core.cad_engine import RawNode
        from core.geometry import translation_matrix
        from samples.library import PARTS
        pd = PARTS[key]
        shape = pd.make(**(params or {}))
        node = RawNode(pd.title, shape=shape, local_matrix=translation_matrix(list(pos)))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "peca.step"
            self.engine.write_step([node], path)
            if new_project:
                project = self.project_manager.new_project(pd.title)
            else:
                project = self.project
            res = ProjectImporter(self.engine, project.ids).import_file(path)
        comp = res.root
        if new_project:
            project.set_root(comp)
            comp.name = pd.title
            project.log("Peça da biblioteca", pd.title)
            self._set_project(project)
        else:
            comp.name = pd.title
            for leaf in comp.leaves():
                if leaf.name.lower().startswith(("peca", "part", "shape", "solid")) or not leaf.name:
                    leaf.name = pd.title
            project.components.root.add_child(comp)
            project.components.reindex()
            project.log("Peça da biblioteca", f"{pd.title} em {tuple(round(v, 1) for v in pos)}")
            self._structure_changed()
        self.console.log("ok", f"'{pd.title}' adicionada. {pd.note}")
        return comp

    def show_interference(self):
        from interface.interference_dialog import InterferenceDialog
        dlg = InterferenceDialog(self)
        dlg.show()
        self._interference_dialog = dlg
        return dlg

    def open_lab(self) -> None:
        self.central_tabs.setCurrentWidget(self.lab_tab)

    def build_bom(self):
        from modules.bom import BomBuilder
        rep = BomBuilder(self.project.components, self.project.materials, self.inspector).build()
        rep.project = self.project.name
        return rep

    def show_bom(self) -> None:
        if not self.project.components.leaves():
            self.console.log("warn", "Não há peças para a lista de materiais.")
            return
        from modules import bom as bommod
        rep = self.build_bom()
        self.console.log("info" if rep.complete else "warn", rep.summary())
        dlg = BomDialog(rep, self)

        def _export(kind: str) -> None:
            ext = "csv" if kind == "csv" else "xlsx"
            path, _ = QFileDialog.getSaveFileName(dlg, "Exportar BOM", f"exports/{self.project.name}_BOM.{ext}",
                                                  f"{ext.upper()} (*.{ext})")
            if not path:
                return
            try:
                out = bommod.export_csv(rep, path) if kind == "csv" else bommod.export_xlsx(rep, path, self.project.name)
            except Exception as exc:  # noqa: BLE001 - mostra ao usuário
                self.console.log("error", f"Falha ao exportar BOM: {exc}")
                QMessageBox.critical(dlg, "Falha ao exportar", str(exc))
                return
            self.project.log("BOM exportada", out.name)
            self.console.log("ok", f"BOM exportada para {out}.")

        dlg.export_csv_btn.clicked.connect(lambda: _export("csv"))
        dlg.export_xlsx_btn.clicked.connect(lambda: _export("xlsx"))
        dlg.exec()

    # ============================================================== fadiga (V2.0)
    def _primary_name(self) -> str:
        cid = self.selection.primary
        node = self.project.components.find(cid) if cid else None
        return node.name if node is not None else ""

    def open_fatigue(self) -> None:
        self.central_tabs.setCurrentWidget(self.fatigue_tab)
        self.fatigue_tab.library = self.project.materials
        self.fatigue_tab.use_selected()

    # ============================================================== cinemática (V1.8)
    def open_kinematics(self) -> None:
        from interface.kinematics_dialog import KinematicsDialog
        from samples.mechanisms import build_mechanism
        if not self.project.components.leaves():
            self.console.log("warn", "Abra um modelo antes de animar.")
            return
        dlg = getattr(self, "_kin_dialog", None)
        if dlg is not None and dlg.isVisible():
            dlg.raise_()
            return
        mech = build_mechanism(self.project.components)
        if not mech.links:
            self.console.log("warn", "A animação existe só para os projetos predefinidos com mecanismo (motor 4 cilindros, carro F1 2026). Outros modelos não "
                                     "trazem mecanismo: o NEXUS não deduz movimento da geometria.")
            return
        self.mechanism = mech
        dlg = KinematicsDialog(mech, self)
        dlg.angleChanged.connect(self.set_kin_angle)
        dlg.closedByUser.connect(self.stop_kinematics)
        self._kin_dialog = dlg
        dlg.set_angle(self.kin_deg or 0.0)
        dlg.show()
        self.console.log("info", f"Animação: {len(mech.moving_ids)} peça(s) com movimento prescrito.")

    def set_kin_angle(self, deg: float) -> None:
        mech = getattr(self, "mechanism", None)
        if mech is None:
            return
        self.kin_deg = float(deg)
        self.scene.set_poses(mech.poses(deg), self.project.components)
        self.viewport.refresh()

    def stop_kinematics(self) -> None:
        self.kin_deg = None
        self.scene.set_poses({}, self.project.components)
        self.viewport.refresh()

    # ============================================================== juntas inferidas
    def find_joints(self):
        from modules.joint_finder import JointFinder
        return JointFinder(self.project.components).find()

    def show_joints(self) -> None:
        if not self.project.components.leaves():
            self.console.log("warn", "Não há peças para analisar.")
            return
        from modules import joint_finder
        rep = self.find_joints()
        self.console.log("info", rep.summary())
        dlg = JointsDialog(rep, self)

        def _select() -> None:
            r = dlg.table.currentRow()
            if 0 <= r < len(rep.joints):
                j = rep.joints[r]
                self.selection.select([i for i in (j.a_id, j.b_id) if i], source="api")

        def _export() -> None:
            path, _ = QFileDialog.getSaveFileName(dlg, "Exportar juntas", f"exports/{self.project.name}_juntas.csv", "CSV (*.csv)")
            if path:
                out = joint_finder.export_csv(rep, path)
                self.console.log("ok", f"Juntas exportadas para {out}.")

        dlg.table.cellDoubleClicked.connect(lambda *_: _select())
        dlg.export_btn.clicked.connect(_export)
        dlg.exec()

    # ============================================================== relatório PDF
    def export_report(self, path: str, detail_parts: bool = True, show_progress: bool = False) -> Optional[Path]:
        if not self.project.components.leaves():
            self.console.log("warn", "Não há peças para o relatório.")
            return None
        from modules.report import ReportBuilder
        dlg = None
        if show_progress:
            from PySide6.QtWidgets import QProgressDialog
            dlg = QProgressDialog("Gerando relatório…", None, 0, 100, self)
            dlg.setWindowModality(Qt.WindowModal)
            dlg.setMinimumDuration(0)

        def prog(i: int, n: int, msg: str) -> None:
            if dlg is not None:
                dlg.setValue(int(100 * i / max(n, 1)))
                dlg.setLabelText(f"Gerando relatório… {msg}")
                QApplication.processEvents()

        try:
            out = ReportBuilder(self.project, self.inspector, APP_VERSION).build(
                path, detail_parts=detail_parts, progress=prog)
        except Exception as exc:  # noqa: BLE001 - informa o usuário
            self.console.log("error", f"Falha ao gerar o relatório: {exc}")
            if show_progress:
                QMessageBox.critical(self, "Relatório PDF", str(exc))
            return None
        finally:
            if dlg is not None:
                dlg.close()
        self.project.log("Relatório PDF", out.name)
        self.console.log("ok", f"Relatório salvo em {out}.")
        self._update_title()
        return out

    def export_report_dialog(self) -> None:
        if not self.project.components.leaves():
            self.console.log("warn", "Não há peças para o relatório.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Relatório PDF", f"exports/{self.project.name}_relatorio.pdf",
                                              "PDF (*.pdf)")
        if not path:
            return
        n = len(list(self.project.components.leaves()))
        detail = QMessageBox.question(
            self, "Relatório PDF", f"Incluir uma ficha para cada um dos {n} componentes?\n"
            "(Não = só capa, BOM e cenas — bem mais rápido.)",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes) == QMessageBox.Yes
        self.export_report(path, detail, show_progress=True)

    # ============================================================== cenas salvas
    def _fill_scenes_menu(self) -> None:
        m = self.scenes_menu
        m.clear()
        m.addAction(self.actions_by_key["scene_save"])
        m.addAction(self.actions_by_key["scene_manage"])
        names = self.project.scenes.names()
        if names:
            m.addSeparator()
        for i, n in enumerate(names):
            act = m.addAction(f"{i + 1}. {n}" if i < 9 else n)
            act.triggered.connect(lambda _=False, name=n: self.apply_scene(name))

    def capture_scene(self, name: str) -> "Scene":
        import numpy as np
        from modules.scene_manager import Scene
        cam = self.scene.renderer.GetActiveCamera()
        comps = self.project.components
        bar = self.section_bar
        return Scene(
            name=name,
            camera={"position": list(cam.GetPosition()), "focal": list(cam.GetFocalPoint()),
                    "up": list(cam.GetViewUp()), "scale": cam.GetParallelScale(),
                    "parallel": bool(cam.GetParallelProjection())},
            offsets={n.id: [float(x) for x in n.offset] for n in comps.root.walk()
                     if any(abs(float(x)) > 1e-9 for x in n.offset)},
            hidden=[n.id for n in comps.root.walk() if not n.visible],
            section={"axis": bar.axis, "fraction": bar.fraction, "flip": bar.flip} if bar.enabled else None,
            holo=bool(self.scene.holo), edges=bool(self.scene.edges_visible),
            selection=list(self.selection.selected),
            poses={k: [float(x) for x in m.reshape(-1)] for k, m in self.scene.poses.items()
                   if not np.allclose(m, np.eye(4))},
            kin_deg=self.kin_deg)

    def save_scene(self, name: str, replace: bool = False) -> "Scene":
        sc = self.project.scenes.add(self.capture_scene(name), replace=replace)
        self.project.log("Cena salva", sc.name)
        self.console.log("ok", f"Cena '{sc.name}' salva.")
        self._update_title()
        return sc

    def save_scene_dialog(self):
        if not self.scene.parts:
            self.console.log("warn", "Abra um modelo antes de salvar uma cena.")
            return None
        name, ok = QInputDialog.getText(self, "Salvar cena", "Nome da cena:",
                                        text=f"Cena {len(self.project.scenes) + 1}")
        if not ok or not name.strip():
            return None
        replace = False
        if self.project.scenes.get(name.strip()):
            if QMessageBox.question(self, "Cena existente", f"Substituir a cena '{name.strip()}'?",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
                return None
            replace = True
        return self.save_scene(name, replace).name

    def rename_scene_dialog(self, old: str):
        new, ok = QInputDialog.getText(self, "Renomear cena", "Novo nome:", text=old)
        if not ok or not new.strip():
            return None
        try:
            self.project.scenes.rename(old, new)
        except ValueError as exc:
            self.console.log("error", str(exc))
            return None
        self.project.log("Cena renomeada", f"{old} → {new.strip()}")
        self._update_title()
        return new.strip()

    def delete_scene(self, name: str) -> None:
        if self.project.scenes.remove(name):
            self.project.log("Cena excluída", name)
            self.console.log("info", f"Cena '{name}' excluída.")
            self._update_title()

    def apply_scene(self, name: str) -> int:
        """Aplica a cena; devolve quantos ids guardados não existem mais (ignorados)."""
        import numpy as np
        sc = self.project.scenes.get(name)
        if sc is None:
            self.console.log("error", f"Cena '{name}' não encontrada.")
            return -1
        comps = self.project.components
        missing = 0
        # visibilidade
        hidden = set(sc.hidden)
        for n in comps.root.walk():
            n.visible = n.id not in hidden
        missing += sum(1 for i in hidden if comps.find(i) is None)
        # corte e estilo
        bar = self.section_bar
        for w in (bar.enable_check, bar.axis_combo, bar.slider, bar.flip_check, bar.holo_check):
            w.blockSignals(True)
        bar.enable_check.setChecked(sc.section is not None)
        if sc.section:
            bar.axis_combo.setCurrentIndex(int(sc.section["axis"]))
            bar.slider.setValue(int(round(float(sc.section["fraction"]) * 1000)))
            bar.pos_label.setText(f"{bar.slider.value() / 10:.0f}%")
            bar.flip_check.setChecked(bool(sc.section.get("flip", False)))
        bar.holo_check.setChecked(sc.holo)
        for w in (bar.enable_check, bar.axis_combo, bar.slider, bar.flip_check, bar.holo_check):
            w.blockSignals(False)
        self.scene.set_holo(sc.holo)
        self.scene.set_edges_visible(sc.edges, comps)
        self.scene.sync_visibility(comps)
        self._apply_section()
        # explosão: alvo = offsets da cena; peças não citadas voltam a zero
        target = {n.id: np.zeros(3) for n in comps.root.walk()}
        for cid, off in sc.offsets.items():
            if cid in target:
                target[cid] = np.asarray(off, dtype=float)
            else:
                missing += 1
        # câmera
        cam = self.scene.renderer.GetActiveCamera()
        c = sc.camera
        if c:
            cam.SetParallelProjection(bool(c.get("parallel", False)))
            cam.SetPosition(*c["position"])
            cam.SetFocalPoint(*c["focal"])
            cam.SetViewUp(*c["up"])
            if c.get("parallel"):
                cam.SetParallelScale(float(c["scale"]))
            self.scene.renderer.ResetCameraClippingRange()
        if self.actions_by_key.get("perspective"):
            with QSignalBlocker(self.actions_by_key["perspective"]):
                self.actions_by_key["perspective"].setChecked(not bool(c.get("parallel", False)) if c else True)
        ids = [i for i in sc.selection if comps.find(i) is not None]
        self.selection.select(ids, source="api") if ids else self.selection.clear("api")
        self.panel.refresh_states()
        poses = {k: np.asarray(v, dtype=float).reshape(4, 4) for k, v in (sc.poses or {}).items() if comps.find(k) is not None}
        mech = getattr(self, "mechanism", None)
        dlg = getattr(self, "_kin_dialog", None)
        if poses:
            self.kin_deg = sc.kin_deg
            self.scene.set_poses(poses, comps)
            if dlg is not None and dlg.isVisible() and sc.kin_deg is not None:
                dlg.set_angle(sc.kin_deg, emit=False)
        elif self.scene.poses:
            self.scene.set_poses({}, comps)
            self.kin_deg = None
            if dlg is not None and dlg.isVisible():
                dlg.set_angle(0.0, emit=False)
        self._animate_to(target, f"Cena '{name}'")
        if missing:
            self.console.log("warn", f"Cena '{name}': {missing} item(ns) guardado(s) não existem mais e foram ignorados.")
        else:
            self.console.log("ok", f"Cena '{name}' aplicada.")
        self.viewport.refresh()
        return missing

    def show_history(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Histórico de alterações")
        dlg.resize(760, 420)
        lay = QVBoxLayout(dlg)
        table = QTableWidget(0, 3)
        table.setHorizontalHeaderLabels(["Data/hora", "Ação", "Detalhe"])
        table.horizontalHeader().setStretchLastSection(True)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        for entry in reversed(self.project.history.entries):
            row = table.rowCount()
            table.insertRow(row)
            for col, text in enumerate((entry.timestamp.replace("T", " "), entry.action, entry.detail)):
                table.setItem(row, col, QTableWidgetItem(text))
        table.resizeColumnToContents(0)
        table.resizeColumnToContents(1)
        lay.addWidget(table)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dlg.reject)
        lay.addWidget(buttons)
        dlg.exec()

    # ============================================================ montagem
    def identify_solids(self) -> None:
        root = self.project.components.root
        if root is None:
            self.console.log("warn", "Não há modelo carregado.")
            return
        report = analyze_tree(root, self.engine)
        self.console.log("ok", "Estrutura identificada: " + report.summary() + ".")
        for cid in report.multi_solid:
            self.console.log("info", f"Composto: '{self.project.components.get(cid).name}' "
                                     f"({self.project.components.get(cid).geometry_kind.label}).")
        if report.has_splittable:
            self.selection.select(report.multi_solid, source="menu")
        self.panel.refresh_states()
        self._refresh_inspector()

    def split_composites(self, ids: Optional[list[str]] = None) -> None:
        """Separa os objetos compostos (selecionados ou, sem ids, todos os que podem ser separados)."""
        comps = self.project.components
        if comps.root is None:
            self.console.log("warn", "Não há modelo carregado.")
            return
        if ids is None:
            targets = [n for n in comps.root.walk() if can_split(n)]
        else:
            targets = [n for i in ids if (n := comps.find(i)) is not None and can_split(n)]
        if not targets:
            self.console.log("warn", "Nenhum objeto composto para separar.")
            return
        created = 0
        for node in targets:
            created += len(split_into_solids(node, self.engine, self.project.ids))
        comps.reindex()
        self.inspector.clear_cache()
        self.project.log("Sólidos separados", f"{len(targets)} objeto(s) → {created} componente(s)")
        self.console.log("ok", f"{len(targets)} objeto(s) separado(s) em {created} componente(s) individuais.")
        self._structure_changed()

    def undo_split_selected(self) -> None:
        nodes = [n for n in self._selected_nodes() if n.split_backup is not None]
        if not nodes:
            self.console.log("warn", "Selecione um objeto separado para desfazer a separação.")
            return
        for n in nodes:
            undo_split(n)
        self.project.components.reindex()
        self.inspector.clear_cache()
        self.project.log("Separação desfeita", ", ".join(n.name for n in nodes))
        self.console.log("ok", f"Separação desfeita em {len(nodes)} objeto(s).")
        self._structure_changed()

    def _structure_changed(self) -> None:
        """A árvore mudou (separar/agrupar): reconstrói cena e painéis mantendo a câmera."""
        self.selection.prune(self.project.components.ids_set(), source="api")
        self._rebuild_scene(fit=False)
        self.panel.populate(self.project)
        self._update_title()
        self._update_state_labels()
        self._refresh_inspector()

    def group_selected(self) -> None:
        ids = self.selection.selected
        if len(ids) < 2:
            self.console.log("warn", "Selecione ao menos dois componentes para agrupar.")
            return
        name, ok = QInputDialog.getText(self, "Agrupar", "Nome do grupo:", text="Novo grupo")
        if not ok:
            return
        try:
            group = self.project.assembly.group_components(ids, name)
        except ValueError as exc:
            self.console.log("error", str(exc))
            QMessageBox.warning(self, "Não foi possível agrupar", str(exc))
            return
        self.project.log("Grupo criado", f"{group.name} ({len(group.children)} componentes)")
        self.console.log("ok", f"Grupo '{group.name}' criado com {len(group.children)} componente(s).")
        self.panel.populate(self.project)
        self.selection.select(group.id, source="api")
        self._update_title()

    def ungroup_selected(self) -> None:
        nodes = [n for n in self._selected_nodes() if n.children and not n.has_geometry and n.parent is not None]
        if not nodes:
            self.console.log("warn", "Selecione um grupo para desagrupar.")
            return
        try:
            for n in nodes:
                self.project.assembly.ungroup(n.id)
        except ValueError as exc:
            self.console.log("error", str(exc))
            QMessageBox.warning(self, "Não foi possível desagrupar", str(exc))
            return
        self.project.log("Desagrupado", ", ".join(n.name for n in nodes))
        self.selection.clear("api")
        self.panel.populate(self.project)
        self._update_title()

    # ============================================================== explosão
    def _animate_to(self, target: dict, label: str) -> None:
        asm = self.project.assembly
        self._anim_label = label
        if self.animator.running:
            self.animator.stop()
        if self.explode_bar.animate and self.scene.parts:
            self.animator.start(asm.current_offsets(), target, int(self.config.get("animation_ms", 900)))
            return
        asm.apply_offsets(target)
        self._on_anim_finished()

    def _on_anim_frame(self, offsets: dict) -> None:
        self.project.assembly.apply_offsets(offsets)
        self.scene.sync_offsets(self.project.components)
        self.viewport.refresh()

    def _on_anim_finished(self) -> None:
        self.scene.sync_offsets(self.project.components)
        self.panel.refresh_states()
        self._update_state_labels()
        self._refresh_inspector()
        self.viewport.refresh()
        if self._anim_label:
            self.project.log("Explosão", self._anim_label)
            self.console.log("ok", self._anim_label)
            self._anim_label = ""
        self._update_title()

    def _describe(self, what: str) -> str:
        p = self.explode_bar.params()
        mode = self.explode_bar.mode_combo.currentText()
        return f"{what} — {mode}, distância {p.factor:.2f}×"

    def explode_all(self) -> None:
        try:
            target = self.project.assembly.target_explode_all(self.explode_bar.params())
        except ValueError as exc:
            self.console.log("error", str(exc))
            return
        if not self.project.components.leaves():
            self.console.log("warn", "Não há peças para explodir.")
            return
        self._last_explode = ("all", [])
        self._animate_to(target, self._describe("Montagem explodida"))

    def explode_group(self) -> None:
        groups = [n for n in self._selected_nodes() if n.children]
        if not groups:
            self.console.log("warn", "Selecione um grupo ou montagem (na árvore) para explodir.")
            return
        try:
            target = self.project.assembly.target_explode_group(groups[0].id, self.explode_bar.params())
        except ValueError as exc:
            self.console.log("error", str(exc))
            return
        self._last_explode = ("group", [groups[0].id])
        self._animate_to(target, self._describe(f"Grupo '{groups[0].name}' explodido"))

    def separate_part(self) -> None:
        parts = [n for n in self._selected_nodes() if n.parent is not None]
        if not parts:
            self.console.log("warn", "Selecione uma peça para separar.")
            return
        try:
            target = self.project.assembly.target_separate_part(parts[0].id, self.explode_bar.params())
            for extra in parts[1:]:
                t = self.project.assembly.target_separate_part(extra.id, self.explode_bar.params())
                target[extra.id] = t[extra.id]
        except ValueError as exc:
            self.console.log("error", str(exc))
            return
        self._last_explode = ("part", [p.id for p in parts])
        names = ", ".join(p.name for p in parts[:3]) + ("…" if len(parts) > 3 else "")
        self._animate_to(target, self._describe(f"Peça separada: {names}"))

    def restore_assembly(self) -> None:
        self._last_explode = None
        if not self.project.assembly.is_exploded():
            self.console.log("info", "A montagem já está na posição original.")
            return
        self._animate_to(self.project.assembly.target_restore(), "Montagem restaurada à posição original")

    def _on_explode_params_changed(self) -> None:
        """Ajuste ao vivo: mexer na distância/direção reaplica a última explosão sem animar."""
        if self._last_explode is None or self.animator.running or not hasattr(self, "project"):
            return
        kind, ids = self._last_explode
        asm, params = self.project.assembly, self.explode_bar.params()
        try:
            if kind == "all":
                target = asm.target_explode_all(params)
            elif kind == "group":
                target = asm.target_explode_group(ids[0], params)
            else:
                target = asm.target_separate_part(ids[0], params)
                for extra in ids[1:]:
                    target[extra] = asm.target_separate_part(extra, params)[extra]
        except (ValueError, KeyError):
            return
        asm.apply_offsets(target)
        self.scene.sync_offsets(self.project.components)
        self.panel.refresh_states()
        self._update_state_labels()
        self.viewport.refresh()

    # ====================================================== painel de componentes
    def _on_panel_action(self, action: str, ids: list[str]) -> None:
        if ids and ids != self.selection.selected:
            self.selection.select(ids, source="api")
        handlers = {
            "hide": self.hide_selected, "show": self.show_selected, "isolate": self.isolate_selected,
            "show_all": self.show_all, "explode_group": self.explode_group,
            "separate_part": self.separate_part, "split": lambda: self.split_composites(ids),
            "undo_split": self.undo_split_selected, "group": self.group_selected,
            "ungroup": self.ungroup_selected, "material": self.assign_material,
            "rename": self.rename_selected, "fit_selection": self.fit_selection,
        }
        handlers[action]()

    # ================================================================ análise
    def toggle_visibility_dock(self) -> None:
        self.dock_right.setVisible(not self.dock_right.isVisible())

    def show_stats(self) -> None:
        comps = self.project.components
        if comps.root is None:
            self.console.log("warn", "Não há modelo carregado.")
            return
        c = comps.counts()
        box = comps.bbox(comps.root)
        size = "—" if box is None else " × ".join(f"{v:,.1f}".replace(",", " ") for v in box.size) + " mm"
        report = analyze_tree(comps.root, self.engine)
        self.console.log("info", f"Projeto '{self.project.name}': {c['parts']} peça(s), {c['groups']} grupo(s), "
                                 f"{c['hidden']} oculto(s). Caixa total: {size}.")
        self.console.log("info", report.summary() + ".")

    def measure_selected(self) -> None:
        nodes = self._selected_nodes()
        if len(nodes) != 2:
            self.console.log("warn", "Para medir, selecione exatamente duas peças (Shift+clique no 3D ou Ctrl+clique na árvore).")
            return
        try:
            result = MeasureEngine(self.project.components).measure(nodes[0], nodes[1])
        except ValueError as exc:
            self.console.log("warn", str(exc))
            return
        self.last_measurement = result
        level = "ok" if result.min_distance is not None else "error"
        self.console.log(level, result.summary())
        if result.original_min_distance is not None:
            self.console.log("info", f"Na montagem original: {result.original_min_distance:.3f} mm.".replace(".", ","))
        if result.delta is not None:
            dx, dy, dz = result.delta
            self.console.log("info", f"Deslocamento entre centros: X {dx:.2f}  Y {dy:.2f}  Z {dz:.2f} mm".replace(".", ","))
        for note in result.notes:
            self.console.log("warn", note)
        if result.point_a is not None and result.min_distance:
            self.scene.set_measure_line(result.point_a, result.point_b)
            self.viewport.refresh()
        self.project.log("Medição", result.summary(), dirty=False)

    def measure_angle(self) -> None:
        nodes = self._selected_nodes()
        if len(nodes) != 2:
            self.console.log("warn", "Para medir o ângulo, selecione exatamente duas peças.")
            return
        try:
            res = MeasureEngine(self.project.components).angle(nodes[0], nodes[1])
        except ValueError as exc:
            self.console.log("warn", str(exc))
            return
        self.last_angle = res
        self.console.log("ok" if res.angle_deg is not None else "error", res.summary())
        for note in res.notes:
            self.console.log("warn", note)
        self.project.log("Medição de ângulo", res.summary(), dirty=False)
        self._update_hud()

    def list_diameters(self) -> None:
        node = self.project.components.find(self.selection.primary) if self.selection.primary else None
        if node is None or not node.has_geometry:
            self.console.log("warn", "Selecione uma peça para listar seus diâmetros.")
            return
        diams = MeasureEngine(self.project.components).diameters(node)
        if not diams:
            self.console.log("info", f"'{node.name}' não tem superfícies cilíndricas exatas (nenhum diâmetro).")
            return
        for d in diams:
            self.console.log("ok", f"{node.name}: Ø {d.diameter:.3f} mm, eixo {axis_label(d.axis)}.".replace(".", ","))

    # ---------------------------------------------------------- corte / holograma
    def _apply_section(self) -> None:
        bar = self.section_bar
        if not bar.enabled or not self.scene.parts:
            self.scene.set_section(None)
        else:
            rng = self.scene.section_range(bar.axis)
            if rng is None:
                return
            pos = rng[0] + (rng[1] - rng[0]) * bar.fraction
            self.scene.set_section(bar.axis, pos, bar.flip)
        self._update_hud()
        self.viewport.refresh()

    def set_holo(self, on: bool) -> None:
        self.scene.set_holo(on)
        self._update_hud()
        self.viewport.refresh()

    # ------------------------------------------------------------------- HUD
    def _update_hud(self) -> None:
        comps = self.project.components
        c = comps.counts()
        sel = self.selection.selected
        node = comps.find(self.selection.primary) if self.selection.primary else None
        lines = [f"NEXUS // BANCADA  v{APP_VERSION}",
                 f"PROJETO  {self.project.name}",
                 f"PECAS    {c['parts']}   OCULTAS {c['hidden']}",
                 "ESTADO   " + ("EXPLODIDA" if comps.displaced_ids() else "MONTADA")]
        if sel:
            lines.append("SELECAO  " + (node.name if node else "?") + (f" (+{len(sel) - 1})" if len(sel) > 1 else ""))
        sec = self.scene.section
        if sec:
            lines.append(f"CORTE    plano {'XYZ'[sec[0]]} = {sec[1]:.1f} mm")
        if self.last_measurement is not None and self.last_measurement.min_distance is not None and self.scene.has_measure_line:
            lines.append(f"DIST     {self.last_measurement.min_distance:.2f} mm")
        self.scene.set_hud([ln for ln in lines])

    def clear_measurement(self) -> None:
        self.scene.clear_measure_line()
        self.viewport.refresh()

    # ================================================================== ajuda
    def show_environment(self) -> None:
        env = environment_report(self.config.get("freecad_path"))
        lines = [f"Python: {env['python']}", f"Sistema: {env['platform']}",
                 f"OpenCascade (cadquery-ocp): {env['cadquery-ocp'] or 'NÃO INSTALADO'}",
                 f"PySide6: {env['PySide6']}", f"VTK: {env['vtk']}", f"NumPy: {env['numpy']}",
                 f"trimesh: {env['trimesh']}",
                 f"FreeCAD detectado: {env['freecad'] or 'não (não é necessário na V1.0)'}"]
        QMessageBox.information(self, "Ambiente", "\n".join(lines))

    def show_about(self) -> None:
        QMessageBox.about(
            self, f"Sobre o {APP_NAME}",
            f"<b>{APP_NAME}</b> v{APP_VERSION}<br>Laboratório digital de engenharia: importação, "
            "desmontagem virtual e inspeção de projetos CAD.<br><br>"
            f"Motor CAD: {self.engine.backend_name}.<br>Simulação, edição paramétrica e IA são etapas "
            "futuras e aparecem desabilitadas nos menus.")

    def show_quick_guide(self) -> None:
        QMessageBox.information(
            self, "Guia rápido",
            "Mouse no 3D:\n"
            "  • Botão esquerdo (arrastar): girar     • Roda / botão direito: zoom\n"
            "  • Botão do meio ou Shift+esquerdo: mover a câmera\n"
            "  • Clique: selecionar peça   • Shift+clique: somar à seleção   • Clique no vazio: limpar\n\n"
            "Atalhos: Ctrl+I importar · Ctrl+O abrir · Ctrl+S salvar · Ctrl+E explodir · Ctrl+R restaurar\n"
            "Ctrl+H ocultar · Ctrl+Shift+I isolar · Ctrl+Alt+H mostrar tudo · Home ajustar vista\n"
            "Ctrl+1…6 vistas · Ctrl+0 isométrica · Ctrl+P perspectiva/ortográfica")

    # ============================================================== fechamento
    def closeEvent(self, event) -> None:
        if not self._maybe_save():
            event.ignore()
            return
        self.animator.stop()
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(3000)
        self.viewport.shutdown()
        event.accept()
