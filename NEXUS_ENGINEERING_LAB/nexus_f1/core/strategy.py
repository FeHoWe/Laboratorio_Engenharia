"""Estratégia de corrida: stints, desgaste, combustível, pit stops e comparação de estratégias.

O tempo de cada volta vem do simulador físico: ajustamos, por composto, uma superfície
tempo(desgaste, combustível) com poucas voltas simuladas e interpolamos (bilinear). Nada é fixado a priori.
O tempo de pit stop é um PARÂMETRO CONFIGURÁVEL (perda total em relação a uma volta normal) - não é dado oficial.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field

import numpy as np

from . import regulations
from .circuits import Track, get_track
from .config import CarConfig, Environment
from .laptime import LapSimulator, format_time

WEAR_GRID = (0.0, 0.35, 0.7, 1.0, 1.4)


@dataclass
class CompoundModel:
    compound: str
    wear_grid: tuple
    fuel_grid: tuple
    times: np.ndarray            # [wear, fuel]
    wear_per_lap: float          # fração de vida por volta (em wear=0)
    wear_rate_slope: float
    fuel_per_lap: float
    cold_delta: float            # s extra de uma volta de saída (pneus em t_init) vs volta rápida
    temp_mean: float

    def lap_time(self, wear: float, fuel: float) -> float:
        w = float(np.clip(wear, self.wear_grid[0], self.wear_grid[-1]))
        f = float(np.clip(fuel, self.fuel_grid[0], self.fuel_grid[-1]))
        wi = int(np.clip(np.searchsorted(self.wear_grid, w) - 1, 0, len(self.wear_grid) - 2))
        w0, w1 = self.wear_grid[wi], self.wear_grid[wi + 1]
        tw = (w - w0) / (w1 - w0)
        f0, f1 = self.fuel_grid
        tf = (f - f0) / (f1 - f0)
        a = self.times[wi, 0] * (1 - tf) + self.times[wi, 1] * tf
        b = self.times[wi + 1, 0] * (1 - tf) + self.times[wi + 1, 1] * tf
        return a * (1 - tw) + b * tw


@dataclass
class Stint:
    compound: str
    laps: int


@dataclass
class Strategy:
    name: str
    stints: list

    def stops(self) -> int:
        return len(self.stints) - 1


@dataclass
class StrategyResult:
    strategy: Strategy
    total_time: float
    lap_times: list
    compound_per_lap: list
    wear_per_lap: list
    fuel_per_lap: list
    pit_laps: list
    pit_loss: float
    valid: bool = True
    notes: list = field(default_factory=list)

    def fmt(self) -> str:
        t = self.total_time
        return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:06.3f}"


class StrategyModel:
    def __init__(self, track_key: str, car: CarConfig, env: Environment | None = None, ds: float = 8.0,
                 pit_loss_s: float | None = None, race_laps: int | None = None, cold_t_init: float = 55.0):
        self.car, self.env = car, env or Environment()
        self.season = regulations.get_season(car.season)
        self.track: Track = get_track(track_key, car.season)
        self.race_laps = race_laps or self.track.race_laps
        self.pit_loss = pit_loss_s if pit_loss_s is not None else float(self.season.value("pit_loss_s", 22.0))
        self.cold_t_init = cold_t_init
        self.ds = ds
        self._models: dict[str, CompoundModel] = {}

    def model(self, compound: str) -> CompoundModel:
        if compound not in self._models:
            self._models[compound] = self._fit(compound)
        return self._models[compound]

    def _fit(self, compound: str) -> CompoundModel:
        car = self.car.copy(compound=compound)
        sim = LapSimulator(self.track, car, self.env, self.season, ds=self.ds)
        f_hi = car.fuel_start_kg
        fuel_grid = (0.0, f_hi)
        times = np.zeros((len(WEAR_GRID), 2))
        for i, w in enumerate(WEAR_GRID):
            for j, f in enumerate(fuel_grid):
                times[i, j] = sim.run(wear=w, fuel_kg=f).lap_time
        mid = sim.run(wear=0.0, fuel_kg=f_hi * 0.5)
        mid2 = sim.run(wear=0.7, fuel_kg=f_hi * 0.5)
        cold = sim.run(wear=0.0, fuel_kg=f_hi * 0.5, t_init=self.cold_t_init)
        wpl0, wpl1 = mid.summary["tyre_wear_per_lap"], mid2.summary["tyre_wear_per_lap"]
        return CompoundModel(compound, WEAR_GRID, fuel_grid, times, wpl0, (wpl1 - wpl0) / 0.7,
                             mid.summary["fuel_used_kg"], max(cold.lap_time - mid.lap_time, 0.0),
                             mid.summary["tyre_temp_mean_c"])

    # ------------------------------------------------------------------ corrida
    def simulate(self, strategy: Strategy, start_fuel: float | None = None) -> StrategyResult:
        N = self.race_laps
        total_planned = sum(s.laps for s in strategy.stints)
        notes, valid = [], True
        if total_planned != N:
            notes.append(f"Soma dos stints ({total_planned}) difere das voltas da corrida ({N}).")
            valid = False
        fuel = self.car.fuel_start_kg if start_fuel is None else start_fuel
        lap_times, comps, wears, fuels, pit_laps = [], [], [], [], []
        lap = 0
        for si, st in enumerate(strategy.stints):
            m = self.model(st.compound)
            wear = 0.0
            for k in range(st.laps):
                lt = m.lap_time(wear, fuel)
                if k == 0 and si > 0:
                    lt += m.cold_delta                      # volta de saída com pneus frios
                if k == st.laps - 1 and si < len(strategy.stints) - 1:
                    lt += self.pit_loss                     # volta de entrada: perda do pit stop
                    pit_laps.append(lap + 1)
                lap_times.append(lt); comps.append(st.compound); wears.append(wear); fuels.append(fuel)
                wear += m.wear_per_lap + m.wear_rate_slope * wear
                fuel = max(fuel - m.fuel_per_lap, 0.0)
                lap += 1
            if wear > 1.4:
                notes.append(f"Stint {si + 1} ({st.compound}) termina com desgaste {wear:.2f} (> vida útil estimada).")
                valid = valid and wear <= 1.4
        if fuel < -1e-6:
            notes.append("Combustível insuficiente.")
        if fuels and fuels[-1] - self.model(strategy.stints[-1].compound).fuel_per_lap < -0.5:
            notes.append("Combustível inicial pode não bastar para a distância (alvo: ~0 kg ao final).")
        slicks = {s.compound for s in strategy.stints if s.compound in ("soft", "medium", "hard")}
        if self.env.wetness == 0 and len(slicks) < 2:
            notes.append("Aviso: em pista seca, o regulamento esportivo exige ao menos dois compostos distintos (conferir).")
        return StrategyResult(strategy, float(sum(lap_times)), lap_times, comps, wears, fuels, pit_laps, self.pit_loss, valid, notes)

    def compare(self, strategies: list[Strategy]) -> list[StrategyResult]:
        res = [self.simulate(s) for s in strategies]
        return sorted(res, key=lambda r: (not r.valid, r.total_time))

    def optimize(self, compounds=("soft", "medium", "hard"), max_stops: int = 2, step: int = 2,
                 min_stint: int = 8, top: int = 8) -> list[StrategyResult]:
        N = self.race_laps
        out = []
        for stops in range(1, max_stops + 1):
            n_st = stops + 1
            for combo in itertools.product(compounds, repeat=n_st):
                if self.env.wetness == 0 and len(set(combo)) < 2:
                    continue
                if stops == 1:
                    for p in range(min_stint, N - min_stint + 1, step):
                        s = Strategy(f"{stops} parada: {'-'.join(c[0].upper() for c in combo)} (box volta {p})",
                                     [Stint(combo[0], p), Stint(combo[1], N - p)])
                        out.append(self.simulate(s))
                else:
                    for p1 in range(min_stint, N - 2 * min_stint + 1, step * 2):
                        for p2 in range(p1 + min_stint, N - min_stint + 1, step * 2):
                            s = Strategy(f"{stops} paradas: {'-'.join(c[0].upper() for c in combo)} (box voltas {p1}/{p2})",
                                         [Stint(combo[0], p1), Stint(combo[1], p2 - p1), Stint(combo[2], N - p2)])
                            out.append(self.simulate(s))
        out = [r for r in out if r.valid]
        out.sort(key=lambda r: r.total_time)
        return out[:top]


def default_strategies(model: StrategyModel) -> list[Strategy]:
    N = model.race_laps
    a, b = N // 3, N // 2
    return [
        Strategy("1 parada M-H", [Stint("medium", b), Stint("hard", N - b)]),
        Strategy("1 parada S-H", [Stint("soft", N // 3), Stint("hard", N - N // 3)]),
        Strategy("2 paradas S-M-M", [Stint("soft", a), Stint("medium", a), Stint("medium", N - 2 * a)]),
    ]
