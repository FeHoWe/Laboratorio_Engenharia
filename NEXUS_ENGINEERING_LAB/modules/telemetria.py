"""Simulador de telemetria F1 (V2.8) — canais SINTÉTICOS derivados da volta quase-estacionária de modules.lapsim.

NÃO é telemetria real nem de equipe: cada canal sai do perfil de velocidade v(s) calculado pelo NEXUS-LapSim com SEUS parâmetros.
  · v, tempo, g longitudinal/lateral, arrasto e downforce: derivados de v(s), do raio e dos coeficientes (físicos, dentro do modelo de ponto material).
  · pedais (acelerador/freio): ESTIMADOS — potência/força necessária ÷ disponível; não há mapa de motor nem de freio.
  · marcha e rotação: ILUSTRATIVAS — n marchas de razão fixa, topo de cada marcha a rpm_max; dados SEUS (n, rpm_max, velocidade na última marcha).
  · ERS: energia acumulada em ordem de volta a partir do ponto mais lento, como no LapSim.
Sem pneus, temperaturas, combustível, DRS nem sensores: esses canais não existem aqui.
"""
from __future__ import annotations

import csv

from . import lapsim
from .lapsim import G, Carro
from .result_trace import TracedResult

SOLVER, VERSAO = "NEXUS-Telemetria", "1.0"
CANAIS = [("s_m", "Distância (m)"), ("t_s", "Tempo (s)"), ("v_kmh", "Velocidade (km/h)"), ("g_long", "g longitudinal"), ("g_lat", "g lateral"),
          ("acelerador_pct", "Acelerador (% estimado)"), ("freio_pct", "Freio (% estimado)"), ("marcha", "Marcha (ilustrativa)"), ("rpm", "Rotação (ilustrativa)"),
          ("arrasto_N", "Arrasto (N)"), ("downforce_N", "Downforce (N)"), ("ers_MJ", "ERS usado acumulado (MJ)")]


def telemetria(c: Carro, pista=None, ds: float = 2.0, n_marchas: int = 8, rpm_max: float = 15000.0, v_topo_kmh: float = 340.0, setores: int = 3) -> TracedResult:
    if n_marchas < 1 or rpm_max <= 0 or v_topo_kmh <= 0 or setores < 1:
        raise ValueError("marchas ≥ 1; rpm, velocidade de topo > 0; setores ≥ 1")
    pista = pista or lapsim.PISTA_EXEMPLO
    base = lapsim.volta(c, pista, ds)
    v = base.valores["v_ms"]
    R = lapsim._perfil(pista, ds)
    n = len(v)
    i0 = min(range(n), key=lambda q: v[q])
    ch = {k: [0.0] * n for k, _ in CANAIS}
    dv = v_topo_kmh / 3.6 / n_marchas
    t = 0.0
    for i in range(n):
        k = (i + 1) % n
        a = (v[k] ** 2 - v[i] ** 2) / (2 * ds)
        arr = 0.5 * c.rho * c.cda * v[i] ** 2
        dwn = 0.5 * c.rho * c.cla * v[i] ** 2
        roll = c.crr * c.massa * G
        grip = c.mu * (c.massa * G + dwn)
        if a > 1e-6:
            p_av = c.p_ice + c.p_ers
            acel = min(100.0, max(0.0, (c.massa * a + arr + roll) * v[i] / p_av * 100.0))
            freio = 0.0
        elif a < -1e-6:
            acel = 0.0
            freio = min(100.0, max(0.0, (-c.massa * a - arr - roll) / grip * 100.0))
        else:
            acel = min(100.0, max(0.0, (arr + roll) * v[i] / (c.p_ice + c.p_ers) * 100.0))   # velocidade constante: só vence resistência
            freio = 0.0
        gear = min(n_marchas, 1 + int(v[i] / dv))
        ch["s_m"][i] = i * ds
        ch["t_s"][i] = t
        ch["v_kmh"][i] = v[i] * 3.6
        ch["g_long"][i] = a / G
        ch["g_lat"][i] = (v[i] ** 2 / R[i] / G) if R[i] > 0 else 0.0
        ch["acelerador_pct"][i] = acel
        ch["freio_pct"][i] = freio
        ch["marcha"][i] = gear
        ch["rpm"][i] = rpm_max * v[i] / (gear * dv)
        ch["arrasto_N"][i] = arr
        ch["downforce_N"][i] = dwn
        t += 2 * ds / (v[i] + v[k])
    e = 0.0
    for st in range(n):
        i = (i0 + st) % n
        ch["ers_MJ"][i] = e / 1e6
        if ch["g_long"][i] > 0 and e < c.e_ers and c.p_ers > 0:
            e += c.p_ers * (ds / max(0.5 * (v[i] + v[(i + 1) % n]), 1.0))
    # setores por distância igual
    tot = t
    sec = []
    for q in range(setores):
        a0, a1 = q * n // setores, (q + 1) * n // setores
        t0 = ch["t_s"][a0]
        t1 = ch["t_s"][a1] if a1 < n else tot
        sec.append(t1 - t0)
    vals = {"tempo_s": tot, "setores_s": sec, "g_lat_max": max(ch["g_lat"]), "g_frenagem_max": -min(ch["g_long"]), "g_acel_max": max(ch["g_long"]),
            "rpm_max_visto": max(ch["rpm"]), "tempo_acelerador_pleno_pct": 100.0 * sum(1 for x in ch["acelerador_pct"] if x >= 99.0) / n,
            "tempo_freio_pct": 100.0 * sum(1 for x in ch["freio_pct"] if x > 0) / n, "canais": ch}
    return TracedResult(
        "Telemetria sintética de volta", "SIMULACAO_NUMERICA", "Canais derivados do perfil v(s) do LapSim (ponto material)", solver=SOLVER, solver_versao=VERSAO, valores=vals,
        entradas={**base.entradas, "n_marchas": n_marchas, "rpm_max": rpm_max, "v_topo_kmh": v_topo_kmh, "setores": setores},
        premissas=base.premissas + ["Pedais ESTIMADOS por razão força(potência) necessária/disponível", "Marcha/rotação ILUSTRATIVAS (razões fixas, topo de cada marcha a rpm_max)",
                                    "Amostras por distância (ds), não por tempo"],
        limitacoes=base.limitacoes + ["NÃO é telemetria real: sem pneus, temperaturas, combustível, DRS, sensores ou mapa de motor", "Não comparável com dados de equipe"])


def para_csv(res: TracedResult, caminho) -> str:
    ch = res.valores["canais"]
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([f"# {res.nome} — {res.classe} — {res.solver} {res.solver_versao} — dados SINTÉTICOS (não são telemetria real)"])
        w.writerow([k for k, _ in CANAIS])
        for i in range(len(ch["s_m"])):
            w.writerow([f"{ch[k][i]:.6g}" for k, _ in CANAIS])
    return str(caminho)
