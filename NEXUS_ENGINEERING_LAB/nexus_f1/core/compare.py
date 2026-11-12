"""Comparação de configurações de carro (A, B, C...) no mesmo circuito e condições."""
from __future__ import annotations

from dataclasses import dataclass

from .api import simulate_lap
from .config import CarConfig, Environment
from .laptime import LapResult, format_time


@dataclass
class Comparison:
    track_key: str
    env: Environment
    results: dict           # nome -> LapResult
    metrics: dict           # nome -> dict
    ranking: list           # nomes por tempo
    winner: str
    deltas: dict            # nome -> atraso para o melhor (s)


def degradation_per_lap(car: CarConfig, track_key: str, env: Environment, base: LapResult, ds: float = 8.0) -> float:
    """Perda média de tempo por volta (s) ao longo de 10 voltas de desgaste (vem de duas simulações)."""
    w10 = base.summary["tyre_wear_per_lap"] * 10
    r = simulate_lap(track_key, car, env, wear=w10, fuel_kg=base.fuel_kg, ds=ds)
    return (r.lap_time - base.lap_time) / 10.0


def compare_configs(track_key: str, configs: dict, env: Environment | None = None, fuel_kg: float | None = None,
                    with_degradation: bool = True) -> Comparison:
    env = env or Environment()
    results, metrics = {}, {}
    for name, car in configs.items():
        r = simulate_lap(track_key, car, env, fuel_kg=fuel_kg)
        results[name] = r
        s = r.summary
        metrics[name] = dict(
            lap_time=r.lap_time, v_max_kmh=s["v_max_kmh"], v_avg_kmh=s["v_avg_kmh"], v_min_kmh=s["v_min_kmh"],
            time_corners=s["time_corners_s"], time_straights=s["time_straights_s"],
            braking_distance_m=s["braking_distance_total_m"], a_lat_max_g=s["a_lat_max_g"],
            a_brake_max_g=s["a_brake_max_g"], tyre_temp_c=s["tyre_temp_mean_c"],
            wear_per_lap=s["tyre_wear_per_lap"], fuel_kg=s["fuel_used_kg"],
            degradation_s_per_lap=degradation_per_lap(car, track_key, env, r) if with_degradation else float("nan"),
            compliant=r.compliant, violations=len([v for v in r.violations if v.severity == "error"]),
        )
    ranking = sorted(results, key=lambda n: results[n].lap_time)
    best = results[ranking[0]].lap_time
    deltas = {n: results[n].lap_time - best for n in results}
    return Comparison(track_key, env, results, metrics, ranking, ranking[0], deltas)
