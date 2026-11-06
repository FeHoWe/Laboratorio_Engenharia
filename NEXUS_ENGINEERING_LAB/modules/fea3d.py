"""FEA 3D linear-elástico com tetraedros lineares (Tet4) — solver PRÓPRIO do NEXUS.

Classe do resultado: SIMULACAO_NUMERICA (solver "NEXUS-Tet4"), validado apenas
contra os casos listados em tests/test_fea3d.py. Limitações: Tet4 é rígido em
flexão (travamento) — malha grossa SUBESTIMA deslocamentos; malhador próprio só
gera caixas estruturadas (6 tetraedros/hexaedro) com máscara opcional.
Unidades: mm, N, MPa. Material (E, nu) SEMPRE informado pelo usuário.
"""
from __future__ import annotations
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spl
from dataclasses import dataclass
from .result_trace import TracedResult

SOLVER, SOLVER_VER = "NEXUS-Tet4", "1.0"

_HEX_TETS = [(0, 1, 3, 7), (0, 1, 5, 7), (0, 4, 5, 7), (0, 4, 6, 7), (0, 2, 6, 7), (0, 2, 3, 7)]


@dataclass
class Mesh:
    nodes: np.ndarray   # (n,3)
    tets: np.ndarray    # (m,4)


def box_mesh(lx, ly, lz, nx, ny, nz, mask=None) -> Mesh:
    """Malha estruturada de caixa [0,lx]x[0,ly]x[0,lz]. mask(cx,cy,cz)->bool filtra células (peças não-prismáticas)."""
    if min(nx, ny, nz) < 1 or min(lx, ly, lz) <= 0:
        raise ValueError("dimensões/divisões inválidas")
    xs, ys, zs = (np.linspace(0, L, n + 1) for L, n in ((lx, nx), (ly, ny), (lz, nz)))
    idx = lambda i, j, k: (i * (ny + 1) + j) * (nz + 1) + k
    nodes = np.array([(x, y, z) for x in xs for y in ys for z in zs])
    tets = []
    for i in range(nx):
        for j in range(ny):
            for k in range(nz):
                if mask is not None and not mask((xs[i] + xs[i+1]) / 2, (ys[j] + ys[j+1]) / 2, (zs[k] + zs[k+1]) / 2):
                    continue
                c = [idx(i + a, j + b, k + d) for d in (0, 1) for b in (0, 1) for a in (0, 1)]
                # c ordenado (a fastest): 0=(0,0,0) 1=(1,0,0) 2=(0,1,0) 3=(1,1,0) 4=(0,0,1)...
                # reordena para convenção do corte de 6 tets (diagonal 0-7)
                for t in _HEX_TETS:
                    tets.append([c[t[0]], c[t[1]], c[t[2]], c[t[3]]])
    tets = np.array(tets, dtype=int)
    used = np.unique(tets)
    remap = -np.ones(len(nodes), dtype=int); remap[used] = np.arange(len(used))
    tets = remap[tets]
    # garante volume positivo
    P = nodes[used][tets]
    vol = np.einsum('ij,ij->i', np.cross(P[:, 1]-P[:, 0], P[:, 2]-P[:, 0]), P[:, 3]-P[:, 0]) / 6
    flip = vol < 0
    tets[flip] = tets[flip][:, [0, 2, 1, 3]]
    return Mesh(nodes[used], tets)


def _D(E, nu):
    if E <= 0 or not (-1 < nu < 0.5):
        raise ValueError("E>0 e -1<nu<0.5 exigidos")
    l = E * nu / ((1 + nu) * (1 - 2 * nu)); m = E / (2 * (1 + nu))
    D = np.zeros((6, 6)); D[:3, :3] = l; D[range(3), range(3)] += 2 * m; D[range(3, 6), range(3, 6)] = m
    return D


def _B(P):
    M = np.hstack([np.ones((4, 1)), P])
    V6 = np.linalg.det(M)
    C = np.linalg.inv(M)            # colunas: coeficientes das funções de forma
    g = C[1:, :]                    # (3,4) gradientes
    B = np.zeros((6, 12))
    for a in range(4):
        bx, by, bz = g[:, a]
        B[0, 3*a] = bx; B[1, 3*a+1] = by; B[2, 3*a+2] = bz
        B[3, 3*a] = by; B[3, 3*a+1] = bx
        B[4, 3*a+1] = bz; B[4, 3*a+2] = by
        B[5, 3*a] = bz; B[5, 3*a+2] = bx
    return B, abs(V6) / 6


