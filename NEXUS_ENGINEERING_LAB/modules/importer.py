"""Importação de projetos: STEP/STP, STL, OBJ e FCStd.

Formatos diferem no que preservam:

    ============  =======================================================
    Formato       O que o arquivo guarda
    ============  =======================================================
    STEP / STP    B-Rep exato + hierarquia de montagem + nomes + posições
    FCStd         B-Rep exato + grupos/partes do FreeCAD + visibilidade
                  (Documento ZIP: Document.xml + um .brp por objeto)
    OBJ           Malhas; separa por objetos ``o``/``g`` quando existirem
    STL           Uma única malha, sem estrutura nem nomes
    ============  =======================================================

O importador NUNCA trata o arquivo como "uma peça só" automaticamente: ele
constrói a árvore real e, em seguida, o analisador de sólidos classifica cada
objeto (um sólido, vários sólidos, malha com vários corpos...).
"""
from __future__ import annotations

import tempfile
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
from core.lazy import lazy_import
trimesh = lazy_import("trimesh")

from core.cad_engine import CadEngine, CadEngineError, RawNode, fix_text
from core.model import Component, ComponentKind, GeometryKind, IdGenerator, MeshData
from modules.solid_analyzer import AnalysisReport, analyze_tree

SUPPORTED_EXTENSIONS = {".step": "STEP", ".stp": "STEP", ".stl": "STL", ".obj": "OBJ", ".fcstd": "FCStd"}
FILE_DIALOG_FILTER = (
    "Projetos CAD (*.step *.stp *.stl *.obj *.FCStd);;"
    "STEP (*.step *.stp);;Malhas (*.stl *.obj);;FreeCAD (*.FCStd);;Todos os arquivos (*)"
)


# Objetos auxiliares do FreeCAD (planos de referência, esboços): não são peças.
_FC_IGNORED_TYPES = {"App::Origin", "App::Line", "App::Plane", "App::OriginGroupExtension",
                     "Sketcher::SketchObject"}


class ImportFailure(Exception):
    """Falha de importação com mensagem pronta para o usuário (português)."""


@dataclass
class ImportResult:
    root: Component
    format: str
    path: str
    report: AnalysisReport
    warnings: list[str] = field(default_factory=list)
    preserves_hierarchy: bool = False


