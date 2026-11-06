"""Dinâmica longitudinal de veículo (integração temporal real, modelo 1D).

NÃO é a animação prescrita do F1. Todos os parâmetros são informados pelo usuário.
Premissas: ponto material longitudinal, pista plana (ou inclinação dada), arrasto
½ρCdA v², rolamento Crr·m·g, força trativa limitada por aderência μ·N_eixo_motriz
(transferência de carga longitudinal ignorada se `carga_motriz` informada).
"""
from __future__ import annotations
from dataclasses import dataclass
import math
from .result_trace import TracedResult

G = 9.80665

@dataclass
class Veiculo:
    massa: float            # kg
    cd: float
    area: float             # m²
    crr: float
    forca_motriz: float     # N (limite de potência tratado por potencia)
    potencia: float         # W (limite)
    mu: float               # aderência
    fracao_peso_motriz: float = 1.0
    rho: float = 1.225
    inclinacao: float = 0.0  # rad

def simular(v: Veiculo, t_final: float, dt: float = 0.01, v0: float = 0.0, frear_em: float | None = None, forca_freio: float = 0.0):
    if min(v.massa, v.area, v.potencia, v.forca_motriz, dt, t_final) <= 0:
        raise ValueError("parâmetros devem ser positivos")
    t = x = 0.0; vel = v0
    hist = [(0.0, x, vel, 0.0)]
    while t < t_final - 1e-12:
        def acc(vel_, tt):
            drag = 0.5 * v.rho * v.cd * v.area * vel_ * vel_
            roll = v.crr * v.massa * G * math.cos(v.inclinacao)
            grade = v.massa * G * math.sin(v.inclinacao)
            if frear_em is not None and tt >= frear_em:
                ft = -forca_freio
            else:
                ft = min(v.forca_motriz, v.potencia / max(vel_, 0.1), v.mu * v.fracao_peso_motriz * v.massa * G)
            return (ft - drag - roll - grade) / v.massa
        k1 = acc(vel, t); k2 = acc(vel + 0.5*dt*k1, t+0.5*dt)
        k3 = acc(vel + 0.5*dt*k2, t+0.5*dt); k4 = acc(vel + dt*k3, t+dt)
        a = (k1 + 2*k2 + 2*k3 + k4) / 6
        vn = max(vel + a*dt, 0.0)
        x += 0.5*(vel + vn)*dt; vel = vn; t += dt
        hist.append((t, x, vel, a))
    return hist

def resumo(v: Veiculo, hist) -> TracedResult:
    vmax = max(h[2] for h in hist)
    return TracedResult(
        nome="Dinâmica longitudinal", classe="ANALITICO",
        metodo="Integração RK4 de m·dv/dt = F_trat − ½ρCdAv² − Crr·m·g·cosθ − m·g·sinθ",
        valores={"v_max_ms": vmax, "distancia_m": hist[-1][1], "t_final_s": hist[-1][0]},
        entradas=v.__dict__.copy(),
        premissas=["modelo 1D de ponto material", "sem transferência de carga", "parâmetros informados pelo usuário"],
        limitacoes=["não é multicorpo", "não modela pneu (slip), câmbio nem aerodinâmica de assoalho"])
