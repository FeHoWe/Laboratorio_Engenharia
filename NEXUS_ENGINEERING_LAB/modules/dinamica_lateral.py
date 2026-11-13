"""V70 — Dinâmica lateral linear (modelo de bicicleta de 2 GDL: deriva β e guinada r) a velocidade constante.

Entradas SUAS: massa, a, b, Iz, rigidezes de curva Cf e Cr [N/rad] (por EIXO). O NEXUS não estima rigidez de pneu. Resultados:
ganhos de regime (gradiente de subesterço K, ganho de guinada, velocidade característica/crítica), autovalores (estabilidade, ωn, ζ) e resposta ao
degrau de esterço exata (exponencial de matriz). Classe: ANALITICO — modelo LINEAR (pneus lineares, ângulos pequenos, sem transferência de carga, sem
aerodinâmica, velocidade constante); não vale perto do limite de aderência nem para manobras bruscas.
Convenção: δ = esterço das rodas dianteiras [rad]; ay = U·(β̇ + r).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass
class ParamsLat:
    massa: float
    a: float
    b: float
    iz: float
    cf: float
    cr: float

    @property
    def L(self):
        return self.a + self.b


def _checar(p: ParamsLat, U: float):
    if min(p.massa, p.a, p.b, p.iz, p.cf, p.cr) <= 0:
        raise ValueError("massa, a, b, Iz, Cf e Cr devem ser > 0")
    if U <= 0.5:
        raise ValueError("velocidade deve ser > 0,5 m/s (o modelo linear degenera a baixa velocidade)")


def matrizes(p: ParamsLat, U: float):
    _checar(p, U)
    m, a, b, I, Cf, Cr = p.massa, p.a, p.b, p.iz, p.cf, p.cr
    A = np.array([[-(Cf + Cr) / (m * U), -1.0 - (a * Cf - b * Cr) / (m * U * U)],
                  [-(a * Cf - b * Cr) / I, -(a * a * Cf + b * b * Cr) / (I * U)]])
    B = np.array([Cf / (m * U), a * Cf / I])
    return A, B


def ganhos(p: ParamsLat, U: float) -> dict:
    A, B = matrizes(p, U)
    K = p.massa / p.L * (p.b / p.cf - p.a / p.cr)                       # gradiente de subesterço [rad/(m/s²)]
    r_ss = U / (p.L + K * U * U)                                        # r/δ em regime [1/s]
    ay_ss = U * r_ss                                                    # (β̇ = 0)
    lam = np.linalg.eigvals(A)
    complexo = bool(np.any(np.abs(lam.imag) > 1e-9))
    wn = float(math.sqrt(abs(np.linalg.det(A)))) if complexo else None
    zeta = float(-lam.real[0] / wn) if complexo and wn else None
    if K > 1e-12:
        tipo, v_car, v_crit = "subesterçante", math.sqrt(p.L / K), None
    elif K < -1e-12:
        tipo, v_car, v_crit = "sobreesterçante", None, math.sqrt(p.L / -K)
    else:
        tipo, v_car, v_crit = "neutro", None, None
    return {"classe": "ANALITICO", "velocidade_ms": U, "gradiente_subesterco_rad_por_ms2": K, "gradiente_subesterco_graus_por_g": math.degrees(K) * 9.80665, "tipo": tipo,
            "ganho_guinada_1_por_s": r_ss, "ganho_ay_ms2_por_rad": ay_ss, "velocidade_caracteristica_ms": v_car, "velocidade_critica_ms": v_crit,
            "autovalores": [[float(x.real), float(x.imag)] for x in lam], "estavel": bool(np.all(lam.real < 0)), "wn_rad_s": wn, "zeta": zeta,
            "limitacoes": ["Modelo LINEAR de 2 GDL: pneus lineares (Cf, Cr SEUS), ângulos pequenos, velocidade constante, sem transferência de carga nem aerodinâmica.",
                           "Não representa o comportamento perto do limite de aderência; não valida contra dados de equipe."]}


def degrau(p: ParamsLat, U: float, delta: float = 0.02, t_fim: float = 3.0, dt: float = 0.005) -> dict:
    """Resposta a um degrau de esterço `delta` [rad] em t = 0 (solução EXATA por exponencial de matriz)."""
    from scipy.linalg import expm
    A, B = matrizes(p, U)
    if not 0 < t_fim <= 60 or not 1e-4 <= dt <= t_fim / 10:
        raise ValueError("t_fim em (0, 60] s e dt em [1e-4, t_fim/10]")
    g = ganhos(p, U)
    n = int(round(t_fim / dt))
    Ad = expm(A * dt)
    Bd = np.linalg.solve(A, (Ad - np.eye(2)) @ B)
    x = np.zeros(2)
    t, beta, r, ay = [0.0], [0.0], [0.0], [0.0]
    for k in range(1, n + 1):
        xp = x
        x = Ad @ x + Bd * delta
        bdot = A[0] @ x + B[0] * delta
        t.append(k * dt); beta.append(float(x[0])); r.append(float(x[1])); ay.append(float(U * (bdot + x[1])))
    r_ss = g["ganho_guinada_1_por_s"] * delta
    pico = max(r, key=abs)
    sobre = max(0.0, 100.0 * (abs(pico) - abs(r_ss)) / abs(r_ss)) if g["estavel"] and abs(r_ss) > 0 else None
    t63 = next((t[i] for i, x in enumerate(r) if abs(x) >= 0.632 * abs(r_ss)), None) if g["estavel"] else None
    acomod = None
    if g["estavel"]:
        for i in range(len(r) - 1, -1, -1):
            if abs(r[i] - r_ss) > 0.02 * abs(r_ss):
                acomod = t[min(i + 1, len(t) - 1)] if i + 1 < len(t) else None
                break
        else:
            acomod = 0.0
    out = dict(g)
    out.update({"delta_rad": delta, "t_s": t, "beta_rad": beta, "r_rad_s": r, "ay_ms2": ay, "r_regime_rad_s": r_ss, "ay_regime_ms2": g["ganho_ay_ms2_por_rad"] * delta,
                "sobressinal_pct": sobre, "t63_s": t63, "tempo_acomodacao_2pct_s": acomod, "t_pico_s": t[r.index(pico)],
                "acomodou_na_janela": acomod is not None})
    if g["estavel"] and acomod is None:
        out["limitacoes"] = [f"A resposta não se acomodou (±2 %) na janela de {t_fim:g} s: aumente `t_fim` para ver o regime."] + out["limitacoes"]
    if not g["estavel"]:
        out["limitacoes"] = ["INSTÁVEL a esta velocidade: a resposta diverge no modelo linear (acima da velocidade crítica)."] + out["limitacoes"]
    return out


def varredura_velocidade(p: ParamsLat, velocidades) -> list[dict]:
    return [ganhos(p, float(u)) for u in velocidades]


def texto(g: dict) -> str:
    L = [f"Dinâmica lateral linear — {g['classe']} · U = {g['velocidade_ms']:.1f} m/s",
         f"  K = {g['gradiente_subesterco_graus_por_g']:+.3f} °/g ({g['tipo']}) · ganho de guinada {g['ganho_guinada_1_por_s']:.3f} 1/s · ay/δ {g['ganho_ay_ms2_por_rad']:.1f} m/s²/rad"]
    if g["velocidade_caracteristica_ms"]:
        L.append(f"  velocidade característica {g['velocidade_caracteristica_ms']:.1f} m/s")
    if g["velocidade_critica_ms"]:
        L.append(f"  velocidade CRÍTICA {g['velocidade_critica_ms']:.1f} m/s (acima disso: instável)")
    L.append(f"  estável: {'sim' if g['estavel'] else 'NÃO'}" + (f" · ωn {g['wn_rad_s']:.2f} rad/s · ζ {g['zeta']:.3f}" if g["wn_rad_s"] else ""))
    if "sobressinal_pct" in g and g["sobressinal_pct"] is not None:
        t63 = f"{g['t63_s']:.3f} s" if g["t63_s"] is not None else "não atingido"
        ac = f"{g['tempo_acomodacao_2pct_s']:.2f} s" if g["tempo_acomodacao_2pct_s"] is not None else "não acomodou na janela"
        L.append(f"  degrau {g['delta_rad']:.4f} rad: r regime {g['r_regime_rad_s']:.4f} rad/s · t63 {t63} · sobressinal {g['sobressinal_pct']:.1f} % · acomodação 2 % {ac}")
    return "\n".join(L + ["⚠ " + x for x in g["limitacoes"]])