class ProjectImporter:
    def __init__(self, engine: CadEngine, ids: Optional[IdGenerator] = None) -> None:
        self.engine = engine
        self.ids = ids or IdGenerator()

    # ------------------------------------------------------------------ entrada
    def import_file(self, path: str | Path) -> ImportResult:
        path = Path(path)
        if not path.is_file():
            raise ImportFailure(f"Arquivo não encontrado: {path}")
        ext = path.suffix.lower()
        fmt = SUPPORTED_EXTENSIONS.get(ext)
        if fmt is None:
            raise ImportFailure(
                f"Formato '{path.suffix}' não suportado. Use: STEP, STP, STL, OBJ ou FCStd.")
        if path.stat().st_size == 0:
            raise ImportFailure(f"O arquivo '{path.name}' está vazio.")

        warnings: list[str] = []
        try:
            if fmt == "STEP":
                root, hierarchy = self._import_step(path, warnings)
            elif fmt == "STL":
                root, hierarchy = self._import_stl(path, warnings)
            elif fmt == "OBJ":
                root, hierarchy = self._import_obj(path, warnings)
            else:
                root, hierarchy = self._import_fcstd(path, warnings)
        except ImportFailure:
            raise
        except CadEngineError as exc:
            raise ImportFailure(str(exc)) from exc
        except (zipfile.BadZipFile, ET.ParseError) as exc:
            raise ImportFailure(f"Arquivo '{path.name}' corrompido ou em formato inesperado: {exc}") from exc
        except Exception as exc:  # erro inesperado: nunca derrubar a interface
            raise ImportFailure(f"Erro inesperado ao importar '{path.name}': {exc}") from exc

        if not any(True for _ in root.leaves()):
            raise ImportFailure(f"'{path.name}' não contém nenhuma geometria utilizável.")
        self._dedupe_names(root)
        report = analyze_tree(root, self.engine)
        return ImportResult(root, fmt, str(path), report, warnings, hierarchy)

    # --------------------------------------------------------------------- util
    def _new(self, name: str, kind: ComponentKind, source: str, **kw) -> Component:
        return Component(id=self.ids.next(), name=name, kind=kind, source=source, **kw)

    def _project_root(self, path: Path) -> Component:
        return self._new(path.stem, ComponentKind.ASSEMBLY, path.name)

    @staticmethod
    def _dedupe_names(root: Component) -> None:
        """Instâncias repetidas (ex.: 4 parafusos) recebem sufixo #2, #3 ..."""
        for node in root.walk():
            seen: dict[str, int] = {}
            for child in node.children:
                n = seen.get(child.name, 0) + 1
                seen[child.name] = n
                if n > 1:
                    child.name = f"{child.name} #{n}"

    # --------------------------------------------------------------------- STEP
    def _import_step(self, path: Path, warnings: list[str]) -> tuple[Component, bool]:
        raws = self.engine.read_step(path)
        root = self._project_root(path)
        counter = {"part": 0, "asm": 0}

        def convert(raw: RawNode) -> Component:
            if raw.is_assembly:
                counter["asm"] += 1
                node = self._new(raw.name or f"Montagem {counter['asm']}", ComponentKind.ASSEMBLY, path.name,
                                 placement=raw.world_matrix.copy())
                for child in raw.children:
                    node.add_child(convert(child))
                return node
            counter["part"] += 1
            return self._new(raw.name or f"Peça {counter['part']}", ComponentKind.PART, path.name,
                             shape=raw.shape, placement=raw.world_matrix.copy())

        for raw in raws:
            root.add_child(convert(raw))
        # Estrutura "real" = existe alguma montagem ou mais de uma forma livre
        hierarchy = any(r.is_assembly for r in raws) or len(raws) > 1
        if not hierarchy:
            warnings.append("O STEP contém uma única forma sem montagem; "
                            "a separação em sólidos (se houver) está disponível em Componentes.")
        return root, hierarchy

    # ---------------------------------------------------------------------- STL
    def _import_stl(self, path: Path, warnings: list[str]) -> tuple[Component, bool]:
        mesh = trimesh.load(str(path), file_type="stl", force="mesh")
        if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) == 0:
            raise ImportFailure(f"O STL '{path.name}' não contém triângulos.")
        root = self._project_root(path)
        root.add_child(self._new(path.stem, ComponentKind.PART, path.name,
                                 mesh=MeshData(np.asarray(mesh.vertices), np.asarray(mesh.faces))))
        warnings.append("STL guarda apenas uma malha, sem nomes nem montagem. "
                        "Corpos desconexos são identificados e podem ser separados em Componentes.")
        return root, False

    # ---------------------------------------------------------------------- OBJ
    def _import_obj(self, path: Path, warnings: list[str]) -> tuple[Component, bool]:
        objects = parse_obj(path)
        if not objects:
            raise ImportFailure(f"O OBJ '{path.name}' não contém faces.")
        root = self._project_root(path)
        for name, verts, faces in objects:
            root.add_child(self._new(name, ComponentKind.PART, path.name, mesh=MeshData(verts, faces)))
        if len(objects) == 1:
            warnings.append("OBJ sem grupos nomeados: tratado como uma malha única.")
        return root, len(objects) > 1

    # -------------------------------------------------------------------- FCStd
    def _import_fcstd(self, path: Path, warnings: list[str]) -> tuple[Component, bool]:
        with zipfile.ZipFile(path) as zf:
            names = set(zf.namelist())
            if "Document.xml" not in names:
                raise ImportFailure(f"'{path.name}' não é um FCStd válido (Document.xml ausente).")
            doc = ET.fromstring(zf.read("Document.xml"))
            visibility = _fcstd_visibility(zf) if "GuiDocument.xml" in names else {}
            types = {o.get("name"): o.get("type", "") for o in doc.findall("./Objects/Object")}
            data = {}
            for obj in doc.findall("./ObjectData/Object"):
                data[obj.get("name")] = _fcstd_properties(obj)

            consumed: set[str] = set()   # objetos usados dentro de Part::Compound ("Links")
            child_of_group: set[str] = set()
            for props in data.values():
                consumed.update(props.get("Links", []))
                child_of_group.update(props.get("Group", []))

            tmp = tempfile.TemporaryDirectory(prefix="nexus_fcstd_")
            skipped: list[str] = []
            visited: set[str] = set()
            root = self._project_root(path)

            def build(name: str, parent_matrix: np.ndarray) -> Optional[Component]:
                if name in visited or name not in data:
                    return None
                visited.add(name)
                props = data[name]
                label = props.get("Label") or name
                fc_type = types.get(name, "")
                matrix = parent_matrix
                if "Group" in props:
                    own = props.get("Placement", np.eye(4)) if fc_type == "App::Part" else np.eye(4)
                    matrix = parent_matrix @ own
                    kind = ComponentKind.ASSEMBLY if fc_type == "App::Part" else ComponentKind.GROUP
                    node = self._new(label, kind, path.name, placement=matrix.copy(),
                                     metadata={"fc_type": fc_type, "fc_name": name})
                    node.visible = visibility.get(name, True)
                    for child_name in props["Group"]:
                        child = build(child_name, matrix)
                        if child is not None:
                            node.add_child(child)
                    return node if node.children else None
                if fc_type in _FC_IGNORED_TYPES:
                    return None
                brp = props.get("Shape")
                if not brp or brp not in names:
                    skipped.append(label)
                    return None
                dest = Path(tmp.name) / f"{name}.brp"
                dest.write_bytes(zf.read(brp))
                shape = self.engine.read_brep_file(dest)
                if not np.allclose(parent_matrix, np.eye(4)):
                    shape = self.engine.transform(shape, parent_matrix)
                node = self._new(label, ComponentKind.PART, path.name, shape=shape,
                                 placement=parent_matrix.copy(),
                                 parametric=(fc_type != "Part::Feature"),
                                 metadata={"fc_type": fc_type, "fc_name": name})
                node.visible = visibility.get(name, True)
                return node

            try:
                for name in data:
                    if name in child_of_group or name in consumed:
                        continue
                    node = build(name, np.eye(4))
                    if node is not None:
                        root.add_child(node)
            finally:
                tmp.cleanup()

        try:
            from modules.declared_joints import read_fcstd_joints
            with zipfile.ZipFile(path) as zf2:
                fc_joints = read_fcstd_joints(zf2)
            if fc_joints:
                root.metadata["fc_joints"] = [j.to_dict() for j in fc_joints]
                warnings.append(f"{len(fc_joints)} junta(s) gravada(s) no FCStd lida(s) (apenas listadas em Analyze › Relações de "
                                "montagem; não viram restrições nem movimento).")
        except Exception as exc:  # junta ilegível não derruba a importação
            warnings.append(f"Juntas do FCStd não puderam ser lidas: {exc}")
        if skipped:
            warnings.append(f"{len(skipped)} objeto(s) do FreeCAD sem geometria ignorado(s): "
                            + ", ".join(skipped[:6]) + ("..." if len(skipped) > 6 else ""))
        if any(c.parametric for c in root.leaves()):
            warnings.append("Objetos paramétricos do FreeCAD foram importados como geometria final; "
                            "o histórico de construção não é editável no NEXUS V1.0.")
        return root, True


