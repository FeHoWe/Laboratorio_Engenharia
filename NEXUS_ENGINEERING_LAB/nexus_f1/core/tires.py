"""Modelo de pneus: aderência, janela térmica, desgaste, degradação e pista molhada.

TODOS os parâmetros dos compostos abaixo são ESTIMATIVAS de engenharia (não são dados da Pirelli).
Nenhum tempo de volta é fixado por composto: o tempo resulta da simulação.

mu(Fz) = mu0 * f_T(T) * f_wear(w) * f_wet(wetness) * f_track * (1 - ks*(Fz/Fz_ref - 1))
"""
from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

FZ_REF = 3500.0  # N por pneu (carga de referência)


@dataclass(frozen=True)
class Compound:
    key: str
    mu0_dry: float          # aderência de pico em carga de referência, janela ideal, pista seca
    mu0_wet: float          # idem, pista totalmente molhada (wetness = 1)
    t_opt: float            # temperatura ótima da superfície (°C)
    t_width: float          # largura da janela (°C): queda quadrática ao redor de t_opt
    heat_gain: float        # sensibilidade térmica (geração de calor relativa)
    life_laps: float        # voltas nominais até desgaste = 1.0 (severidade de referência)
    deg_lin: float          # perda linear de aderência por unidade de desgaste
    cliff: float            # perda extra após 'cliff_start'
    cliff_start: float
    load_sens: float        # ks: sensibilidade à carga vertical
    aqua_start: float       # umidade a partir da qual há penalidade extra de aquaplanagem (0 = n/a)
    overheat_wear: float    # multiplicador de desgaste acima da janela


COMPOUNDS = {
    "soft":         Compound("soft", 2.42, 1.30, 101.0, 44.0, 1.00, 22.0, 0.050, 0.07, 0.75, 0.15, 0.0, 3.0),
    "medium":       Compound("medium", 2.34, 1.28, 103.0, 46.0, 1.00, 36.0, 0.042, 0.07, 0.77, 0.14, 0.0, 2.6),
    "hard":         Compound("hard", 2.26, 1.26, 105.0, 48.0, 1.00, 52.0, 0.036, 0.06, 0.78, 0.13, 0.0, 2.2),
    "intermediate": Compound("intermediate", 1.98, 1.60, 78.0, 55.0, 0.80, 35.0, 0.045, 0.07, 0.75, 0.12, 0.70, 3.5),
    "wet":          Compound("wet", 1.74, 1.66, 66.0, 60.0, 0.70, 45.0, 0.040, 0.06, 0.78, 0.11, 0.0, 4.0),
}

# Fator global de calibração de aderência (ajustado para que tempos simulados fiquem em média
# próximos de tempos de qualificação publicados; os circuitos aqui são esquemáticos).
GRIP_SCALE = 0.88
COMPOUNDS = {k: replace(c, mu0_dry=c.mu0_dry * GRIP_SCALE, mu0_wet=c.mu0_wet * GRIP_SCALE) for k, c in COMPOUNDS.items()}


def get_compound(key: str) -> Compound:
    if key not in COMPOUNDS:
        raise KeyError(f"Composto '{key}' desconhecido: {list(COMPOUNDS)}")
    return COMPOUNDS[key]


def f_temp(c: Compound, T):
    x = (np.asarray(T, float) - c.t_opt) / c.t_width
    return np.clip(1.0 - 0.40 * x * x, 0.55, 1.0)


def f_wear(c: Compound, w):
    w = np.asarray(w, float)
    cliff = c.cliff * np.clip((w - c.cliff_start) / (1.0 - c.cliff_start), 0, None) ** 2
    return np.maximum(1.0 - c.deg_lin * w - cliff, 0.70)


def f_wet(c: Compound, wetness: float) -> float:
    """Fator de aderência por umidade. A mistura é não linear: o filme d'água derruba o grip de slicks
    rapidamente; intermediários perdem eficácia (aquaplanagem) com pista muito molhada."""
    wl = float(np.clip(wetness, 0, 1))
    x = wl ** 0.8
    f = (1.0 - x) + x * (c.mu0_wet / c.mu0_dry)
    if c.aqua_start > 0 and wl > c.aqua_start:
        f *= 1.0 - 0.8 * (wl - c.aqua_start)
    return float(np.clip(f, 0.2, 1.0))


def mu(c: Compound, Fz, T, wear, wetness, track_grip=1.0):
    """Coeficiente de atrito efetivo (vetorizado). Fz em N por pneu."""
    load = 1.0 - c.load_sens * (np.asarray(Fz, float) / FZ_REF - 1.0)
    load = np.clip(load, 0.35, 1.3)
    return c.mu0_dry * f_temp(c, T) * f_wear(c, wear) * f_wet(c, wetness) * track_grip * load


def tyre_force_max(c: Compound, Fz, T, wear, wetness, track_grip=1.0):
    """Força máx. do pneu (N) = mu(Fz) * Fz."""
    Fz = np.asarray(Fz, float)
    return mu(c, Fz, T, wear, wetness, track_grip) * Fz


# --------------------------------------------------------------------------- térmica
H_GAIN = 165.0     # K (regime, utilização 1, resfriamento unitário) - calibrado p/ condição nominal
TAU_S = 25.0       # constante de tempo térmica (s) - temperatura de massa do pneu


def cooling(v):
    """Resfriamento relativo (ar de passagem): aumenta com a velocidade."""
    return 0.80 + 0.40 * np.asarray(v, float) / 80.0


def t_env(air_c: float, track_c: float) -> float:
    return 0.35 * air_c + 0.65 * track_c


def wear_increment(c: Compound, util: float, T: float, abrasiveness: float, ds: float, track_len: float) -> float:
    """Desgaste (fração da vida) acumulado em ds metros."""
    over = max(T - (c.t_opt + 0.6 * c.t_width), 0.0) / c.t_width
    mult = 1.0 + c.overheat_wear * over * over
    # severidade normalizada: util^2.2 médio de referência ~0.30 -> 1/life_laps por volta
    sev = util ** 2.2 / 0.30
    return (ds / track_len) * sev * mult * abrasiveness / c.life_laps