def surface_load(mesh: Mesh, nodes_sel, force) -> dict:
    """Distribui força total (Fx,Fy,Fz) em N sobre a face externa formada pelos nós `nodes_sel`,
    com carga consistente (área/3 por nó de cada triângulo de contorno)."""
    sel = set(int(i) for i in nodes_sel)
    cnt = {}
    for t in mesh.tets:
        for f in ((0,1,2),(0,1,3),(0,2,3),(1,2,3)):
            key = tuple(sorted(int(t[a]) for a in f)); cnt[key] = cnt.get(key, 0) + 1
    w = {}
    tot = 0.0
    for key, c in cnt.items():
        if c == 1 and all(k in sel for k in key):
            p = mesh.nodes[list(key)]
            A = 0.5*np.linalg.norm(np.cross(p[1]-p[0], p[2]-p[0])); tot += A
            for k in key: w[k] = w.get(k, 0.0) + A/3
    if tot <= 0:
        raise ValueError("seleção não forma face de contorno")
    f = np.asarray(force, float)
    return {k: tuple(f*a/tot) for k, a in w.items()}


def _safe_solve(Kff, f):
    """Solução direta com verificação de resíduo: mecanismo/apoio insuficiente vira erro, nunca número absurdo."""
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        x = spl.spsolve(Kff, f)
    nf = np.linalg.norm(f)
    if not np.all(np.isfinite(x)) or (nf > 0 and np.linalg.norm(Kff @ x - f) > 1e-6 * nf):
        raise RuntimeError("sistema singular ou mal condicionado (apoios insuficientes?)")
    return x


def _tet4_batch(P):
    """P:(m,4,3) → B:(m,6,12), V:(m,)  (gradientes constantes, vetorizado)."""
    m = len(P)
    M = np.concatenate([np.ones((m, 4, 1)), P], axis=2)
    V6 = np.linalg.det(M)
    C = np.linalg.inv(M)                       # (m,4,4)
    g = C[:, 1:, :]                            # (m,3,4)
    B = np.zeros((m, 6, 12))
    for a in range(4):
        bx, by, bz = g[:, 0, a], g[:, 1, a], g[:, 2, a]
        B[:, 0, 3*a] = bx; B[:, 1, 3*a+1] = by; B[:, 2, 3*a+2] = bz
        B[:, 3, 3*a] = by; B[:, 3, 3*a+1] = bx; B[:, 4, 3*a+1] = bz; B[:, 4, 3*a+2] = by; B[:, 5, 3*a] = bz; B[:, 5, 3*a+2] = bx
    return B, np.abs(V6) / 6


def solve(mesh: Mesh, E: float, nu: float, fixed: dict, loads: dict):
    """fixed: {nó: (0,1,2)} dofs restritos; loads: {nó:(Fx,Fy,Fz)} N. Retorna (u[n,3], vm_elem, R, volume)."""
    n = len(mesh.nodes); D = _D(E, nu); T = mesh.tets; m = len(T)
    B, V = _tet4_batch(mesh.nodes[T])
    if (V <= 0).any():
        raise ValueError("elemento degenerado")
    Ke = np.matmul(B.transpose(0, 2, 1), np.matmul(D, B)) * V[:, None, None]
    dof = (3 * T[:, :, None] + np.arange(3)[None, None, :]).reshape(m, 12)
    K = sp.csr_matrix((Ke.ravel(), (np.repeat(dof, 12, axis=1).ravel(), np.tile(dof, (1, 12)).ravel())), shape=(3*n, 3*n))
    Fv = np.zeros(3*n)
    for nd, f in loads.items():
        Fv[3*nd:3*nd+3] += f
    fixed_dofs = np.array(sorted({3*nd + c for nd, cs in fixed.items() for c in cs}), dtype=int)
    if len(fixed_dofs) == 0:
        raise ValueError("sem apoios: corpo rígido livre")
    usedmask = np.zeros(n, bool); usedmask[np.unique(T)] = True
    mask = np.zeros(3*n, bool); mask[fixed_dofs] = True
    free = np.flatnonzero(~mask & np.repeat(usedmask, 3))
    u = np.zeros(3*n)
    Kff = K[free][:, free].tocsc()
    u[free] = _safe_solve(Kff, Fv[free])
    R = K @ u - Fv
    s = np.matmul(D, np.matmul(B, u[dof][:, :, None]))[:, :, 0]
    vm = np.sqrt(0.5*((s[:, 0]-s[:, 1])**2 + (s[:, 1]-s[:, 2])**2 + (s[:, 2]-s[:, 0])**2) + 3*(s[:, 3]**2 + s[:, 4]**2 + s[:, 5]**2))
    return u.reshape(-1, 3), vm, R, float(V.sum())


def to_traced(nome, mesh, E, nu, u, vm, vol, validacao_ref="") -> TracedResult:
    return TracedResult(
        nome=nome, classe="VALIDADO" if validacao_ref else "SIMULACAO_NUMERICA",
        metodo="Elasticidade linear 3D, Tet4 (deformação constante), solução direta esparsa",
        valores={"u_max_mm": float(np.abs(u).max()), "vm_max_MPa": float(vm.max()), "nos": len(mesh.nodes), "elementos": len(mesh.tets), "volume_mm3": vol},
        entradas={"E_MPa": E, "nu": nu},
        premissas=["material linear isotrópico informado pelo usuário", "pequenas deformações", "malha estruturada de caixa"],
        limitacoes=["Tet4 trava em flexão: malha grossa subestima deslocamento", "tensão por elemento (não suavizada)", "sem contato, plasticidade nem não-linearidade geométrica"],
        solver=SOLVER, solver_versao=SOLVER_VER, validacao_ref=validacao_ref)


