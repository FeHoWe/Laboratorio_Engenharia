"""Ajuste de rigidez de curva C_α e atrito μ do pneu de escova a dados MEDIDOS (CSV: alpha_graus, fz_N, fy_N). V3.6.

Mínimos quadrados sobre Fy_modelo(α, Fz; C, μ) = `vehicle_lateral.pneu_fy`. O resultado traz RMSE, nº de pontos e se μ é identificável
(só se há pontos perto da saturação). Dados sintéticos servem apenas para testar o ajuste — o ajuste a dados reais é responsabilidade do usuário.
Classe do resultado: ANALITICO (ajuste de modelo), nunca VALIDADO.
"""
from __future__ import annotations

import csv, math
import numpy as np
from scipy.optimize import least_squares
from . import vehicle_lateral as vl


def ler_csv(path) -> list:
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        rd = csv.DictReader(f)
        need = {"alpha_graus", "fz_N", "fy_N"}
        if not rd.fieldnames or not need <= set(rd.fieldnames):
            raise ValueError(f"CSV deve ter as colunas {sorted(need)}")
        for i, r in enumerate(rd, 2):
            try: rows.append((float(r["alpha_graus"]), float(r["fz_N"]), float(r["fy_N"])))
            except (TypeError, ValueError): raise ValueError(f"linha {i}: valor numérico inválido")
    return rows


def ajustar(dados: list, c0: float = 50000.0, mu0: float = 1.2) -> dict:
    if len(dados) < 6:
        raise ValueError("são necessários ao menos 6 pontos")
    a = np.radians([d[0] for d in dados]); fz = np.array([d[1] for d in dados], float); fy = np.array([d[2] for d in dados], float)
    if not (np.all(np.isfinite(a)) and np.all(np.isfinite(fz)) and np.all(np.isfinite(fy))) or np.any(fz <= 0):
        raise ValueError("dados devem ser finitos e Fz > 0")
    if len(set(np.round(a, 6))) < 4:
        raise ValueError("variação de α insuficiente (mínimo 4 valores distintos)")

    def res(p):
        c, mu = p
        return np.array([vl.pneu_fy(ai, zi, c, mu) for ai, zi in zip(a, fz)]) - fy

    s = least_squares(res, [c0, mu0], bounds=([1.0, 0.05], [1e8, 5.0]), x_scale=[1e4, 1.0])
    c, mu = float(s.x[0]), float(s.x[1])
    rmse = float(math.sqrt(np.mean(s.fun ** 2)))
    sat = bool(np.any(np.abs(fy) >= 0.9 * mu * fz))
    return {"c_alpha_N_rad": c, "mu": mu, "rmse_N": rmse, "n": len(dados), "mu_identificavel": sat,
            "aviso": None if sat else "nenhum ponto perto da saturação: μ NÃO é identificável com estes dados (valor é só um limite inferior)",
            "classe": "ANALITICO"}
