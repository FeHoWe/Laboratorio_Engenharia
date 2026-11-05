"""Medições entre componentes (V1.1).

Regras de honestidade:
    * B-Rep contra B-Rep: distância mínima EXATA (OpenCascade).
    * Se algum lado é malha (STL/OBJ): distância aproximada entre VÉRTICES, sempre rotulada como
      aproximada (a resolução é a da malha).
    * Medidas valem para a posição exibida (explosão incluída) e, separadamente, para a montagem
      original. Nada é estimado: sem geometria, o campo fica ``None`` com uma nota.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from core.component_manager import ComponentManager
from core.geometry import translation_matrix
from core.model import Component

CONTACT_TOLERANCE_MM = 1e-6
AXIS_TOL = 1e-4          # tolerância para considerar dois eixos/raios iguais (mm / adimensional)
_CHUNK = 2000


@dataclass
class Measurement:
    name_a: str
    name_b: str
    min_distance: Optional[float] = None              # mm (posição exibida)
    point_a: Optional[tuple[float, float, float]] = None
    point_b: Optional[tuple[float, float, float]] = None
    exact: bool = True                                # False = aproximada (malha)
    center_distance: Optional[float] = None           # mm entre centros das caixas (exibida)
    delta: Optional[tuple[float, float, float]] = None  # B - A, centros (mm)
    original_min_distance: Optional[float] = None     # na montagem original
    in_contact: bool = False
    notes: list[str] = field(default_factory=list)

    def summary(self) -> str:
        if self.min_distance is None:
            return f"{self.name_a} ↔ {self.name_b}: distância indisponível."
        kind = "" if self.exact else " (aproximada, malha)"
        state = "em contato/interpenetrando" if self.in_contact else f"{self.min_distance:.3f} mm".replace(".", ",")
        out = f"{self.name_a} ↔ {self.name_b}: menor distância {state}{kind}"
        if self.center_distance is not None:
            out += f"; entre centros {self.center_distance:.2f} mm".replace(".", ",")
        return out + "."


@dataclass
class DiameterInfo:
    diameter: float                                   # mm
    axis: tuple[float, float, float]                  # direção do eixo (unitária, sem sentido)
    point: tuple[float, float, float]                 # ponto sobre o eixo
    area: float                                       # mm² de superfície cilíndrica com esse diâmetro/eixo

    @property
    def axis_label(self) -> str:
        return axis_label(self.axis)


@dataclass
class AngleMeasurement:
    name_a: str
    name_b: str
    angle_deg: Optional[float] = None                 # 0..90 (entre retas, sem sentido)
    basis_a: str = ""
    basis_b: str = ""
    notes: list[str] = field(default_factory=list)

    def summary(self) -> str:
        if self.angle_deg is None:
            return f"{self.name_a} ↔ {self.name_b}: ângulo indisponível."
        return (f"{self.name_a} ↔ {self.name_b}: ângulo {self.angle_deg:.2f}° ".replace(".", ",")
                + f"({self.basis_a} × {self.basis_b}).")


def axis_label(v) -> str:
    """'X', 'Y', 'Z' se o eixo for alinhado ao mundo; senão o vetor."""
    v = np.asarray(v, dtype=float)
    for i, name in enumerate("XYZ"):
        if abs(abs(v[i]) - 1.0) < 1e-6:
            return name
    return "({:.2f}, {:.2f}, {:.2f})".format(*v).replace(".", ",")


def _canon(axis: np.ndarray) -> np.ndarray:
    """Eixo sem sentido: primeira componente significativa positiva."""
    axis = np.asarray(axis, dtype=float)
    axis = axis / np.linalg.norm(axis)
    for c in axis:
        if abs(c) > 1e-9:
            return axis if c > 0 else -axis
    return axis


class MeasureEngine:
    def __init__(self, components: ComponentManager) -> None:
        self.components = components
        self.engine = components.engine

    # ---------------------------------------------------------------- helpers
    def _shape_at(self, comp: Component, displaced: bool):
        shape = comp.shape
        if shape is None or not displaced:
            return shape
        off = comp.effective_offset()
        if not np.any(off):
            return shape
        return self.engine.transform(shape, translation_matrix(off))

    def _vertices_at(self, comp: Component, displaced: bool) -> np.ndarray:
        mesh = comp.mesh if comp.mesh is not None else self.components.render_mesh(comp)
        v = np.asarray(mesh.vertices, dtype=float)
        return v + comp.effective_offset() if displaced else v

    @staticmethod
    def _mesh_distance(va: np.ndarray, vb: np.ndarray) -> tuple[float, np.ndarray, np.ndarray]:
        best, pa, pb = np.inf, va[0], vb[0]
        for i in range(0, len(va), _CHUNK):
            a = va[i:i + _CHUNK]
            d = np.linalg.norm(a[:, None, :] - vb[None, :, :], axis=2)
            idx = np.unravel_index(np.argmin(d), d.shape)
            if d[idx] < best:
                best, pa, pb = float(d[idx]), a[idx[0]], vb[idx[1]]
        return best, pa, pb

    def _distance(self, a: Component, b: Component, displaced: bool):
        if a.shape is not None and b.shape is not None:
            return (*self.engine.min_distance(self._shape_at(a, displaced), self._shape_at(b, displaced)), True)
        d, pa, pb = self._mesh_distance(self._vertices_at(a, displaced), self._vertices_at(b, displaced))
        return d, pa, pb, False

    # ------------------------------------------------------------------ API
    def measure(self, a: Component, b: Component) -> Measurement:
        if a.id == b.id:
            raise ValueError("Escolha dois componentes diferentes.")
        for c in (a, b):
            if not c.has_geometry:
                raise ValueError(f"'{c.name}' é um grupo; selecione peças com geometria.")
        m = Measurement(a.name, b.name)
        try:
            d, pa, pb, exact = self._distance(a, b, displaced=True)
            m.min_distance, m.exact = d, exact
            m.point_a, m.point_b = tuple(map(float, pa)), tuple(map(float, pb))
            m.in_contact = d <= CONTACT_TOLERANCE_MM
            if any(c.is_displaced() for c in (a, b)):
                m.original_min_distance = self._distance(a, b, displaced=False)[0]
        except Exception as exc:
            m.notes.append(f"Distância mínima indisponível: {exc}")
        ba, bb = self.components.displayed_bbox(a), self.components.displayed_bbox(b)
        if ba is not None and bb is not None:
            delta = bb.center - ba.center
            m.delta = tuple(float(x) for x in delta)
            m.center_distance = float(np.linalg.norm(delta))
        if not m.exact:
            m.notes.append("Pelo menos um componente é malha: a distância é entre vértices (aproximada).")
        return m

    # ------------------------------------------------------------ diâmetros
    def diameters(self, comp: Component) -> list[DiameterInfo]:
        """Diâmetros das superfícies cilíndricas exatas do B-Rep (vazio para malhas)."""
        if comp.shape is None:
            return []
        cyls, _ = self.engine.analytic_faces(comp.shape)
        groups: list[dict] = []
        for c in cyls:
            axis = _canon(c.axis)
            for g in groups:
                same_axis = abs(abs(float(np.dot(g["axis"], axis))) - 1.0) < AXIS_TOL
                if same_axis and abs(g["r"] - c.radius) < AXIS_TOL and self._on_axis(g, c.point):
                    g["area"] += c.area
                    break
            else:
                groups.append({"r": c.radius, "axis": axis, "point": c.point, "area": c.area})
        groups.sort(key=lambda g: -g["area"])
        return [DiameterInfo(2 * g["r"], tuple(map(float, g["axis"])), tuple(map(float, g["point"])), g["area"])
                for g in groups]

    @staticmethod
    def _on_axis(g: dict, point: np.ndarray) -> bool:
        d = np.asarray(point, dtype=float) - g["point"]
        perp = d - np.dot(d, g["axis"]) * g["axis"]
        return float(np.linalg.norm(perp)) < 1e-3

    # --------------------------------------------------------------- ângulos
    def principal_axis(self, comp: Component) -> Optional[tuple[np.ndarray, str]]:
        """Direção característica da peça: eixo do cilindro dominante ou normal da maior face plana."""
        if comp.shape is None:
            return None
        diams = self.diameters(comp)
        if diams:
            return np.array(diams[0].axis), f"eixo do cilindro Ø{diams[0].diameter:.2f} mm".replace(".", ",")
        _, planes = self.engine.analytic_faces(comp.shape)
        if planes:
            best = max(planes, key=lambda p: p.area)
            return _canon(best.normal), "normal da maior face plana"
        return None

    def angle(self, a: Component, b: Component) -> AngleMeasurement:
        if a.id == b.id:
            raise ValueError("Escolha dois componentes diferentes.")
        for c in (a, b):
            if not c.has_geometry:
                raise ValueError(f"'{c.name}' é um grupo; selecione peças com geometria.")
        res = AngleMeasurement(a.name, b.name)
        pa, pb = self.principal_axis(a), self.principal_axis(b)
        for comp, pr in ((a, pa), (b, pb)):
            if pr is None:
                res.notes.append(f"'{comp.name}' não tem cilindros nem faces planas analíticas (malha ou superfície livre): "
                                 "ângulo indisponível.")
        if pa is None or pb is None:
            return res
        cos = min(1.0, abs(float(np.dot(pa[0], pb[0]))))
        res.angle_deg = float(np.degrees(np.arccos(cos)))
        res.basis_a, res.basis_b = pa[1], pb[1]
        return res
