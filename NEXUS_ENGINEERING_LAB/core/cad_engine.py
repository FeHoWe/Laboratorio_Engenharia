"""Camada de acesso ao motor CAD (OpenCascade via pacote ``cadquery-ocp``).

Por que OCP e não o FreeCAD embarcado? (resumo; detalhes em docs/ARQUITETURA.md)
    * O FreeCAD traz o PRÓPRIO Python e as PRÓPRIAS bibliotecas Qt/OpenCascade.
      Misturá-los com o PySide6/VTK do NEXUS gera conflitos de DLL e de versão
      no Windows — exatamente o que o projeto precisa evitar.
    * ``cadquery-ocp`` entrega o mesmo OpenCascade (OCCT) como pacote pip
      normal, instalável no mesmo ambiente do NEXUS, sem instalar o FreeCAD.
    * O restante do NEXUS só fala com a classe :class:`CadEngine`. Um backend
      FreeCAD ou próprio pode ser criado depois implementando a mesma interface.

Somente este módulo importa ``OCP``. Nenhum outro módulo depende do OpenCascade
diretamente, exceto para guardar o objeto opaco ``TopoDS_Shape``.
"""
from __future__ import annotations

import glob
import os
import platform
import shutil
import sys
import unicodedata
from dataclasses import dataclass, field
from importlib import metadata
from pathlib import Path
from typing import Optional

import numpy as np

from core.geometry import BoundingBox, smooth_vertex_normals
from core.model import MeshData

try:  # pragma: no cover - exercitado pelos testes quando OCP existe
    from OCP.BRep import BRep_Builder, BRep_Tool
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepBndLib import BRepBndLib
    from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Copy, BRepBuilderAPI_Transform
    from OCP.BRepGProp import BRepGProp
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.BRepTools import BRepTools
    from OCP.Bnd import Bnd_Box
    from OCP.BinTools import BinTools
    from OCP.GProp import GProp_GProps
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPCAFControl import STEPCAFControl_Reader, STEPCAFControl_Writer
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDF import TDF_Label
    from OCP.TDataStd import TDataStd_Name
    from OCP.TDocStd import TDocStd_Document
    from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED, TopAbs_SHELL, TopAbs_SOLID
    from OCP.TopExp import TopExp
    from OCP.TopLoc import TopLoc_Location
    from OCP.collections import IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as TopTools_IndexedMapOfShape
    from OCP.TopoDS import TopoDS, TopoDS_Shape
    from OCP.XCAFDoc import XCAFDoc_DocumentTool, XCAFDoc_ShapeTool
    from OCP.collections import Sequence_TDF_Label
    from OCP.gp import gp_Trsf

    OCP_AVAILABLE = True
    OCP_IMPORT_ERROR: Optional[str] = None
except Exception as exc:  # pragma: no cover
    OCP_AVAILABLE = False
    OCP_IMPORT_ERROR = str(exc)


class CadEngineError(RuntimeError):
    """Erro de leitura, escrita ou processamento geométrico (mensagem em português)."""


@dataclass
class RawNode:
    """Nó neutro (sem tipos do OpenCascade) devolvido/consumido pelo engine."""

    name: str
    shape: object = None                       # TopoDS_Shape (folhas) ou None (montagens)
    children: list["RawNode"] = field(default_factory=list)
    world_matrix: np.ndarray = field(default_factory=lambda: np.eye(4))   # leitura
    local_matrix: np.ndarray = field(default_factory=lambda: np.eye(4))   # escrita

    @property
    def is_assembly(self) -> bool:
        return self.shape is None


@dataclass
class ShapeProperties:
    volume: Optional[float]         # mm³ — None quando não há sólido
    area: float                     # mm²
    centroid: np.ndarray            # centro de massa (sólidos) ou do centroide de área
    centroid_kind: str              # "volume" | "area"


