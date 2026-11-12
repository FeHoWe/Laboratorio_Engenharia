"""Dinâmica simplificada do trem de válvulas (V2.1): força de contato came–seguidor e rotação de flutuação (corpo rígido).

Modelo (1 grau de liberdade, trem de válvulas RÍGIDO): a massa equivalente m segue exatamente o levantamento y(θ) prescrito pelo
came; o came empurra contra a mola (taxa k, força F0 com a válvula fechada) e contra a inércia:
        F_contato(θ) = m·y'' + c·y' + k·y + F0
Se F_contato < 0 o seguidor perderia o contato (flutuação / "valve float"). Limites do modelo: sem elasticidade do trem (ressonâncias),
sem surto da mola, sem pressão de gás sobre a válvula, sem folga dinâmica e sem atrito; massa, k, F0 e amortecimento são
informados pelo usuário (o NEXUS não os inventa).
Unidades: mm, N, kg, rpm de virabrequim (ângulo do virabrequim 0…720° por ciclo).
"""
from __future__ import annotations

import math

import numpy as np


def contact_force(lift_mm, step_deg: float, rpm: float, mass_kg: float, k_n_mm: float, preload_n: float,
                  damping_ns_m: float = 0.0) -> np.ndarray:
    """Força de contato (N) ao longo do ciclo, uma amostra por ``step_deg`` de virabrequim. A curva é periódica (720°)."""
    if rpm <= 0 or mass_kg <= 0 or k_n_mm < 0 or preload_n < 0 or damping_ns_m < 0:
        raise ValueError("rpm e massa devem ser positivos; k, pré-carga e amortecimento não podem ser negativos.")
    y = np.asarray(lift_mm, dtype=float)
    if len(y) > 1 and abs(y[0] - y[-1]) < 1e-9 and abs(len(y) * step_deg - 720.0 - step_deg) < 1e-6:
        y = y[:-1]                                                       # remove a amostra repetida (720° = 0°)
    r = math.radians(step_deg)
    w = 2.0 * math.pi * rpm / 60.0                                       # rad/s do virabrequim
    d1 = (np.roll(y, -1) - np.roll(y, 1)) / (2 * r)                      # mm/rad (diferença central periódica)
    d2 = (np.roll(y, -1) - 2 * y + np.roll(y, 1)) / (r * r)              # mm/rad²
    acc = d2 * w * w * 1e-3                                              # m/s²
    vel = d1 * w * 1e-3                                                  # m/s
    return mass_kg * acc + damping_ns_m * vel + k_n_mm * y + preload_n


def float_rpm(lift_mm, step_deg: float, mass_kg: float, k_n_mm: float, preload_n: float, damping_ns_m: float = 0.0,
              rpm_max: float = 40000.0) -> float:
    """Menor rotação do virabrequim em que a força de contato mínima chega a zero; ``inf`` se não ocorre até ``rpm_max``."""
    def fmin(rpm):
        return float(contact_force(lift_mm, step_deg, rpm, mass_kg, k_n_mm, preload_n, damping_ns_m).min())
    if fmin(1.0) <= 0:
        return 0.0                                                       # a pré-carga nem sustenta o contato em repouso
    if fmin(rpm_max) > 0:
        return math.inf
    lo, hi = 1.0, rpm_max
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if fmin(mid) > 0 else (lo, mid)
    return 0.5 * (lo + hi)


def analyze_valvetrain(lift_mm, step_deg: float, rpm: float, mass_kg: float, k_n_mm: float, preload_n: float,
                       damping_ns_m: float = 0.0) -> dict:
    f = contact_force(lift_mm, step_deg, rpm, mass_kg, k_n_mm, preload_n, damping_ns_m)
    fl = float_rpm(lift_mm, step_deg, mass_kg, k_n_mm, preload_n, damping_ns_m)
    idx = int(np.argmin(f))
    return {"force": f, "f_min": float(f.min()), "f_max": float(f.max()), "angle_at_min_deg": idx * step_deg,
            "float_rpm": fl, "floats": bool(f.min() < 0),
            "margin": None if preload_n == 0 else float(f.min()) / preload_n,
            "notes": ["Corpo rígido, 1 g.d.l.: sem elasticidade do trem, surto da mola, pressão de gás, folga dinâmica ou atrito.",
                      "Massa equivalente, k, pré-carga e amortecimento são dados do usuário."]}
