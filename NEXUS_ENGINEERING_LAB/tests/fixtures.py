"""Geradores de arquivos de teste (STEP, STL, OBJ, FCStd) criados em tempo de teste.

Nenhum arquivo binário é versionado: tudo é gerado a partir de primitivas reais
do OpenCascade, então os testes exercitam leitura/escrita de verdade.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import numpy as np
import trimesh
from OCP.BRep import BRep_Builder
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.BRepTools import BRepTools
from OCP.TopoDS import TopoDS_Compound
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

from core.cad_engine import CadEngine, RawNode
from core.geometry import translation_matrix


def box(dx, dy, dz, at=(0, 0, 0)):
    return BRepPrimAPI_MakeBox(gp_Pnt(*at), dx, dy, dz).Shape()


def cylinder(radius, height, at=(0, 0, 0), axis=(0, 0, 1)):
    return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(*at), gp_Dir(*axis)), radius, height).Shape()


def compound(*shapes):
    comp = TopoDS_Compound()
    builder = BRep_Builder()
    builder.MakeCompound(comp)
    for s in shapes:
        builder.Add(comp, s)
    return comp


def write_engine_step(engine: CadEngine, path: Path) -> Path:
    """STEP de um 'motor' simplificado.

    Motor
      ├─ Bloco              caixa 100x60x40 (centro em 50,30,20)
      ├─ Pistões            sub-montagem com 4 instâncias do MESMO pistão
      ├─ Virabrequim        cilindro CONCÊNTRICO ao centro do bloco (eixo X)
      └─ Eixo composto      1 objeto com 2 sólidos independentes
    """
    piston = cylinder(8, 30, at=(0, 0, 0))
    pistons = RawNode("Pistoes", children=[
        RawNode("Pistao", shape=piston, local_matrix=translation_matrix([20 * (i + 1), 30, 45]))
        for i in range(4)
    ])
    motor = RawNode("Motor", children=[
        RawNode("Bloco", shape=box(100, 60, 40)),
        pistons,
        RawNode("Virabrequim", shape=cylinder(6, 100, at=(0, 30, 20), axis=(1, 0, 0))),
        RawNode("Eixo composto", shape=compound(
            cylinder(4, 30, at=(0, -40, 0)), cylinder(4, 30, at=(60, -40, 0)))),
    ])
    engine.write_step([motor], path)
    return path


def write_two_body_stl(path: Path) -> Path:
    a = trimesh.creation.box(extents=(10, 10, 10))
    b = trimesh.creation.cylinder(radius=3, height=20)
    b.apply_translation([40, 0, 0])
    trimesh.util.concatenate([a, b]).export(str(path))
    return path


def write_two_object_obj(path: Path) -> Path:
    """OBJ com dois objetos nomeados, um com quad (polígono de 4 vértices)."""
    path.write_text(
        "# teste\n"
        "o Bloco\n"
        "v 0 0 0\nv 10 0 0\nv 10 10 0\nv 0 10 0\nv 0 0 10\nv 10 0 10\nv 10 10 10\nv 0 10 10\n"
        "f 1/1/1 4/2/1 3/3/1 2/4/1\n"          # quad com vt/vn
        "f 5 6 7 8\n"
        "f 1 2 6 5\n"                           # lateral: liga base e topo (um só corpo)
        "o Eixo\n"
        "v 20 0 0\nv 30 0 0\nv 25 10 0\nv 25 5 10\n"
        "f -4 -3 -2\nf -4 -2 -1\n",             # índices negativos
        encoding="utf-8")
    return path


def write_fcstd(path: Path) -> Path:
    """FCStd sintético com a estrutura real do Document.xml do FreeCAD."""
    shapes = {
        "Box": box(10, 20, 30),
        "Cyl": cylinder(5, 40, at=(100, 0, 0)),
        "Wedge": box(5, 5, 5),
        "Base": box(50, 50, 5),
    }
    tmp = path.parent / "_fc_tmp"
    tmp.mkdir(exist_ok=True)
    brps = {}
    for name, shape in shapes.items():
        f = tmp / f"{name}.brp"
        BRepTools.Write_s(shape, str(f))
        brps[name] = f

    def obj_xml(name, label, extra=""):
        return (f'<Object name="{name}"><Properties Count="3">'
                f'<Property name="Label" type="App::PropertyString"><String value="{label}"/></Property>'
                f'{extra}</Properties></Object>')

    def shape_prop(file):
        return f'<Property name="Shape" type="Part::PropertyPartShape"><Part file="{file}"/></Property>'

    def group_prop(*names):
        links = "".join(f'<Link value="{n}"/>' for n in names)
        return f'<Property name="Group" type="App::PropertyLinkList"><LinkList count="{len(names)}">{links}</LinkList></Property>'

    placement = ('<Property name="Placement" type="App::PropertyPlacement">'
                 '<PropertyPlacement Px="500" Py="0" Pz="0" Q0="0" Q1="0" Q2="0" Q3="1" A="0" Ox="0" Oy="0" Oz="1"/>'
                 '</Property>')
    document = f"""<?xml version='1.0' encoding='utf-8'?>
<Document SchemaVersion="4" ProgramVersion="1.0.0" FileVersion="1">
 <Objects Count="7" Dependencies="1">
  <Object type="Part::Box" name="Box"/>
  <Object type="Part::Cylinder" name="Cyl"/>
  <Object type="App::DocumentObjectGroup" name="Grupo1"/>
  <Object type="App::Part" name="Parte"/>
  <Object type="Part::Feature" name="Wedge"/>
  <Object type="Part::Feature" name="Base"/>
  <Object type="Sketcher::SketchObject" name="Sketch"/>
 </Objects>
 <ObjectData Count="7">
  {obj_xml("Box", "Caixa", shape_prop("Box.brp"))}
  {obj_xml("Cyl", "Cilindro", shape_prop("Cyl.brp"))}
  {obj_xml("Grupo1", "Grupo Um", group_prop("Box", "Cyl"))}
  {obj_xml("Parte", "Parte Montada", placement + group_prop("Wedge"))}
  {obj_xml("Wedge", "Cunha", shape_prop("Wedge.brp"))}
  {obj_xml("Base", "Base oculta", shape_prop("Base.brp"))}
  {obj_xml("Sketch", "Esboço", "")}
 </ObjectData>
</Document>"""
    gui = """<?xml version='1.0' encoding='utf-8'?>
<Document SchemaVersion="1"><ViewProviderData Count="1">
 <ViewProvider name="Base"><Properties Count="1">
  <Property name="Visibility" type="App::PropertyBool"><Bool value="false"/></Property>
 </Properties></ViewProvider></ViewProviderData></Document>"""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("Document.xml", document)
        zf.writestr("GuiDocument.xml", gui)
        for name, f in brps.items():
            zf.write(f, f"{name}.brp")
    for f in brps.values():
        f.unlink()
    tmp.rmdir()
    return path
