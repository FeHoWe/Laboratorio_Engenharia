"""Sintetizador de motor em tempo real (com estado): recebe parâmetros do veículo a cada bloco.

Entradas por bloco: rpm, velocidade (m/s), aceleração longitudinal (m/s²), marcha, carga (0..1) e distância do
observador (m) + velocidade radial (m/s, positiva = afastando). Saída: bloco estéreo float32.
Mantém fase contínua entre blocos (sem cliques) e inércia de rotação (o rpm não muda instantaneamente).
"""
from __future__ import annotations

import numpy as np

from .synth import C_SOUND, EngineProfile, get_profile, harmonic_bank, shaped_noise, soft_limit


class RealtimeEngineSynth:
    def __init__(self, profile: str | EngineProfile = "v6_turbo_hibrido", sr: int = 44100, seed: int = 11):
        self.prof = get_profile(profile) if isinstance(profile, str) else profile
        self.sr = sr
        self.phase = 0.0
        self.rpm = 4000.0
        self.gear = 1
        self.rng = np.random.default_rng(seed)
        self.max_rpm_rate = 30000.0       # rpm/s (inércia do conjunto)
        self.enabled = True
        self.volume = 0.8                 # master
        self.intensity = 1.0              # ganho do motor
        self.engine_vol, self.ambient_vol, self.fx_vol = 1.0, 0.25, 0.5
        self._noise = shaped_noise(sr * 4, sr, 80, 6000, self.rng, slope=-3.0)
        self._pos = 0
        self._shift_env = 0.0

    def set_profile(self, name: str):
        self.prof = get_profile(name)

    def process(self, n: int, rpm: float, speed: float = 0.0, accel: float = 0.0, gear: int | None = None,
                load: float = 0.5, distance: float = 6.0, radial_speed: float = 0.0, brake: float = 0.0) -> np.ndarray:
        if not self.enabled:
            return np.zeros((n, 2), np.float32)
        sr = self.sr
        # inércia: rpm segue o alvo com taxa limitada; troca de marcha gera queda perceptível
        dt = n / sr
        step = np.clip(rpm - self.rpm, -self.max_rpm_rate * dt, self.max_rpm_rate * dt)
        rpm_arr = self.rpm + step * (np.arange(1, n + 1) / n)
        self.rpm += step
        if gear is not None and gear != self.gear:
            self._shift_env = 1.0
            self.gear = gear
        # Doppler: f_obs = f / (1 + v_r/c)
        dop = 1.0 / (1.0 + radial_speed / C_SOUND)
        f_fire = self.prof.fire_hz(rpm_arr) * dop
        phase = self.phase + 2 * np.pi * np.cumsum(f_fire) / sr
        self.phase = float(phase[-1] % (2 * np.pi * 1000))
        loadv = np.full(n, float(np.clip(load, 0, 1)))
        dist = np.full(n, max(distance, 1.0))
        jit = self.rng.standard_normal(n) * 0.5
        eng = harmonic_bank(phase, f_fire, loadv, dist, self.prof, jit)
        # carga/entrega e proximidade
        amp = (0.30 + 0.70 * float(np.clip(load, 0, 1)) ** 0.8) * min(1.0, 8.0 / max(distance, 1.0))
        # corte de ignição na troca de marcha
        if self._shift_env > 0:
            cut = 1.0 - 0.55 * self._shift_env * np.linspace(1, 0.2, n)
            eng *= cut
            self._shift_env = max(0.0, self._shift_env - dt / 0.06)
        eng *= amp * self.intensity * self.engine_vol * 0.12
        # ruído de vento + pneus (proporcional a v²) e freio
        idx = (self._pos + np.arange(n)) % self._noise.shape[0]
        self._pos = int((self._pos + n) % self._noise.shape[0])
        nz = self._noise[idx]
        wind = nz * (speed / 90.0) ** 2 * 0.10 * min(1.0, 8.0 / max(distance, 1.0))
        squeal = nz * brake * 0.08 * (speed / 80.0)
        amb = nz * 0.02 * self.ambient_vol
        mono = eng + (wind * self.ambient_vol + squeal * self.fx_vol) + amb
        out = soft_limit(mono * self.volume * 1.4, 1.0).astype(np.float32)
        return np.stack([out, out], axis=1)

    @staticmethod
    def test_sweep(profile: str = "v6_turbo_hibrido", seconds: float = 6.0, sr: int = 44100) -> np.ndarray:
        """Teste do som do motor: aceleração 4000->redline com trocas de marcha, depois desaceleração."""
        syn = RealtimeEngineSynth(profile, sr)
        n_blocks = int(seconds * sr / 1024)
        outs = []
        lo, hi = syn.prof.rpm_range
        for b in range(n_blocks):
            u = b / n_blocks
            if u < 0.75:
                g = int(u / 0.75 * 6) + 1
                local = (u / 0.75 * 6) % 1.0
                rpm = 8800 + local * (hi - 1500 - 8800) if g > 1 else lo + local * (hi - 1500 - lo)
                load = 1.0
            else:
                g = 7
                rpm = (hi - 1500) - (u - 0.75) / 0.25 * (hi - 1500 - 6500)
                load = 0.0
            outs.append(syn.process(1024, rpm, speed=rpm / 60, load=load, gear=g, distance=4.0))
        return np.concatenate(outs)
