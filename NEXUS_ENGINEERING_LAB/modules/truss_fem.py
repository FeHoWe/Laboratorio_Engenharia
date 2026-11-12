"""Treliça espacial de barras articuladas — método da rigidez direta (V2.4).

Resolve deslocamentos, reações e esforço axial de cada barra. Unidades: mm, N, MPa (N/mm²).
HONESTIDADE: modelo linear elástico de pequenos deslocamentos, nós rotulados (sem momento nas barras), cargas só nos nós, sem peso próprio automático,
sem plasticidade nem flambagem global; a verificação de flambagem de cada barra comprimida é Euler (rotulada nas duas pontas) e só serve de triagem.
Equilíbrio global e comprimento/geometria são conferidos no resultado; um mecanismo (estrutura hipostática) é detectado e recusado.

Formato de texto (uma instrução por linha, '#' comenta):
  NODE id x y z [fix=xyz]        # fix: letras dos graus de liberdade restritos (ex.: fix=xz)
  BAR  id n1 n2 A E [I=...]      # A em mm², E em MPa; I (mm⁴) opcional, para a triagem de Euler
  LOAD node fx fy fz             # N
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np


class TrussError(ValueError):
    pass


@dataclass
class Node:
    id: str
    xyz: np.ndarray
    fixed: tuple = (False, False, False)


@dataclass
class Bar:
    id: str
    n1: str
    n2: str
    area: float
    E: float
    inertia: float = 0.0


@dataclass
class Truss:
    nodes: dict = field(default_factory=dict)
    bars: dict = field(default_factory=dict)
    loads: dict = field(default_factory=dict)

    def add_node(self, id, x, y, z, fix=""):
        self.nodes[id] = Node(id, np.array([x, y, z], float), tuple(c in fix for c in "xyz"))

    def add_bar(self, id, n1, n2, area, E, inertia=0.0):
        if n1 not in self.nodes or n2 not in self.nodes:
            raise TrussError(f"Barra {id}: nó inexistente ({n1}, {n2}).")
        if n1 == n2:
            raise TrussError(f"Barra {id}: nós iguais.")
        if area <= 0 or E <= 0:
            raise TrussError(f"Barra {id}: A e E devem ser positivos.")
        self.bars[id] = Bar(id, n1, n2, float(area), float(E), float(inertia))

    def add_load(self, node, fx, fy, fz):
        if node not in self.nodes:
            raise TrussError(f"Carga em nó inexistente: {node}.")
        v = self.loads.get(node, np.zeros(3))
        self.loads[node] = v + np.array([fx, fy, fz], float)


def parse(text: str) -> Truss:
    t = Truss()
    for ln, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#")[0].strip()
        if not line:
            continue
        p = line.split()
        try:
            kind = p[0].upper()
            if kind == "NODE":
                fix = next((q[4:] for q in p[5:] if q.lower().startswith("fix=")), "")
                t.add_node(p[1], float(p[2]), float(p[3]), float(p[4]), fix.lower())
            elif kind == "BAR":
                inertia = next((float(q[2:]) for q in p[6:] if q.upper().startswith("I=")), 0.0)
                t.add_bar(p[1], p[2], p[3], float(p[4]), float(p[5]), inertia)
            elif kind == "LOAD":
                t.add_load(p[1], float(p[2]), float(p[3]), float(p[4]))
            else:
                raise TrussError(f"instrução desconhecida '{p[0]}'")
        except TrussError as exc:
            raise TrussError(f"Linha {ln}: {exc}") from None
        except (IndexError, ValueError):
            raise TrussError(f"Linha {ln}: formato inválido → '{line}'") from None
    return t


@dataclass
class TrussResult:
    displacement: dict
    reactions: dict
    force: dict          # esforço axial por barra (N, + tração)
    stress: dict         # MPa
    length: dict
    equilibrium_error: float
    buckling: dict       # id -> (Pcr, coeficiente de segurança) para barras comprimidas com I informado


def solve(t: Truss) -> TrussResult:
    ids = list(t.nodes)
    idx = {n: i for i, n in enumerate(ids)}
    n = 3 * len(ids)
    if not t.bars:
        raise TrussError("Sem barras.")
    K = np.zeros((n, n))
    geom = {}
    for b in t.bars.values():
        p1, p2 = t.nodes[b.n1].xyz, t.nodes[b.n2].xyz
        d = p2 - p1
        L = float(np.linalg.norm(d))
        if L < 1e-9:
            raise TrussError(f"Barra {b.id}: comprimento nulo.")
        c = d / L
        k = b.E * b.area / L * np.outer(c, c)
        s = [3 * idx[b.n1] + i for i in range(3)] + [3 * idx[b.n2] + i for i in range(3)]
        for a in range(3):
            for bb in range(3):
                K[s[a], s[bb]] += k[a, bb]
                K[s[3 + a], s[3 + bb]] += k[a, bb]
                K[s[a], s[3 + bb]] -= k[a, bb]
                K[s[3 + a], s[bb]] -= k[a, bb]
        geom[b.id] = (L, c, s)
    F = np.zeros(n)
    for nid, v in t.loads.items():
        F[3 * idx[nid]:3 * idx[nid] + 3] += v
    fixed = np.array([f for nid in ids for f in t.nodes[nid].fixed])
    free = np.where(~fixed)[0]
    if len(free) == 0:
        raise TrussError("Todos os graus de liberdade estão restritos.")
    Kff = K[np.ix_(free, free)]
    if np.linalg.matrix_rank(Kff) < len(free):
        raise TrussError("Estrutura hipostática (mecanismo) ou com graus de liberdade soltos: faltam barras/apoios (ou nó isolado). "
                         "Em treliça plana restrinja o eixo fora do plano nos nós.")
    u = np.zeros(n)
    u[free] = np.linalg.solve(Kff, F[free])
    R = K @ u - F
    R[free] = 0.0
    forces, stress, length, buck = {}, {}, {}, {}
    for b in t.bars.values():
        L, c, s = geom[b.id]
        ue = u[s]
        N = b.E * b.area / L * float(c @ (ue[3:] - ue[:3]))
        forces[b.id], stress[b.id], length[b.id] = N, N / b.area, L
        if N < -1e-6 and b.inertia > 0:
            pcr = math.pi ** 2 * b.E * b.inertia / L ** 2
            buck[b.id] = (pcr, pcr / -N)
    scale = max(float(np.abs(F).sum()), 1.0)
    return TrussResult(
        displacement={nid: u[3 * idx[nid]:3 * idx[nid] + 3].copy() for nid in ids},
        reactions={nid: R[3 * idx[nid]:3 * idx[nid] + 3].copy() for nid in ids if fixed[3 * idx[nid]:3 * idx[nid] + 3].any()},
        force=forces, stress=stress, length=length, equilibrium_error=float(np.abs(
            np.array([F[0::3].sum() + R[0::3].sum(), F[1::3].sum() + R[1::3].sum(), F[2::3].sum() + R[2::3].sum()])).max() / scale),
        buckling=buck)


def warren_example(panels: int = 6, panel: float = 2000.0, height: float = 2000.0, area: float = 8000.0, E: float = 200000.0,
                   inertia: float = 6.0e6, load_per_node: float = 50000.0) -> str:
    """Texto de uma treliça Warren plana (plano x–z) com montantes: apoio fixo em 0, rolete no último nó inferior, carga vertical nos nós inferiores."""
    out = ["# Treliça Warren plana (plano x-z; y restrito em todos os nós). mm, N, MPa. Valores de A, E, I e cargas são EXEMPLOS: troque pelos seus."]
    for i in range(panels + 1):
        fixb = "y" + ("xz" if i == 0 else ("z" if i == panels else ""))
        out.append(f"NODE B{i} {i * panel:g} 0 0 fix={fixb}")
    for i in range(panels + 1):
        out.append(f"NODE T{i} {i * panel:g} 0 {height:g} fix=y")
    n = 0
    def bar(a, b):
        nonlocal n
        n += 1
        out.append(f"BAR m{n} {a} {b} {area:g} {E:g} I={inertia:g}")
    for i in range(panels):
        bar(f"B{i}", f"B{i + 1}")
        bar(f"T{i}", f"T{i + 1}")
        bar(f"B{i}", f"T{i + 1}") if i % 2 == 0 else bar(f"T{i}", f"B{i + 1}")
    for i in range(panels + 1):
        bar(f"B{i}", f"T{i}")
    for i in range(1, panels):
        out.append(f"LOAD B{i} 0 0 {-load_per_node:g}")
    return "\n".join(out)


def report(t: Truss, r: TrussResult, yield_strength: float = 0.0) -> str:
    out = "Treliça — método da rigidez direta\n" + "─" * 36 + "\n"
    out += f"  nós {len(t.nodes)} · barras {len(t.bars)} · erro de equilíbrio global {r.equilibrium_error:.2e} (relativo)\n\n"
    out += "  barra   nós        L[mm]    N[kN]   σ[MPa]   situação\n"
    worst = None
    for b in t.bars.values():
        N = r.force[b.id]
        st = "tração" if N > 1e-6 else ("compressão" if N < -1e-6 else "nula")
        extra = ""
        if yield_strength > 0 and abs(r.stress[b.id]) > 1e-6:
            extra = f" n_esc={yield_strength / abs(r.stress[b.id]):.2f}"
        if b.id in r.buckling:
            extra += f" n_Euler={r.buckling[b.id][1]:.2f}"
        out += f"  {b.id:<7} {b.n1}-{b.n2:<7} {r.length[b.id]:>8.0f} {N / 1000:>9.2f} {r.stress[b.id]:>8.1f}   {st}{extra}\n"
        if worst is None or abs(N) > abs(r.force[worst]):
            worst = b.id
    umax = max(r.displacement.items(), key=lambda kv: np.linalg.norm(kv[1]))
    out += f"\n  maior esforço axial: {worst} ({r.force[worst] / 1000:.2f} kN)\n"
    out += f"  maior deslocamento: nó {umax[0]} = {np.linalg.norm(umax[1]):.3f} mm  (ux {umax[1][0]:.3f}, uy {umax[1][1]:.3f}, uz {umax[1][2]:.3f})\n"
    out += "  reações:\n" + "".join(f"    {k}: Rx {v[0] / 1000:.2f} Ry {v[1] / 1000:.2f} Rz {v[2] / 1000:.2f} kN\n" for k, v in r.reactions.items())
    return out + ("\nHipóteses: nós rotulados, linear elástico, pequenos deslocamentos, cargas só nos nós, sem peso próprio; "
                  "Euler (rotulado-rotulado) é triagem, não verificação normativa; sem ligações, excentricidades ou fadiga.\n")
