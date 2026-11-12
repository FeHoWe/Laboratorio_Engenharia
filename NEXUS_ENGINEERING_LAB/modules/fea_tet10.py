"""Elemento tetraédrico QUADRÁTICO (Tet10, isoparamétrico) — sem travamento de flexão.

Ordem dos nós: 0-3 vértices; 4:(0-1) 5:(1-2) 6:(2-0) 7:(0-3) 8:(1-3) 9:(2-3).
Rigidez: regra de 4 pontos (exata p/ elementos de arestas retas). Massa consistente: tabela
analítica exata (assume arestas retas). Tensão por elemento = média nos 4 pontos de Gauss.
Mesma interface de unidades de fea3d (mm, N, MPa; densidade em t/mm³).
"""
from __future__ import annotations
import math
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spl
from .fea3d import Mesh, _D, SOLVER_VER, _safe_solve

SOLVER10 = "NEXUS-Tet10"
_A, _B_ = 0.5854101966249685, 0.1381966011250105
_GP = [(_B_, _B_, _B_), (_A, _B_, _B_), (_B_, _A, _B_), (_B_, _B_, _A)]   # (ξ1,ξ2,ξ3)
_EDGES = [(0, 1), (1, 2), (2, 0), (0, 3), (1, 3), (2, 3)]


def to_quadratic(mesh: Mesh) -> Mesh:
    """Adiciona nós de meio de aresta (arestas retas). Se a malha já é Tet10, devolve igual."""
    if mesh.tets.shape[1] == 10:
        return mesh
    nodes = [tuple(p) for p in mesh.nodes]; cache = {}; out = []
    for t in mesh.tets:
        row = list(t)
        for a, b in _EDGES:
            key = (min(t[a], t[b]), max(t[a], t[b]))
            if key not in cache:
                cache[key] = len(nodes); nodes.append(tuple((mesh.nodes[t[a]] + mesh.nodes[t[b]]) / 2))
            row.append(cache[key])
        out.append(row)
    return Mesh(np.array(nodes), np.array(out, dtype=int))


def _dN_dxi(xi):
    x1, x2, x3 = xi; L = np.array([1 - x1 - x2 - x3, x1, x2, x3])
    dL = np.zeros((10, 4))
    for i in range(4):
        dL[i, i] = 4 * L[i] - 1
    for k, (a, b) in enumerate(_EDGES):
        dL[4 + k, a] = 4 * L[b]; dL[4 + k, b] = 4 * L[a]
    return dL[:, 1:] - dL[:, [0]]          # (10,3) em ξ1..ξ3


def _Bmat(P, xi):
    J = _dN_dxi(xi).T @ P                  # (3,3)
    detJ = np.linalg.det(J)
    g = np.linalg.solve(J, _dN_dxi(xi).T)  # (3,10) dN/dx
    B = np.zeros((6, 30))
    for a in range(10):
        bx, by, bz = g[:, a]
        B[0, 3*a] = bx; B[1, 3*a+1] = by; B[2, 3*a+2] = bz
        B[3, 3*a] = by; B[3, 3*a+1] = bx; B[4, 3*a+1] = bz; B[4, 3*a+2] = by; B[5, 3*a] = bz; B[5, 3*a+2] = bx
    return B, detJ


def _Bbatch(P, xi):
    """P:(m,10,3) → B:(m,6,30), detJ:(m,)"""
    dN = _dN_dxi(xi)                                   # (10,3)
    J = np.einsum('aj,mak->mjk', dN, P)                # (m,3,3)
    detJ = np.linalg.det(J)
    g = np.linalg.solve(J, np.broadcast_to(dN.T, (len(P), 3, 10)))   # (m,3,10)
    B = np.zeros((len(P), 6, 30))
    for a in range(10):
        bx, by, bz = g[:, 0, a], g[:, 1, a], g[:, 2, a]
        B[:, 0, 3*a] = bx; B[:, 1, 3*a+1] = by; B[:, 2, 3*a+2] = bz
        B[:, 3, 3*a] = by; B[:, 3, 3*a+1] = bx; B[:, 4, 3*a+1] = bz; B[:, 4, 3*a+2] = by; B[:, 5, 3*a] = bz; B[:, 5, 3*a+2] = bx
    return B, detJ


