"""Malha de voxels→tetraedros a partir de QUALQUER sólido OCP (peça da biblioteca ou STEP).

Cada célula cujo centro está dentro do sólido (BRepClass3d_SolidClassifier) vira 6 tetraedros.
Geometria aproximada em ESCADA: o volume da malha difere do volume exato — o erro é reportado
e nunca escondido. Unidades: as do modelo (mm).
"""
from __future__ import annotations
import numpy as np
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.gp import gp_Pnt
from OCP.TopAbs import TopAbs_IN
from . import fea3d


def shape_bbox(shape):
    b = Bnd_Box(); BRepBndLib.Add_s(shape, b)
    return np.array([b.CornerMin().X(), b.CornerMin().Y(), b.CornerMin().Z()]), np.array([b.CornerMax().X(), b.CornerMax().Y(), b.CornerMax().Z()])


def exact_volume(shape) -> float:
    p = GProp_GProps(); BRepGProp.VolumeProperties_s(shape, p); return abs(p.Mass())


def mesh_from_shape(shape, h: float, max_cells: int = 200000):
    """Retorna (Mesh em coordenadas do modelo, info). `h` = aresta do voxel (mm)."""
    if h <= 0:
        raise ValueError("h deve ser positivo")
    lo, hi = shape_bbox(shape)
    lo, hi = np.round(lo, 5), np.round(hi, 5)      # remove a folga de 1e-7 do Bnd_Box (alinha a grade)
    n = np.maximum(np.ceil((hi - lo) / h - 1e-6).astype(int), 1)
    if int(np.prod(n)) > max_cells:
        raise ValueError(f"{int(np.prod(n))} células excedem o limite {max_cells}; aumente h")
    L = n * h  # caixa ligeiramente maior que o bbox, centralizada
    org = lo
    clf = BRepClass3d_SolidClassifier(shape)

    def inside(cx, cy, cz):
        clf.Perform(gp_Pnt(*(org + np.array([cx, cy, cz]))), 1e-7)
        return clf.State() == TopAbs_IN

    m = fea3d.box_mesh(L[0], L[1], L[2], n[0], n[1], n[2], mask=inside)
    if len(m.tets) == 0:
        raise ValueError("nenhuma célula dentro do sólido: reduza h")
    m.nodes = m.nodes + org
    P = m.nodes[m.tets]
    vm = float(np.einsum('ij,ij->i', np.cross(P[:, 1]-P[:, 0], P[:, 2]-P[:, 0]), P[:, 3]-P[:, 0]).sum() / 6)
    ve = exact_volume(shape)
    info = {"celulas": int(np.prod(n)), "nos": len(m.nodes), "tetraedros": len(m.tets), "h": h,
            "volume_malha_mm3": vm, "volume_exato_mm3": ve, "erro_volume_pct": 100 * (vm - ve) / ve}
    return m, info
