"""Fachada de alto nível: valida regulamento e executa a simulação."""
from __future__ import annotations

from . import circuits, regulations
from .config import CarConfig, Environment
from .laptime import LapSimulator, LapResult


def simulate_lap(track_key: str, car: CarConfig, env: Environment | None = None, wear: float = 0.0,
                 fuel_kg: float | None = None, t_init: float | None = None, ds: float = 6.0) -> LapResult:
    season = regulations.get_season(car.season)
    if car.mode == "regulatory":
        viol = regulations.check_regulatory(car, season)       # levanta RegulationError se houver erro
    else:
        viol = regulations.validate(car, season)
    track = circuits.get_track(track_key, car.season)
    sim = LapSimulator(track, car, env or Environment(), season, ds=ds)
    res = sim.run(wear=wear, fuel_kg=fuel_kg, t_init=t_init)
    res.violations = viol
    res.compliant = not any(v.severity == "error" for v in viol)
    return res