def write_calculix_inp(mesh: Mesh, E, nu, fixed, loads, path):
    """Escreve .inp C3D4 para o CalculiX (executa só se `ccx` instalado — ver solver_registry)."""
    L = ["*NODE"] + [f"{i+1}, {x:.9g}, {y:.9g}, {z:.9g}" for i, (x, y, z) in enumerate(mesh.nodes)]
    L += ["*ELEMENT, TYPE=C3D4, ELSET=EALL"] + [f"{i+1}, " + ", ".join(str(a+1) for a in t) for i, t in enumerate(mesh.tets)]
    L += ["*MATERIAL, NAME=MAT", "*ELASTIC", f"{E:.9g}, {nu:.9g}", "*SOLID SECTION, ELSET=EALL, MATERIAL=MAT", "*STEP", "*STATIC", "*BOUNDARY"]
    for nd, cs in fixed.items():
        for c in cs: L.append(f"{nd+1}, {c+1}, {c+1}")
    L.append("*CLOAD")
    for nd, f in loads.items():
        for c in range(3):
            if f[c]: L.append(f"{nd+1}, {c+1}, {f[c]:.9g}")
    L += ["*NODE FILE", "U", "*EL FILE", "S", "*END STEP"]
    open(path, "w").write("\n".join(L) + "\n")


def modal(mesh: Mesh, E: float, nu: float, rho: float, fixed: dict, n_modes: int = 6):
    """Frequências naturais (Hz) com massa consistente de Tet4. rho em t/mm³ (N·s²/mm⁴): aço ≈ 7.85e-9.
    A densidade é SEMPRE informada pelo usuário."""
    if rho <= 0:
        raise ValueError("rho deve ser > 0 (t/mm³)")
    n = len(mesh.nodes); D = _D(E, nu)
    rk, ck, vk, rm, cm, vm_ = [], [], [], [], [], []
    Mref = np.zeros((12, 12))
    for a in range(4):
        for b in range(4):
            f = 2.0 if a == b else 1.0
            for c in range(3):
                Mref[3*a+c, 3*b+c] = f / 20.0
    for t in mesh.tets:
        B, V = _B(mesh.nodes[t])
        Ke = B.T @ D @ B * V; Me = Mref * rho * V
        dof = np.array([3*a + c for a in t for c in range(3)])
        r = np.repeat(dof, 12); c_ = np.tile(dof, 12)
        rk.extend(r); ck.extend(c_); vk.extend(Ke.ravel()); rm.extend(r); cm.extend(c_); vm_.extend(Me.ravel())
    K = sp.csr_matrix((vk, (rk, ck)), shape=(3*n, 3*n)); M = sp.csr_matrix((vm_, (rm, cm)), shape=(3*n, 3*n))
    fd = sorted({3*nd + c for nd, cs in fixed.items() for c in cs})
    free = np.setdiff1d(np.arange(3*n), fd)
    Kf, Mf = K[free][:, free].tocsc(), M[free][:, free].tocsc()
    k = min(n_modes, len(free) - 2)
    w2, _ = spl.eigsh(Kf, k=k, M=Mf, sigma=0, which="LM")
    w2 = np.sort(np.abs(w2))
    return np.sqrt(w2) / (2 * np.pi)


def export_vtk(path, mesh: Mesh, u=None, vm=None, title="NEXUS-Tet4"):
    """Exporta malha + deslocamento (nó) + von Mises (elemento) em VTK legado ASCII (abre no ParaView)."""
    n, m = len(mesh.nodes), len(mesh.tets)
    L = ["# vtk DataFile Version 3.0", title, "ASCII", "DATASET UNSTRUCTURED_GRID", f"POINTS {n} double"]
    L += [f"{x:.9g} {y:.9g} {z:.9g}" for x, y, z in mesh.nodes]
    L += [f"CELLS {m} {5*m}"] + [f"4 {a} {b} {c} {d}" for a, b, c, d in mesh.tets]
    L += [f"CELL_TYPES {m}"] + ["10"] * m
    if u is not None:
        L += [f"POINT_DATA {n}", "VECTORS deslocamento_mm double"] + [f"{a:.9g} {b:.9g} {c:.9g}" for a, b, c in u]
    if vm is not None:
        L += [f"CELL_DATA {m}", "SCALARS von_mises_MPa double 1", "LOOKUP_TABLE default"] + [f"{x:.9g}" for x in vm]
    open(path, "w").write("\n".join(L) + "\n")
