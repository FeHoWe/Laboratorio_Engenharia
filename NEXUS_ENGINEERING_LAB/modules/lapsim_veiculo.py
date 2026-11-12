"""Volta quase-estacionária com o modelo de VEÍCULO (V3.7): usa `VeiculoLateral` (transferência de carga, pneu por eixo) e o círculo de atrito por pneu
(`vehicle_combined`) em vez do ponto material com μ único de `lapsim`.

Por velocidade e fração de ay usada, a aceleração/frenagem longitudinal máxima vem de uma TABELA pré-calculada (bissecção sobre `ay_limite_com_fx`)
interpolada — o passo de pista é barato. Tração e frenagem repartidas entre eixos conforme `reparticao` (fração do esforço no eixo TRASEIRO; None = proporcional
à carga estática). Com μ constante (sens_mu = 0, padrão) a transferência LATERAL não muda o limite (só uma roda levantando); com `sens_mu_f/r` > 0 (V3.8, modelo linear de μ(Fz), a ser alimentado por ensaio) a transferência de carga reduz o limite lateral. Premissas: sem transferência longitudinal (arfagem), sem diferencial, potência e arrasto como `lapsim`. Classe SIMULACAO_NUMERICA (modelo simplificado).
LIMITES: parâmetros SEUS; pista exemplo SINTÉTICA; não valida contra dados de equipe.
"""
from __future__ import annotations

import math
import numpy as np
from . import vehicle_combined as vc, vehicle_lateral as vl, lapsim as ls
from .result_trace import TracedResult

G = 9.80665
SOLVER, VERSAO = "NEXUS-LapSim-Veiculo", "1.0"


def _ax_max(v: vl.VeiculoLateral, vel: float, ay: float, sinal: int, rep) -> float:
    """Maior |Fx total| [N] com ay dado (sinal +1 tração, −1 frenagem)."""
    fzf = v.m * G * v.b / v.L; fzr = v.m * G * v.a / v.L
    fr = (fzr / (fzf + fzr)) if rep is None else rep
    lo, hi = 0.0, 3.0 * v.m * G
    def ok(F):
        r = vc.ay_limite_com_fx(v, vel, sinal * F * (1 - fr), sinal * F * fr)
        return r["viavel"] and r["ay_ms2"] >= ay - 1e-9
    if not ok(0.0): return 0.0
    for _ in range(40):
        m = 0.5 * (lo + hi)
        lo, hi = (m, hi) if ok(m) else (lo, m)
    return lo


class Tabela:
    """ax_max(v, ay) por interpolação bilinear em grade (v × fração de ay_limite)."""
    def __init__(self, v: vl.VeiculoLateral, vmax: float, rep, nv: int = 14, nf: int = 12):
        self.v, self.vs = v, np.linspace(1.0, vmax, nv); self.fs = np.array([0, .2, .4, .6, .75, .85, .92, .96, .98, .99, .995, 1.0])      # adensada perto de 1 (ax cai como √(1−f²))
        self.ayl = np.array([vl.ay_limite(v, float(x))["ay_ms2"] for x in self.vs])
        self.acc = np.array([[_ax_max(v, float(x), f * a, +1, rep) for f in self.fs] for x, a in zip(self.vs, self.ayl)])
        self.fre = np.array([[_ax_max(v, float(x), f * a, -1, rep) for f in self.fs] for x, a in zip(self.vs, self.ayl)])

    def _interp(self, T, vel, ay):
        vel = min(max(vel, self.vs[0]), self.vs[-1]); i = min(max(int(np.searchsorted(self.vs, vel) - 1), 0), len(self.vs) - 2)
        t = (vel - self.vs[i]) / (self.vs[i + 1] - self.vs[i]); aylim = (1 - t) * self.ayl[i] + t * self.ayl[i + 1]
        f = min(max(ay / max(aylim, 1e-9), 0.0), 1.0)
        return (1 - t) * float(np.interp(f, self.fs, T[i])) + t * float(np.interp(f, self.fs, T[i + 1]))

    def acel(self, vel, ay): return self._interp(self.acc, vel, ay)
    def freio(self, vel, ay): return self._interp(self.fre, vel, ay)


def volta(v: vl.VeiculoLateral, p_ice: float, cda: float, crr: float = 0.012, pista=None, ds: float = 3.0, reparticao=None, v_max: float = 90.0) -> TracedResult:
    v.validar()
    if p_ice <= 0 or cda < 0 or ds <= 0: raise ValueError("potência > 0, CdA ≥ 0, ds > 0")
    pista = pista or ls.PISTA_EXEMPLO
    R = ls._perfil(pista, ds); n = len(R); tab = Tabela(v, v_max, reparticao)
    vl_ = [v_max if r <= 0 else min(v_max, vl.skidpad(v, r)["v_ms"]) for r in R]
    vv = vl_[:]
    fres = lambda vel: 0.5 * v.rho * cda * vel * vel + crr * v.m * G   # noqa: E731
    for _ in range(2):
        for i in range(2 * n - 1, -1, -1):
            j, k = i % n, (i + 1) % n
            ay = vv[k] ** 2 / R[j] if R[j] > 0 else 0.0
            ab = (tab.freio(vv[k], ay) + fres(vv[k])) / v.m
            vv[j] = min(vv[j], math.sqrt(vv[k] ** 2 + 2 * ab * ds))
    i0 = min(range(n), key=lambda q: vv[q])
    if vv[i0] >= v_max - 1e-9: vv[i0] = 1.0
    for s in range(n):
        i = (i0 + s) % n; k = (i + 1) % n; vel = max(vv[i], 1.0)
        ay = vv[i] ** 2 / R[i] if R[i] > 0 else 0.0
        trac = min(p_ice / vel, tab.acel(vel, ay)); aa = (trac - fres(vel)) / v.m
        vn = math.sqrt(max(vv[i] ** 2 + 2 * aa * ds, 0.0)) if aa > 0 else vv[i]
        if vn < vv[k] and k != i0: vv[k] = vn
    t = sum(2 * ds / (vv[i] + vv[(i + 1) % n]) for i in range(n)); comp = n * ds
    return TracedResult("Volta quase-estacionária (modelo de veículo)", "SIMULACAO_NUMERICA", "VeiculoLateral + círculo de atrito por pneu, tabela ax(v, ay)", solver=SOLVER,
                        solver_versao=VERSAO, valores={"tempo_s": t, "comprimento_m": comp, "v_media_kmh": comp / t * 3.6, "v_max_kmh": max(vv) * 3.6, "v_min_kmh": min(vv) * 3.6,
                                                       "s_m": [i * ds for i in range(n)], "v_ms": vv},
                        entradas={"massa_kg": v.m, "p_ice_kW": p_ice / 1e3, "CdA_m2": cda, "ClA_m2": v.cla, "mu_f": v.mu_f, "mu_r": v.mu_r, "ds_m": ds, "segmentos": len(pista),
                                  "reparticao_eixo_traseiro": "proporcional à carga" if reparticao is None else reparticao},
                        premissas=["Transferência lateral de carga (rolagem) incluída; longitudinal (arfagem) NÃO", "Círculo de atrito por pneu em saturação; sem diferencial"],
                        limitacoes=["Pista de exemplo é SINTÉTICA", "Parâmetros do veículo são seus (exemplo é ILUSTRATIVO)", "Não valida contra dados de equipe", "Sem ERS, DRS, combustível, degradação"])
