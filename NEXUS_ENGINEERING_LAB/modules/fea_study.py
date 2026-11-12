"""Estudo FEA completo: peça (biblioteca ou sólido OCP) → malha de voxels → NEXUS-Tet4 → resultado rastreado."""
from __future__ import annotations
import numpy as np
from . import fea3d, fea_voxel
from .result_trace import TracedResult

FACES = {"xmin": (0, -1), "xmax": (0, 1), "ymin": (1, -1), "ymax": (1, 1), "zmin": (2, -1), "zmax": (2, 1)}


def face_nodes(mesh, face: str, tol: float | None = None):
    ax, side = FACES[face]
    c = mesh.nodes[:, ax]; ref = c.min() if side < 0 else c.max()
    tol = tol if tol is not None else 1e-6 * max(1.0, abs(ref))
    return [i for i, v in enumerate(c) if abs(v - ref) <= tol]


def _mesh(shape, h, mesher, order):
    from . import fea_tet10, fea_gmsh
    if mesher == "gmsh":
        if not fea_gmsh.available():
            raise RuntimeError("Gmsh não disponível (pip install gmsh)")
        return fea_gmsh.mesh_from_shape(shape, h, order)
    m, info = fea_voxel.mesh_from_shape(shape, h)
    return (fea_tet10.to_quadratic(m) if order == 2 else m), info


def run(shape, h, E, nu, fixed_face, load_face, force, sigma_yield=None, nome="Estudo FEA", mesher="voxel", order=1) -> tuple[TracedResult, dict]:
    """E, nu e (opcional) sigma_yield são SEMPRE do usuário. mesher: 'voxel' (escada) ou 'gmsh' (conforme à superfície);
    order: 1 (Tet4, trava em flexão) ou 2 (Tet10, recomendado). Sem sigma_yield não há coeficiente de segurança."""
    from . import fea_tet10
    if fixed_face == load_face:
        raise ValueError("face fixa e face carregada devem ser diferentes")
    mesh, info = _mesh(shape, h, mesher, order)
    quad = mesh.tets.shape[1] == 10
    fx = face_nodes(mesh, fixed_face)
    ln = face_nodes(mesh, load_face)
    if not fx or not ln:
        raise ValueError("face sem nós (h muito grande?)")
    fixed = {i: (0, 1, 2) for i in fx}
    if quad:
        loads = fea_tet10.surface_load10(mesh, ln, force)
        u, vm, R, vol = fea_tet10.solve(mesh, E, nu, fixed, loads)
        sg, vmn = fea_tet10.nodal_stress(mesh, u, E, nu)
        vm_ref = float(vmn.max()); solver, ver = fea_tet10.SOLVER10, fea3d.SOLVER_VER
    else:
        loads = fea3d.surface_load(mesh, ln, force)
        u, vm, R, vol = fea3d.solve(mesh, E, nu, fixed, loads)
        vmn = None; vm_ref = float(vm.max()); solver, ver = fea3d.SOLVER, fea3d.SOLVER_VER
    react = np.array([sum(R[3*i + c] for i in fx) for c in range(3)])
    res = fea3d.to_traced(nome, mesh, E, nu, u, vm, vol)
    res.solver, res.solver_versao = solver, ver
    res.valores.update({"reacao_N": react.tolist(), "erro_volume_malha_pct": info["erro_volume_pct"], "vm_max_MPa": vm_ref,
                        "vm_max_tipo": "nodal suavizada (Tet10)" if quad else "média por elemento (Tet4)"})
    res.entradas.update({"h_mm": h, "face_fixa": fixed_face, "face_carga": load_face, "forca_N": list(map(float, force)), "malhador": mesher, "ordem": 2 if quad else 1})
    if quad:
        res.metodo = "Elasticidade linear 3D, Tet10 isoparamétrico (sem travamento), solução direta esparsa"
        res.limitacoes = ["verificação do código (não validação da sua peça): viga/Timoshenko <5%, placa com furo vs Peterson −1% (tests/)",
                          "linear, pequenas deformações, sem contato/plasticidade", "tensão em quina viva/apoio rígido é singular (cresce com o refino)"]
        if mesher == "voxel":
            res.limitacoes.append("malha em escada (voxel): tensão local NÃO confiável; use mesher='gmsh'")
    else:
        res.limitacoes.append("Tet4 trava em flexão: use order=2")
        if mesher == "voxel":
            res.limitacoes.append("geometria em escada (voxels): tensão máxima NÃO é confiável localmente")
    if sigma_yield:
        res.valores["fator_seguranca_escoamento_ref"] = sigma_yield / vm_ref
        res.premissas.append(f"limite de escoamento informado pelo usuário: {sigma_yield} MPa")
    return res, {"mesh": mesh, "u": u, "vm": vm, "vm_nodal": vmn, "info": info}


def convergencia(shape, hs, E, nu, fixed_face, load_face, force, tol_pct: float = 5.0, mesher="voxel", order=1):
    """Estudo de malha: roda a mesma análise em várias arestas h (decrescentes) e compara o deslocamento máximo.
    Convergido só se a variação entre as duas últimas malhas < tol_pct. Tensão máxima NÃO entra (singularidades de voxel)."""
    hs = sorted(hs, reverse=True)
    if len(hs) < 2:
        raise ValueError("informe ao menos 2 valores de h")
    rows = []
    for h in hs:
        r, d = run(shape, h, E, nu, fixed_face, load_face, force, mesher=mesher, order=order)
        rows.append({"h": h, "tetraedros": r.valores["elementos"], "u_max_mm": r.valores["u_max_mm"]})
    var = abs(rows[-1]["u_max_mm"] - rows[-2]["u_max_mm"]) / rows[-1]["u_max_mm"] * 100
    conv = var < tol_pct
    res = TracedResult("Estudo de convergência de malha", "SIMULACAO_NUMERICA", "Refino sucessivo de voxels (NEXUS-Tet4)",
                       {"malhas": rows, "variacao_ultimas_pct": var, "convergido": conv},
                       {"E_MPa": E, "nu": nu, "tol_pct": tol_pct},
                       ["mesmo carregamento e apoios em todas as malhas"],
                       ["convergência de deslocamento não prova correção do modelo", "voxels em escada: tensão local não converge"],
                       solver=r.solver, solver_versao=r.solver_versao)
    return res
