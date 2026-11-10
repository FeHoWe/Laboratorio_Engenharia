"""Áudio sincronizado à telemetria de uma volta simulada.

O som é função pura do tempo do observador (fase = Φ(t_emissão(t_obs))), então qualquer bloco pode ser
renderizado em qualquer ordem, com fase contínua e Doppler físico exato; permite reproduzir, pausar e buscar.

Barramentos separados: motor, ambiente e efeitos (troca de marcha, frenagem, desaceleração), cada um com volume.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .synth import (C_SOUND, EngineProfile, fft_convolve, get_profile, harmonic_bank, reverb_ir, shaped_noise,
                    soft_limit)

FINE_DT = 0.001  # s, grade fina para integração de fase


@dataclass
class AudioSettings:
    enabled: bool = True
    profile: str = "v6_turbo_hibrido"
    mode: str = "trackside"            # trackside | onboard
    observer_s: float = 0.0             # posição do observador ao longo da pista (m)
    observer_offset: float = 25.0       # distância lateral da pista (m)
    master: float = 0.8
    engine_vol: float = 1.0
    ambient_vol: float = 0.35
    fx_vol: float = 0.6
    intensity: float = 1.0
    reverb: float = 0.18                # mistura (0..1)
    sr: int = 44100
    loop_pad_s: float = 2.0             # silêncio/ambiente antes e depois da volta


class SimulationAudio:
    def __init__(self, result, settings: AudioSettings | None = None):
        self.res = result
        self.cfg = settings or AudioSettings()
        self.prof: EngineProfile = get_profile(self.cfg.profile)
        self._build()

    # ----------------------------------------------------------------- preparação
    def _build(self):
        r, cfg = self.res, self.cfg
        tel = r.tel
        t = tel["t"]
        T = float(r.lap_time)
        self.duration = T
        te = np.arange(0.0, T, FINE_DT)                      # tempo de emissão (grade fina)
        interp = lambda a: np.interp(te, t, np.asarray(a, float))
        rpm_t = interp(tel["rpm"])
        # inércia do motor: limita a taxa de variação do rpm (trocas viram quedas rápidas, não degraus)
        rate = 40000.0 * FINE_DT
        rpm = np.empty_like(rpm_t); rpm[0] = rpm_t[0]
        for i in range(1, rpm.shape[0]):
            rpm[i] = rpm[i - 1] + np.clip(rpm_t[i] - rpm[i - 1], -rate, rate)
        self.rpm_fine = rpm
        self.load = np.clip(0.15 + 0.85 * interp(tel["throttle"]), 0, 1)
        self.brake = interp(tel["brake"])
        self.speed = interp(tel["v"])
        self.accel = interp(tel["ax"])
        x, y = interp(tel["x"]), interp(tel["y"])
        # observador
        if cfg.mode == "onboard":
            d = np.full_like(te, 1.2)
            self.pan = np.zeros_like(te)
        else:
            s_obs = cfg.observer_s % r.track.length_m
            k = int(np.argmin(np.abs(tel["s"] - s_obs)))
            px, py = tel["x"][k], tel["y"][k]
            hd = tel["heading"][k]
            nx, ny = -np.sin(hd), np.cos(hd)                 # normal à pista
            ox, oy = px + nx * cfg.observer_offset, py + ny * cfg.observer_offset
            d = np.hypot(x - ox, y - oy)
            # direção que o observador encara: para o ponto da pista
            fx, fy = px - ox, py - oy
            fn = np.hypot(fx, fy) + 1e-9
            fx, fy = fx / fn, fy / fn
            vx, vy = x - ox, y - oy
            cross = fx * vy - fy * vx
            self.pan = np.clip(cross / (np.hypot(vx, vy) + 1e-6), -1, 1)
        self.dist = d
        # tempo retardado: t_obs = t_e + d/c   (monótono porque v << c)
        t_obs = te + d / C_SOUND
        self.t_obs_of_e = t_obs
        # fase de emissão Φ(t_e)
        f_fire = self.prof.fire_hz(rpm)
        self.f_fire = f_fire
        self.Phi = 2 * np.pi * np.cumsum(f_fire) * FINE_DT
        self.te = te
        # camadas de ruído pré-geradas
        rng = np.random.default_rng(23)
        n_noise = int(cfg.sr * (T + 2 * cfg.loop_pad_s + 1))
        self.n_total = int((T + 2 * cfg.loop_pad_s) * cfg.sr)
        self.wind_n = shaped_noise(n_noise, cfg.sr, 60, 5000, rng, slope=-4.0)
        self.rubber_n = shaped_noise(n_noise, cfg.sr, 1500, 7000, rng, slope=0.0)
        self.crowd_n = shaped_noise(n_noise, cfg.sr, 100, 3500, rng, slope=-3.0)
        self.jit_n = shaped_noise(n_noise, cfg.sr, 5, 400, rng, slope=0.0)
        self.pop_rng = rng
        # eventos: trocas de marcha e estalos de desaceleração
        g = np.asarray(tel["gear"], float)
        sh = np.flatnonzero(np.diff(g) != 0)
        self.shift_times = [(float(t[i + 1]), float(g[i + 1] - g[i])) for i in sh]
        thr = tel["throttle"]; rpm_s = tel["rpm"]
        over = (thr < 0.05) & (rpm_s > 9000) & (np.asarray(tel["brake"]) < 0.6)
        self.pops = []
        for i in np.flatnonzero(over):
            if rng.random() < 0.05:
                self.pops.append(float(t[i] + rng.random() * 0.05))
        self.ir = reverb_ir(cfg.sr, 0.9)

    # ----------------------------------------------------------------- renderização
    def length_s(self) -> float:
        return self.n_total / self.cfg.sr

    def render(self, t0: float, n: int) -> np.ndarray:
        """Bloco estéreo float32 a partir do tempo do observador t0 (s, 0 = início do trecho com margem)."""
        cfg = self.cfg
        if not cfg.enabled:
            return np.zeros((n, 2), np.float32)
        sr = cfg.sr
        t_o = t0 - cfg.loop_pad_s + np.arange(n) / sr                # tempo do observador relativo ao início da volta
        # tempo de emissão correspondente (exato)
        t_e = np.interp(t_o, self.t_obs_of_e, self.te, left=np.nan, right=np.nan)
        valid = ~np.isnan(t_e)
        te_c = np.where(valid, t_e, 0.0)
        ip = lambda arr: np.interp(te_c, self.te, arr)
        phase = np.interp(te_c, self.te, self.Phi)
        f_fire = ip(self.f_fire)
        load = ip(self.load)
        dist = ip(self.dist)
        pan = ip(self.pan)
        speed = ip(self.speed)
        brake = ip(self.brake)
        # Doppler já está embutido: phase_obs(t_o) = Φ(t_e(t_o)); frequência aparente = f_e · dt_e/dt_o
        i0 = int(round(t0 * sr))
        idx = (i0 + np.arange(n)) % self.jit_n.shape[0]
        eng = harmonic_bank(phase, f_fire, load, dist, self.prof, self.jit_n[idx] * 0.5)
        near = 1.0 / np.maximum(dist, 4.0) * 6.0 if cfg.mode == "trackside" else np.full(n, 0.55)
        amp = (0.28 + 0.72 * load ** 0.8) * near
        # corte de ignição nas trocas de marcha
        cut = np.ones(n)
        shift_fx = np.zeros(n)
        for ts, dg in self.shift_times:
            m = (te_c >= ts) & (te_c < ts + 0.05)
            if m.any():
                cut[m] = 0.45
                if dg > 0:   # tranco mecânico no upshift
                    shift_fx[m] += 0.35 * self.rubber_n[idx][m] * np.exp(-(te_c[m] - ts) / 0.015)
        eng = eng * amp * cut * cfg.intensity * cfg.engine_vol * 0.20
        eng = np.where(valid, eng, 0.0)
        # estalos de desaceleração (overrun)
        pop = np.zeros(n)
        for tp in self.pops:
            m = (te_c >= tp) & (te_c < tp + 0.03)
            if m.any():
                pop[m] += 0.5 * self.rubber_n[idx][m] * np.exp(-(te_c[m] - tp) / 0.008)
        # ruídos: vento e pneu ∝ v², freio ∝ pressão
        prox = near if cfg.mode == "trackside" else np.full(n, 0.5)
        wind = self.wind_n[idx] * (speed / 90.0) ** 2 * 0.22 * prox
        tyre = self.rubber_n[idx] * (speed / 90.0) ** 1.5 * 0.035 * prox
        squeal = self.rubber_n[idx] * brake * (speed / 80.0) * 0.07 * prox
        fx = (pop + shift_fx) * prox * cfg.fx_vol + squeal * cfg.fx_vol
        amb = (self.crowd_n[idx] * 0.045 + wind * 0.3 + tyre) * cfg.ambient_vol
        # atenuação nas margens (fora da volta o carro não existe)
        mono_dry = eng + fx + wind * cfg.ambient_vol + tyre * cfg.ambient_vol + self.crowd_n[idx] * 0.03 * cfg.ambient_vol
        # estéreo por pan equal-power
        th = (pan * 0.5 + 0.5) * (np.pi / 2)
        L = mono_dry * np.cos(th) + self.crowd_n[(idx + 977) % self.crowd_n.shape[0]] * 0.01 * cfg.ambient_vol
        R = mono_dry * np.sin(th) + self.crowd_n[(idx + 1913) % self.crowd_n.shape[0]] * 0.01 * cfg.ambient_vol
        st = np.stack([L, R], axis=1).astype(np.float32)
        return soft_limit(st * cfg.master * 2.2, 1.1)

    def render_all(self, with_reverb: bool = True, normalize: bool = True) -> np.ndarray:
        cfg = self.cfg
        block = 1 << 15
        out = [self.render(i / cfg.sr, min(block, self.n_total - i)) for i in range(0, self.n_total, block)]
        a = np.concatenate(out, axis=0)
        if with_reverb and cfg.reverb > 0:
            for ch in range(2):
                wet = fft_convolve(a[:, ch], self.ir)
                a[:, ch] = (1 - cfg.reverb) * a[:, ch] + cfg.reverb * 1.6 * wet
            a = soft_limit(a, 1.05)
        if normalize:
            a = a * (0.9 / max(float(np.abs(a).max()), 1e-6))
        return a.astype(np.float32)
