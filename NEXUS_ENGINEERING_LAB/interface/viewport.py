"""Visualização 3D (VTK) e animação da explosão.

Duas camadas, para poder testar a lógica sem abrir janela:

* :class:`SceneController` — só VTK. Converte componentes em atores, aplica
  deslocamentos de explosão, visibilidade, destaque, vistas e seleção por raio.
* :class:`Viewport` — widget Qt que hospeda o VTK, captura cliques (diferenciando
  clique de arrastar) e emite sinais.

A explosão move o ATOR (``SetPosition``); a malha/geometria nunca é alterada.
"""
from __future__ import annotations

from typing import Callable, Iterable, Optional

import numpy as np
from PySide6.QtCore import QElapsedTimer, QObject, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QVBoxLayout, QWidget
from vtkmodules.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray
import vtkmodules.vtkInteractionStyle  # noqa: F401  (registra estilos de interação)
import vtkmodules.vtkRenderingOpenGL2  # noqa: F401  (registra o backend OpenGL)
from vtkmodules.vtkCommonCore import vtkPoints
from vtkmodules.vtkCommonMath import vtkMatrix4x4
from vtkmodules.vtkCommonDataModel import vtkCellArray, vtkPolyData
from vtkmodules.vtkFiltersCore import vtkFeatureEdges, vtkPolyDataNormals
from vtkmodules.vtkInteractionStyle import vtkInteractorStyleTrackballCamera
from vtkmodules.vtkInteractionWidgets import vtkOrientationMarkerWidget
from vtkmodules.vtkRenderingAnnotation import vtkAxesActor
from vtkmodules.vtkFiltersSources import vtkLineSource, vtkSphereSource
from vtkmodules.vtkCommonDataModel import vtkPlane
from vtkmodules.vtkRenderingCore import vtkActor2D, vtkPolyDataMapper2D, vtkProperty, vtkTextActor
from vtkmodules.vtkRenderingCore import vtkActor, vtkCellPicker, vtkPolyDataMapper, vtkRenderer

from core.component_manager import ComponentManager
from core.geometry import BoundingBox
from core.model import MeshData
from interface import styles
from modules.explode_engine import interpolate_offsets

# direção (do foco para a câmera) e "para cima" de cada vista. Convenção CAD: Z para cima.
STANDARD_VIEWS: dict[str, tuple[tuple[float, float, float], tuple[float, float, float]]] = {
    "front": ((0, -1, 0), (0, 0, 1)),
    "back": ((0, 1, 0), (0, 0, 1)),
    "left": ((-1, 0, 0), (0, 0, 1)),
    "right": ((1, 0, 0), (0, 0, 1)),
    "top": ((0, 0, 1), (0, 1, 0)),
    "bottom": ((0, 0, -1), (0, -1, 0)),
    "iso": ((1, -1, 0.85), (0, 0, 1)),
}
VIEW_LABELS = {"front": "Frontal", "back": "Posterior", "left": "Esquerda", "right": "Direita",
               "top": "Superior", "bottom": "Inferior", "iso": "Isométrica"}


def mesh_to_polydata(mesh: MeshData) -> vtkPolyData:
    """MeshData (NumPy) -> vtkPolyData, com normais."""
    pts = vtkPoints()
    pts.SetData(numpy_to_vtk(np.ascontiguousarray(mesh.vertices), deep=True))
    n = len(mesh.faces)
    cells = np.hstack([np.full((n, 1), 3, dtype=np.int64), mesh.faces]).ravel()
    ca = vtkCellArray()
    ca.SetCells(n, numpy_to_vtkIdTypeArray(cells, deep=True))
    pd = vtkPolyData()
    pd.SetPoints(pts)
    pd.SetPolys(ca)
    if mesh.normals is not None and len(mesh.normals) == len(mesh.vertices):
        pd.GetPointData().SetNormals(numpy_to_vtk(np.ascontiguousarray(mesh.normals), deep=True))
        return pd
    # malhas sem normais (STL/OBJ): suaviza só onde o ângulo é suave, preservando quinas
    gen = vtkPolyDataNormals()
    gen.SetInputData(pd)
    gen.SplittingOn()
    gen.SetFeatureAngle(40.0)
    gen.ConsistencyOn()
    gen.AutoOrientNormalsOff()
    gen.Update()
    out = vtkPolyData()
    out.DeepCopy(gen.GetOutput())
    return out


