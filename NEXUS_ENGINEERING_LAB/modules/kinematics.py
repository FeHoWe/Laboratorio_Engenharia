"""Cinemática por poses (V1.8): movimento de exibição de peças rígidas em função de um ângulo de entrada.

Cada ``Link`` associa peças (ids) a uma função ``f(theta_graus) -> matriz 4x4`` no referencial do MUNDO.
A geometria nunca é alterada: a matriz só é aplicada ao ator na cena (como a explosão) e na tela de celular.
Só movimentos prescritos (sem dinâmica, sem forças, sem contato, sem folgas). Peça sem Link fica parada.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np

PoseFn = Callable[[float], np.ndarray]


def rotation_about(point, axis, angle_rad: float) -> np.ndarray:
    """Matriz 4x4 de rotação de ``angle_rad`` (regra da mão direita) em torno da reta (point, axis)."""
    p = np.asarray(point, dtype=float)
    a = np.asarray(axis, dtype=float)
    a = a / np.linalg.norm(a)
    k = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    r = np.eye(3) + np.sin(angle_rad) * k + (1 - np.cos(angle_rad)) * (k @ k)
    m = np.eye(4)
    m[:3, :3] = r
    m[:3, 3] = p - r @ p
    return m


def translation(v) -> np.ndarray:
    m = np.eye(4)
    m[:3, 3] = np.asarray(v, dtype=float)
    return m


def scale_about(point, factors) -> np.ndarray:
    """Escala não uniforme em torno de um ponto (usada só para ilustrar mola comprimida)."""
    p = np.asarray(point, dtype=float)
    f = np.asarray(factors, dtype=float)
    m = np.eye(4)
    m[0, 0], m[1, 1], m[2, 2] = f
    m[:3, 3] = p - f * p
    return m


@dataclass
class Link:
    ids: list[str]
    fn: PoseFn
    label: str = ""
    rigid: bool = True          # False: a pose inclui escala (ilustrativa)
    js: Optional[dict] = None   # descritor analítico para o visualizador de celular (mesma matemática, em JavaScript)


@dataclass
class Mechanism:
    name: str
    input_label: str
    period_deg: float
    links: list[Link] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    readout: Optional[Callable[[float], str]] = None       # texto de leituras para a janela de animação
    extra: dict = field(default_factory=dict)             # dados globais para o celular (tabelas de came, trajeto da correia)

    def poses(self, theta_deg: float) -> dict[str, np.ndarray]:
        out: dict[str, np.ndarray] = {}
        for ln in self.links:
            m = ln.fn(theta_deg)
            for i in ln.ids:
                out[i] = m
        return out

    @property
    def moving_ids(self) -> set[str]:
        return {i for ln in self.links for i in ln.ids}

    def mobile_spec(self, index_of: dict) -> Optional[dict]:
        """Descrição compacta para o celular: ligações com descritor, ids trocados pelos índices das peças."""
        links = []
        for ln in self.links:
            idx = [index_of[i] for i in ln.ids if i in index_of]
            if idx and ln.js:
                links.append({"ids": idx, "d": ln.js})
        if not links:
            return None
        return {"name": self.name, "label": self.input_label, "period": self.period_deg, "links": links, "notes": self.notes, "extra": self.extra}

    def at_rest(self) -> dict[str, np.ndarray]:
        return {}


def is_rigid(m: np.ndarray, tol: float = 1e-9) -> bool:
    r = m[:3, :3]
    return bool(np.allclose(r @ r.T, np.eye(3), atol=tol) and abs(np.linalg.det(r) - 1) < tol)


# ------------------------------------------------------------------ trajeto fechado (correia)
@dataclass
class ClosedPath:
    """Contorno convexo fechado, anti-horário no plano (y, z), em torno de círculos: retas tangentes + arcos.

    ``pieces``: {"k":"L","p":[y,z],"u":[uy,uz],"n":[ny,nz],"len":l} ou {"k":"A","c":[y,z],"r":r,"a0":rad,"len":l}
    (o arco percorre sentido anti-horário a partir de a0; n = normal externa, à direita do sentido de percurso).
    """
    pieces: list
    length: float

    def at(self, s: float):
        """(ponto [y,z], tangente [y,z], normal externa [y,z]) na posição de arco ``s`` (módulo o comprimento)."""
        s = s % self.length
        for pc in self.pieces:
            if s <= pc["len"] + 1e-12 or pc is self.pieces[-1]:
                if pc["k"] == "L":
                    u, n = np.array(pc["u"]), np.array(pc["n"])
                    return np.array(pc["p"]) + s * u, u, n
                a = pc["a0"] + s / pc["r"]
                n = np.array([math.cos(a), math.sin(a)])
                return np.array(pc["c"]) + pc["r"] * n, np.array([-n[1], n[0]]), n
            s -= pc["len"]
        raise AssertionError

    def frame(self, s: float) -> np.ndarray:
        """Referencial rígido do dente em ``s``: x=X, y local = tangente, z local = normal para DENTRO (destro)."""
        p, t, n = self.at(s)
        m = np.eye(4)
        m[:3, 1] = (0, t[0], t[1])
        m[:3, 2] = (0, -n[0], -n[1])
        m[:3, 3] = (0, p[0], p[1])
        return m

    def to_json(self) -> dict:
        r = lambda v: [round(float(x), 6) for x in v]  # noqa: E731
        out = []
        for pc in self.pieces:
            if pc["k"] == "L":
                out.append({"k": "L", "p": r(pc["p"]), "u": r(pc["u"]), "n": r(pc["n"]), "len": round(float(pc["len"]), 6)})
            else:
                out.append({"k": "A", "c": r(pc["c"]), "r": round(float(pc["r"]), 6), "a0": round(float(pc["a0"]), 8),
                            "len": round(float(pc["len"]), 6)})
        return {"pieces": out, "length": round(float(self.length), 6)}


def hull_path(circles) -> ClosedPath:
    """Trajeto convexo anti-horário envolvendo [(y, z, r), ...] (mesma construção do contorno da correia no gerador)."""
    n = len(circles)
    tang = []
    for i in range(n):
        ay, az, ra = circles[i]
        by, bz, rb = circles[(i + 1) % n]
        dy, dz = by - ay, bz - az
        L = math.hypot(dy, dz)
        uy, uz = dy / L, dz / L
        vy, vz = uz, -uy
        k = (ra - rb) / L
        c = math.sqrt(1 - k * k)
        ny, nz = k * uy + c * vy, k * uz + c * vz
        tang.append(((ay + ra * ny, az + ra * nz), (by + rb * ny, bz + rb * nz), (ny, nz)))
    pieces = []
    for i in range(n):
        p1, p2, nn = tang[i]
        d = np.array(p2) - np.array(p1)
        ln = float(np.linalg.norm(d))
        pieces.append({"k": "L", "p": list(p1), "u": list(d / ln), "n": list(nn), "len": ln})
        cy, cz, r = circles[(i + 1) % n]
        nxt = tang[(i + 1) % n][0]
        a0 = math.atan2(p2[1] - cz, p2[0] - cy)
        a1 = math.atan2(nxt[1] - cz, nxt[0] - cy)
        sweep = (a1 - a0) % (2 * math.pi)
        pieces.append({"k": "A", "c": [cy, cz], "r": r, "a0": a0, "len": r * sweep})
    return ClosedPath(pieces, sum(pc["len"] for pc in pieces))
