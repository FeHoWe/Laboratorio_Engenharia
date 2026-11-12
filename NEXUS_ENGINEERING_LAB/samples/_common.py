"""Utilidades comuns dos projetos predefinidos adicionais (V2.7)."""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from core.cad_engine import CadEngine, RawNode  # noqa: E402,F401
from core.geometry import translation_matrix  # noqa: E402
from samples import geo as g  # noqa: E402,F401
from samples.library import PARTS  # noqa: E402,F401


def at(x=0.0, y=0.0, z=0.0):
    return translation_matrix([x, y, z])


def L(name, shape, m=None):
    return RawNode(name, shape=shape, local_matrix=(at() if m is None else m))


def group(name, *kids):
    return RawNode(name, children=list(kids))


def write_step(builder, path):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    CadEngine().write_step([builder()], path)
    return path