class _PartActors:
    __slots__ = ("body", "edges", "base_color", "opacity")

    def __init__(self, body: vtkActor, edges: vtkActor, base_color: tuple[float, float, float], opacity: float = 1.0) -> None:
        self.body, self.edges, self.base_color, self.opacity = body, edges, base_color, opacity


class SceneController:
    """Lógica da cena 3D, independente de Qt."""

    EDGE_COLOR = (0.035, 0.05, 0.075)
    EDGE_SELECTED = (0.75, 0.92, 1.0)

    def __init__(self, renderer: Optional[vtkRenderer] = None) -> None:
        self.renderer = renderer or vtkRenderer()
        self.renderer.GradientBackgroundOn()
        self.renderer.SetBackground(*styles.VIEWPORT_BOTTOM)
        self.renderer.SetBackground2(*styles.VIEWPORT_TOP)
        self.parts: dict[str, _PartActors] = {}
        self.poses: dict[str, np.ndarray] = {}          # cinemática (V1.8): id -> matriz 4x4 de exibição (mundo)
        self._actor_ids: dict[vtkActor, str] = {}
        self._highlight: set[str] = set()
        self.edges_visible = True
        self._measure_actors: list[vtkActor] = []
        self.holo = True
        self.project_key: Optional[str] = None   # chave do projeto predefinido (para a aparência visual); None = genérico
        self._floor: Optional[vtkActor] = None
        self._section: Optional[tuple[int, float, bool]] = None
        self._hud_size = (0, 0)
        self._hud_lines: list[str] = []
        self._hud_frame = vtkActor2D()
        self._hud_text = vtkTextActor()
        self._init_hud()
        self._picker = vtkCellPicker()
        self._picker.SetTolerance(0.0008)
        self.renderer.GetActiveCamera().SetParallelProjection(False)

    # ------------------------------------------------------------------ cena
    def clear(self) -> None:
        for pa in self.parts.values():
            self.renderer.RemoveActor(pa.body)
            self.renderer.RemoveActor(pa.edges)
        self.clear_measure_line()
        self.parts.clear()
        self.poses = {}
        self._actor_ids.clear()
        self._highlight.clear()

    def build(self, components: ComponentManager,
              progress: Optional[Callable[[int, int, str], None]] = None) -> list[str]:
        """Cria os atores de todas as peças. Devolve mensagens de peças que falharam."""
        self.clear()
        leaves = components.leaves()
        failures: list[str] = []
        for i, comp in enumerate(leaves):
            if progress:
                progress(i, len(leaves), comp.name)
            try:
                mesh = components.render_mesh(comp)
                self._add_part(comp.id, mesh, i, comp.name)
            except Exception as exc:  # peça sem faces (ex.: só arestas) não derruba o projeto
                failures.append(f"{comp.name}: {exc}")
        if progress:
            progress(len(leaves), len(leaves), "")
        self.sync_visibility(components)
        self.sync_offsets(components)
        self._update_floor()
        if self._section is not None:
            self.set_section(*self._section)
        return failures

    def _add_part(self, comp_id: str, mesh: MeshData, index: int, name: str = "") -> None:
        poly = mesh_to_polydata(mesh)
        mapper = vtkPolyDataMapper()
        mapper.SetInputData(poly)
        mapper.ScalarVisibilityOff()
        mapper.SetResolveCoincidentTopologyToPolygonOffset()
        body = vtkActor()
        body.SetMapper(mapper)
        color = styles.PART_COLORS[index % len(styles.PART_COLORS)]
        prop = body.GetProperty()
        opacity = 1.0
        if name:
            # aparência VISUAL realista por tipo de peça (não é material de engenharia; ver modules/appearance.py)
            from modules.appearance import appearance
            hx, metal, rough, opacity = appearance(self.project_key or "", name)
            color = tuple(int(hx[k:k + 2], 16) / 255.0 for k in (1, 3, 5))
            prop.SetSpecular(0.25 + 0.55 * metal)
            prop.SetSpecularPower(14 + 90 * (1.0 - rough))
            prop.SetSpecularColor(*(tuple(0.6 + 0.4 * c for c in color) if metal > 0.5 else (1.0, 1.0, 1.0)))
        else:
            prop.SetSpecular(0.3)
            prop.SetSpecularPower(28)
        prop.SetColor(*color)
        prop.SetAmbient(0.22)
        prop.SetDiffuse(0.8)

        feat = vtkFeatureEdges()
        feat.SetInputData(poly)
        feat.BoundaryEdgesOn()
        feat.FeatureEdgesOn()
        feat.SetFeatureAngle(35.0)
        feat.NonManifoldEdgesOff()
        feat.ManifoldEdgesOff()
        feat.ColoringOff()
        edge_mapper = vtkPolyDataMapper()
        edge_mapper.SetInputConnection(feat.GetOutputPort())
        edge_mapper.ScalarVisibilityOff()
        edges = vtkActor()
        edges.SetMapper(edge_mapper)
        edges.GetProperty().SetColor(*self.EDGE_COLOR)
        edges.GetProperty().SetLineWidth(1.2)
        edges.GetProperty().LightingOff()
        edges.PickableOff()
        edges.SetVisibility(self.edges_visible)

        self.renderer.AddActor(body)
        self.renderer.AddActor(edges)
        self.parts[comp_id] = _PartActors(body, edges, color, opacity)
        self._actor_ids[body] = comp_id
        self._style(comp_id, False)

    # -------------------------------------------------- sincronização com o modelo
    def sync_visibility(self, components: ComponentManager) -> None:
        for cid, pa in self.parts.items():
            comp = components.find(cid)
            vis = bool(comp and components.is_effectively_visible(comp))
            pa.body.SetVisibility(vis)
            pa.edges.SetVisibility(vis and self.edges_visible)

    def sync_offsets(self, components: ComponentManager) -> None:
        for cid, pa in self.parts.items():
            comp = components.find(cid)
            if comp is None:
                continue
            self.place(cid, comp.effective_offset())

    def place(self, cid: str, offset, pose: Optional[np.ndarray] = None) -> None:
        """Posiciona o ator: deslocamento de explosão (e a pose cinemática, se houver). A malha não muda."""
        pa = self.parts.get(cid)
        if pa is None:
            return
        pose = self.poses.get(cid) if pose is None else pose
        if pose is None:
            for act in (pa.body, pa.edges):
                act.SetUserMatrix(None)
                act.SetPosition(*offset)
            return
        m = np.array(pose, dtype=float)
        m[:3, 3] += np.asarray(offset, dtype=float)       # T(offset)·pose
        vm = vtkMatrix4x4()
        for r in range(4):
            for c in range(4):
                vm.SetElement(r, c, float(m[r, c]))
        for act in (pa.body, pa.edges):
            act.SetPosition(0, 0, 0)
            act.SetUserMatrix(vm)

    def set_poses(self, poses: Optional[dict], components: ComponentManager) -> None:
        self.poses = dict(poses or {})
        self.sync_offsets(components)

    def set_edges_visible(self, visible: bool, components: ComponentManager) -> None:
        self.edges_visible = visible
        self.sync_visibility(components)

    # ------------------------------------------------------------------ destaque
    def set_measure_line(self, p1, p2, color=(1.0, 0.78, 0.2)) -> None:
        """Mostra o segmento de medição (e marcas nas pontas) sobre a cena."""
        self.clear_measure_line()
        p1, p2 = np.asarray(p1, float), np.asarray(p2, float)
        size = max(float(np.linalg.norm(p2 - p1)) * 0.02, 0.5)
        for src in (self._line_source(p1, p2), self._sphere_source(p1, size), self._sphere_source(p2, size)):
            mapper = vtkPolyDataMapper()
            mapper.SetInputConnection(src.GetOutputPort())
            actor = vtkActor()
            actor.SetMapper(mapper)
            actor.GetProperty().SetColor(*color)
            actor.GetProperty().SetLineWidth(2.5)
            actor.GetProperty().LightingOff()
            actor.PickableOff()
            self.renderer.AddActor(actor)
            self._measure_actors.append(actor)

    @staticmethod
    def _line_source(p1, p2):
        src = vtkLineSource()
        src.SetPoint1(*p1)
        src.SetPoint2(*p2)
        return src

    @staticmethod
    def _sphere_source(center, radius):
        src = vtkSphereSource()
        src.SetCenter(*center)
        src.SetRadius(radius)
        return src

    def clear_measure_line(self) -> None:
        for actor in self._measure_actors:
            self.renderer.RemoveActor(actor)
        self._measure_actors.clear()

    @property
    def has_measure_line(self) -> bool:
        return bool(self._measure_actors)

    @property
    def highlighted(self) -> set[str]:
        return set(self._highlight)

    def set_highlight(self, leaf_ids: Iterable[str]) -> None:
        new = {i for i in leaf_ids if i in self.parts}
        for cid in self._highlight - new:
            self._style(cid, False)
        for cid in new - self._highlight:
            self._style(cid, True)
        self._highlight = new

    def _style(self, cid: str, selected: bool) -> None:
        pa = self.parts[cid]
        prop = pa.body.GetProperty()
        eprop = pa.edges.GetProperty()
        if self.holo:
            prop.SetOpacity(0.78 if selected else 0.34)
            prop.SetColor(*(styles.HOLO_SELECTION if selected else styles.HOLO_COLOR))
            prop.SetAmbient(0.55 if selected else 0.45)
            eprop.SetColor(*((1.0, 0.88, 0.55) if selected else styles.HOLO_EDGE))
            eprop.SetLineWidth(2.4 if selected else 1.5)
            eprop.SetOpacity(1.0)
            return
        prop.SetOpacity(1.0 if selected else pa.opacity)
        if selected:
            prop.SetColor(*styles.SELECTION_COLOR)
            prop.SetAmbient(0.30)
            eprop.SetColor(*self.EDGE_SELECTED)
            eprop.SetLineWidth(2.0)
        else:
            prop.SetColor(*pa.base_color)
            prop.SetAmbient(0.22)
            eprop.SetColor(*self.EDGE_COLOR)
            eprop.SetLineWidth(1.2)

    def set_holo(self, on: bool) -> None:
        """Alterna o estilo holográfico (bancada) e o estilo sólido técnico."""
        self.holo = on
        for cid in self.parts:
            self._style(cid, cid in self._highlight)
        self._update_floor()

    # ------------------------------------------------------------- chão de bancada
    @staticmethod
    def _nice_step(extent: float) -> float:
        raw = extent / 12.0
        mag = 10 ** np.floor(np.log10(max(raw, 1e-9)))
        for m in (1, 2, 5, 10):
            if raw <= m * mag:
                return float(m * mag)
        return float(10 * mag)

    def _update_floor(self) -> None:
        if self._floor is not None:
            self.renderer.RemoveActor(self._floor)
            self._floor = None
        b = self._all_bounds()
        if not self.holo or b is None:
            return
        cx, cy = (b.min[0] + b.max[0]) / 2, (b.min[1] + b.max[1]) / 2
        half = max(b.size[0], b.size[1], b.size[2]) * 1.15
        step = self._nice_step(half * 2)
        n = int(np.ceil(half / step))
        z = float(b.min[2]) - step * 0.05
        pts, lines = vtkPoints(), vtkCellArray()

        def seg(p1, p2):
            i = pts.InsertNextPoint(*p1)
            pts.InsertNextPoint(*p2)
            lines.InsertNextCell(2, [i, i + 1])

        gx, gy = round(cx / step) * step, round(cy / step) * step
        for k in range(-n, n + 1):
            seg((gx + k * step, gy - n * step, z), (gx + k * step, gy + n * step, z))
            seg((gx - n * step, gy + k * step, z), (gx + n * step, gy + k * step, z))
        for r in (half * 0.55, half * 0.85, half * 1.1):          # anéis do projetor
            m = 96
            for j in range(m):
                a0, a1 = 2 * np.pi * j / m, 2 * np.pi * (j + 1) / m
                seg((cx + r * np.cos(a0), cy + r * np.sin(a0), z), (cx + r * np.cos(a1), cy + r * np.sin(a1), z))
        poly = vtkPolyData()
        poly.SetPoints(pts)
        poly.SetLines(lines)
        mapper = vtkPolyDataMapper()
        mapper.SetInputData(poly)
        actor = vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(*styles.HOLO_GRID)
        actor.GetProperty().SetOpacity(0.55)
        actor.GetProperty().SetLineWidth(1.0)
        actor.GetProperty().LightingOff()
        actor.PickableOff()
        self.renderer.AddActor(actor)
        self._floor = actor

    def _all_bounds(self) -> Optional[BoundingBox]:
        boxes = []
        for pa in self.parts.values():
            b = pa.body.GetBounds()
            if b[0] <= b[1]:
                boxes.append(BoundingBox(np.array([b[0], b[2], b[4]]), np.array([b[1], b[3], b[5]])))
        return BoundingBox.union(boxes) if boxes else None

    # ------------------------------------------------------------------ corte de seção
    def section_range(self, axis: int) -> Optional[tuple[float, float]]:
        b = self._all_bounds()
        return None if b is None else (float(b.min[axis]), float(b.max[axis]))

    def set_section(self, axis: Optional[int], position: float = 0.0, flip: bool = False) -> None:
        """Plano de corte alinhado a X/Y/Z (axis 0/1/2). ``None`` desliga. Só afeta a exibição."""
        self._section = None if axis is None else (axis, position, flip)
        for pa in self.parts.values():
            for actor in (pa.body, pa.edges):
                actor.GetMapper().RemoveAllClippingPlanes()
            if axis is None:
                pa.body.SetBackfaceProperty(None)
                continue
            plane = vtkPlane()
            normal = [0.0, 0.0, 0.0]
            normal[axis] = -1.0 if flip else 1.0
            plane.SetNormal(*normal)
            origin = [0.0, 0.0, 0.0]
            origin[axis] = position
            plane.SetOrigin(*origin)
            for actor in (pa.body, pa.edges):
                actor.GetMapper().AddClippingPlane(plane)
            back = vtkProperty()
            back.SetColor(1.0, 0.70, 0.18)
            back.SetAmbient(0.8)
            back.SetOpacity(0.9)
            pa.body.SetBackfaceProperty(back)

    @property
    def section(self) -> Optional[tuple[int, float, bool]]:
        return self._section

    # --------------------------------------------------------------------- HUD
    def _init_hud(self) -> None:
        self._hud_frame.GetProperty().SetColor(*styles.HUD_COLOR)
        self._hud_frame.GetProperty().SetLineWidth(2.0)
        self._hud_frame.GetProperty().SetOpacity(0.9)
        t = self._hud_text.GetTextProperty()
        t.SetFontFamilyToCourier()
        t.SetFontSize(14)
        t.SetColor(*styles.HUD_COLOR)
        t.SetLineSpacing(1.25)
        t.SetVerticalJustificationToTop()
        self._hud_text.SetPickable(False)
        self._hud_frame.SetPickable(False)
        self._hud_on = False
        self.set_hud_visible(True)

    def set_hud_visible(self, on: bool) -> None:
        if on == getattr(self, "_hud_on", False):
            return
        for prop in (self._hud_frame, self._hud_text):
            (self.renderer.AddViewProp if on else self.renderer.RemoveViewProp)(prop)
        self._hud_on = on

    def set_hud(self, lines: list[str]) -> None:
        self._hud_lines = list(lines)
        self._hud_text.SetInput("\n".join(self._hud_lines))

    @property
    def hud_lines(self) -> list[str]:
        return list(self._hud_lines)

    def layout_hud(self, w: int, h: int) -> None:
        """Cantos de mira e posição do texto, em pixels (refeito quando o tamanho muda)."""
        if (w, h) == self._hud_size or w < 40 or h < 40:
            return
        self._hud_size = (w, h)
        m, a = 14.0, min(w, h) * 0.06
        pts, lines = vtkPoints(), vtkCellArray()
        for (x, y, sx, sy) in ((m, m, 1, 1), (w - m, m, -1, 1), (m, h - m, 1, -1), (w - m, h - m, -1, -1)):
            i = pts.InsertNextPoint(x + sx * a, y, 0)
            pts.InsertNextPoint(x, y, 0)
            pts.InsertNextPoint(x, y + sy * a, 0)
            lines.InsertNextCell(3, [i, i + 1, i + 2])
        # cruz de mira central discreta
        cx, cy, c = w / 2, h / 2, 7.0
        for p1, p2 in (((cx - c, cy), (cx + c, cy)), ((cx, cy - c), (cx, cy + c))):
            i = pts.InsertNextPoint(*p1, 0)
            pts.InsertNextPoint(*p2, 0)
            lines.InsertNextCell(2, [i, i + 1])
        poly = vtkPolyData()
        poly.SetPoints(pts)
        poly.SetLines(lines)
        mapper = vtkPolyDataMapper2D()
        mapper.SetInputData(poly)
        self._hud_frame.SetMapper(mapper)
        self._hud_text.SetPosition(m + 12, h - m - 10)

    @property
    def bounds_box(self) -> Optional[BoundingBox]:
        return self._all_bounds()

    # --------------------------------------------------------------------- picking
    def pick(self, x: int, y: int) -> Optional[str]:
        """Peça sob o pixel (x, y) (origem embaixo, como o VTK) ou None."""
        if self._picker.Pick(x, y, 0, self.renderer):
            return self._actor_ids.get(self._picker.GetActor())
        return None

    def world_to_display(self, point: Iterable[float]) -> tuple[int, int]:
        """Projeta um ponto do mundo para pixels (origem embaixo, como o VTK)."""
        self.renderer.SetWorldPoint(*point, 1.0)
        self.renderer.WorldToDisplay()
        x, y, _ = self.renderer.GetDisplayPoint()
        return int(round(x)), int(round(y))

    def pick_at_world(self, point: Iterable[float]) -> Optional[str]:
        """Peça visível no pixel onde ``point`` aparece (mesmo caminho do clique do mouse)."""
        x, y = self.world_to_display(point)
        return self.pick(x, y)

    # ---------------------------------------------------------------------- câmera
    def visible_bounds(self) -> Optional[BoundingBox]:
        boxes = []
        for pa in self.parts.values():
            if pa.body.GetVisibility():
                b = pa.body.GetBounds()
                boxes.append(BoundingBox(np.array([b[0], b[2], b[4]]), np.array([b[1], b[3], b[5]])))
        return BoundingBox.union(boxes)

    def fit(self) -> None:
        b = self._all_bounds()          # só as peças: chão e HUD não entram no enquadramento
        if b is not None:
            self.renderer.ResetCamera(b.min[0], b.max[0], b.min[1], b.max[1], b.min[2], b.max[2])
        else:
            self.renderer.ResetCamera()
        self.renderer.ResetCameraClippingRange()

    def fit_to(self, leaf_ids: Iterable[str]) -> bool:
        """Enquadra a câmera nas peças dadas (na posição exibida). False se nenhuma existe."""
        boxes = []
        for cid in leaf_ids:
            pa = self.parts.get(cid)
            if pa is not None:
                b = pa.body.GetBounds()
                boxes.append(BoundingBox(np.array([b[0], b[2], b[4]]), np.array([b[1], b[3], b[5]])))
        union = BoundingBox.union(boxes)
        if union is None:
            return False
        self.renderer.ResetCamera(union.min[0], union.max[0], union.min[1], union.max[1],
                                  union.min[2], union.max[2])
        self.renderer.ResetCameraClippingRange()
        return True

    def set_view(self, name: str) -> None:
        if name not in STANDARD_VIEWS:
            raise ValueError(f"Vista desconhecida: {name}")
        direction, up = STANDARD_VIEWS[name]
        bounds = self.visible_bounds()
        center = bounds.center if bounds is not None else np.zeros(3)
        d = np.array(direction, dtype=float)
        d /= np.linalg.norm(d)
        cam = self.renderer.GetActiveCamera()
        cam.SetFocalPoint(*center)
        cam.SetPosition(*(center + d * max(1.0, (bounds.diagonal if bounds is not None else 100.0)) * 2.0))
        cam.SetViewUp(*up)
        cam.OrthogonalizeViewUp()
        self.fit()

    def set_perspective(self, perspective: bool) -> None:
        cam = self.renderer.GetActiveCamera()
        cam.SetParallelProjection(not perspective)
        self.fit()

    @property
    def is_perspective(self) -> bool:
        return not self.renderer.GetActiveCamera().GetParallelProjection()


