"""Component Inspector: propriedades técnicas calculadas da geometria real.

Regras (do requisito 6):
    * Valores vêm do B-Rep exato (OpenCascade) ou, para malhas, da própria malha.
    * Quando algo não pode ser calculado de forma confiável, o campo fica ``None``
      acompanhado de uma NOTA explicando o motivo — nunca se inventa um número.
        - Volume de malha só existe se a malha for fechada (watertight).
        - Massa só existe com material definido pelo usuário E volume conhecido.
    * Unidades: mm, mm², mm³ (padrão STEP) e gramas.
    * Dimensões = extensão da caixa delimitadora alinhada aos eixos do MUNDO:
      Comprimento = X, Largura = Y, Altura = Z.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from core.lazy import lazy_import
trimesh = lazy_import("trimesh")

from core.component_manager import ComponentManager
from core.geometry import BoundingBox, euler_from_matrix, mesh_area
from core.model import Component, ComponentKind, GeometryKind
from modules.material_manager import MaterialLibrary


@dataclass
class InspectionReport:
    name: str
    id: str
    node_kind: str
    geometry_type: str
    size: Optional[tuple[float, float, float]] = None       # (comprimento X, largura Y, altura Z)
    volume: Optional[float] = None                          # mm³
    area: Optional[float] = None                            # mm²
    centroid: Optional[tuple[float, float, float]] = None   # mm (mundo, em repouso)
    centroid_note: str = ""
    material: Optional[str] = None
    density: Optional[float] = None                         # g/cm³
    mass: Optional[float] = None                            # g
    mass_note: str = ""
    position: Optional[tuple[float, float, float]] = None   # centro da caixa + deslocamento
    displacement: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0)  # graus (rx, ry, rz)
    n_solids: Optional[int] = None
    n_faces: Optional[int] = None
    n_triangles: Optional[int] = None
    parametric: bool = False
    visible: bool = True
    notes: list[str] = field(default_factory=list)
    child_count: int = 0
    part_count: int = 0
    diameters: list[tuple[float, str]] = field(default_factory=list)   # (Ø mm, eixo)


class ComponentInspector:
    def __init__(self, components: ComponentManager, materials: MaterialLibrary) -> None:
        self.components = components
        self.materials = materials
        self._cache: dict[tuple, dict] = {}

    def clear_cache(self) -> None:
        self._cache.clear()

    # ------------------------------------------------------------------ núcleo
    def inspect(self, comp: Component) -> InspectionReport:
        rep = InspectionReport(
            name=comp.name, id=comp.id, node_kind=_KIND_LABEL[comp.kind],
            geometry_type=comp.geometry_kind.label if comp.has_geometry else _KIND_LABEL[comp.kind],
            parametric=comp.parametric, visible=comp.visible,
            child_count=len(comp.children),
            part_count=sum(1 for _ in comp.leaves()),
        )
        box = self.components.bbox(comp)
        offset = comp.effective_offset()
        rep.displacement = tuple(float(x) for x in offset)  # type: ignore[assignment]
        if box is not None:
            rep.size = tuple(float(x) for x in box.size)  # type: ignore[assignment]
            rep.position = tuple(float(x) for x in (box.center + offset))  # type: ignore[assignment]
        rx, ry, rz = euler_from_matrix(comp.placement)
        rep.rotation = (rx, ry, rz)

        mat = self.materials.get(comp.material)
        rep.material = comp.material
        rep.density = mat.density_g_cm3 if mat else None

        if comp.has_geometry:
            self._fill_part(rep, comp)
        else:
            self._fill_group(rep, comp)

        # massa: depende de material + volume
        if rep.volume is not None and mat is not None and comp.has_geometry:
            rep.mass = MaterialLibrary.mass_g(rep.volume, mat)
        elif comp.has_geometry:
            if mat is None:
                rep.mass_note = "Defina um material para calcular a massa."
            else:
                rep.mass_note = "Volume indisponível para esta geometria."
        return rep

    # ------------------------------------------------------------------ peças
    def _part_props(self, comp: Component) -> dict:
        key = (comp.id, id(comp.shape), id(comp.mesh))
        if key in self._cache:
            return self._cache[key]
        data: dict = {"notes": []}
        if comp.shape is not None:
            eng = self.components.engine
            props = eng.properties(comp.shape)
            data.update(volume=props.volume, area=props.area, centroid=tuple(props.centroid),
                        centroid_kind=props.centroid_kind,
                        n_solids=eng.count_solids(comp.shape), n_faces=eng.count_faces(comp.shape))
            if props.volume is None:
                data["notes"].append("Geometria sem sólido (apenas superfícies): volume indisponível.")
            try:
                from modules.measure_engine import MeasureEngine
                data["diameters"] = [(x.diameter, x.axis_label) for x in MeasureEngine(self.components).diameters(comp)]
            except Exception:
                data["diameters"] = []
            try:
                data["n_triangles"] = len(self.components.render_mesh(comp).faces)
            except Exception:
                data["n_triangles"] = None
        else:
            m = comp.mesh
            tm = trimesh.Trimesh(m.vertices, m.faces, process=False)
            tm.merge_vertices()
            data.update(area=mesh_area(m.vertices, m.faces), n_triangles=len(m.faces), n_faces=None,
                        n_solids=None)
            if tm.is_watertight:
                vol = abs(float(tm.volume))
                data.update(volume=vol, centroid=tuple(tm.center_mass), centroid_kind="volume")
            else:
                data.update(volume=None, centroid=tuple(tm.centroid), centroid_kind="area")
                data["notes"].append("Malha aberta (não estanque): volume e massa não podem ser calculados.")
        self._cache[key] = data
        return data

    def _fill_part(self, rep: InspectionReport, comp: Component) -> None:
        d = self._part_props(comp)
        rep.volume = d.get("volume")
        rep.area = d.get("area")
        rep.centroid = d.get("centroid")
        rep.centroid_note = ("Centro de massa geométrico (densidade uniforme)"
                             if d.get("centroid_kind") == "volume" else
                             "Centroide da superfície (não há volume fechado)")
        rep.n_solids, rep.n_faces, rep.n_triangles = d.get("n_solids"), d.get("n_faces"), d.get("n_triangles")
        rep.diameters = d.get("diameters", [])
        rep.notes.extend(d["notes"])
        if comp.parametric:
            rep.notes.append("Veio de um objeto paramétrico do FreeCAD, mas foi importado como geometria final: "
                             "não há histórico de construção editável no NEXUS.")
        elif comp.shape is not None:
            rep.notes.append("Geometria importada sem histórico de construção (não paramétrica).")

    # ------------------------------------------------------------ grupos
    def _fill_group(self, rep: InspectionReport, comp: Component) -> None:
        leaves = list(comp.leaves())
        if not leaves:
            return
        datas = [self._part_props(c) for c in leaves]
        areas = [d.get("area") for d in datas]
        if all(a is not None for a in areas):
            rep.area = float(sum(areas))
        vols = [d.get("volume") for d in datas]
        if all(v is not None for v in vols):
            rep.volume = float(sum(vols))
            total = rep.volume
            if total > 0:
                cs = np.array([d["centroid"] for d in datas]) * np.array(vols)[:, None]
                rep.centroid = tuple(float(x) for x in cs.sum(axis=0) / total)
                rep.centroid_note = "Centro de massa geométrico do conjunto (densidade uniforme)"
        else:
            rep.notes.append("Volume total indisponível: há peças sem volume fechado.")
        # massa do conjunto: somente se TODAS as peças tiverem material e volume
        masses = []
        for c, d in zip(leaves, datas):
            mat = self.materials.get(c.material)
            if mat is None or d.get("volume") is None:
                masses = None
                break
            masses.append(MaterialLibrary.mass_g(d["volume"], mat))
        if masses:
            rep.mass = float(sum(masses))
        else:
            rep.mass_note = "A massa do conjunto exige material em todas as peças."
        rep.n_triangles = sum(d.get("n_triangles") or 0 for d in datas)


_KIND_LABEL = {
    ComponentKind.ASSEMBLY: "Montagem",
    ComponentKind.GROUP: "Grupo",
    ComponentKind.PART: "Peça",
}
