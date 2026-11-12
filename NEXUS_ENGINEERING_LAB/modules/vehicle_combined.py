"""Aderência combinada do veículo (V3.6): limite lateral sob tração/frenagem, diagrama g-g, rigidez de rolagem por molas e geometria estática 3D do pino-mestre.

Classe ANALITICO. Em saturação o pneu de escova fica no círculo de atrito: Fy_max(i) = sqrt((μ·Fz_i)² − Fx_i²) (exato para o modelo de escova
em deslizamento total). Fx do eixo é dividido entre os pneus do eixo proporcionalmente a Fz (mesmo escorregamento). Sem diferencial/aerodinâmica
de arrasto/transferência longitudinal (arfagem): declarado, não escondido. Parâmetros são do usuário.
"""
from __future__ import annotations

import math
from . import vehicle_lateral as vl

G = vl.G


def fy_max_eixo_com_fx(v, eixo: str, vel: float, ay: float, fx_eixo: float) -> float | None:
    """Fy máx do eixo quando ele também transmite `fx_eixo` [N]. None se Fx excede o atrito (inviável)."""
    cg = vl.cargas_eixos(v, vel, ay)
    mu = v.mu_f if eixo == "f" else v.mu_r
    f1, f2 = (cg["f_int"], cg["f_ext"]) if eixo == "f" else (cg["r_int"], cg["r_ext"])
    f1, f2 = max(f1, 0.0), max(f2, 0.0); tot = f1 + f2
    if tot <= 0:
        return 0.0
    s = 0.0
    for fz in (f1, f2):
        fx = fx_eixo * fz / tot
        r = (mu * fz) ** 2 - fx * fx
        if r < -1e-9:
            return None
        s += math.sqrt(max(r, 0.0))
    return s


def ay_limite_com_fx(v, vel: float, fx_f: float = 0.0, fx_r: float = 0.0) -> dict:
    """Maior ay sustentável com forças longitudinais `fx_f`, `fx_r` [N] nos eixos (+ tração, − frenagem). ay=0 se já inviável."""
    v.validar()
    lo, hi = 0.0, 8.0 * G
    if fy_max_eixo_com_fx(v, "f", vel, 0.0, fx_f) is None or fy_max_eixo_com_fx(v, "r", vel, 0.0, fx_r) is None:
        return {"ay_ms2": 0.0, "ay_g": 0.0, "viavel": False, "limite": "força longitudinal excede o atrito de um eixo"}
    for _ in range(80):
        ay = 0.5 * (lo + hi)
        mf, mr = fy_max_eixo_com_fx(v, "f", vel, ay, fx_f), fy_max_eixo_com_fx(v, "r", vel, ay, fx_r)
        ok = mf is not None and mr is not None and v.m * ay * v.b / v.L <= mf and v.m * ay * v.a / v.L <= mr
        lo, hi = (ay, hi) if ok else (lo, ay)
    return {"ay_ms2": lo, "ay_g": lo / G, "viavel": True, "limite": "ok"}


def diagrama_gg(v, vel: float, n: int = 13, f_traseira_frenagem: float = 0.5) -> list:
    """Pontos (ax_g, ay_g): ax>0 tração (traseira), ax<0 frenagem repartida (`f_traseira_frenagem` = fração no eixo traseiro). Ignora arrasto e arfagem."""
    if not 0 <= f_traseira_frenagem <= 1:
        raise ValueError("fração de frenagem em [0,1]")
    pts = []
    for i in range(n):
        ax_g = -1.5 + 3.0 * i / (n - 1)
        F = v.m * ax_g * G
        fx_r, fx_f = (F, 0.0) if F >= 0 else (F * f_traseira_frenagem, F * (1 - f_traseira_frenagem))
        r = ay_limite_com_fx(v, vel, fx_f, fx_r)
        pts.append((ax_g, r["ay_g"] if r["viavel"] else None))
    return pts


def rigidez_rolagem(k_mola_roda: float, bitola: float, k_barra: float = 0.0) -> float:
    """Rigidez de rolagem do eixo [N·m/rad] = ½·k_roda·t² + K_barra. `k_mola_roda` é a taxa NA RODA [N/m] (mola × razão de instalação²)."""
    if not (k_mola_roda > 0 and bitola > 0 and k_barra >= 0):
        raise ValueError("k_roda e bitola devem ser positivos; barra ≥ 0")
    return 0.5 * k_mola_roda * bitola ** 2 + k_barra


def pino_mestre_3d(B: tuple, D: tuple, P: tuple) -> dict:
    """Geometria estática do pino-mestre. Eixos: x à frente, y para fora, z acima. B = rótula inferior, D = superior, P = contato do pneu (z=0 típico).
    caster [°] (+ = topo do eixo para TRÁS), KPI [°] (+ = topo para DENTRO), trail mecânico [m] (+ = contato atrás da interseção do eixo com o solo),
    scrub [m] (+ = interseção do eixo com o solo DENTRO do contato)."""
    ax = [D[i] - B[i] for i in range(3)]
    if ax[2] <= 1e-9:
        raise ValueError("rótula superior deve estar acima da inferior")
    caster = math.degrees(math.atan2(-ax[0], ax[2]))
    kpi = math.degrees(math.atan2(-ax[1], ax[2]))
    t = (P[2] - B[2]) / ax[2]
    gx, gy = B[0] + t * ax[0], B[1] + t * ax[1]
    return {"caster_graus": caster, "kpi_graus": kpi, "trail_m": P[0] - gx, "scrub_m": P[1] - gy}