class OffsetAnimator(QObject):
    """Anima os deslocamentos da explosão/restauração com suavização."""

    frame = Signal(dict)     # offsets intermediários {id: vetor}
    finished = Signal()

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self._clock = QElapsedTimer()
        self._start: dict[str, np.ndarray] = {}
        self._target: dict[str, np.ndarray] = {}
        self._duration = 1

    @property
    def running(self) -> bool:
        return self._timer.isActive()

    def start(self, start: dict[str, np.ndarray], target: dict[str, np.ndarray], duration_ms: int = 900) -> None:
        self.stop()
        self._start, self._target = start, target
        self._duration = max(1, int(duration_ms))
        self._clock.start()
        self._timer.start()

    def stop(self, jump_to_target: bool = False) -> None:
        if self._timer.isActive():
            self._timer.stop()
            if jump_to_target:
                self.frame.emit(dict(self._target))

    def _tick(self) -> None:
        t = self._clock.elapsed() / self._duration
        if t >= 1.0:
            self._timer.stop()
            self.frame.emit(dict(self._target))
            self.finished.emit()
            return
        self.frame.emit(interpolate_offsets(self._start, self._target, t))


# ---------------------------------------------------------------------- widget Qt
class Viewport(QWidget):
    """Widget 3D: câmera trackball (girar/zoom/pan), clique para selecionar."""

    pick_requested = Signal(object, bool)   # (id da peça ou None, aditivo?)

    CLICK_TOLERANCE_PX = 4

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        viewport = self

        class _Interactor(QVTKRenderWindowInteractor):
            """Diferencia clique de arrasto para não selecionar ao girar a câmera."""

            def paintEvent(self, ev):
                if QGuiApplication.platformName() == "offscreen":
                    return          # sem OpenGL real (testes/CI): não desenhar
                super().paintEvent(ev)

            def mousePressEvent(self, ev):
                self._press = (ev.position().x(), ev.position().y())
                super().mousePressEvent(ev)

            def mouseReleaseEvent(self, ev):
                super().mouseReleaseEvent(ev)
                from PySide6.QtCore import Qt
                if ev.button() != Qt.LeftButton or getattr(self, "_press", None) is None:
                    return
                dx = ev.position().x() - self._press[0]
                dy = ev.position().y() - self._press[1]
                self._press = None
                if (dx * dx + dy * dy) ** 0.5 <= viewport.CLICK_TOLERANCE_PX:
                    x, y = self.GetRenderWindow().GetInteractor().GetEventPosition()
                    viewport._on_click(x, y, bool(ev.modifiers() & Qt.ShiftModifier))

        self._iren = _Interactor(self)
        layout.addWidget(self._iren)
        self.scene = SceneController()
        if QGuiApplication.platformName() == "offscreen":
            self.scene.set_hud_visible(False)      # texto VTK exige OpenGL real
        self._render_window = self._iren.GetRenderWindow()
        self._render_window.AddRenderer(self.scene.renderer)
        self._render_window.SetMultiSamples(4)
        self._iren.SetInteractorStyle(vtkInteractorStyleTrackballCamera())
        self._iren.Initialize()
        self._iren.Start()

        self._axes = vtkAxesActor()
        self._axes.SetTotalLength(1, 1, 1)
        self._axes.SetShaftTypeToCylinder()
        for cap in (self._axes.GetXAxisCaptionActor2D(), self._axes.GetYAxisCaptionActor2D(),
                    self._axes.GetZAxisCaptionActor2D()):
            cap.GetCaptionTextProperty().SetColor(0.84, 0.88, 0.93)
            cap.GetCaptionTextProperty().ShadowOff()
        self._marker = vtkOrientationMarkerWidget()
        self._marker.SetOrientationMarker(self._axes)
        self._marker.SetInteractor(self._iren.GetRenderWindow().GetInteractor())
        self._marker.SetViewport(0.0, 0.0, 0.14, 0.2)
        self._marker.SetEnabled(1)
        self._marker.InteractiveOff()

    def _on_click(self, x: int, y: int, additive: bool) -> None:
        self.pick_requested.emit(self.scene.pick(x, y), additive)

    def refresh(self) -> None:
        self.scene.layout_hud(*self._render_window.GetSize())
        if QGuiApplication.platformName() == "offscreen":
            return          # sem contexto OpenGL utilizável (testes/CI): o desenho real só ocorre com tela
        self._render_window.Render()

    def render_to_image(self, path: str) -> None:
        """Salva a vista atual em PNG (usado em testes e documentação)."""
        from vtkmodules.vtkIOImage import vtkPNGWriter
        from vtkmodules.vtkRenderingCore import vtkWindowToImageFilter
        self.refresh()
        w2i = vtkWindowToImageFilter()
        w2i.SetInput(self._render_window)
        w2i.ReadFrontBufferOff()
        w2i.Update()
        writer = vtkPNGWriter()
        writer.SetFileName(path)
        writer.SetInputConnection(w2i.GetOutputPort())
        writer.Write()

    def shutdown(self) -> None:
        """Libera o contexto OpenGL (chamar ao fechar a janela)."""
        try:
            self._marker.SetEnabled(0)
            self._iren.Finalize()
        except Exception:
            pass
