"""Exportação de modelos: STEP e FCStd (com hierarquia), STL e OBJ.

Honestidade sobre limites:
    * STEP precisa de geometria B-Rep. Componentes que vieram de malhas
      (STL/OBJ) NÃO são convertidos — são listados em ``ExportResult.skipped``.
    * Nomes em STEP saem sem acentos (portabilidade entre CADs); o projeto
      ``.nexus`` preserva os nomes originais completos.
    * FCStd: escrito diretamente (ZIP com Document.xml + um .brp por peça; grupos como
      ``App::DocumentObjectGroup``, peças como ``Part::Feature``, posição já no mundo, visibilidade
      em GuiDocument.xml). Relido pelo importador do NEXUS nos testes, mas NÃO validado abrindo no
      FreeCAD de verdade; não leva histórico paramétrico, materiais nem cenas.
    * ``include_explosion=True`` exporta a vista explodida atual; o padrão é
      exportar a montagem na posição original.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
from core.lazy import lazy_import
trimesh = lazy_import("trimesh")

from core.geometry import translation_matrix
from core.cad_engine import CadEngine, RawNode
from core.model import Component
from core.project_manager import Project

EXPORT_FILTER = "STEP (*.step *.stp);;FreeCAD (*.FCStd);;STL (*.stl);;Wavefront OBJ (*.obj)"


class ExportError(Exception):
    """Falha de exportação com mensagem em português."""


@dataclass
class ExportResult:
    path: Path
    format: str
    exported: int
    skipped: list[str] = field(default_factory=list)


class Exporter:
    def __init__(self, engine: CadEngine) -> None:
        self.engine = engine

    def export(self, project: Project, path: str | Path, include_explosion: bool = False,
               only_visible: bool = False) -> ExportResult:
        path = Path(path)
        ext = path.suffix.lower()
        try:
            if ext in (".step", ".stp"):
                return self._export_step(project, path, include_explosion, only_visible)
            if ext == ".fcstd":
                return self._export_fcstd(project, path, include_explosion, only_visible)
            if ext == ".stl":
                return self._export_stl(project, path, include_explosion, only_visible)
            if ext == ".obj":
                return self._export_obj(project, path, include_explosion, only_visible)
        except ExportError:
            raise
        except Exception as exc:
            raise ExportError(f"Falha ao exportar '{path.name}': {exc}") from exc
        raise ExportError(f"Formato de exportação '{path.suffix}' não suportado (use STEP, FCStd, STL ou OBJ).")

    # ------------------------------------------------------------------- util
    @staticmethod
    def _included(node: Component, only_visible: bool) -> bool:
        return node.visible or not only_visible

    def _leaf_list(self, project: Project, only_visible: bool) -> list[Component]:
        root = project.components.root
        leaves = []
        for leaf in root.leaves():
            if only_visible and not project.components.is_effectively_visible(leaf):
                continue
            leaves.append(leaf)
        return leaves

    # ------------------------------------------------------------------- STEP
    def _export_step(self, project: Project, path: Path, explosion: bool, only_visible: bool) -> ExportResult:
        skipped: list[str] = []
        count = {"n": 0}

        def convert(node: Component) -> Optional[RawNode]:
            if not self._included(node, only_visible):
                return None
            local = translation_matrix(node.offset) if explosion else np.eye(4)
            if node.shape is not None and not node.children:
                count["n"] += 1
                return RawNode(node.name, shape=node.shape, local_matrix=local)
            if node.has_geometry and node.shape is None and not node.children:
                skipped.append(node.name)
                return None
            kids = [k for k in (convert(c) for c in node.children) if k is not None]
            if not kids:
                return None
            return RawNode(node.name, children=kids, local_matrix=local)

        raw = convert(project.components.root)
        if raw is None or count["n"] == 0:
            raise ExportError("Não há geometria B-Rep exportável para STEP"
                              + (" (os componentes são malhas)." if skipped else "."))
        raw.local_matrix = np.eye(4)  # a raiz não se desloca
        self.engine.write_step([raw], path)
        return ExportResult(path, "STEP", count["n"], skipped)

    # ------------------------------------------------------------------ FCStd
    def _export_fcstd(self, project: Project, path: Path, explosion: bool, only_visible: bool) -> ExportResult:
        import tempfile
        import zipfile
        from xml.sax.saxutils import quoteattr

        objects: list[tuple[str, str]] = []           # (tipo, nome interno)
        data: list[str] = []
        brps: dict[str, Path] = {}
        hidden: list[str] = []
        skipped: list[str] = []
        counter = {"i": 0, "parts": 0}
        tmp = tempfile.TemporaryDirectory(prefix="nexus_fcstd_out_")

        def new_name(prefix: str) -> str:
            counter["i"] += 1
            return f"{prefix}{counter['i']:04d}"

        def prop_label(label: str) -> str:
            return f'<Property name="Label" type="App::PropertyString"><String value={quoteattr(label)}/></Property>'

        def convert(node: Component) -> Optional[str]:
            if not self._included(node, only_visible):
                return None
            if node.has_geometry and not node.children:
                if node.shape is None:
                    skipped.append(node.name)
                    return None
                shape = node.shape
                if explosion and np.linalg.norm(node.effective_offset()) > 1e-9:
                    shape = self.engine.transform(shape, translation_matrix(node.effective_offset()))
                name = new_name("Peca")
                f = Path(tmp.name) / f"{name}.brp"
                self.engine.write_brep_file(shape, f)
                brps[name] = f
                objects.append(("Part::Feature", name))
                data.append(f'<Object name="{name}"><Properties Count="2">{prop_label(node.name)}'
                            f'<Property name="Shape" type="Part::PropertyPartShape"><Part file="{name}.brp"/></Property>'
                            f'</Properties></Object>')
                if not node.visible:
                    hidden.append(name)
                counter["parts"] += 1
                return name
            kids = [k for k in (convert(c) for c in node.children) if k is not None]
            if not kids:
                return None
            name = new_name("Grupo")
            objects.append(("App::DocumentObjectGroup", name))
            links = "".join(f'<Link value="{k}"/>' for k in kids)
            data.append(f'<Object name="{name}"><Properties Count="2">{prop_label(node.name)}'
                        f'<Property name="Group" type="App::PropertyLinkList"><LinkList count="{len(kids)}">{links}</LinkList></Property>'
                        f'</Properties></Object>')
            if not node.visible:
                hidden.append(name)
            return name

        try:
            # filhos da raiz viram objetos de topo (a raiz é só o contêiner do projeto)
            for child in project.components.root.children:
                convert(child)
            if counter["parts"] == 0:
                raise ExportError("Não há geometria B-Rep exportável para FCStd"
                                  + (" (os componentes são malhas)." if skipped else "."))
            obj_list = "".join(f'<Object type="{t}" name="{n}"/>' for t, n in objects)
            document = ("<?xml version='1.0' encoding='utf-8'?>\n"
                        '<Document SchemaVersion="4" ProgramVersion="1.0.0" FileVersion="1">\n'
                        f' <Properties Count="1"><Property name="Label" type="App::PropertyString"><String value={quoteattr(project.name)}/></Property></Properties>\n'
                        f' <Objects Count="{len(objects)}" Dependencies="1">{obj_list}</Objects>\n'
                        f' <ObjectData Count="{len(data)}">{"".join(data)}</ObjectData>\n</Document>\n')
            gui = ("<?xml version='1.0' encoding='utf-8'?>\n"
                   f'<Document SchemaVersion="1"><ViewProviderData Count="{len(hidden)}">'
                   + "".join(f'<ViewProvider name="{h}"><Properties Count="1"><Property name="Visibility" '
                             f'type="App::PropertyBool"><Bool value="false"/></Property></Properties></ViewProvider>'
                             for h in hidden)
                   + "</ViewProviderData></Document>\n")
            tmp_out = path.with_name(path.name + ".tmp")
            with zipfile.ZipFile(tmp_out, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("Document.xml", document)
                zf.writestr("GuiDocument.xml", gui)
                for name, f in brps.items():
                    zf.write(f, f"{name}.brp")
            tmp_out.replace(path)
        finally:
            tmp.cleanup()
        return ExportResult(path, "FCStd", counter["parts"], skipped)

    # --------------------------------------------------------------- malhas
    def _world_mesh(self, project: Project, leaf: Component, explosion: bool):
        mesh = project.components.render_mesh(leaf)
        verts = mesh.vertices + (leaf.effective_offset() if explosion else 0.0)
        return verts, mesh.faces

    def _export_stl(self, project: Project, path: Path, explosion: bool, only_visible: bool) -> ExportResult:
        leaves = self._leaf_list(project, only_visible)
        if not leaves:
            raise ExportError("Não há componentes para exportar.")
        meshes = []
        for leaf in leaves:
            v, f = self._world_mesh(project, leaf, explosion)
            meshes.append(trimesh.Trimesh(v, f, process=False))
        trimesh.util.concatenate(meshes).export(str(path), file_type="stl")
        return ExportResult(path, "STL", len(leaves))

    def _export_obj(self, project: Project, path: Path, explosion: bool, only_visible: bool) -> ExportResult:
        leaves = self._leaf_list(project, only_visible)
        if not leaves:
            raise ExportError("Não há componentes para exportar.")
        lines = [f"# NEXUS ENGINEERING LAB — {project.name}", "# Unidades: mm"]
        base = 0
        used: dict[str, int] = {}
        for leaf in leaves:
            v, f = self._world_mesh(project, leaf, explosion)
            n = used.get(leaf.name, 0) + 1
            used[leaf.name] = n
            name = leaf.name if n == 1 else f"{leaf.name} #{n}"
            lines.append(f"o {name}")
            lines.extend(f"v {x:.6f} {y:.6f} {z:.6f}" for x, y, z in v)
            lines.extend(f"f {a + 1 + base} {b + 1 + base} {c + 1 + base}" for a, b, c in f)
            base += len(v)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return ExportResult(path, "OBJ", len(leaves))