# ---------------------------------------------------------------- utilitários
def fix_text(text: Optional[str]) -> Optional[str]:
    """Repara nomes UTF-8 lidos como Latin-1 (acontece em alguns arquivos STEP)."""
    if not text:
        return text
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def ascii_fold(text: str) -> str:
    """Remove acentos (nomes gravados em STEP precisam ser ASCII para portabilidade)."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii") or "peca"


def matrix_to_trsf(m: np.ndarray):
    """Matriz 4x4 -> gp_Trsf."""
    t = gp_Trsf()
    a = np.asarray(m, dtype=np.float64)
    t.SetValues(
        a[0, 0], a[0, 1], a[0, 2], a[0, 3],
        a[1, 0], a[1, 1], a[1, 2], a[1, 3],
        a[2, 0], a[2, 1], a[2, 2], a[2, 3],
    )
    return t


def trsf_to_matrix(t) -> np.ndarray:
    m = np.eye(4)
    for i in range(3):
        for j in range(4):
            m[i, j] = t.Value(i + 1, j + 1)
    return m


def environment_report(freecad_hint: Optional[str] = None) -> dict:
    """Relatório do ambiente (passo 1–2 da missão: Python, FreeCAD, OCC...)."""
    def ver(pkg: str) -> Optional[str]:
        try:
            return metadata.version(pkg)
        except metadata.PackageNotFoundError:
            return None

    candidates: list[str] = []
    if freecad_hint:
        candidates.append(freecad_hint)
    for exe in ("FreeCADCmd", "freecadcmd", "FreeCAD", "freecad"):
        found = shutil.which(exe)
        if found:
            candidates.append(found)
    if platform.system() == "Windows":
        for pattern in (r"C:\Program Files\FreeCAD*\bin\FreeCADCmd.exe",
                        r"C:\Program Files\FreeCAD*\bin\FreeCAD.exe"):
            candidates.extend(glob.glob(pattern))
    freecad = next((c for c in candidates if os.path.exists(c)), None)

    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "ocp_available": OCP_AVAILABLE,
        "ocp_error": OCP_IMPORT_ERROR,
        "cadquery-ocp": ver("cadquery-ocp"),
        "PySide6": ver("PySide6"),
        "vtk": ver("vtk"),
        "numpy": ver("numpy"),
        "trimesh": ver("trimesh"),
        "freecad": freecad,   # detectado apenas para informação; não é usado na V1.0
    }


@dataclass
class CylinderFace:
    radius: float                 # mm
    point: np.ndarray             # ponto sobre o eixo
    axis: np.ndarray              # direção do eixo (unitária)
    area: float                   # mm² da face


@dataclass
class PlaneFace:
    normal: np.ndarray            # normal PARA FORA do sólido
    point: np.ndarray
    area: float
    bounds: Optional[tuple] = None   # (min xyz, max xyz) da face, no mundo


# --------------------------------------------------------------------- engine
class CadEngine:
    """Operações CAD usadas pelo NEXUS. Backend: OpenCascade (OCP)."""

    backend_name = "OpenCascade (cadquery-ocp)"

    def __init__(self, relative_deflection: float = 0.0012, angular_deflection: float = 0.35) -> None:
        if not OCP_AVAILABLE:
            raise CadEngineError(
                "OpenCascade (pacote 'cadquery-ocp') não está instalado. "
                f"Execute: pip install cadquery-ocp  (detalhe: {OCP_IMPORT_ERROR})"
            )
        self.relative_deflection = relative_deflection
        self.angular_deflection = angular_deflection

    # ------------------------------------------------------------ STEP: leitura
    @staticmethod
    def _label_name(label) -> Optional[str]:
        attr = TDataStd_Name()
        if label.FindAttribute(TDataStd_Name.GetID_s(), attr):
            return fix_text(attr.Get().ToExtString())
        return None

    def read_step(self, path: str | os.PathLike) -> list[RawNode]:
        """Lê um STEP/STP preservando a estrutura de montagem (XCAF).

        Devolve a lista de formas "livres" do arquivo (cada uma pode ser uma
        montagem com filhos ou uma peça). A posição de cada instância é
        acumulada ao longo da hierarquia e aplicada à geometria das folhas.
        """
        path = str(path)
        if not os.path.isfile(path):
            raise CadEngineError(f"Arquivo não encontrado: {path}")
        doc = TDocStd_Document(TCollection_ExtendedString("XmlOcaf"))
        reader = STEPCAFControl_Reader()
        reader.SetNameMode(True)
        try:
            status = reader.ReadFile(path)
        except Exception as exc:
            raise CadEngineError(f"Falha ao abrir o STEP: {exc}") from exc
        if status != IFSelect_RetDone:
            raise CadEngineError("O arquivo STEP é inválido ou está corrompido (leitura recusada).")
        if not reader.Transfer(doc):
            raise CadEngineError("Não foi possível converter o conteúdo do STEP para geometria.")

        shape_tool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
        free = Sequence_TDF_Label()
        shape_tool.GetFreeShapes(free)
        if free.Length() == 0:
            raise CadEngineError("O arquivo STEP não contém nenhuma forma geométrica.")

        nodes = [self._walk_step_label(free.Value(i), TopLoc_Location()) for i in range(1, free.Length() + 1)]
        return nodes

    def _walk_step_label(self, label, parent_loc) -> RawNode:
        name = self._label_name(label) or ""
        world = trsf_to_matrix(parent_loc.Transformation())
        if XCAFDoc_ShapeTool.IsAssembly_s(label):
            node = RawNode(name=name, shape=None, world_matrix=world)
            comps = Sequence_TDF_Label()
            XCAFDoc_ShapeTool.GetComponents_s(label, comps)
            for i in range(1, comps.Length() + 1):
                comp = comps.Value(i)
                ref = TDF_Label()
                if not XCAFDoc_ShapeTool.GetReferredShape_s(comp, ref):
                    ref = comp
                loc = XCAFDoc_ShapeTool.GetLocation_s(comp)
                child = self._walk_step_label(ref, parent_loc * loc)
                node.children.append(child)
            return node
        shape = XCAFDoc_ShapeTool.GetShape_s(label)
        if shape.IsNull():
            raise CadEngineError(f"Forma nula encontrada no STEP (componente '{name}').")
        return RawNode(name=name, shape=shape.Moved(parent_loc), world_matrix=world)

    # ------------------------------------------------------------ STEP: escrita
    def write_step(self, roots: list[RawNode], path: str | os.PathLike) -> None:
        """Escreve um STEP com hierarquia e nomes (nomes convertidos para ASCII)."""
        doc = TDocStd_Document(TCollection_ExtendedString("XmlOcaf"))
        shape_tool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
        used_shapes: set[int] = set()   # formas (sem posição) já gravadas neste arquivo

        def unique_base(shape):
            """Instâncias da MESMA forma virariam um único produto STEP (o último nome
            venceria). Copiamos a geometria repetida para cada instância manter o
            próprio produto e o próprio nome."""
            key = hash(shape)
            if key in used_shapes:
                shape = BRepBuilderAPI_Copy(shape, True, False).Shape()
                key = hash(shape)
            used_shapes.add(key)
            return shape

        def build(node: RawNode, top: bool = False):
            """Devolve (rótulo, localização extra do componente).

            Formas lidas de outro STEP trazem uma ``Location`` própria. O XCAF cria,
            para formas localizadas, um rótulo de *referência* — e o nome ficaria no
            rótulo errado. Por isso gravamos a forma SEM localização como produto e
            passamos a posição como localização do componente na montagem (é
            exatamente a semântica de montagem do STEP).
            """
            extra = TopLoc_Location()
            if node.is_assembly:
                label = shape_tool.NewShape()
                for child in node.children:
                    child_label, child_loc = build(child)
                    loc = TopLoc_Location(matrix_to_trsf(child.local_matrix)) * child_loc
                    shape_tool.AddComponent(label, child_label, loc)
            elif top or node.shape.Location().IsIdentity():
                label = shape_tool.AddShape(unique_base(node.shape), False)
            else:
                extra = node.shape.Location()
                label = shape_tool.AddShape(unique_base(node.shape.Located(TopLoc_Location())), False)
            TDataStd_Name.Set_s(label, TCollection_ExtendedString(ascii_fold(node.name)))
            return label, extra

        for root in roots:
            build(root, top=True)
        shape_tool.UpdateAssemblies()
        writer = STEPCAFControl_Writer()
        writer.SetNameMode(True)
        if not writer.Transfer(doc):
            raise CadEngineError("Falha ao converter a montagem para STEP.")
        if writer.Write(str(path)) != IFSelect_RetDone:
            raise CadEngineError(f"Falha ao gravar o arquivo STEP em {path}.")

    # ---------------------------------------------------------- formas (B-Rep)
    def read_brep_file(self, path: str | os.PathLike):
        """Lê um arquivo .brp/.brep (usado pelo importador de FCStd)."""
        shape = TopoDS_Shape()
        if not BRepTools.Read_s(shape, str(path), BRep_Builder()) or shape.IsNull():
            raise CadEngineError(f"Forma B-Rep ilegível: {path}")
        return shape

    def write_brep_file(self, shape, path: str | os.PathLike) -> None:
        """Grava a forma em .brp (texto OpenCascade, o formato que o FreeCAD guarda dentro do FCStd)."""
        if not BRepTools.Write_s(shape, str(path)):
            raise CadEngineError(f"Falha ao gravar a forma B-Rep em {path}.")

    def write_shape_bin(self, shape, path: str | os.PathLike) -> None:
        """Grava a forma em binário OpenCascade (formato interno do projeto .nexus)."""
        BinTools.Write_s(shape, str(path))

    def read_shape_bin(self, path: str | os.PathLike):
        shape = TopoDS_Shape()
        BinTools.Read_s(shape, str(path))
        if shape.IsNull():
            raise CadEngineError(f"Geometria binária ilegível: {path}")
        return shape

    def transform(self, shape, matrix: np.ndarray):
        """Devolve uma cópia da forma transformada por uma matriz 4x4 rígida."""
        return BRepBuilderAPI_Transform(shape, matrix_to_trsf(matrix), True).Shape()

    # --------------------------------------------------------------- análise
    @staticmethod
    def _unique_subshapes(shape, shape_type) -> list:
        shapes = TopTools_IndexedMapOfShape()
        TopExp.MapShapes_s(shape, shape_type, shapes)
        return [shapes.FindKey(i) for i in range(1, shapes.Extent() + 1)]

    def solids(self, shape) -> list:
        return self._unique_subshapes(shape, TopAbs_SOLID)

    def count_solids(self, shape) -> int:
        return len(self.solids(shape))

    def count_shells(self, shape) -> int:
        return len(self._unique_subshapes(shape, TopAbs_SHELL))

    def count_faces(self, shape) -> int:
        return len(self._unique_subshapes(shape, TopAbs_FACE))

    def bbox(self, shape) -> Optional[BoundingBox]:
        box = Bnd_Box()
        BRepBndLib.AddOptimal_s(shape, box, False, False)
        if box.IsVoid():
            return None
        return BoundingBox(
            np.array([box.GetXMin(), box.GetYMin(), box.GetZMin()]),
            np.array([box.GetXMax(), box.GetYMax(), box.GetZMax()]),
        )

    def analytic_faces(self, shape) -> tuple[list["CylinderFace"], list["PlaneFace"]]:
        """Faces cilíndricas e planas do B-Rep (superfícies analíticas reais, já na posição do mundo)."""
        cyls: list[CylinderFace] = []
        planes: list[PlaneFace] = []
        for face_shape in self._unique_subshapes(shape, TopAbs_FACE):
            face = TopoDS.Face_s(face_shape) if hasattr(TopoDS, "Face_s") else TopoDS.Face(face_shape)
            surf = BRepAdaptor_Surface(face, True)
            kind = surf.GetType()
            area_props = GProp_GProps()
            BRepGProp.SurfaceProperties_s(face, area_props)
            area = float(area_props.Mass())
            if kind == GeomAbs_Cylinder:
                cyl = surf.Cylinder()
                loc, d = cyl.Axis().Location(), cyl.Axis().Direction()
                cyls.append(CylinderFace(float(cyl.Radius()), np.array([loc.X(), loc.Y(), loc.Z()]),
                                         np.array([d.X(), d.Y(), d.Z()]), area))
            elif kind == GeomAbs_Plane:
                pl = surf.Plane()
                loc, d = pl.Axis().Location(), pl.Axis().Direction()
                n = np.array([d.X(), d.Y(), d.Z()])
                if face.Orientation() == TopAbs_REVERSED:      # normal PARA FORA do sólido
                    n = -n
                fb = Bnd_Box()
                BRepBndLib.AddOptimal_s(face, fb, False, False)
                planes.append(PlaneFace(n, np.array([loc.X(), loc.Y(), loc.Z()]), area,
                                        (np.array([fb.GetXMin(), fb.GetYMin(), fb.GetZMin()]),
                                         np.array([fb.GetXMax(), fb.GetYMax(), fb.GetZMax()]))))
        return cyls, planes

    def min_distance(self, a, b) -> tuple[float, np.ndarray, np.ndarray]:
        """Menor distância exata entre dois B-Reps: (distância mm, ponto em A, ponto em B).

        Distância 0 significa contato ou interpenetração.
        """
        calc = BRepExtrema_DistShapeShape(a, b)
        if not calc.IsDone() or calc.NbSolution() < 1:
            raise CadEngineError("Não foi possível calcular a distância entre as geometrias.")
        pa, pb = calc.PointOnShape1(1), calc.PointOnShape2(1)
        return (float(calc.Value()), np.array([pa.X(), pa.Y(), pa.Z()]), np.array([pb.X(), pb.Y(), pb.Z()]))

    def properties(self, shape) -> ShapeProperties:
        """Volume, área e centro calculados a partir da geometria B-Rep real."""
        area_props = GProp_GProps()
        BRepGProp.SurfaceProperties_s(shape, area_props)
        area = float(area_props.Mass())
        if self.count_solids(shape) > 0:
            vol_props = GProp_GProps()
            BRepGProp.VolumeProperties_s(shape, vol_props)
            com = vol_props.CentreOfMass()
            return ShapeProperties(abs(float(vol_props.Mass())), area,
                                   np.array([com.X(), com.Y(), com.Z()]), "volume")
        com = area_props.CentreOfMass()
        return ShapeProperties(None, area, np.array([com.X(), com.Y(), com.Z()]), "area")

    # ------------------------------------------------------------ tesselação
    def tessellate(self, shape, linear_deflection: Optional[float] = None) -> MeshData:
        """Converte um B-Rep em malha triangular para exibição/exportação.

        A tolerância linear padrão é relativa ao tamanho da peça (``relative_deflection``
        × diagonal), para que peças pequenas e grandes tenham qualidade equivalente.
        """
        if linear_deflection is None:
            box = self.bbox(shape)
            diag = box.diagonal if box is not None else 1.0
            linear_deflection = max(diag * self.relative_deflection, 1e-5)
        BRepMesh_IncrementalMesh(shape, linear_deflection, False, self.angular_deflection, True)

        verts: list[np.ndarray] = []
        faces: list[np.ndarray] = []
        base = 0
        for face_shape in self._unique_subshapes(shape, TopAbs_FACE):
            face = TopoDS.Face_s(face_shape) if hasattr(TopoDS, "Face_s") else TopoDS.Face(face_shape)
            loc = TopLoc_Location()
            tri = BRep_Tool.Triangulation_s(face, loc)
            if tri is None:
                continue
            trsf = loc.Transformation()
            n_nodes = tri.NbNodes()
            pts = np.empty((n_nodes, 3))
            for i in range(1, n_nodes + 1):
                p = tri.Node(i).Transformed(trsf)
                pts[i - 1] = (p.X(), p.Y(), p.Z())
            n_tri = tri.NbTriangles()
            idx = np.empty((n_tri, 3), dtype=np.int64)
            reverse = face.Orientation() == TopAbs_REVERSED
            for i in range(1, n_tri + 1):
                a, b, c = tri.Triangle(i).Get()
                idx[i - 1] = (a - 1, c - 1, b - 1) if reverse else (a - 1, b - 1, c - 1)
            verts.append(pts)
            faces.append(idx + base)
            base += n_nodes
        if not verts:
            raise CadEngineError("A geometria não pôde ser triangulada (nenhuma face renderizável).")
        v = np.vstack(verts)
        f = np.vstack(faces)
        return MeshData(v, f, smooth_vertex_normals(v, f))
