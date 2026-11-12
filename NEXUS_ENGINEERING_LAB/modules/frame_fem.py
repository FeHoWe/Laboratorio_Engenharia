"""Pórtico espacial de vigas (Euler–Bernoulli, 6 GDL/nó) — método da rigidez direta (V2.5).

Unidades: mm, N, MPa (N/mm²), N·mm. Resolve deslocamentos, rotações, reações e esforços de extremidade (N, Vy, Vz, T, My, Mz) de cada viga.
HONESTIDADE: linear elástico, pequenos deslocamentos, seção prismática, SEM deformação por cisalhamento (Euler–Bernoulli: vale para L/h ≳ 10),
sem flambagem global/P-Δ, sem plasticidade, sem empenamento de torção. Cargas distribuídas são uniformes e em eixos GLOBAIS; o peso próprio NÃO é automático.
Um modelo hipostático (mecanismo) é detectado e recusado.

Formato de texto ('#' comenta):
  NODE id x y z [fix=xyzXYZ]            # minúsculas = translações restritas; MAIÚSCULAS = rotações (X Y Z) restritas
  BEAM id n1 n2 A Iy Iz J E G [ref=vx,vy,vz] [c=mm]   # eixo local x = n1→n2; ref define o plano local x-z (padrão: Z global; se a viga for vertical, X global — assim Iy/My é sempre a flexão no plano x–z global); c = fibra extrema p/ tensão
  LOAD node fx fy fz [mx my mz]         # N, N·mm (globais)
  DLOAD beam wx wy wz                   # N/mm, uniforme, eixos globais
  MASS node m                           # massa concentrada (kg) — só para a análise modal (e BEAM ... rho=kg/m³ para a massa distribuída)
Eixos locais: y = z × x ; My = momento em torno de y local (flexão no plano x–z); Mz = em torno de z local (plano x–y). Iy ↔ flexão no plano x-z.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np


class FrameError(ValueError):
    pass


@dataclass
class FNode:
    id: str
    xyz: np.ndarray
    fixed: tuple = (False,) * 6


@dataclass
class FBeam:
    id: str
    n1: str
    n2: str
    A: float
    Iy: float
    Iz: float
    J: float
    E: float
    G: float
    ref: tuple | None = None
    rho: float | None = None        # densidade (kg/m³), só para a análise modal
    c: float | None = None          # distância à fibra extrema (mm), opcional: habilita a tensão normal máxima


@dataclass
class Frame:
    nodes: dict = field(default_factory=dict)
    beams: dict = field(default_factory=dict)
    loads: dict = field(default_factory=dict)     # node -> 6 forças/momentos
    dloads: dict = field(default_factory=dict)    # beam -> (wx, wy, wz)
    masses: dict = field(default_factory=dict)    # node -> massa concentrada (kg), só modal


def parse(text: str) -> Frame:
    f = Frame()
    for ln, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#")[0].strip()
        if not line:
            continue
        p = line.split()
        try:
            k = p[0].upper()
            if k == "NODE":
                fix = next((q[4:] for q in p[5:] if q.lower().startswith("fix=")), "")
                f.nodes[p[1]] = FNode(p[1], np.array([float(p[2]), float(p[3]), float(p[4])]),
                                      tuple(c in fix for c in "xyzXYZ"))
            elif k == "BEAM":
                if p[2] not in f.nodes or p[3] not in f.nodes:
                    raise FrameError(f"nó inexistente ({p[2]}, {p[3]})")
                if p[2] == p[3]:
                    raise FrameError("nós iguais")
                ref = next((tuple(float(x) for x in q[4:].split(",")) for q in p[10:] if q.lower().startswith("ref=")), None)
                rho = next((float(q[4:]) for q in p[10:] if q.lower().startswith("rho=")), None)
                cfib = next((float(q[2:]) for q in p[10:] if q.lower().startswith("c=")), None)
                vals = [float(x) for x in p[4:10]]
                if min(vals) <= 0:
                    raise FrameError("A, Iy, Iz, J, E e G devem ser positivos")
                f.beams[p[1]] = FBeam(p[1], p[2], p[3], *vals, ref=ref, c=cfib, rho=rho)
            elif k == "LOAD":
                if p[1] not in f.nodes:
                    raise FrameError(f"nó inexistente: {p[1]}")
                v = np.zeros(6)
                v[:len(p) - 2] = [float(x) for x in p[2:8]]
                f.loads[p[1]] = f.loads.get(p[1], np.zeros(6)) + v
            elif k == "MASS":
                if p[1] not in f.nodes:
                    raise FrameError(f"nó inexistente: {p[1]}")
                if float(p[2]) <= 0:
                    raise FrameError("massa deve ser positiva")
                f.masses[p[1]] = f.masses.get(p[1], 0.0) + float(p[2])
            elif k == "DLOAD":
                if p[1] not in f.beams:
                    raise FrameError(f"viga inexistente: {p[1]}")
                f.dloads[p[1]] = tuple(float(x) for x in p[2:5])
            else:
                raise FrameError(f"instrução desconhecida '{p[0]}'")
        except FrameError as exc:
            raise FrameError(f"Linha {ln}: {exc}") from None
        except (IndexError, ValueError):
            raise FrameError(f"Linha {ln}: formato inválido → '{line}'") from None
    return f


def local_axes(p1, p2, ref=None) -> tuple[np.ndarray, float]:
    d = np.asarray(p2, float) - np.asarray(p1, float)
    L = float(np.linalg.norm(d))
    if L < 1e-9:
        raise FrameError("viga com comprimento nulo")
    ex = d / L
    v = np.array(ref, float) if ref is not None else (np.array([0, 0, 1.0]) if abs(ex[2]) < 0.999 else np.array([1.0, 0, 0]))
    ez = v - np.dot(v, ex) * ex
    if np.linalg.norm(ez) < 1e-9:
        raise FrameError("vetor de referência paralelo ao eixo da viga")
    ez /= np.linalg.norm(ez)
    ey = np.cross(ez, ex)
    return np.array([ex, ey, ez]), L          # linhas = eixos locais em coordenadas globais


def local_stiffness(b: FBeam, L: float) -> np.ndarray:
    E, G, A, Iy, Iz, J = b.E, b.G, b.A, b.Iy, b.Iz, b.J
    k = np.zeros((12, 12))
    a = E * A / L
    t = G * J / L
    k[0, 0] = k[6, 6] = a; k[0, 6] = k[6, 0] = -a
    k[3, 3] = k[9, 9] = t; k[3, 9] = k[9, 3] = -t
    # flexão no plano x-y (Iz): v (1,7), θz (5,11)
    c1, c2, c3, c4 = 12 * E * Iz / L ** 3, 6 * E * Iz / L ** 2, 4 * E * Iz / L, 2 * E * Iz / L
    for (i, j, v) in ((1, 1, c1), (7, 7, c1), (1, 7, -c1), (7, 1, -c1), (1, 5, c2), (5, 1, c2), (1, 11, c2), (11, 1, c2),
                      (7, 5, -c2), (5, 7, -c2), (7, 11, -c2), (11, 7, -c2), (5, 5, c3), (11, 11, c3), (5, 11, c4), (11, 5, c4)):
        k[i, j] += v
    # flexão no plano x-z (Iy): w (2,8), θy (4,10) — sinais trocados nos acoplamentos
    d1, d2, d3, d4 = 12 * E * Iy / L ** 3, 6 * E * Iy / L ** 2, 4 * E * Iy / L, 2 * E * Iy / L
    for (i, j, v) in ((2, 2, d1), (8, 8, d1), (2, 8, -d1), (8, 2, -d1), (2, 4, -d2), (4, 2, -d2), (2, 10, -d2), (10, 2, -d2),
                      (8, 4, d2), (4, 8, d2), (8, 10, d2), (10, 8, d2), (4, 4, d3), (10, 10, d3), (4, 10, d4), (10, 4, d4)):
        k[i, j] += v
    return k


def transform(R: np.ndarray) -> np.ndarray:
    T = np.zeros((12, 12))
    for i in range(4):
        T[3 * i:3 * i + 3, 3 * i:3 * i + 3] = R
    return T


def fixed_end_local(w_local: np.ndarray, L: float) -> np.ndarray:
    """Forças de engastamento perfeito (locais, atuando NOS nós) para carga uniforme w=(wx,wy,wz) local."""
    wx, wy, wz = w_local
    f = np.zeros(12)
    f[0] = f[6] = wx * L / 2
    f[1] = f[7] = wy * L / 2
    f[5], f[11] = wy * L ** 2 / 12, -wy * L ** 2 / 12
    f[2] = f[8] = wz * L / 2
    f[4], f[10] = -wz * L ** 2 / 12, wz * L ** 2 / 12
    return f


@dataclass
class FrameResult:
    displacement: dict          # nó -> 6 (u,v,w em mm; rotações em rad)
    reactions: dict             # nó -> 6 (N, N·mm)
    end_forces: dict            # viga -> 12 (locais, esforços que o NÓ exerce sobre a viga: N,Vy,Vz,T,My,Mz em n1 e n2)
    equilibrium_error: float
    extremes: dict              # viga -> {"L": comprimento}


def solve(fr: Frame) -> FrameResult:
    ids = list(fr.nodes)
    idx = {n: i for i, n in enumerate(ids)}
    n = 6 * len(ids)
    if not fr.beams:
        raise FrameError("Sem vigas.")
    K = np.zeros((n, n))
    F = np.zeros(n)
    info = {}
    for b in fr.beams.values():
        R, L = local_axes(fr.nodes[b.n1].xyz, fr.nodes[b.n2].xyz, b.ref)
        T = transform(R)
        kg = T.T @ local_stiffness(b, L) @ T
        s = list(range(6 * idx[b.n1], 6 * idx[b.n1] + 6)) + list(range(6 * idx[b.n2], 6 * idx[b.n2] + 6))
        K[np.ix_(s, s)] += kg
        fe = np.zeros(12)
        if b.id in fr.dloads:
            wl = R @ np.array(fr.dloads[b.id])
            fe = fixed_end_local(wl, L)
            F[s] += T.T @ fe
        info[b.id] = (R, L, T, s, fe)
    P = F.copy()
    for nid, v in fr.loads.items():
        P[6 * idx[nid]:6 * idx[nid] + 6] += v
    fixed = np.array([x for nid in ids for x in fr.nodes[nid].fixed])
    free = np.where(~fixed)[0]
    if len(free) == 0:
        raise FrameError("Todos os graus de liberdade estão restritos.")
    Kff = K[np.ix_(free, free)]
    if np.linalg.matrix_rank(Kff, tol=1e-9 * np.abs(np.diag(Kff)).max()) < len(free):
        raise FrameError("Estrutura hipostática (mecanismo) ou com graus de liberdade soltos: faltam apoios/vigas "
                         "(em pórtico plano restrinja v, θx e θz, ou o equivalente no plano usado).")
    u = np.zeros(n)
    u[free] = np.linalg.solve(Kff, P[free])
    Rr = K @ u - P
    Rr[free] = 0.0
    ends, ext = {}, {}
    for b in fr.beams.values():
        R, L, T, s, fe = info[b.id]
        f_loc = local_stiffness(b, L) @ (T @ u[s]) - fe          # esforços no nó sobre a viga (convenção: positivo no sentido do eixo local)
        ends[b.id] = f_loc
        ext[b.id] = {"L": L}
    scale = max(float(np.abs(P).sum()), 1.0)
    eq = np.abs(np.array([P[0::6].sum() + Rr[0::6].sum(), P[1::6].sum() + Rr[1::6].sum(), P[2::6].sum() + Rr[2::6].sum()])).max() / scale
    return FrameResult({nid: u[6 * idx[nid]:6 * idx[nid] + 6].copy() for nid in ids},
                       {nid: Rr[6 * idx[nid]:6 * idx[nid] + 6].copy() for nid in ids if fixed[6 * idx[nid]:6 * idx[nid] + 6].any()},
                       ends, float(eq), ext)


def moment_at(fr: Frame, res: FrameResult, beam_id: str, s: float) -> tuple[float, float]:
    """Momentos fletores (My, Mz) em N·mm na fração s∈[0,1] do vão: momento, em relação à seção, das ações do trecho [0, x] (esforços de extremidade
    em n1 + carga distribuída) — no mesmo sinal dos esforços de extremidade. My(x)=My1+x·Vz1+wz·x²/2 ; Mz(x)=Mz1−x·Vy1−wy·x²/2.
    Valida: em s=1 vale −(momento de extremidade em n2)."""
    b = fr.beams[beam_id]
    R, L = local_axes(fr.nodes[b.n1].xyz, fr.nodes[b.n2].xyz, b.ref)
    f = res.end_forces[beam_id]
    w = R @ np.array(fr.dloads.get(beam_id, (0.0, 0.0, 0.0)))
    x = s * L
    return float(f[4] + x * f[2] + w[2] * x * x / 2), float(f[5] - x * f[1] - w[1] * x * x / 2)


def shear_at(fr: Frame, res: FrameResult, beam_id: str, s: float) -> tuple[float, float]:
    """Cortantes (Vy, Vz) em N na fração s do vão: resultante das ações do trecho [0, x]."""
    b = fr.beams[beam_id]
    R, L = local_axes(fr.nodes[b.n1].xyz, fr.nodes[b.n2].xyz, b.ref)
    f = res.end_forces[beam_id]
    w = R @ np.array(fr.dloads.get(beam_id, (0.0, 0.0, 0.0)))
    return float(f[1] + w[1] * s * L), float(f[2] + w[2] * s * L)


def portal_example(span: float = 6000.0, height: float = 3000.0, w: float = 20.0) -> str:
    """Pórtico plano (x–z) bi-engastado com viga carregada: perfil genérico ~IPE 300 (A, I, c). Valores são EXEMPLOS — troque pelos seus."""
    sec = "5380 8.356e7 6.04e6 2.0e5 210000 80000"
    # rho=7850 kg/m³ (aço) só é usado na análise modal
    return "\n".join([
        "# Pórtico plano x-z (y e rotações X,Z restritos nos nós livres de apoio). mm, N, MPa, N·mm. Valores genéricos: troque pelos seus.",
        "NODE A 0 0 0 fix=xyzXYZ", f"NODE B 0 0 {height:g} fix=yXZ", f"NODE C {span:g} 0 {height:g} fix=yXZ", f"NODE D {span:g} 0 0 fix=xyzXYZ",
        f"BEAM c1 A B {sec} c=150 rho=7850", f"BEAM v B C {sec} c=150 rho=7850", f"BEAM c2 C D {sec} c=150 rho=7850", f"DLOAD v 0 0 {-w:g}", "LOAD B 10000 0 0"])


def report(fr: Frame, res: FrameResult, sy: float = 0.0, stations: int = 11) -> str:
    out = "Pórtico espacial de vigas — rigidez direta (Euler–Bernoulli)\n" + "─" * 52 + "\n"
    out += f"  nós {len(fr.nodes)} · vigas {len(fr.beams)} · erro de equilíbrio global {res.equilibrium_error:.2e} (relativo)\n\n"
    out += "  viga   L[mm]   N[kN]  Vy[kN]  Vz[kN]  T[kN·m]  |My|máx[kN·m]  |Mz|máx[kN·m]  σmáx[MPa]\n"
    worst = (0.0, "")
    for b in fr.beams.values():
        L = res.extremes[b.id]["L"]
        sts = [i / (stations - 1) for i in range(stations)]
        my = max(abs(moment_at(fr, res, b.id, s)[0]) for s in sts)
        mz = max(abs(moment_at(fr, res, b.id, s)[1]) for s in sts)
        f = res.end_forces[b.id]
        vy = max(abs(shear_at(fr, res, b.id, s)[0]) for s in sts)
        vz = max(abs(shear_at(fr, res, b.id, s)[1]) for s in sts)
        sig = ""
        if b.c:
            smax = max(abs(f[0]) / b.A + abs(moment_at(fr, res, b.id, s)[0]) * b.c / b.Iy + abs(moment_at(fr, res, b.id, s)[1]) * b.c / b.Iz for s in sts)
            sig = f"{smax:9.1f}" + (f"  n={sy / smax:.2f}" if sy > 0 and smax > 0 else "")
            if smax > worst[0]:
                worst = (smax, b.id)
        out += f"  {b.id:<6} {L:>7.0f} {f[0] / 1000:>7.2f} {vy / 1000:>7.2f} {vz / 1000:>7.2f} {abs(f[3]) / 1e6:>8.2f} {my / 1e6:>13.2f} {mz / 1e6:>13.2f}  {sig}\n"
    out += "\n  deslocamentos (mm) e rotações (mrad):\n"
    for nid, d in res.displacement.items():
        out += f"   {nid:<5} u={d[0]:9.3f} v={d[1]:9.3f} w={d[2]:9.3f}   θx={d[3] * 1e3:8.3f} θy={d[4] * 1e3:8.3f} θz={d[5] * 1e3:8.3f}\n"
    out += "\n  reações (kN, kN·m):\n"
    for nid, r in res.reactions.items():
        out += f"   {nid:<5} Fx={r[0] / 1000:9.2f} Fy={r[1] / 1000:9.2f} Fz={r[2] / 1000:9.2f}   Mx={r[3] / 1e6:8.2f} My={r[4] / 1e6:8.2f} Mz={r[5] / 1e6:8.2f}\n"
    if worst[1]:
        out += f"\n  tensão normal máxima: {worst[0]:.1f} MPa na viga {worst[1]} (N/A + M·c/I nas duas flexões, soma conservadora)\n"
    out += ("\n  Hipóteses: linear elástico, pequenos deslocamentos, Euler–Bernoulli (sem cisalhamento), sem P-Δ/flambagem global, "
            "sem peso próprio automático, carga distribuída uniforme em eixos globais.\n")
    return out


def local_mass(b: FBeam, L: float) -> np.ndarray:
    """Matriz de massa consistente (12×12, local). ρ em kg/m³ → t/mm³ (×1e-12) para unidades coerentes (mm, N, t, s)."""
    if not b.rho or b.rho <= 0:
        raise FrameError(f"Viga {b.id}: informe rho=kg/m³ para a análise modal.")
    rho = b.rho * 1e-12
    m = np.zeros((12, 12))
    c = rho * b.A * L / 6
    m[0, 0] = m[6, 6] = 2 * c; m[0, 6] = m[6, 0] = c
    ct = rho * (b.Iy + b.Iz) * L / 6
    m[3, 3] = m[9, 9] = 2 * ct; m[3, 9] = m[9, 3] = ct
    k = rho * b.A * L / 420
    base = np.array([[156, 22 * L, 54, -13 * L], [22 * L, 4 * L * L, 13 * L, -3 * L * L], [54, 13 * L, 156, -22 * L], [-13 * L, -3 * L * L, -22 * L, 4 * L * L]]) * k
    for dofs, sgn in (((1, 5, 7, 11), 1.0), ((2, 4, 8, 10), -1.0)):
        S = np.diag([1, sgn, 1, sgn])
        mb = S @ base @ S
        for a, ia in enumerate(dofs):
            for q, iq in enumerate(dofs):
                m[ia, iq] += mb[a, q]
    return m


@dataclass
class ModalResult:
    freq_hz: list
    shapes: list            # cada modo: dict nó -> 6 (normalizado a deslocamento máx = 1)
    mass_total_kg: float


def modal(fr: Frame, n_modes: int = 6) -> ModalResult:
    """Frequências naturais (Hz) e modos do pórtico: K φ = ω² M φ (massa consistente + massas concentradas). Sem amortecimento, linear."""
    from scipy.linalg import eigh
    ids = list(fr.nodes)
    idx = {n: i for i, n in enumerate(ids)}
    n = 6 * len(ids)
    K = np.zeros((n, n))
    M = np.zeros((n, n))
    total = 0.0
    for b in fr.beams.values():
        R, L = local_axes(fr.nodes[b.n1].xyz, fr.nodes[b.n2].xyz, b.ref)
        T = transform(R)
        s = list(range(6 * idx[b.n1], 6 * idx[b.n1] + 6)) + list(range(6 * idx[b.n2], 6 * idx[b.n2] + 6))
        K[np.ix_(s, s)] += T.T @ local_stiffness(b, L) @ T
        M[np.ix_(s, s)] += T.T @ local_mass(b, L) @ T
        total += b.rho * 1e-9 * b.A * L if b.rho else 0.0          # kg: ρ[kg/m³]·A[mm²]·L[mm]·1e-9
    for nid, m in fr.masses.items():
        for d in range(3):
            M[6 * idx[nid] + d, 6 * idx[nid] + d] += m * 1e-3          # kg → t
        total += m
    fixed = np.array([x for nid in ids for x in fr.nodes[nid].fixed])
    free = np.where(~fixed)[0]
    if len(free) == 0:
        raise FrameError("Todos os graus de liberdade estão restritos.")
    Kff, Mff = K[np.ix_(free, free)], M[np.ix_(free, free)]
    if np.linalg.matrix_rank(Kff, tol=1e-9 * np.abs(np.diag(Kff)).max()) < len(free):
        raise FrameError("Estrutura hipostática (mecanismo): a análise modal exige apoios suficientes.")
    w2, vec = eigh(Kff, Mff)
    out_f, shapes = [], []
    for i in range(min(n_modes, len(w2))):
        out_f.append(math.sqrt(max(w2[i], 0.0)) / (2 * math.pi))
        full = np.zeros(n)
        full[free] = vec[:, i]
        mx = np.abs(full).max() or 1.0
        shapes.append({nid: (full[6 * idx[nid]:6 * idx[nid] + 6] / mx).tolist() for nid in ids})
    return ModalResult(out_f, shapes, total)


def modal_report(m: ModalResult, fr: Frame) -> str:
    out = "\nAnálise modal (K φ = ω² M φ; massa consistente + massas concentradas; sem amortecimento)\n" + "─" * 52 + "\n"
    out += f"  massa total considerada: {m.mass_total_kg:,.1f} kg\n".replace(",", ".")
    out += "  modo   f [Hz]   T [s]    maior componente (nó, GDL)\n"
    names = ["u", "v", "w", "θx", "θy", "θz"]
    for i, (f, sh) in enumerate(zip(m.freq_hz, m.shapes), 1):
        nid, d = max(((n, k) for n, v in sh.items() for k in range(6)), key=lambda t: abs(sh[t[0]][t[1]]))
        out += f"  {i:>3}  {f:8.3f}  {1 / f if f > 0 else math.inf:7.4f}   {nid}.{names[d]}\n"
    out += "  Nota: modos duplos aparecem quando Iy = Iz (flexão nos dois planos); torsional/axial entram se o modelo os excita.\n"
    return out


def geometric_stiffness(b: FBeam, L: float, N: float) -> np.ndarray:
    """Rigidez geométrica local (12×12) para esforço axial N (tração +), ref. Przemieniecki/Cook; inclui o termo de torção N·Ip/(A·L)."""
    kg = np.zeros((12, 12))
    base = N / (30 * L) * np.array([[36, 3 * L, -36, 3 * L], [3 * L, 4 * L * L, -3 * L, -L * L], [-36, -3 * L, 36, -3 * L], [3 * L, -L * L, -3 * L, 4 * L * L]])
    for dofs, sgn in (((1, 5, 7, 11), 1.0), ((2, 4, 8, 10), -1.0)):
        S = np.diag([1, sgn, 1, sgn])
        mb = S @ base @ S
        for a, ia in enumerate(dofs):
            for q, iq in enumerate(dofs):
                kg[ia, iq] += mb[a, q]
    t = N * (b.Iy + b.Iz) / (b.A * L)
    kg[3, 3] = kg[9, 9] = t
    kg[3, 9] = kg[9, 3] = -t
    return kg


@dataclass
class BucklingResult:
    factors: list          # λ_cr: multiplicadores do carregamento de referência que causam flambagem (apenas λ > 0)
    shapes: list           # modos (nó -> 6), normalizados
    reference_axial: dict  # viga -> N (N, tração +) no carregamento de referência


def buckling(fr: Frame, n_modes: int = 3) -> BucklingResult:
    """Flambagem linear (bifurcação): (K + λ·Kg(N_ref)) φ = 0, com N_ref do carregamento aplicado. Carga crítica = λ·(carga de referência).
    Só vale para o regime elástico linear, imperfeições nulas e cargas que não mudam de direção; ignora plasticidade (colunas curtas flambam abaixo disso em Johnson)."""
    from scipy.linalg import eigh
    res = solve(fr)
    ids = list(fr.nodes)
    idx = {n: i for i, n in enumerate(ids)}
    n = 6 * len(ids)
    K = np.zeros((n, n))
    Kg = np.zeros((n, n))
    ref_axial = {}
    for b in fr.beams.values():
        R, L = local_axes(fr.nodes[b.n1].xyz, fr.nodes[b.n2].xyz, b.ref)
        T = transform(R)
        N = -float(res.end_forces[b.id][0])           # força do nó sobre a viga em +x local = compressão ⇒ N de tração = −f[0]
        ref_axial[b.id] = N
        s = list(range(6 * idx[b.n1], 6 * idx[b.n1] + 6)) + list(range(6 * idx[b.n2], 6 * idx[b.n2] + 6))
        K[np.ix_(s, s)] += T.T @ local_stiffness(b, L) @ T
        Kg[np.ix_(s, s)] += T.T @ geometric_stiffness(b, L, N) @ T
    fixed = np.array([x for nid in ids for x in fr.nodes[nid].fixed])
    free = np.where(~fixed)[0]
    Kf, Kgf = K[np.ix_(free, free)], Kg[np.ix_(free, free)]
    nu, vec = eigh(-Kgf, Kf)
    pos = [(1.0 / v, i) for i, v in enumerate(nu) if v > 1e-12 * max(1.0, abs(nu).max())]
    pos.sort()
    factors, shapes = [], []
    for lam, i in pos[:n_modes]:
        full = np.zeros(n)
        full[free] = vec[:, i]
        mx = np.abs(full).max() or 1.0
        factors.append(lam)
        shapes.append({nid: (full[6 * idx[nid]:6 * idx[nid] + 6] / mx).tolist() for nid in ids})
    return BucklingResult(factors, shapes, ref_axial)


def buckling_report(b: BucklingResult) -> str:
    out = "\nFlambagem linear ((K + λ·Kg) φ = 0; λ multiplica o carregamento aplicado)\n" + "─" * 52 + "\n"
    comp = {k: -v for k, v in b.reference_axial.items() if v < -1e-9}
    if not b.factors:
        return out + "  Nenhum fator crítico positivo: o carregamento de referência não comprime nenhuma viga.\n"
    for i, lam in enumerate(b.factors, 1):
        out += f"  modo {i}: λcr = {lam:.4f}\n"
    out += "  compressão de referência (kN): " + ", ".join(f"{k}={v / 1000:.2f}" for k, v in comp.items()) + "\n"
    out += f"  Primeira carga crítica = {b.factors[0]:.4f} × carregamento aplicado. Elástica, sem imperfeições, cargas seguidoras desprezadas;\n"
    out += "  colunas curtas escoam antes (use Johnson); confira também o modo local da seção.\n"
    return out