# ============================================================ OBJ e FCStd (parsers)
def parse_obj(path: Path) -> list[tuple[str, np.ndarray, np.ndarray]]:
    """Lê um OBJ e devolve ``[(nome, vértices, faces)]`` por objeto/grupo.

    Suporta ``v``, ``f`` (formatos ``v``, ``v/vt``, ``v//vn``, ``v/vt/vn``), índices
    negativos, polígonos (triangulados em leque) e separação por ``o``/``g``.
    """
    vertices: list[tuple[float, float, float]] = []
    groups: dict[str, list[tuple[int, int, int]]] = {}
    current = "Objeto"
    counter = 0
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line_no, line in enumerate(fh, start=1):
                if line.startswith("v "):
                    p = line.split()
                    vertices.append((float(p[1]), float(p[2]), float(p[3])))
                elif line.startswith("f "):
                    idx = []
                    for tok in line.split()[1:]:
                        i = int(tok.split("/")[0])
                        idx.append(i - 1 if i > 0 else len(vertices) + i)
                    tris = groups.setdefault(current, [])
                    for k in range(1, len(idx) - 1):
                        tris.append((idx[0], idx[k], idx[k + 1]))
                elif line.startswith(("o ", "g ")):
                    counter += 1
                    current = line[2:].strip() or f"Objeto {counter}"
    except (ValueError, IndexError) as exc:
        raise ImportFailure(f"OBJ inválido (linha {line_no}): {exc}") from exc

    result = []
    all_v = np.asarray(vertices, dtype=np.float64).reshape(-1, 3)
    for name, tris in groups.items():
        if not tris:
            continue
        f = np.asarray(tris, dtype=np.int64)
        if f.min() < 0 or f.max() >= len(all_v):
            raise ImportFailure(f"OBJ inválido: o objeto '{name}' referencia vértices inexistentes.")
        used, inverse = np.unique(f, return_inverse=True)
        result.append((name, all_v[used], inverse.reshape(-1, 3)))
    return result


