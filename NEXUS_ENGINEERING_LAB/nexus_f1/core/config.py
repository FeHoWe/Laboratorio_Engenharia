"""Configuração do carro e do ambiente (dataclasses serializáveis)."""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field, asdict, replace

AERO_PRESETS = {
    # (Cd*A [m²], Cl*A [m²], fração de downforce no eixo dianteiro). Valores ESTIMADOS.
    "low_drag":     {"cda": 0.95, "cla": 3.10, "front": 0.42},
    "medium":       {"cda": 1.10, "cla": 3.80, "front": 0.44},
    "high_downforce": {"cda": 1.25, "cla": 4.40, "front": 0.45},
}


@dataclass
class CarConfig:
    name: str = "Carro base"
    season: str = "2025"
    mode: str = "regulatory"  # regulatory | experimental
    # --- massa / geometria (massa = carro + piloto, sem combustível)
    mass_kg: float = 800.0
    fuel_start_kg: float = 100.0
    front_weight_frac: float = 0.445          # fração estática no eixo dianteiro (estimada)
    cog_height_m: float = 0.27                # altura do CG (estimada)
    wheelbase_m: float = 3.60
    track_width_m: float = 1.60
    roll_stiffness_front: float = 0.50        # distribuição da transferência lateral
    # --- aerodinâmica
    aero_preset: str = "medium"
    cda: float = 1.10
    cla: float = 3.80
    aero_front_frac: float = 0.44
    crr: float = 0.012
    # --- unidade de potência
    ice_pmax_kw: float = 560.0
    ice_peak_rpm: float = 11500.0
    redline_rpm: float = 15000.0
    ice_thermal_eff: float = 0.46             # estimada
    mguk_kw: float = 120.0
    deploy_cap_mj: float = 4.0
    harvest_cap_mj: float = 2.0
    mguh_extra_mj: float = 2.0
    ers_roundtrip_eff: float = 0.85
    # --- transmissão
    gear_ratios: list = field(default_factory=lambda: [2.60, 2.05, 1.70, 1.45, 1.27, 1.12, 1.00, 0.90])
    final_drive: float = 4.00
    wheel_radius_m: float = 0.360
    drivetrain_eff: float = 0.93
    shift_rpm: float = 13200.0
    downshift_rpm: float = 8800.0
    shift_time_s: float = 0.03
    # --- freios
    brake_bias_front: float = 0.58
    max_brake_g: float = 6.0                  # capacidade do sistema de freios (g)
    # --- pneus
    compound: str = "medium"
    # --- estratégia de condução
    ers_strategy: str = "uniform"            # uniform | greedy
    lift_coast: float = 0.0

    def copy(self, **kw) -> "CarConfig":
        c = copy.deepcopy(self)
        for k, v in kw.items():
            setattr(c, k, v)
        return c

    def apply_aero_preset(self, name: str) -> "CarConfig":
        p = AERO_PRESETS[name]
        self.aero_preset, self.cda, self.cla, self.aero_front_frac = name, p["cda"], p["cla"], p["front"]
        return self

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "CarConfig":
        c = CarConfig()
        for k, v in d.items():
            if hasattr(c, k):
                setattr(c, k, v)
        return c

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


@dataclass
class Environment:
    air_temp_c: float = 25.0
    track_temp_c: float = 38.0
    wetness: float = 0.0                      # 0 seco .. 1 encharcado
    headwind_ms: float = 0.0                  # média sobre a volta (simplificação)

    def to_dict(self) -> dict:
        return asdict(self)


def default_car(season: str = "2025") -> CarConfig:
    """Carro-base coerente com a temporada (parâmetros de engenharia estimados)."""
    c = CarConfig(season=season)
    c.apply_aero_preset("medium")
    if season == "2026":
        c.mass_kg = 768.0
        c.ice_pmax_kw = 400.0
        c.ice_peak_rpm = 11500.0
        c.mguk_kw = 350.0
        c.deploy_cap_mj = 8.5
        c.harvest_cap_mj = 8.5
        c.mguh_extra_mj = 0.0
        c.wheel_radius_m = 0.355
        c.fuel_start_kg = 70.0
        c.front_weight_frac = 0.44
        c.cda, c.cla = 1.00, 3.00
        c.aero_front_frac = 0.43
    return c