def _Ke(P, D):
    K = np.zeros((30, 30)); Bs = []
    for xi in _GP:
        B, dj = _Bmat(P, xi)
        if dj <= 0:
            raise ValueError("elemento Tet10 invertido/degenerado")
        K += B.T @ D @ B * dj / 24.0; Bs.append(B)
    return K, Bs


# --- massa consistente exata: N como polinômios nas coordenadas de volume (L0..L3)
def _poly_mul(p, q):
    r = {}
    for e1, c1 in p.items():
        for e2, c2 in q.items():
            e = tuple(a + b for a, b in zip(e1, e2)); r[e] = r.get(e, 0.0) + c1 * c2
    return r


def _mass_ref():
    def mono(*idx, c=1.0):
        e = [0, 0, 0, 0]
        for i in idx: e[i] += 1
        return tuple(e), c
    N = []
    for i in range(4):
        N.append({mono(i, i)[0]: 2.0, mono(i)[0]: -1.0})
    for a, b in _EDGES:
        N.append({mono(a, b)[0]: 4.0})
    M = np.zeros((10, 10))
    for i in range(10):
        for j in range(10):
            for e, c in _poly_mul(N[i], N[j]).items():
                M[i, j] += c * 6 * np.prod([math.factorial(k) for k in e]) / math.factorial(sum(e) + 3)
    return M          # multiplicar por V (volume do tet)


_MREF = _mass_ref()


def surface_load10(mesh: Mesh, nodes_sel, force) -> dict:
    sel = set(int(i) for i in nodes_sel)
    faces = ((0, 1, 2, 4, 5, 6), (0, 1, 3, 4, 8, 7), (0, 2, 3, 6, 9, 7), (1, 2, 3, 5, 9, 8))
    cnt = {}
    for t in mesh.tets:
        for f in faces:
            key = tuple(sorted(int(t[a]) for a in f[:3])); cnt.setdefault(key, []).append([int(t[a]) for a in f])
    w, tot = {}, 0.0
    for key, lst in cnt.items():
        if len(lst) != 1 or not all(int(k) in sel for k in lst[0]):
            continue
        n6 = lst[0]; p = mesh.nodes[n6[:3]]
        A = 0.5 * np.linalg.norm(np.cross(p[1] - p[0], p[2] - p[0])); tot += A
        for k in n6[3:]: w[k] = w.get(k, 0.0) + A / 3         # carga consistente: 0 nos vértices, A/3 nos meios
    if tot <= 0:
        raise ValueError("seleção não forma face de contorno")
    f = np.asarray(force, float)
    return {k: tuple(f * a / tot) for k, a in w.items()}


def _assemble(mesh, E, nu, rho=None):
    n = len(mesh.nodes); D = _D(E, nu); T = mesh.tets; m = len(T)
    P = mesh.nodes[T]
    Ke = np.zeros((m, 30, 30)); Bs = []
    for xi in _GP:
        B, dj = _Bbatch(P, xi)
        if (dj <= 0).any():
            raise ValueError("elemento Tet10 invertido/degenerado")
        Ke += np.matmul(B.transpose(0, 2, 1), np.matmul(D, B)) * (dj / 24.0)[:, None, None]; Bs.append(B)
    dof = (3 * T[:, :, None] + np.arange(3)[None, None, :]).reshape(m, 30)
    r = np.repeat(dof, 30, axis=1).ravel(); c = np.tile(dof, (1, 30)).ravel()
    K = sp.csr_matrix((Ke.ravel(), (r, c)), shape=(3*n, 3*n))
    V = np.abs(np.linalg.det(np.concatenate([np.ones((m, 4, 1)), P[:, :4]], axis=2))) / 6
    M = None
    if rho:
        Me = np.einsum('m,ij->mij', rho * V, np.kron(_MREF, np.eye(3)))
        M = sp.csr_matrix((Me.ravel(), (r, c)), shape=(3*n, 3*n))
    return K, M, Bs, V, D


MAX_DOF_DIRECT = 120_000


