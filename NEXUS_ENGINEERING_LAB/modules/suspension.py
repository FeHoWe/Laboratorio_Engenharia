"""Cinemática de suspensão duplo-A (vista frontal, 2D) — camber, bitola (scrub), centro instantâneo e centro de rolagem.

Modelo: braço inferior A(interno)→B(externo, na manga), braço superior C(interno)→D(externo, na manga); a manga (upright) é o corpo rígido
B–D com o centro da roda W e o ponto de contato P presos a ele. Comprimentos |AB|, |CD|, |BD| constantes. Plano y–z (y para fora do
carro, z para cima). Heave = deslocamento VERTICAL do centro da roda (bump>0). Resolvido por bissecção sobre o ângulo do braço inferior +
interseção de dois círculos (fechado). Sem buchas/elastocinemática; geometria 2D (sem caster/KPI/convergência) — é a vista frontal.
Verificação analítica no teste: camber gain ≈ 1/FVSA (FVSA = distância do centro instantâneo ao centro da roda, em y).
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class DuploA:
    A: tuple     # pivô interno inferior (y, z) [m]
    B: tuple     # rótula externa inferior
    C: tuple     # pivô interno superior
    D: tuple     # rótula externa superior
    W: tuple     # centro da roda
    P: tuple     # ponto de contato com o solo

    def validar(self) -> None:
        for n in "ABCDWP":
            p = getattr(self, n)
            if len(p) != 2 or not all(math.isfinite(x) for x in p):
                raise ValueError(f"ponto {n} inválido")
        if _d(self.A, self.B) <= 0 or _d(self.C, self.D) <= 0 or _d(self.B, self.D) <= 0:
            raise ValueError("comprimentos de braço/manga devem ser positivos")


def _d(p, q):
    return math.hypot(p[0] - q[0], p[1] - q[1])


def _circ(c1, r1, c2, r2, ref):
    """Interseção de dois círculos; escolhe a solução mais próxima de `ref`. None se não se cruzam."""
    d = _d(c1, c2)
    if d < 1e-12 or d > r1 + r2 + 1e-12 or d < abs(r1 - r2) - 1e-12:
        return None
    a = (r1 * r1 - r2 * r2 + d * d) / (2 * d)
    h = math.sqrt(max(r1 * r1 - a * a, 0.0))
    mx, my = c1[0] + a * (c2[0] - c1[0]) / d, c1[1] + a * (c2[1] - c1[1]) / d
    s1 = (mx + h * (c2[1] - c1[1]) / d, my - h * (c2[0] - c1[0]) / d)
    s2 = (mx - h * (c2[1] - c1[1]) / d, my + h * (c2[0] - c1[0]) / d)
    return s1 if _d(s1, ref) <= _d(s2, ref) else s2


def _pose(s: DuploA, th: float):
    """Pose para o ângulo `th` do braço inferior (medido a partir do estado de projeto). Retorna (B, D, W, P) ou None."""
    ab = _d(s.A, s.B)
    th0 = math.atan2(s.B[1] - s.A[1], s.B[0] - s.A[0])
    B = (s.A[0] + ab * math.cos(th0 + th), s.A[1] + ab * math.sin(th0 + th))
    D = _circ(s.C, _d(s.C, s.D), B, _d(s.B, s.D), s.D)
    if D is None:
        return None
    # corpo rígido da manga: rotação que leva (B0→D0) para (B→D)
    a0 = math.atan2(s.D[1] - s.B[1], s.D[0] - s.B[0])
    a1 = math.atan2(D[1] - B[1], D[0] - B[0])
    r = a1 - a0
    c, sn = math.cos(r), math.sin(r)

    def mov(p):
        v = (p[0] - s.B[0], p[1] - s.B[1])
        return (B[0] + c * v[0] - sn * v[1], B[1] + sn * v[0] + c * v[1])

    return B, D, mov(s.W), mov(s.P), r


def resolver(s: DuploA, heave: float) -> dict:
    """Posição para um heave (m, vertical do centro da roda). Devolve camber (graus; + = topo da roda para FORA), Δbitola (m, + = roda para fora),
    centro instantâneo IC e centro de rolagem RC (altura, m, em y=0). Levanta ValueError se o heave está fora da faixa cinemática."""
    s.validar()
    f = lambda th: (_pose(s, th)[2][1] - s.W[1] - heave) if _pose(s, th) else None  # noqa: E731
    lo, hi = -1.2, 1.2
    # varredura para achar intervalo de sinal com pose válida
    xs = [lo + (hi - lo) * i / 600 for i in range(601)]
    vals = [(x, f(x)) for x in xs]
    vals = [(x, v) for x, v in vals if v is not None]
    br = None
    for (x0, v0), (x1, v1) in zip(vals, vals[1:]):
        if v0 == 0:
            br = (x0, x0); break
        if v0 * v1 < 0 and abs(x1 - x0) < 0.01 and abs(x0) < 0.6:
            br = (x0, x1) if br is None or abs(x0) < abs(br[0]) else br
    if br is None:
        raise ValueError("heave fora da faixa cinemática do mecanismo")
    a, b = br
    for _ in range(80):
        m = 0.5 * (a + b)
        fm, fa = f(m), f(a)
        if fm is None or fa is None:
            break
        if fa * fm <= 0:
            b = m
        else:
            a = m
    th = 0.5 * (a + b)
    B, D, W, P, rot = _pose(s, th)
    camber = -math.degrees(rot)             # manga girando "para fora" no topo = camber positivo
    ic = _inter_retas(s.A, B, s.C, D)
    rc = None
    if ic is not None and abs(P[0] - ic[0]) > 1e-9:
        t = (0.0 - P[0]) / (ic[0] - P[0])
        rc = P[1] + t * (ic[1] - P[1])
    return {"heave_m": heave, "camber_graus": camber, "delta_bitola_m": P[0] - s.P[0], "B": B, "D": D, "W": W, "P": P, "IC": ic, "RC_altura_m": rc,
            "FVSA_m": (abs(ic[0] - W[0]) if ic else None)}


def _inter_retas(p1, p2, p3, p4):
    d1, d2 = (p2[0] - p1[0], p2[1] - p1[1]), (p4[0] - p3[0], p4[1] - p3[1])
    den = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(den) < 1e-12:
        return None                          # braços paralelos: IC no infinito
    t = ((p3[0] - p1[0]) * d2[1] - (p3[1] - p1[1]) * d2[0]) / den
    return (p1[0] + t * d1[0], p1[1] + t * d1[1])


def curva_heave(s: DuploA, h_min: float = -0.04, h_max: float = 0.04, n: int = 9) -> list:
    return [resolver(s, h_min + (h_max - h_min) * i / (n - 1)) for i in range(n)]


def exemplo_ilustrativo() -> DuploA:
    """Geometria ILUSTRATIVA (não é de um carro real): braço superior mais curto e braços convergindo para dentro (IC interno) → camber negativo em bump."""
    return DuploA(A=(0.20, 0.14), B=(0.60, 0.12), C=(0.25, 0.30), D=(0.56, 0.32), W=(0.63, 0.24), P=(0.63, 0.0))
