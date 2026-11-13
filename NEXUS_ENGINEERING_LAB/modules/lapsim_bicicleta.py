"""V60 — Volta quase-estacionária com MODELO DE BICICLETA: cargas por eixo (estática + aerodinâmica + transferência longitudinal), μ por eixo com
sensibilidade de carga OPCIONAL, tração traseira ou integral, frenagem com divisão fixa (ou ideal) e indicação de sub/sobre-esterço no limite.

Ainda é um modelo SIMPLIFICADO e todos os parâmetros são SEUS: sem transferência lateral entre rodas, sem cinemática de suspensão, sem curvas de pneu reais
(μ por eixo, com `k_carga` opcional: μ_ef = μ0·(1 − k·(N/N_ref − 1)), N_ref = carga estática do eixo; k = 0 → μ constante), sem mapas de motor.
Combinação longitudinal × lateral por fator elíptico calculado com a utilização lateral do eixo mais exigido (aproximação).
Se `k_carga = 0`, μ_f = μ_r, h = 0 e tração integral, ele reduz ao `lapsim` de ponto material (testado).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .lapsim import G, _perfil
from .result_trace import TracedResult

SOLVER, VERSAO = "NEXUS-LapSim-Bicicleta", "1.0"


@dataclass
class CarroB:
    massa: float                  # kg
    a: float                      # m, CG → eixo dianteiro
    b: float                      # m, CG → eixo traseiro
    h: float                      # m, altura do CG
    p_ice: float                  # W
    cda: float
    cla: float
    mu_f: float
    mu_r: float
    bal_aero: float = 0.5         # fração do downforce no eixo dianteiro (0–1)
    k_carga: float = 0.0          # sensibilidade de carga do μ (0 = constante)
    tracao: str = "traseira"      # 'traseira' | 'integral'
    freio_diant: float | None = None   # fração do esforço de frenagem no eixo dianteiro; None = divisão ideal
    crr: float = 0.012
    rho: float = 1.225
    p_ers: float = 0.0
    e_ers: float = 0.0
    v_max: float = 120.0

    @property
    def L(self):
        return self.a + self.b


def _checar(c: CarroB):
    if min(c.massa, c.a, c.b, c.p_ice, c.mu_f, c.mu_r) <= 0 or c.h < 0 or c.cda < 0 or c.cla < 0:
        raise ValueError("massa, a, b, potência e μ devem ser > 0; h, CdA e ClA ≥ 0")
    if not 0 <= c.bal_aero <= 1:
        raise ValueError("bal_aero deve estar em [0, 1]")
    if not 0 <= c.k_carga < 1:
        raise ValueError("k_carga deve estar em [0, 1)")
    if c.tracao not in ("traseira", "integral"):
        raise ValueError("tracao deve ser 'traseira' ou 'integral'")
    if c.freio_diant is not None and not 0 < c.freio_diant < 1:
        raise ValueError("freio_diant deve estar em (0, 1) ou None (ideal)")


def _mu(c, eixo, N):
    mu0 = c.mu_f if eixo == "f" else c.mu_r
    ref = c.massa * G * (c.b / c.L if eixo == "f" else c.a / c.L)
    return max(0.2 * mu0, mu0 * (1.0 - c.k_carga * (max(N, 0.0) / ref - 1.0)))


def _cargas_estaticas(c, v):
    q = 0.5 * c.rho * c.cla * v * v
    return c.massa * G * c.b / c.L + q * c.bal_aero, c.massa * G * c.a / c.L + q * (1 - c.bal_aero)


def _cap(c, eixo, N):
    return _mu(c, eixo, N) * max(N, 0.0)


def _ay_max(c, v):
    """Aceleração lateral máxima no limite (eixo mais fraco) e qual eixo satura primeiro."""
    Nf, Nr = _cargas_estaticas(c, v)
    af = _cap(c, "f", Nf) * c.L / (c.massa * c.b)
    ar = _cap(c, "r", Nr) * c.L / (c.massa * c.a)
    return (af, "dianteiro") if af <= ar else (ar, "traseiro")


def _v_curva(c, r):
    if r <= 0:
        return c.v_max, None
    f = lambda v: v * v / r <= _ay_max(c, v)[0] + 1e-12  # noqa: E731
    v = 1.0
    while v < c.v_max and f(v + 0.5):
        v += 0.5
    if v >= c.v_max - 0.5:
        return c.v_max, None
    lo, hi = v, v + 0.5
    for _ in range(30):
        m = 0.5 * (lo + hi)
        lo, hi = (m, hi) if f(m) else (lo, m)
    return lo, _ay_max(c, lo)[1]


def _elipse(c, v, r):
    if r <= 0:
        return 1.0
    amax = _ay_max(c, v)[0]
    return math.sqrt(max(0.0, 1.0 - (v * v / r / amax) ** 2)) if amax > 0 else 0.0


def _resist(c, v):
    return 0.5 * c.rho * c.cda * v * v + c.crr * c.massa * G


def _a_acel(c, v, r, p):
    vv = max(v, 1.0)
    ell = _elipse(c, v, r)
    D = _resist(c, v)
    Nf0, Nr0 = _cargas_estaticas(c, v)
    F = min(p / vv, 1e5)
    for _ in range(40):                                              # ponto fixo: limite de tração com a transferência causada pela própria força
        t = (F - D) * c.h / c.L
        Nf, Nr = Nf0 - t, Nr0 + t
        cap = _cap(c, "r", Nr) if c.tracao == "traseira" else _cap(c, "f", Nf) + _cap(c, "r", Nr)
        lim = D + max(Nf0, 0.0) * c.L / c.h if c.h > 0 else float("inf")         # empinar: Nf → 0
        Fn = min(p / vv, cap * ell, lim)
        if abs(Fn - F) < 1e-6:
            break
        F = 0.5 * (F + Fn)
    return (F - D) / c.massa


def _a_freio(c, v, r):
    ell = _elipse(c, v, r)
    D = _resist(c, v)
    Nf0, Nr0 = _cargas_estaticas(c, v)
    Fb = 0.0
    for _ in range(60):
        t = (Fb + D) * c.h / c.L
        Nf, Nr = Nf0 + t, max(Nr0 - t, 0.0)
        cf, cr = _cap(c, "f", Nf) * ell, _cap(c, "r", Nr) * ell
        if c.freio_diant is None:
            Fn = cf + cr
        else:
            Fn = min(cf / c.freio_diant, cr / (1 - c.freio_diant))
        if abs(Fn - Fb) < 1e-6:
            break
        Fb = 0.5 * (Fb + Fn)
    return (Fb + D) / c.massa


def volta(c: CarroB, pista=None, ds: float = 2.0) -> TracedResult:
    _checar(c)
    if ds <= 0:
        raise ValueError("ds deve ser > 0")
    propria = bool(pista)
    from .lapsim import PISTA_EXEMPLO
    R = _perfil(pista or PISTA_EXEMPLO, ds)
    n = len(R)
    lim = [_v_curva(c, r) for r in R]
    vl = [x[0] for x in lim]
    v = vl[:]
    for _ in range(2):
        for i in range(2 * n - 1, -1, -1):
            j, k = i % n, (i + 1) % n
            v[j] = min(v[j], math.sqrt(v[k] ** 2 + 2 * _a_freio(c, v[k], R[j]) * ds))
    i0 = min(range(n), key=lambda q: v[q])
    if v[i0] >= c.v_max - 1e-9:
        v[i0] = 1.0
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
    curvas = [(R[i], lim[i][1], v[i]) for i in range(n) if R[i] > 0 and lim[i][1] is not None and v[i] >= vl[i] - 1e-6]
    n_f = sum(1 for _, e, _ in curvas if e == "dianteiro")
    n_r = sum(1 for _, e, _ in curvas if e == "traseiro")
    tot = max(1, n_f + n_r)
    Nf, Nr = _cargas_estaticas(c, 0.0)
    comp = n * ds
    lims = ["ATENÇÃO: sem transferência de carga LATERAL, elevar o CG só aumenta a carga no eixo traseiro ao acelerar (tração RWD) e não penaliza curvas — o modelo NÃO serve para otimizar a altura do CG.",
            "Sem transferência lateral entre rodas, sem cinemática de suspensão, sem curva de pneu real (μ por eixo, k_carga SEU).",
            "Fator elíptico por eixo mais exigido (aproximação); pista plana; sem consumo/degradação.",
            "Não valida contra dados de equipe", ("Pista informada por você (dados seus; o NEXUS não a valida nem a identifica com um circuito real)" if propria else "Pista de exemplo é SINTÉTICA (não é circuito real)")]
    if c.h > 0 and c.mu_r * c.h / c.L >= 1 and c.tracao == "traseira":
        lims.append("μ_r·h/L ≥ 1: a transferência de carga pode empinar o carro antes de saturar a tração (limite de empinamento aplicado).")
    return TracedResult("Volta quase-estacionária (bicicleta)", "SIMULACAO_NUMERICA", "Bicicleta com cargas por eixo, passes frente/trás", solver=SOLVER, solver_versao=VERSAO,
                        valores={"tempo_s": t, "comprimento_m": comp, "v_media_kmh": comp / t * 3.6, "v_max_kmh": max(v) * 3.6, "v_min_kmh": min(v) * 3.6,
                                 "energia_ers_usada_MJ": min(e_used, c.e_ers) / 1e6, "pct_curvas_limite_dianteiro": 100.0 * n_f / tot, "pct_curvas_limite_traseiro": 100.0 * n_r / tot,
                                 "balanco_no_limite": ("subesterçante (dianteiro satura primeiro)" if n_f > n_r else "sobreesterçante (traseiro satura primeiro)" if n_r > n_f else "neutro/indeterminado") if curvas else "sem curvas no limite",
                                 "carga_estatica_diant_N": Nf, "carga_estatica_tras_N": Nr, "s_m": [i * ds for i in range(n)], "v_ms": v},
                        entradas={"massa_kg": c.massa, "a_m": c.a, "b_m": c.b, "h_m": c.h, "p_ice_kW": c.p_ice / 1e3, "CdA_m2": c.cda, "ClA_m2": c.cla, "bal_aero_diant": c.bal_aero,
                                  "mu_f": c.mu_f, "mu_r": c.mu_r, "k_carga": c.k_carga, "tracao": c.tracao, "freio_diant": c.freio_diant, "ds_m": ds},
                        premissas=["Cargas por eixo: estática + downforce (balanço informado) + transferência longitudinal m·a·h/L", "μ por eixo (opcional sensibilidade de carga k)",
                                   "ERS: potência e energia por volta informadas por você"], limitacoes=lims)


def texto(r: TracedResult) -> str:
    v = r.valores
    return (f"Volta (bicicleta) — {r.classe} ({r.solver} {r.solver_versao})\n  tempo {v['tempo_s']:.3f} s · v média {v['v_media_kmh']:.1f} km/h · máx {v['v_max_kmh']:.1f} · mín {v['v_min_kmh']:.1f}\n"
            f"  balanço no limite: {v['balanco_no_limite']} (dianteiro {v['pct_curvas_limite_dianteiro']:.0f} % / traseiro {v['pct_curvas_limite_traseiro']:.0f} % dos pontos de curva no limite)\n"
            f"  cargas estáticas: dianteiro {v['carga_estatica_diant_N']:.0f} N, traseiro {v['carga_estatica_tras_N']:.0f} N\n" + "\n".join("⚠ " + x for x in r.limitacoes))
