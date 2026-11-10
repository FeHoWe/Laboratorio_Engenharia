"""Exportação de telemetria e geração de relatórios técnicos (Markdown / JSON / CSV)."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

from .laptime import LapResult, format_time

TEL_COLUMNS = [
    ("t", "t_s"), ("s", "s_m"), ("x", "x_m"), ("y", "y_m"), ("v_kmh", "v_kmh"), ("ax_g", "a_long_g"), ("ay_g", "a_lat_g"),
    ("rpm", "rpm"), ("gear", "gear"), ("throttle", "throttle"), ("brake", "brake"), ("drag", "drag_N"),
    ("downforce", "downforce_N"), ("Tf", "tyre_T_front_C"), ("Tr", "tyre_T_rear_C"), ("util_f", "grip_use_front"),
    ("util_r", "grip_use_rear"), ("p_ice", "p_ice_W"), ("p_k", "p_mguk_W"), ("p_harv", "p_harvest_W"),
    ("aero_open", "aero_straight_mode"),
]


def export_csv(res: LapResult, path) -> Path:
    path = Path(path)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([h for _, h in TEL_COLUMNS])
        n = len(res.tel["s"])
        for i in range(n):
            w.writerow([f"{res.tel[k][i]:.5g}" for k, _ in TEL_COLUMNS])
    return path


def result_to_dict(res: LapResult, decimate: int = 1) -> dict:
    t = res.tel
    sl = slice(None, None, decimate)
    return dict(
        track=dict(key=res.track.key, name=res.track.name, length_m=res.track.length_m, data_source=res.track.data_source),
        car=res.car.to_dict(), env=res.env.to_dict(), compliant=res.compliant,
        violations=[v.__dict__ for v in res.violations],
        lap_time_s=res.lap_time, lap_time=format_time(res.lap_time), sectors_s=res.sectors,
        summary=res.summary, segments=res.segments, braking_zones=res.braking_zones,
        telemetry={k: np.round(np.asarray(t[k])[sl], 4).tolist() for k in
                   ("t", "s", "x", "y", "v_kmh", "ax_g", "ay_g", "rpm", "gear", "throttle", "brake", "Tf", "Tr", "aero_open")},
    )


def export_json(res: LapResult, path, decimate: int = 1) -> Path:
    path = Path(path)
    path.write_text(json.dumps(result_to_dict(res, decimate), ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def lap_report_md(res: LapResult) -> str:
    s, c = res.summary, res.car
    L = []
    L.append(f"# Relatório técnico de volta — {res.track.name}")
    L.append(f"**Tempo de volta: {format_time(res.lap_time)}** ({res.lap_time:.3f} s)  |  Temporada {c.season}  |  Modo: {c.mode}  |  "
             f"{'REGULAMENTAR' if res.compliant else 'NÃO REGULAMENTAR (experimental)'}")
    L.append("")
    L.append(f"_Dados do circuito: {res.track.data_source}._")
    if res.violations:
        L.append("\n## Desvios do regulamento")
        for v in res.violations:
            L.append(f"- [{v.severity}] {v.message}" + (f" _(limite: {v.status or 'sem status'})_" if v.status else ""))
    L.append("\n## Resultados")
    L.append("| Métrica | Valor |\n|---|---|")
    rows = [("Velocidade máxima", f"{s['v_max_kmh']:.1f} km/h"), ("Velocidade média", f"{s['v_avg_kmh']:.1f} km/h"),
            ("Velocidade mínima", f"{s['v_min_kmh']:.1f} km/h"), ("Aceleração longitudinal máx.", f"{s['a_long_max_g']:.2f} g"),
            ("Desaceleração máx.", f"{s['a_brake_max_g']:.2f} g"), ("Aceleração lateral máx.", f"{s['a_lat_max_g']:.2f} g"),
            ("Downforce máx.", f"{s['downforce_max_kn']:.1f} kN"), ("Distância total de frenagem", f"{s['braking_distance_total_m']:.0f} m em {s['n_braking_zones']} zonas"),
            ("Tempo em curvas / retas", f"{s['time_corners_s']:.2f} s / {s['time_straights_s']:.2f} s"),
            ("Combustível consumido", f"{s['fuel_used_kg']:.2f} kg"), ("Energia recuperada / entregue (MGU-K)", f"{s['harvest_mj']:.2f} / {s['ers_deploy_mj']:.2f} MJ"),
            ("Temperatura média dos pneus", f"{s['tyre_temp_mean_c']:.0f} °C ({s['tyre_temp_min_c']:.0f}–{s['tyre_temp_max_c']:.0f})"),
            ("Desgaste por volta", f"{s['tyre_wear_per_lap'] * 100:.2f} % da vida ({res.compound})")]
    L += [f"| {a} | {b} |" for a, b in rows]
    L.append("\n## Setores")
    L += [f"- S{i + 1}: {format_time(t)}" for i, t in enumerate(res.sectors)]
    L.append("\n## Segmentos")
    L.append("| Segmento | Tipo | Comp. (m) | Tempo (s) | V mín (km/h) | V máx (km/h) | ay máx (g) |\n|---|---|---|---|---|---|---|")
    for g in res.segments:
        L.append(f"| {g['name']} | {g['kind']} | {g['length']:.0f} | {g['time']:.2f} | {g['v_min']:.0f} | {g['v_max']:.0f} | {g['ay_max']:.2f} |")
    L.append("\n## Zonas de frenagem")
    L.append("| # | Início s (m) | Distância (m) | V entrada | V saída | Pico (g) |\n|---|---|---|---|---|---|")
    for i, z in enumerate(res.braking_zones, 1):
        L.append(f"| {i} | {z['s_start']:.0f} | {z['distance']:.0f} | {z['v_in']:.0f} | {z['v_out']:.0f} | {z['peak_g']:.1f} |")
    L.append("\n## Configuração utilizada")
    L.append(f"- Massa {c.mass_kg:.0f} kg (+{res.fuel_kg:.1f} kg combustível) | Aero {c.aero_preset}: CdA {c.cda:.2f} m², ClA {c.cla:.2f} m²")
    L.append(f"- Motor {c.ice_pmax_kw:.0f} kW @ {c.ice_peak_rpm:.0f} rpm, MGU-K {c.mguk_kw:.0f} kW, limite {c.redline_rpm:.0f} rpm")
    L.append(f"- Marchas {len(c.gear_ratios)} (final {c.final_drive}), troca em {c.shift_rpm:.0f} rpm | Pneu: {res.compound} (desgaste {res.wear_start:.2f})")
    L.append(f"- Ambiente: ar {res.env.air_temp_c:.0f} °C, pista {res.env.track_temp_c:.0f} °C, umidade da pista {res.env.wetness:.2f}")
    L.append("\n> Valores de pista são estimativas do modelo físico simplificado; parâmetros marcados `estimate` na temporada NÃO são dados oficiais.")
    return "\n".join(L)


def comparison_report_md(cmp) -> str:
    L = [f"# Comparação de configurações — {cmp.track_key}", f"**Melhor configuração (resultado da simulação): {cmp.winner}**", ""]
    L.append("| Config | Tempo | Δ | Vmax | Vmédia | Curvas (s) | Retas (s) | Frenagem (m) | T pneu | Degradação (s/volta) | Regul. |\n|---|---|---|---|---|---|---|---|---|---|---|")
    for n in cmp.ranking:
        m = cmp.metrics[n]
        L.append(f"| {n} | {format_time(m['lap_time'])} | +{cmp.deltas[n]:.3f} | {m['v_max_kmh']:.0f} | {m['v_avg_kmh']:.1f} | "
                 f"{m['time_corners']:.2f} | {m['time_straights']:.2f} | {m['braking_distance_m']:.0f} | {m['tyre_temp_c']:.0f} | "
                 f"{m['degradation_s_per_lap']:.3f} | {'sim' if m['compliant'] else 'NÃO'} |")
    return "\n".join(L)


def strategy_report_md(results, pit_loss) -> str:
    L = ["# Comparação de estratégias", f"_Perda por pit stop configurada: {pit_loss:.1f} s (parâmetro, não dado oficial)._", ""]
    L.append("| # | Estratégia | Tempo total | Δ | Box (voltas) |\n|---|---|---|---|---|")
    best = results[0].total_time
    for i, r in enumerate(results, 1):
        L.append(f"| {i} | {r.strategy.name} | {r.fmt()} | +{r.total_time - best:.1f} s | {r.pit_laps} |")
    return "\n".join(L)