def _check_size(n):
    if 3 * n > MAX_DOF_DIRECT:
        raise ValueError(f"{3*n} GDL excedem o limite do solver direto ({MAX_DOF_DIRECT}); aumente h/tamanho de malha")


def solve(mesh: Mesh, E, nu, fixed, loads):
    n = len(mesh.nodes); _check_size(n)
    K, _, Bs, vols, D = _assemble(mesh, E, nu)
    F = np.zeros(3*n)
    for nd, f in loads.items(): F[3*nd:3*nd+3] += f
    fd = sorted({3*nd + c for nd, cs in fixed.items() for c in cs})
    if not fd: raise ValueError("sem apoios: corpo rígido livre")
    free = np.setdiff1d(np.arange(3*n), fd); u = np.zeros(3*n)
    usedmask = np.zeros(n, bool); usedmask[np.unique(mesh.tets)] = True
    free = free[usedmask[free // 3]]
    u[free] = _safe_solve(K[free][:, free].tocsc(), F[free])
    R = K @ u - F
    T = mesh.tets; dof = (3 * T[:, :, None] + np.arange(3)[None, None, :]).reshape(len(T), 30); ue = u[dof]
    vm = np.zeros(len(T))
    for B in Bs:
        sg = np.matmul(D, np.matmul(B, ue[:, :, None]))[:, :, 0]
        vm += np.sqrt(0.5*((sg[:, 0]-sg[:, 1])**2 + (sg[:, 1]-sg[:, 2])**2 + (sg[:, 2]-sg[:, 0])**2) + 3*(sg[:, 3]**2 + sg[:, 4]**2 + sg[:, 5]**2)) / 4
    return u.reshape(-1, 3), vm, R, float(np.sum(vols))


def modal(mesh: Mesh, E, nu, rho, fixed, n_modes=6):
    if rho <= 0: raise ValueError("rho deve ser > 0 (t/mm³)")
    n = len(mesh.nodes); _check_size(n)
    K, M, *_ = _assemble(mesh, E, nu, rho)
    fd = {3*nd + c for nd, cs in fixed.items() for c in cs}
    usedmask = np.zeros(n, bool); usedmask[np.unique(mesh.tets)] = True
    allv = np.setdiff1d(np.arange(3*n), list(fd)); free = allv[usedmask[allv // 3]]
    w2, _ = spl.eigsh(K[free][:, free].tocsc(), k=min(n_modes, len(free) - 2), M=M[free][:, free].tocsc(), sigma=0, which="LM")
    return np.sqrt(np.sort(np.abs(w2))) / (2 * np.pi)


_XI_NODES = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1), (.5, 0, 0), (.5, .5, 0), (0, .5, 0), (0, 0, .5), (.5, 0, .5), (0, .5, .5)]


def nodal_stress(mesh: Mesh, u, E, nu):
    """Tensor de tensões (sxx,syy,szz,txy,tyz,txz; MPa) AVALIADO NOS NÓS de cada elemento e média entre
    elementos vizinhos (recuperação simples). Retorna (sigma[n,6], vm[n])."""
    D = _D(E, nu); n = len(mesh.nodes); T = mesh.tets; m = len(T)
    P = mesh.nodes[T]; dof = (3 * T[:, :, None] + np.arange(3)[None, None, :]).reshape(m, 30); ue = np.asarray(u).reshape(-1)[dof]
    acc = np.zeros((n, 6)); cnt = np.zeros(n)
    for a, xi in enumerate(_XI_NODES):
        B, _ = _Bbatch(P, xi)
        sg = np.matmul(D, np.matmul(B, ue[:, :, None]))[:, :, 0]
        np.add.at(acc, T[:, a], sg); np.add.at(cnt, T[:, a], 1)
    sg = acc / np.maximum(cnt, 1)[:, None]
    vm = np.sqrt(0.5*((sg[:, 0]-sg[:, 1])**2 + (sg[:, 1]-sg[:, 2])**2 + (sg[:, 2]-sg[:, 0])**2) + 3*(sg[:, 3]**2 + sg[:, 4]**2 + sg[:, 5]**2))
    return sg, vm
