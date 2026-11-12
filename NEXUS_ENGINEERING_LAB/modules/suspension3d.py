"""Suspensão duplo-A 3D completa (V3.8) — cinemática de corpo rígido com 5 barras (2 do braço inferior, 2 do superior, 1 barra de direção).

Eixos: x à frente, y para FORA do carro, z para cima (mesmo de `vehicle_combined.pino_mestre_3d`). A manga (upright) é um corpo rígido que contém a
rótula inferior B, a superior D, a rótula externa da barra Tj, o centro da roda W e o contato P. Cada braço em A tem DUAS barras (pivôs dianteiro e
traseiro até a rótula): |B−LF|, |B−LR|, |D−UF|, |D−UR| e |Tj−T| são constantes (T = ponta interna da barra, no pinhão/cremalheira, deslocada em y pelo curso
da cremalheira). 6 graus de liberdade − 5 barras = 1 grau de liberdade; o heave (z do centro da roda) fecha o sistema → 6 equações, 6 incógnitas
(translação + vetor de rotação da manga), resolvidas por Newton com jacobiano numérico e continuação (homotopia) a partir da pose de projeto.

Saídas: camber, convergência (toe), bump steer (dToe/dHeave), camber gain, caster, KPI, trail mecânico, scrub, variação de bitola e de entre-eixos,
razão de esterçamento (dEsterço/dCurso da cremalheira). Classe ANALITICO (cinemática geométrica exata das barras rígidas).
Elastocinemática: apenas LINEAR e SIMPLIFICADA — coeficientes (°/kN) informados pelo usuário multiplicam as forças no contato; NÃO há modelo de buchas,
nem rigidez de braços, nem dinâmica. Coeficientes padrão = 0 (sem efeito). Geometria de exemplo é ILUSTRATIVA (não de carro real).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import vehicle_combined as vc
from .result_trace import TracedResult


@dataclass
class DuploA3D:
    LF: tuple      # pivô interno inferior dianteiro (x, y, z) [m]
    LR: tuple      # pivô interno inferior traseiro
    B: tuple       # rótula externa inferior (na manga)
    UF: tuple      # pivô interno superior dianteiro
    UR: tuple      # pivô interno superior traseiro
    D: tuple       # rótula externa superior (na manga)
    T: tuple       # ponta INTERNA da barra de direção (cremalheira)
    Tj: tuple      # ponta EXTERNA da barra de direção (na manga)
    W: tuple       # centro da roda
    P: tuple       # ponto de contato com o solo
    camber_estatico_graus: float = 0.0   # + = topo da roda para fora (informado pelo usuário)
    toe_estatico_graus: float = 0.0      # + = convergência (toe-in)

    def validar(self) -> None:
        for n in ("LF", "LR", "B", "UF", "UR", "D", "T", "Tj", "W", "P"):
            p = getattr(self, n)
            if len(p) != 3 or not all(math.isfinite(x) for x in p):
                raise ValueError(f"ponto {n} inválido (esperado x, y, z finitos)")
        for a, b, nome in ((self.LF, self.B, "LF–B"), (self.LR, self.B, "LR–B"), (self.UF, self.D, "UF–D"), (self.UR, self.D, "UR–D"),
                           (self.T, self.Tj, "barra de direção"), (self.B, self.D, "B–D (manga)")):
            if _n(_sub(a, b)) <= 1e-9:
                raise ValueError(f"comprimento {nome} deve ser positivo")
        if self.D[2] <= self.B[2]:
            raise ValueError("rótula superior D deve estar acima da inferior B")
        if abs(self.camber_estatico_graus) > 20 or abs(self.toe_estatico_graus) > 20:
            raise ValueError("camber/toe estáticos fora de ±20°")


def _sub(a, b):
    return np.asarray(a, float) - np.asarray(b, float)


def _n(v):
    return float(np.linalg.norm(v))


def _rodrigues(w: np.ndarray) -> np.ndarray:
    th = float(np.linalg.norm(w))
    if th < 1e-14:
        return np.eye(3) + _skew(w)
    k = w / th
    K = _skew(k)
    return np.eye(3) + math.sin(th) * K + (1 - math.cos(th)) * (K @ K)


def _skew(w):
    return np.array([[0, -w[2], w[1]], [w[2], 0, -w[0]], [-w[1], w[0], 0]])


def _frame0(s: DuploA3D):
    """Vetores 'frente da roda' f0 e 'eixo de giro' (para fora) s0 no estado de projeto, com toe e camber estáticos."""
    t, c = math.radians(s.toe_estatico_graus), math.radians(s.camber_estatico_graus)
    f1 = np.array([math.cos(t), -math.sin(t), 0.0])          # toe-in: frente da roda aponta para dentro (−y)
    s1 = np.array([math.sin(t), math.cos(t), 0.0])
    s0 = s1 * math.cos(c) + np.array([0, 0, -1.0]) * math.sin(c)   # camber +: eixo (para fora) inclina para BAIXO
    f0 = f1
    return f0, s0


def _estado(s: DuploA3D):
    pts = {n: np.asarray(getattr(s, n), float) for n in ("LF", "LR", "B", "UF", "UR", "D", "T", "Tj", "W", "P")}
    L = dict(bf=_n(pts["B"] - pts["LF"]), br=_n(pts["B"] - pts["LR"]), df=_n(pts["D"] - pts["UF"]), dr=_n(pts["D"] - pts["UR"]), t=_n(pts["Tj"] - pts["T"]))
    return pts, L


def _pose(pts, x):
    c, w = x[:3], x[3:]
    R = _rodrigues(w)
    W0 = pts["W"]
    mov = lambda p: c + R @ (p - W0)          # noqa: E731  (c = posição do centro da roda)
    return R, mov


def _res(pts, L, x, heave, rack):
    R, mov = _pose(pts, x)
    B, D, Tj = mov(pts["B"]), mov(pts["D"]), mov(pts["Tj"])
    T = pts["T"] + np.array([0.0, rack, 0.0])
    return np.array([_n(B - pts["LF"]) ** 2 - L["bf"] ** 2, _n(B - pts["LR"]) ** 2 - L["br"] ** 2,
                     _n(D - pts["UF"]) ** 2 - L["df"] ** 2, _n(D - pts["UR"]) ** 2 - L["dr"] ** 2,
                     _n(Tj - T) ** 2 - L["t"] ** 2, (x[2] - pts["W"][2]) - heave])


def _newton(pts, L, x0, heave, rack):
    x = x0.copy()
    for _ in range(60):
        r = _res(pts, L, x, heave, rack)
        if np.max(np.abs(r[:5])) < 1e-13 and abs(r[5]) < 1e-13:
            return x
        J = np.empty((6, 6))
        for j in range(6):
            dx = np.zeros(6); h = 1e-7; dx[j] = h
            J[:, j] = (_res(pts, L, x + dx, heave, rack) - _res(pts, L, x - dx, heave, rack)) / (2 * h)
        try:
            step = np.linalg.solve(J, -r)
        except np.linalg.LinAlgError:
            return None
        # busca em linha simples
        a, n0 = 1.0, np.linalg.norm(r)
        while a > 1e-4 and np.linalg.norm(_res(pts, L, x + a * step, heave, rack)) > n0 * (1 - 1e-4 * a):
            a *= 0.5
        x = x + a * step
        if np.linalg.norm(a * step) < 1e-15:
            break
    r = _res(pts, L, x, heave, rack)
    return x if (np.max(np.abs(r[:5])) < 1e-9 and abs(r[5]) < 1e-9) else None


def resolver_3d(s: DuploA3D, heave: float = 0.0, rack: float = 0.0, passos: int = 12) -> dict:
    """Pose da manga para `heave` [m, + = bump, vertical do centro da roda] e curso da cremalheira `rack` [m, + = ponta interna da barra para FORA].

    Continuação em `passos` etapas a partir do projeto. ValueError se o mecanismo não fecha (fora da faixa cinemática)."""
    s.validar()
    pts, L = _estado(s)
    x = np.concatenate([pts["W"], np.zeros(3)])
    for k in range(1, passos + 1):
        f = k / passos
        x = _newton(pts, L, x, heave * f, rack * f)
        if x is None:
            raise ValueError("heave/curso da cremalheira fora da faixa cinemática do mecanismo")
    R, mov = _pose(pts, x)
    B, D, W, P, Tj = mov(pts["B"]), mov(pts["D"]), mov(pts["W"]), mov(pts["P"]), mov(pts["Tj"])
    f0, s0 = _frame0(s)
    ax, fw = R @ s0, R @ f0
    camber = -math.degrees(math.asin(max(-1.0, min(1.0, float(ax[2])))))
    toe_in = -math.degrees(math.atan2(fw[1], fw[0]))
    pm = vc.pino_mestre_3d(tuple(B), tuple(D), tuple(P))
    return {"heave_m": heave, "rack_m": rack, "camber_graus": camber, "toe_in_graus": toe_in,
            "caster_graus": pm["caster_graus"], "kpi_graus": pm["kpi_graus"], "trail_m": pm["trail_m"], "scrub_m": pm["scrub_m"],
            "delta_bitola_m": float(P[1] - pts["P"][1]), "delta_entre_eixos_m": float(P[0] - pts["P"][0]),
            "B": tuple(B), "D": tuple(D), "W": tuple(W), "P": tuple(P), "Tj": tuple(Tj)}


def curva_heave_3d(s: DuploA3D, h_min: float = -0.04, h_max: float = 0.04, n: int = 9, rack: float = 0.0) -> list:
    if n < 2:
        raise ValueError("n deve ser ≥ 2")
    return [resolver_3d(s, h_min + (h_max - h_min) * i / (n - 1), rack) for i in range(n)]


def derivadas(s: DuploA3D, dh: float = 1e-3, dr: float = 1e-3) -> dict:
    """Derivadas por diferenças centrais no projeto: camber gain [°/m], bump steer [°/m de toe-in], razão de esterçamento [°/mm de cremalheira]."""
    a, b = resolver_3d(s, -dh), resolver_3d(s, dh)
    c, d = resolver_3d(s, 0.0, -dr), resolver_3d(s, 0.0, dr)
    return {"camber_gain_graus_por_m": (b["camber_graus"] - a["camber_graus"]) / (2 * dh),
            "bump_steer_graus_por_m": (b["toe_in_graus"] - a["toe_in_graus"]) / (2 * dh),
            "razao_esterco_graus_por_mm": (d["toe_in_graus"] - c["toe_in_graus"]) / (2 * dr * 1000.0),
            "camber_por_curso_graus_por_mm": (d["camber_graus"] - c["camber_graus"]) / (2 * dr * 1000.0)}


@dataclass
class CoefElasto:
    """Coeficientes LINEARES de elastocinemática por força no contato [°/kN]. Informados pelo usuário (medição/cálculo próprios). Padrão 0."""
    toe_fy: float = 0.0       # toe-in por força lateral (+ Fy = força do solo no pneu apontando para DENTRO do carro)
    toe_fx: float = 0.0       # toe-in por força longitudinal (+ Fx = tração)
    camber_fy: float = 0.0    # camber por força lateral


def com_elastocinematica(s: DuploA3D, heave: float, rack: float, fy_n: float, fx_n: float, k: CoefElasto) -> dict:
    """Pose cinemática + correção linear: Δ = coef·F/1000. Não é modelo de buchas."""
    r = resolver_3d(s, heave, rack)
    r["toe_in_graus"] += k.toe_fy * fy_n / 1000.0 + k.toe_fx * fx_n / 1000.0
    r["camber_graus"] += k.camber_fy * fy_n / 1000.0
    r["elastocinematica_aplicada"] = bool(k.toe_fy or k.toe_fx or k.camber_fy)
    return r


def exemplo_ilustrativo() -> DuploA3D:
    """Geometria ILUSTRATIVA (não de carro real). Barra de direção atrás do eixo, ~paralela ao braço inferior (bump steer baixo, mas não zero)."""
    return DuploA3D(LF=(0.15, 0.20, 0.14), LR=(-0.15, 0.20, 0.14), B=(0.0, 0.60, 0.12),
                    UF=(0.12, 0.25, 0.30), UR=(-0.12, 0.25, 0.30), D=(-0.02, 0.56, 0.32),
                    T=(-0.09, 0.22, 0.16), Tj=(-0.10, 0.58, 0.15), W=(0.0, 0.63, 0.24), P=(0.0, 0.63, 0.0))


def analisar(s: DuploA3D, h_max: float = 0.04, ilustrativo: bool = False) -> TracedResult:
    base = resolver_3d(s)
    der = derivadas(s)
    bump, reb = resolver_3d(s, h_max), resolver_3d(s, -h_max)
    vals = {"caster_graus": base["caster_graus"], "kpi_graus": base["kpi_graus"], "trail_mecanico_m": base["trail_m"], "scrub_m": base["scrub_m"],
            **der, "camber_em_bump_graus": bump["camber_graus"], "camber_em_rebound_graus": reb["camber_graus"],
            "toe_em_bump_graus": bump["toe_in_graus"], "toe_em_rebound_graus": reb["toe_in_graus"],
            "delta_bitola_bump_m": bump["delta_bitola_m"], "delta_bitola_rebound_m": reb["delta_bitola_m"], "h_max_m": h_max}
    prem = ["manga rígida, barras rígidas com rótulas ideais (sem folga/atrito)", "5 barras: 2 por braço em A + barra de direção; heave fecha o grau de liberdade",
            "sem buchas, sem rigidez dos braços, sem dinâmica; elastocinemática só linear com coeficientes do usuário (padrão 0)",
            "eixo de giro da roda: convenção x à frente, y para fora, z acima; camber/toe estáticos informados pelo usuário"]
    if ilustrativo:
        prem.append("GEOMETRIA ILUSTRATIVA — não representa carro real")
    return TracedResult(nome="Suspensão duplo-A 3D (cinemática)", classe="ANALITICO",
                        metodo="Newton 6×6 sobre 5 comprimentos de barra + heave, continuação desde a pose de projeto",
                        valores=vals, entradas={n: getattr(s, n) for n in ("LF", "LR", "B", "UF", "UR", "D", "T", "Tj", "W", "P", "camber_estatico_graus", "toe_estatico_graus")},
                        premissas=prem, limitacoes=["não é multicorpo com buchas/elastocinemática completa", "centro de rolagem 3D não calculado aqui (use a vista frontal 2D)",
                                                    "sem validação contra suspensão real"])
