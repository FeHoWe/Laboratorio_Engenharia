"""V80 — Energia de frenagem ao longo da volta e temperatura de disco (modelo térmico CONCENTRADO, 1 nó por eixo).

Energia: a potência de frenagem vem do perfil de velocidade do `lapsim` (desaceleração menos arrasto e rolamento), repartida entre eixos por `freio_diant`.
Térmica: m·cp·dT/dt = f_disco·P_freio − (h0 + h1·v)·A·(T − T_amb) − ε·σ·A·(T⁴ − T_amb⁴) por eixo (RK2 em cada segmento).
Parâmetros do disco/ar (massa, cp, área, h0, h1, ε, T_amb, fração de calor ao disco) são SEUS; o exemplo da CLI é ILUSTRATIVO (não é de um freio real).
Não inclui gradientes dentro do disco, pastilha/pinça/fluido, desgaste, fade, brake-by-wire/regeneração nem ventilação 3D. Classe: SIMULACAO_NUMERICA.
Se `lim_T_C` for informado, o resultado marca onde o disco passou do limite SEU (não é um limite de material do NEXUS).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from . import lapsim
from .lapsim import G

SIGMA = 5.670374419e-8


@dataclass
class Disco:
    massa: float            # kg (massa térmica do disco do eixo, todos os discos do eixo somados)
    cp: float               # J/(kg·K)
    area: float             # m² (área de troca do eixo)
    h0: float = 20.0        # W/(m²·K)  convecção parada
    h1: float = 1.0         # W·s/(m³·K) acréscimo por velocidade (h = h0 + h1·v)
    emissividade: float = 0.8
    f_disco: float = 1.0    # fração do calor de frenagem que entra no disco (1,0 = conservador para a temperatura do disco)
    lim_T_C: float | None = None


def _checar(d: Disco, nome):
    if min(d.massa, d.cp, d.area) <= 0 or d.h0 < 0 or d.h1 < 0 or not 0 <= d.emissividade <= 1 or not 0 < d.f_disco <= 1:
        raise ValueError(f"disco {nome}: massa, cp e área > 0; h0, h1 ≥ 0; emissividade em [0,1]; f_disco em (0,1]")


def potencia_de_frenagem(c: lapsim.Carro, s, v) -> list[float]:
    """Potência dissipada nos freios [W] em cada ponto da malha: m·a_dec·v − (arrasto + rolamento)·v, ≥ 0 (coasting/aceleração = 0)."""
    n = len(v)
    ds = s[1] - s[0]
    P = []
    for i in range(n):
        k = (i + 1) % n
        a = (v[i] ** 2 - v[k] ** 2) / (2 * ds)                       # desaceleração (>0 freando)
        vm = 0.5 * (v[i] + v[k])
        D = 0.5 * c.rho * c.cda * vm * vm + c.crr * c.massa * G
        P.append(max(0.0, (c.massa * a - D) * vm))
    return P


def termica(c: lapsim.Carro, disco_f: Disco, disco_r: Disco, freio_diant: float = 0.6, pista=None, ds: float = 3.0, voltas: int = 5, T0_C: float = 25.0,
            T_amb_C: float = 25.0) -> dict:
    _checar(disco_f, "dianteiro"); _checar(disco_r, "traseiro")
    if not 0 < freio_diant < 1:
        raise ValueError("freio_diant deve estar em (0, 1)")
    if not 1 <= voltas <= 100:
        raise ValueError("voltas deve estar entre 1 e 100")
    r = lapsim.volta(c, pista, ds)
    s, v = r.valores["s_m"], r.valores["v_ms"]
    n = len(v)
    P = potencia_de_frenagem(c, s, v)
    seg_t = [2 * ds / (v[i] + v[(i + 1) % n]) for i in range(n)]
    Ta = T_amb_C + 273.15
    T = [T0_C + 273.15, T0_C + 273.15]
    discos = (disco_f, disco_r)
    frac = (freio_diant, 1 - freio_diant)

    def dT(Tk, d, p, vv):
        h = d.h0 + d.h1 * vv
        return (d.f_disco * p - h * d.area * (Tk - Ta) - d.emissividade * SIGMA * d.area * (Tk ** 4 - Ta ** 4)) / (d.massa * d.cp)

    res = []
    traco = None
    for volta in range(voltas):
        pico = [T[0], T[1]]
        soma = [0.0, 0.0]
        tempo_acima = [0.0, 0.0]
        traj = [[], []]
        for i in range(n):
            dt, vv = seg_t[i], 0.5 * (v[i] + v[(i + 1) % n])
            for e in (0, 1):
                d, p = discos[e], P[i] * frac[e]
                k1 = dT(T[e], d, p, vv)
                k2 = dT(T[e] + dt * k1, d, p, vv)
                T[e] += 0.5 * dt * (k1 + k2)
                pico[e] = max(pico[e], T[e])
                soma[e] += T[e] * dt
                if d.lim_T_C is not None and T[e] - 273.15 > d.lim_T_C:
                    tempo_acima[e] += dt
                traj[e].append(T[e] - 273.15)
        tv = sum(seg_t)
        res.append({"volta": volta + 1, "T_pico_diant_C": pico[0] - 273.15, "T_pico_tras_C": pico[1] - 273.15, "T_media_diant_C": soma[0] / tv - 273.15, "T_media_tras_C": soma[1] / tv - 273.15,
                    "T_fim_diant_C": T[0] - 273.15, "T_fim_tras_C": T[1] - 273.15, "s_acima_limite_diant": tempo_acima[0], "s_acima_limite_tras": tempo_acima[1]})
        traco = traj
    E_total = sum(p * t for p, t in zip(P, seg_t))
    avisos = []
    for e, nome in enumerate(("dianteiro", "traseiro")):
        if discos[e].lim_T_C is not None and max(x["T_pico_diant_C" if e == 0 else "T_pico_tras_C"] for x in res) > discos[e].lim_T_C:
            avisos.append(f"Disco {nome} passou de {discos[e].lim_T_C:g} °C (limite SEU) em pelo menos uma volta.")
    if res and abs(res[-1]["T_fim_diant_C"] - res[max(0, len(res) - 2)]["T_fim_diant_C"]) > 5 and voltas > 1:
        avisos.append("A temperatura ainda não estabilizou entre as últimas voltas: use mais voltas para ver o regime.")
    return {"classe": "SIMULACAO_NUMERICA", "solver": "NEXUS-Freio-Termico 1.0 (1 nó/eixo, RK2) sobre NEXUS-LapSim 1.0", "tempo_volta_s": r.valores["tempo_s"], "energia_frenagem_MJ": E_total / 1e6,
            "energia_diant_MJ": E_total * freio_diant / 1e6, "energia_tras_MJ": E_total * (1 - freio_diant) / 1e6, "potencia_pico_kW": max(P) / 1e3, "voltas": res,
            "traco_ultima_volta": {"s_m": list(s), "T_diant_C": traco[0], "T_tras_C": traco[1]}, "avisos": avisos,
            "limitacoes": ["Modelo térmico concentrado (1 nó por eixo): sem gradiente no disco, pastilha/pinça/fluido, desgaste nem fade; parâmetros SEUS.",
                           "Energia de frenagem derivada do perfil de velocidade do lapsim (ponto material, pista conforme informada); sem regeneração.",
                           "Não valida contra dados de equipe nem de bancada."]}


def texto(r: dict) -> str:
    L = [f"Freios — {r['classe']} · volta {r['tempo_volta_s']:.3f} s · energia de frenagem {r['energia_frenagem_MJ']:.2f} MJ (diant. {r['energia_diant_MJ']:.2f} / tras. {r['energia_tras_MJ']:.2f}) · potência de pico {r['potencia_pico_kW']:.0f} kW",
         f"{'volta':>6}{'pico D [°C]':>13}{'pico T [°C]':>13}{'médio D':>10}{'médio T':>10}"]
    L += [f"{x['volta']:6d}{x['T_pico_diant_C']:13.0f}{x['T_pico_tras_C']:13.0f}{x['T_media_diant_C']:10.0f}{x['T_media_tras_C']:10.0f}" for x in r["voltas"]]
    return "\n".join(L + ["⚠ " + x for x in r["avisos"] + r["limitacoes"]])