def _fcstd_visibility(zf: zipfile.ZipFile) -> dict[str, bool]:
    out: dict[str, bool] = {}
    try:
        gui = ET.fromstring(zf.read("GuiDocument.xml"))
    except ET.ParseError:
        return out
    for vp in gui.iter("ViewProvider"):
        for prop in vp.iter("Property"):
            if prop.get("name") == "Visibility":
                b = prop.find("Bool")
                if b is not None:
                    out[vp.get("name")] = b.get("value") == "true"
    return out


def _fcstd_properties(obj: ET.Element) -> dict:
    props: dict = {}
    for prop in obj.findall("./Properties/Property"):
        name = prop.get("name")
        if name == "Label":
            s = prop.find("String")
            if s is not None:
                props["Label"] = fix_text(s.get("value"))
        elif name == "Placement":
            p = prop.find("PropertyPlacement")
            if p is not None:
                props["Placement"] = _placement_matrix(p)
        elif name == "Shape":
            part = prop.find("Part")
            if part is not None and part.get("file"):
                props["Shape"] = part.get("file")
        elif name in ("Group", "Links"):
            ll = prop.find("LinkList")
            if ll is not None:
                props[name] = [lk.get("value") for lk in ll.findall("Link") if lk.get("value")]
            elif name == "Group":
                props[name] = []
    return props


def _placement_matrix(p: ET.Element) -> np.ndarray:
    """Posição + quaternion (x, y, z, w = Q0..Q3 no FreeCAD) -> matriz 4x4."""
    x, y, z, w = (float(p.get(k, 0)) for k in ("Q0", "Q1", "Q2", "Q3"))
    n = np.sqrt(x * x + y * y + z * z + w * w) or 1.0
    x, y, z, w = x / n, y / n, z / n, w / n
    m = np.eye(4)
    m[:3, :3] = [
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ]
    m[:3, 3] = [float(p.get("Px", 0)), float(p.get("Py", 0)), float(p.get("Pz", 0))]
    return m
