"""V120 — Séries de ESTADO do veículo (tempo, posição, orientação, velocidades, acelerações) vindas dos SIMULADORES existentes, prontas para alimentar uma animação.

Fontes: (1) longitudinal `vehicle_dynamics.simular` (aceleração e frenagem, reta); (2) degrau de esterçamento `vehicle_lateral.degrau_esterco` com integração da trajetória:
ψ̇ = r, ẋ = V·cos(ψ+β), ẏ = V·sin(ψ+β) (β = atan(vy/V)). Cada série informa a classe SIMULACAO_NUMERICA e o modelo (hipóteses dos solvers originais).
Este módulo NÃO anima nada e NÃO inventa estados: a animação 3D que consumir estas séries seria "dirigida por estados do simulador"; uma animação sem estas séries é ANIMACAO_PRESCRITA.
"""
from __future__ import annotations

import csv
import io
import math

from . import vehicle_dynamics as VD, vehicle_lateral as VL

CAMPOS = ["t_s", "x_m", "y_m", "psi_rad", "v_ms", "ax_ms2", "ay_ms2", "vy_ms", "r_rad_s", "beta_rad"]


class EstadosError(ValueError):
    pass


def longitudinal(v: VD.Veiculo, t_final: float, dt: float = 0.01, v0: float = 0.0, frear_em: float | None = None, forca_freio: float = 0.0) -> dict:
    h = VD.simular(v, t_final, dt, v0, frear_em, forca_freio)
    linhas = [[t, x, 0.0, 0.0, vel, a, 0.0, 0.0, 0.0, 0.0] for t, x, vel, a in h]
    return {"classe": "SIMULACAO_NUMERICA", "modelo": "vehicle_dynamics.simular (reta, ponto material)", "campos": CAMPOS, "linhas": linhas}


def curva(v: VL.VeiculoLateral, vel: float, delta: float, t_final: float = 3.0, dt: float = 0.005, t_step: float = 0.1) -> dict:
    h = VL.degrau_esterco(v, vel, delta, t_final, dt, t_step)
    linhas, x = [], [0.0, 0.0, 0.0]
    psi = xx = yy = 0.0
    prev_t = 0.0
    for t, vy, r, ay, beta in h:
        d = t - prev_t
        if d > 0:
            psi += r * d
            xx += vel * math.cos(psi + beta) * d
            yy += vel * math.sin(psi + beta) * d
        prev_t = t
        linhas.append([t, xx, yy, psi, vel, 0.0, ay, vy, r, beta])
    return {"classe": "SIMULACAO_NUMERICA", "modelo": "vehicle_lateral.degrau_esterco (bicicleta, pneus com saturação, V constante)", "campos": CAMPOS, "linhas": linhas}


def para_csv(s: dict) -> str:
    b = io.StringIO()
    w = csv.writer(b, lineterminator="\n")
    w.writerow(s["campos"])
    w.writerows([[f"{x:.6g}" for x in ln] for ln in s["linhas"]])
    return b.getvalue()


def quadros(s: dict, n: int = 60) -> list[dict]:
    """Reduz a série a n quadros (por índice uniforme) com pose (x, y, ψ) para um visualizador; nenhuma interpolação inventada além da escolha de índices."""
    if n < 2:
        raise EstadosError("n ≥ 2")
    L = s["linhas"]
    idx = sorted({round(i * (len(L) - 1) / (n - 1)) for i in range(n)})
    return [dict(zip(s["campos"], L[i])) for i in idx]
