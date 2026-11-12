"""Juntas GRAVADAS em arquivos FreeCAD (.FCStd) — V1.8.

O Assembly do FreeCAD (1.0+) grava cada junta como um objeto com as propriedades ``JointType``,
``Reference1``/``Reference2`` (objeto + sub-elemento, ex.: ``Face3``) e ``Placement1``/``Placement2``.
Este módulo apenas LÊ esses dados do ``Document.xml`` e os relaciona às peças importadas pelo nome
interno do objeto (``metadata["fc_name"]``).

HONESTIDADE:
    * O leitor foi escrito a partir do formato documentado e testado só com ``Document.xml`` sintéticos
      no mesmo formato; NÃO foi validado com arquivos gerados pelo FreeCAD de verdade.
    * As juntas são lidas e listadas; o NEXUS NÃO as usa como restrição nem para simular movimento.
    * Se a lista de nomes do enum não estiver no arquivo, assume-se a ordem do FreeCAD 1.0 (rotulado).
"""
from __future__ import annotations

import re
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

KIND_DECLARED = "Gravada (FreeCAD)"

# ordem do enum JointType no FreeCAD 1.0 (usada só quando o arquivo não traz a lista)
DEFAULT_JOINT_TYPES = ["Fixed", "Revolute", "Cylindrical", "Slider", "Ball", "Distance", "Parallel",
                       "Perpendicular", "Angle", "RackPinion", "Screw", "Gears", "Belt"]

JOINT_LABELS = {
    "Fixed": "Fixa", "Revolute": "Rotativa (revolute)", "Cylindrical": "Cilíndrica", "Slider": "Deslizante (slider)",
    "Ball": "Esférica", "Distance": "Distância", "Parallel": "Paralela", "Perpendicular": "Perpendicular",
    "Angle": "Ângulo", "RackPinion": "Cremalheira-pinhão", "Screw": "Parafuso", "Gears": "Engrenagens", "Belt": "Correia",
}


@dataclass
class DeclaredJoint:
    name: str                 # nome interno do objeto-junta
    label: str
    joint_type: str
    type_assumed: bool        # True se o nome do tipo veio da ordem padrão do FreeCAD 1.0
    obj1: str
    sub1: str
    obj2: str
    sub2: str

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "DeclaredJoint":
        return DeclaredJoint(**d)


def _link_of(prop: Optional[ET.Element]) -> tuple[str, str]:
    """(objeto, sub-elemento) de uma propriedade XLink/XLinkSub/Link/LinkSub (tolerante a variações)."""
    if prop is None:
        return "", ""
    obj, sub = "", ""
    for el in prop.iter():
        tag = el.tag
        if tag in ("XLink", "XLinkSub", "Link", "LinkSub"):
            for attr in ("name", "obj", "value"):
                v = el.get(attr)
                if v and not obj and attr != "value":
                    obj = v
                elif v and not obj and tag in ("Link", "LinkSub") and not v.isdigit():
                    obj = v
        if tag == "Sub" and not sub:
            sub = el.get("value", "")
    return obj, sub


def read_fcstd_joints(path_or_zip) -> list[DeclaredJoint]:
    """Lê as juntas do Document.xml de um FCStd. Devolve [] se não houver."""
    if isinstance(path_or_zip, zipfile.ZipFile):
        raw = path_or_zip.read("Document.xml")
    else:
        with zipfile.ZipFile(path_or_zip) as zf:
            raw = zf.read("Document.xml")
    return parse_document_xml(raw)


def parse_document_xml(raw: bytes | str) -> list[DeclaredJoint]:
    doc = ET.fromstring(raw)
    out: list[DeclaredJoint] = []
    for obj in doc.findall("./ObjectData/Object"):
        props = {p.get("name"): p for p in obj.findall("./Properties/Property")}
        if "JointType" not in props or "Reference1" not in props or "Reference2" not in props:
            continue
        jp = props["JointType"]
        names = [e.get("value") for e in jp.iter("Enum") if e.get("value")]
        assumed = not names
        names = names or DEFAULT_JOINT_TYPES
        idx_el = jp.find("Integer")
        try:
            idx = int(idx_el.get("value")) if idx_el is not None else -1
        except (TypeError, ValueError):
            idx = -1
        jtype = names[idx] if 0 <= idx < len(names) else "Desconhecida"
        o1, s1 = _link_of(props["Reference1"])
        o2, s2 = _link_of(props["Reference2"])
        label_el = props.get("Label")
        label = ""
        if label_el is not None and label_el.find("String") is not None:
            label = label_el.find("String").get("value", "")
        out.append(DeclaredJoint(obj.get("name", ""), label or obj.get("name", ""), jtype, assumed, o1, s1, o2, s2))
    return out


def resolve_name(fc_name: str, sub: str, by_fc_name: dict):
    """Acha o componente: pelo objeto da junta; se falhar, por qualquer parte do caminho do sub-elemento."""
    if fc_name in by_fc_name:
        return by_fc_name[fc_name]
    for tok in re.split(r"[./]", sub or ""):
        if tok in by_fc_name:
            return by_fc_name[tok]
    return None
