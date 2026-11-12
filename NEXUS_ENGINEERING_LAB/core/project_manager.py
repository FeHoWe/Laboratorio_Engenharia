"""Gerenciamento de projetos: novo, abrir, salvar, salvar como, histórico.

Formato nativo ``.nexus`` (arquivo ZIP):

    project.json          hierarquia, nomes, materiais, offsets da explosão, histórico
    shapes/<id>.bin       geometria B-Rep exata (binário OpenCascade)
    meshes/<id>.npz       malhas (STL/OBJ) — vértices e faces
    shapes/<id>.orig.bin  geometria original de objetos separados (permite desfazer)

Por que não gravar FCStd como formato nativo?  FCStd é um documento do FreeCAD
(com árvore de recursos paramétricos) e só o próprio FreeCAD garante um arquivo
válido. O NEXUS lê FCStd, mas grava ``.nexus`` (que preserva TUDO: explosão,
materiais, histórico) e exporta STEP/STL/OBJ para intercâmbio. A gravação de
FCStd fica para uma versão futura, quando o backend FreeCAD for avaliado.
"""
from __future__ import annotations

import json
import os
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np

from core.assembly_manager import AssemblyManager
from core.cad_engine import CadEngine
from core.component_manager import ComponentManager
from core.model import Component, ComponentKind, GeometryKind, IdGenerator, MeshData
from modules.material_manager import MaterialLibrary
from modules.scene_manager import SceneStore

FORMAT_VERSION = 1
PROJECT_EXTENSION = ".nexus"
PROJECT_FILTER = "Projeto NEXUS (*.nexus)"


class ProjectError(Exception):
    """Erro de projeto com mensagem pronta para o usuário (português)."""


@dataclass
class HistoryEntry:
    timestamp: str
    action: str
    detail: str = ""


class ChangeHistory:
    """Registro cronológico de alterações (importação, explosão, materiais...)."""

    def __init__(self, entries: Optional[list[HistoryEntry]] = None) -> None:
        self.entries: list[HistoryEntry] = entries or []

    def record(self, action: str, detail: str = "") -> HistoryEntry:
        entry = HistoryEntry(datetime.now().isoformat(timespec="seconds"), action, detail)
        self.entries.append(entry)
        return entry

    def to_list(self) -> list[dict]:
        return [e.__dict__.copy() for e in self.entries]

    @staticmethod
    def from_list(items: list[dict]) -> "ChangeHistory":
        return ChangeHistory([HistoryEntry(**i) for i in items])


class Project:
    """Estado completo de um projeto aberto."""

    def __init__(self, name: str, engine: CadEngine) -> None:
        self.name = name
        self.engine = engine
        self.path: Optional[Path] = None
        self.dirty = False
        self.created = datetime.now().isoformat(timespec="seconds")
        self.source_files: list[str] = []
        self.history = ChangeHistory()
        self.scenes = SceneStore()
        self.materials = MaterialLibrary()
        self.ids = IdGenerator()
        self.components = ComponentManager(engine, ids=self.ids)
        self.assembly = AssemblyManager(self.components)

    def set_root(self, root: Component) -> None:
        self.components.set_root(root)
        self.assembly = AssemblyManager(self.components)

    def log(self, action: str, detail: str = "", dirty: bool = True) -> None:
        self.history.record(action, detail)
        if dirty:
            self.dirty = True

    @property
    def title(self) -> str:
        return self.name + (" •" if self.dirty else "")


