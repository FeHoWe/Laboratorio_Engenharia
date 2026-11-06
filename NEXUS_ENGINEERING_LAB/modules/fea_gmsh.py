"""Malhador conforme (Gmsh/OpenCASCADE): sólido OCP → tetraedros que seguem a superfície real (sem escada).

Gera Tet4 ou Tet10 (ordem 2, com arestas curvas projetadas na superfície; o Tet10 do NEXUS usa
isoparamétrico — massa assume arestas retas). Requer `pip install gmsh` (e libGLU no Linux).
"""
from __future__ import annotations
import os, tempfile
import numpy as np
from .fea3d import Mesh


def available() -> bool:
    try:
        import gmsh  # noqa: F401
        return True
    except Exception:
        return False


def mesh_from_shape(shape, size: float, order: int = 2, size_min: float | None = None):
    """size = tamanho alvo de aresta (mm). Retorna (Mesh, info)."""
    import gmsh
    from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
    if size <= 0 or order not in (1, 2):
        raise ValueError("size > 0 e order ∈ {1,2}")
    d = tempfile.mkdtemp(); path = os.path.join(d, "p.step")
    w = STEPControl_Writer(); w.Transfer(shape, STEPControl_AsIs); w.Write(path)
    gmsh.initialize(); gmsh.option.setNumber("General.Terminal", 0)
    try:
        gmsh.model.add("p"); gmsh.model.occ.importShapes(path); gmsh.model.occ.synchronize()
        gmsh.option.setNumber("Mesh.MeshSizeMax", size); gmsh.option.setNumber("Mesh.MeshSizeMin", size_min or size / 4)
        gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 12)
        gmsh.option.setNumber("Mesh.Algorithm3D", 1)
        gmsh.model.mesh.generate(3)
        if order == 2:
            gmsh.option.setNumber("Mesh.HighOrderOptimize", 0); gmsh.model.mesh.setOrder(2)
        tags, coords, _ = gmsh.model.mesh.getNodes()
        et = 4 if order == 1 else 11
        types, _, enodes = gmsh.model.mesh.getElements(3)
        conn = enodes[list(types).index(et)]
        conn = np.asarray(conn, dtype=np.int64).reshape(-1, 4 if order == 1 else 10)
        idx = {int(t): i for i, t in enumerate(tags)}
        tets = np.vectorize(idx.get)(conn)
        if order == 2:
            # Gmsh Tet10: ..., 4:(0-1) 5:(1-2) 6:(2-0) 7:(3-0) 8:(3-2) 9:(3-1) -> NEXUS: 7:(0-3) 8:(1-3) 9:(2-3)
            tets = tets[:, [0, 1, 2, 3, 4, 5, 6, 7, 9, 8]]
        nodes = np.asarray(coords).reshape(-1, 3)
        used = np.unique(tets); remap = -np.ones(len(nodes), int); remap[used] = np.arange(len(used))
        mesh = Mesh(nodes[used], remap[tets])
    finally:
        gmsh.finalize()
    from .fea_voxel import exact_volume
    P = mesh.nodes[mesh.tets[:, :4]]
    vol = np.einsum('ij,ij->i', np.cross(P[:, 1]-P[:, 0], P[:, 2]-P[:, 0]), P[:, 3]-P[:, 0]) / 6
    neg = vol < 0
    if neg.any():                                  # inverte vértices (e meios de aresta correspondentes)
        t = mesh.tets
        if t.shape[1] == 4:
            t[neg] = t[neg][:, [0, 2, 1, 3]]
        else:
            t[neg] = t[neg][:, [0, 2, 1, 3, 6, 5, 4, 7, 9, 8]]
        vol = np.abs(vol)
    ve = exact_volume(shape)
    return mesh, {"nos": len(mesh.nodes), "tetraedros": len(mesh.tets), "ordem": order, "volume_malha_mm3": float(vol.sum()),
                  "volume_exato_mm3": ve, "erro_volume_pct": float(100 * (vol.sum() - ve) / ve)}
