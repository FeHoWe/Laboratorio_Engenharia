"""Gera f1sim.html (visualizador do NEXUS F1: pista animada, telemetria, som sintetizado) e analise_f1.json (sensibilidade, nível ótimo de asa,
uso de marchas e histograma de velocidade por circuito) para o app de celular. Somente leitura: tudo é calculado AQUI, com parâmetros estimados."""
from __future__ import annotations

import json
from pathlib import Path


def build(out: Path) -> None:
    from nexus_f1.core import analysis as A, circuits
    from nexus_f1.core.api import simulate_lap
    from nexus_f1.core.config import default_car
    from nexus_f1.mobile.export import build_mobile_html
    car = default_car("2025")
    res, ana = [], {}
    for key in circuits.list_circuits():
        r = simulate_lap(key, car, fuel_kg=40)
        res.append(r)
        sens = A.sensitivity(key, car, None, 0.02, None, 40.0, 8.0)
        aero = A.optimize_aero(key, car, None, 40.0, 8.0, 9)
        h = A.histogram(r, "v_kmh", 16)
        ana[key] = {"nome": r.track.name, "lap": r.lap_time,
                    "sens": [{"p": x["param"], "v": x["valor"], "d": x["d_lap_por_pct"]} for x in sens],
                    "aero": {"lv": aero["levels"], "t": aero["lap_times"], "best": aero["best_level"]},
                    "gears": {str(k): v for k, v in A.gear_usage(r).items()},
                    "hist": {"x": (0.5 * (h["edges"][1:] + h["edges"][:-1])).round(1).tolist(), "s": h["counts_s"].round(3).tolist()},
                    "pedais": A.throttle_brake_stats(r)}
    (out / "f1sim.html").write_text(build_mobile_html(res), encoding="utf-8")
    (out / "analise_f1.json").write_text(json.dumps({"car": car.name, "season": car.season, "circuitos": ana}, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