class ProjectManager:
    def __init__(self, engine: CadEngine) -> None:
        self.engine = engine

    # -------------------------------------------------------------------- novo
    def new_project(self, name: str = "Novo projeto") -> Project:
        project = Project(name, self.engine)
        root = Component(id=project.ids.next(), name=name, kind=ComponentKind.ASSEMBLY)
        project.set_root(root)
        project.log("Projeto criado", name)
        return project

    # ------------------------------------------------------------------- salvar
    def save(self, project: Project, path: Optional[str | Path] = None) -> Path:
        target = Path(path) if path else project.path
        if target is None:
            raise ProjectError("O projeto ainda não tem arquivo; use 'Salvar como'.")
        if target.suffix.lower() != PROJECT_EXTENSION:
            target = target.with_suffix(PROJECT_EXTENSION)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp_target = target.with_name(target.name + ".tmp")
        try:
            with tempfile.TemporaryDirectory(prefix="nexus_save_") as tmp, \
                    zipfile.ZipFile(tmp_target, "w", zipfile.ZIP_DEFLATED) as zf:
                tree = self._serialize(project.components.root, zf, Path(tmp))
                project.history.record("Projeto salvo", target.name)
                doc = {
                    "nexus_format": FORMAT_VERSION,
                    "name": project.name,
                    "created": project.created,
                    "modified": datetime.now().isoformat(timespec="seconds"),
                    "id_counter": project.ids.counter,
                    "source_files": project.source_files,
                    "custom_materials": [{"name": m.name, "density_g_cm3": m.density_g_cm3}
                                         for m in project.materials.customs()],
                    # instantâneo dos materiais do banco usados: o projeto abre igual mesmo sem o banco
                    "used_db_materials": [{"name": m.name, "density_g_cm3": m.density_g_cm3, "source": m.source}
                                          for m in project.materials.used_db_materials(
                                              n.material for n in project.components.root.walk())],
                    "scenes": project.scenes.to_list(),
                    "history": project.history.to_list(),
                    "root": tree,
                }
                zf.writestr("project.json", json.dumps(doc, ensure_ascii=False, indent=2))
            os.replace(tmp_target, target)
        except Exception as exc:
            if tmp_target.exists():
                tmp_target.unlink()
            raise ProjectError(f"Não foi possível salvar o projeto: {exc}") from exc
        project.path = target
        project.dirty = False
        return target

    def _serialize(self, node: Component, zf: zipfile.ZipFile, tmp: Path) -> dict:
        entry = {
            "id": node.id, "name": node.name, "kind": node.kind.value,
            "geometry_kind": node.geometry_kind.value,
            "visible": node.visible, "material": node.material,
            "offset": [float(x) for x in node.offset],
            "placement": [float(x) for x in node.placement.reshape(-1)],
            "parametric": node.parametric, "source": node.source, "metadata": node.metadata,
            "geometry": self._write_geometry(node.id, node.shape, node.mesh, zf, tmp, ""),
            "split_backup": None,
            "children": [self._serialize(c, zf, tmp) for c in node.children],
        }
        if node.split_backup is not None:
            b = node.split_backup
            entry["split_backup"] = {
                "geometry": self._write_geometry(node.id, b["shape"], b["mesh"], zf, tmp, ".orig"),
                "geometry_kind": b["geometry_kind"].value,
                "kind": b["kind"].value,
            }
        return entry

    def _write_geometry(self, cid: str, shape, mesh: Optional[MeshData], zf: zipfile.ZipFile,
                        tmp: Path, suffix: str) -> Optional[dict]:
        if shape is not None:
            arc = f"shapes/{cid}{suffix}.bin"
            local = tmp / f"{cid}{suffix}.bin"
            self.engine.write_shape_bin(shape, local)
            zf.write(local, arc)
            return {"type": "brep", "file": arc}
        if mesh is not None and not mesh.is_empty:
            arc = f"meshes/{cid}{suffix}.npz"
            local = tmp / f"{cid}{suffix}.npz"
            np.savez_compressed(local, vertices=mesh.vertices, faces=mesh.faces)
            zf.write(local, arc)
            return {"type": "mesh", "file": arc}
        return None

    # -------------------------------------------------------------------- abrir
    def open(self, path: str | Path) -> Project:
        path = Path(path)
        if not path.is_file():
            raise ProjectError(f"Arquivo não encontrado: {path}")
        try:
            with zipfile.ZipFile(path) as zf, tempfile.TemporaryDirectory(prefix="nexus_open_") as tmp:
                if "project.json" not in zf.namelist():
                    raise ProjectError(f"'{path.name}' não é um projeto NEXUS válido.")
                doc = json.loads(zf.read("project.json").decode("utf-8"))
                version = doc.get("nexus_format")
                if version != FORMAT_VERSION:
                    raise ProjectError(f"Versão de projeto não suportada ({version}); esperada {FORMAT_VERSION}.")
                project = Project(doc.get("name", path.stem), self.engine)
                project.created = doc.get("created", project.created)
                project.source_files = list(doc.get("source_files", []))
                project.history = ChangeHistory.from_list(doc.get("history", []))
                project.scenes = SceneStore.from_list(doc.get("scenes", []))
                for m in doc.get("custom_materials", []):
                    project.materials.add_custom(m["name"], m["density_g_cm3"])
                for m in doc.get("used_db_materials", []):
                    project.materials.restore_snapshot(m["name"], m["density_g_cm3"])
                root = self._deserialize(doc["root"], zf, Path(tmp))
                project.ids = IdGenerator(int(doc.get("id_counter", 0)))
                project.components.ids = project.ids
                project.set_root(root)
        except ProjectError:
            raise
        except (zipfile.BadZipFile, json.JSONDecodeError, KeyError, ValueError) as exc:
            raise ProjectError(f"Projeto corrompido ou ilegível ('{path.name}'): {exc}") from exc
        except Exception as exc:
            raise ProjectError(f"Falha ao abrir '{path.name}': {exc}") from exc
        project.path = path
        project.dirty = False
        project.log("Projeto aberto", path.name, dirty=False)
        return project

    def _deserialize(self, entry: dict, zf: zipfile.ZipFile, tmp: Path) -> Component:
        shape, mesh = self._read_geometry(entry.get("geometry"), zf, tmp)
        node = Component(
            id=entry["id"], name=entry["name"], kind=ComponentKind(entry["kind"]),
            shape=shape, mesh=mesh, geometry_kind=GeometryKind(entry["geometry_kind"]),
            placement=np.array(entry["placement"], dtype=np.float64).reshape(4, 4),
            visible=entry["visible"], material=entry.get("material"),
            offset=np.array(entry["offset"], dtype=np.float64),
            parametric=entry.get("parametric", False), source=entry.get("source", ""),
            metadata=entry.get("metadata", {}),
        )
        sb = entry.get("split_backup")
        if sb:
            b_shape, b_mesh = self._read_geometry(sb["geometry"], zf, tmp)
            node.split_backup = {"shape": b_shape, "mesh": b_mesh,
                                 "geometry_kind": GeometryKind(sb["geometry_kind"]),
                                 "kind": ComponentKind(sb["kind"])}
        for child in entry.get("children", []):
            node.add_child(self._deserialize(child, zf, tmp))
        return node

    def _read_geometry(self, info: Optional[dict], zf: zipfile.ZipFile, tmp: Path):
        if not info:
            return None, None
        data = zf.read(info["file"])
        local = tmp / Path(info["file"]).name
        local.write_bytes(data)
        if info["type"] == "brep":
            return self.engine.read_shape_bin(local), None
        with np.load(local) as npz:
            return None, MeshData(npz["vertices"], npz["faces"])
