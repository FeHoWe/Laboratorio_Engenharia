"""Simulação de volta quase-estacionária de ponto material (V2.8) — modelo SIMPLIFICADO, parâmetros SEUS.

Não é o simulador de uma equipe: sem transferência de carga, sem pneus reais (μ constante), sem cinemática de suspensão, sem mapas de motor.
Premissas: pista plana; aderência μ·(m·g + ½ρ·ClA·v²) usada em elipse de atrito (lateral × longitudinal); tração = min(P/v, aderência);
frenagem limitada pela aderência (+ arrasto + rolamento); implantação elétrica (ERS) com potência e energia por volta informadas.
Passes: limite lateral por curva → varredura de frenagem para trás (circular) → aceleração para frente a partir do ponto mais lento (volta lançada).
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from .result_trace import TracedResult

G = 9.80665
SOLVER, VERSAO = "NEXUS-LapSim", "1.0"


@dataclass
class Carro:
    massa: float          # kg (com piloto e combustível da volta)
    p_ice: float          # W  (potência de combustão — SUA)
    cda: float            # m²  (Cd·A)
    cla: float            # m²  (Cl·A, positivo = downforce)
    mu: float             # coeficiente de aderência (constante)
    crr: float = 0.012
    rho: float = 1.225
    p_ers: float = 0.0    # W  implantação elétrica
    e_ers: float = 0.0    # J  energia implantável por volta
    v_max: float = 120.0  # m/s (limite numérico)


# pista: lista de segmentos (comprimento m, raio m; raio 0 = reta)
PISTA_EXEMPLO = [(900, 0), (80, 60), (350, 0), (110, 35), (250, 0), (160, 120), (700, 0), (60, 25), (200, 0), (200, 90), (400, 0), (90, 45)]


def _perfil(pista, ds):
    R = []
    for L, r in pista:
        n = max(1, round(L / ds))
        R += [float(r)] * n
    return R


def _v_curva(c: Carro, r: float) -> float:
    if r <= 0:
        return c.v_max
    den = c.massa / r - 0.5 * c.mu * c.rho * c.cla
    if den <= 1e-12:
        return c.v_max
    return min(c.v_max, math.sqrt(c.mu * c.massa * G / den))


def _elipse(c: Carro, v: float, r: float) -> float:
    if r <= 0:
        return 1.0
    alat = v * v / r
    amax = c.mu * (G + 0.5 * c.rho * c.cla * v * v / c.massa)
    return math.sqrt(max(0.0, 1.0 - (alat / amax) ** 2))


def _a_freio(c, v, r):
    f = c.mu * (c.massa * G + 0.5 * c.rho * c.cla * v * v) * _elipse(c, v, r) + 0.5 * c.rho * c.cda * v * v + c.crr * c.massa * G
    return f / c.massa


def _a_acel(c, v, r, p):
    vv = max(v, 1.0)
    trac = min(p / vv, c.mu * (c.massa * G + 0.5 * c.rho * c.cla * v * v) * _elipse(c, v, r))
    return (trac - 0.5 * c.rho * c.cda * v * v - c.crr * c.massa * G) / c.massa


def volta(c: Carro, pista=None, ds: float = 2.0) -> TracedResult:
    pista = pista or PISTA_EXEMPLO
    if min(c.massa, c.p_ice, c.mu, ds) <= 0 or c.cda < 0 or c.cla < 0:
        raise ValueError("massa, potência, μ e ds devem ser positivos; CdA/ClA ≥ 0")
    R = _perfil(pista, ds)
    n = len(R)
    vl = [_v_curva(c, r) for r in R]
    v = vl[:]
    for _ in range(2):                                              # frenagem circular (volta lançada)
        for i in range(2 * n - 1, -1, -1):                          # frenagem para trás (circular)
            j, k = i % n, (i + 1) % n
            ab = _a_freio(c, v[k], R[j])
            v[j] = min(v[j], math.sqrt(v[k] ** 2 + 2 * ab * ds))
    i0 = min(range(n), key=lambda q: v[q])                           # ponto de menor velocidade: estado consistente para iniciar a aceleração
    if v[i0] >= c.v_max - 1e-9:
        v[i0] = 1.0                                                  # sem curvas: largada parada
    e_used = 0.0
    for step in range(n):
        i = (i0 + step) % n
        k = (i + 1) % n
        p = c.p_ice + (c.p_ers if e_used < c.e_ers else 0.0)
        aa = _a_acel(c, v[i], R[i], p)
        vn = math.sqrt(max(v[i] ** 2 + 2 * aa * ds, 0.0)) if aa > 0 else v[i]
        if vn < v[k] and k != i0:
            if aa > 0 and e_used < c.e_ers and c.p_ers > 0:
                e_used += c.p_ers * (ds / max(0.5 * (v[i] + vn), 1.0))
            v[k] = vn
    t = sum(2 * ds / (v[i] + v[(i + 1) % n]) for i in range(n))
    comp = n * ds
    s = [i * ds for i in range(n)]
    return TracedResult(
        "Volta quase-estacionária", "SIMULACAO_NUMERICA", "Ponto material, elipse de atrito, passes frente/trás", solver=SOLVER, solver_versao=VERSAO,
        valores={"tempo_s": t, "comprimento_m": comp, "v_media_kmh": comp / t * 3.6, "v_max_kmh": max(v) * 3.6, "v_min_kmh": min(v) * 3.6,
                 "energia_ers_usada_MJ": min(e_used, c.e_ers) / 1e6, "s_m": s, "v_ms": v},
        entradas={"massa_kg": c.massa, "p_ice_kW": c.p_ice / 1e3, "p_ers_kW": c.p_ers / 1e3, "e_ers_MJ": c.e_ers / 1e6, "CdA_m2": c.cda, "ClA_m2": c.cla, "mu": c.mu,
                  "crr": c.crr, "rho": c.rho, "ds_m": ds, "segmentos": len(pista)},
        premissas=["Pista plana; μ constante; sem transferência de carga nem pneus reais", "Aderência com elipse de atrito e downforce ½ρClA v²",
                   "ERS: potência e energia por volta informadas por você"],
        limitacoes=["Não valida contra dados de equipe", "Pista de exemplo é SINTÉTICA (não é circuito real)", "Sem consumo de combustível, degradação, DRS/modo de reta"])
