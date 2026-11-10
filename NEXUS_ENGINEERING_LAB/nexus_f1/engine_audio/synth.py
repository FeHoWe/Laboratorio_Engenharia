"""Síntese procedural do som do motor (somente numpy).

Física usada:
- frequência de ignição  f_fire = (rpm/60) · (cilindros/2)            (motor 4 tempos)
- harmônicos k·f_fire com amplitudes do perfil, inclinação espectral por carga e meia-ordem (irregularidade)
- Doppler exato por tempo retardado: t_obs = t_emissão + d(t_emissão)/c  ->  fase_obs(t_obs) = Φ(t_emissão(t_obs))
- atenuação 1/d e absorção do ar por harmônico  exp(-A·(f/1kHz)²·d)
- ruído de vento/pneus/freio e efeitos ligados a eventos da simulação (troca de marcha, frenagem, desaceleração)

Os perfis são sintetizados a partir de parâmetros físicos gerais; NÃO são cópias de gravações.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

C_SOUND = 343.0


@dataclass
class EngineProfile:
    name: str
    cylinders: int
    harmonics: tuple              # amplitudes relativas dos harmônicos da frequência de ignição
    half_order: float = 0.10      # amplitude da meia-ordem (irregularidade de ignição)
    jitter: float = 0.04          # variação ciclo-a-ciclo (rad)
    whine_ratio: float = 0.0      # tom agudo (turbo/MGU) como múltiplo da freq. de ignição
    whine_amp: float = 0.0
    tilt_load: float = 0.5        # brilho adicional sob carga
    absorption: float = 1.4e-4    # coeficiente de absorção do ar (1/m por (kHz)²)
    rpm_range: tuple = (4000.0, 15000.0)
    label: str = ""

    def fire_hz(self, rpm):
        return np.asarray(rpm, float) / 60.0 * (self.cylinders / 2.0)


PROFILES = {
    "v6_turbo_hibrido": EngineProfile(
        "v6_turbo_hibrido", 6, (1.0, 0.62, 0.66, 0.40, 0.34, 0.24, 0.17, 0.13, 0.10, 0.075, 0.055, 0.04),
        half_order=0.10, jitter=0.035, whine_ratio=2.6, whine_amp=0.035, tilt_load=0.55,
        rpm_range=(4000, 15000), label="V6 turbo híbrido (grave, denso)"),
    "v8_aspirado": EngineProfile(
        "v8_aspirado", 8, (1.0, 0.70, 0.55, 0.48, 0.34, 0.28, 0.20, 0.16, 0.12, 0.09, 0.07, 0.05),
        half_order=0.05, jitter=0.03, whine_amp=0.0, tilt_load=0.6,
        rpm_range=(5000, 19000), label="V8 aspirado (2006-2013)"),
    "v10_aspirado": EngineProfile(
        "v10_aspirado", 10, (1.0, 0.78, 0.62, 0.55, 0.45, 0.38, 0.30, 0.24, 0.19, 0.15, 0.12, 0.09),
        half_order=0.03, jitter=0.025, whine_amp=0.0, tilt_load=0.7,
        rpm_range=(6000, 19500), label="V10 aspirado (agudo, 'scream')"),
}


def get_profile(name: str) -> EngineProfile:
    if name not in PROFILES:
        raise KeyError(f"Perfil sonoro '{name}' inexistente: {list(PROFILES)}")
    return PROFILES[name]


# ---------------------------------------------------------------------------------- blocos de síntese
def harmonic_bank(phase: np.ndarray, f_fire: np.ndarray, load: np.ndarray, dist: np.ndarray, prof: EngineProfile,
                  jitter_noise: np.ndarray | None = None) -> np.ndarray:
    """Soma de harmônicos (mono) com inclinação por carga e absorção do ar. Todos os arrays têm o mesmo tamanho."""
    n = phase.shape[0]
    out = np.zeros(n)
    ph = phase if jitter_noise is None else phase + prof.jitter * jitter_noise
    tilt = 0.80 + prof.tilt_load * load                           # >1 sob carga: mais agudos
    for k, a in enumerate(prof.harmonics, start=1):
        fk = f_fire * k
        air = np.exp(-prof.absorption * (fk / 1000.0) ** 2 * np.maximum(dist, 1.0))
        out += a * (tilt ** (0.5 * (k - 1))) * air * np.sin(k * ph + 0.7 * k)
    # meia-ordem: cada cilindro não dispara exatamente igual
    out += prof.half_order * np.sin(0.5 * ph) * np.exp(-prof.absorption * (0.5 * f_fire / 1000.0) ** 2 * np.maximum(dist, 1.0))
    if prof.whine_amp > 0:
        fw = f_fire * prof.whine_ratio
        out += prof.whine_amp * (0.3 + load) * np.sin(prof.whine_ratio * ph) * np.exp(-prof.absorption * (fw / 1000.0) ** 2 * np.maximum(dist, 1.0))
    return out


def shaped_noise(n: int, sr: int, f_lo: float, f_hi: float, rng: np.random.Generator, slope: float = 0.0) -> np.ndarray:
    """Ruído de banda limitada gerado por moldagem espectral. slope: dB/oitava (negativo = rosa/marrom)."""
    spec = rng.standard_normal(n // 2 + 1) + 1j * rng.standard_normal(n // 2 + 1)
    f = np.fft.rfftfreq(n, 1.0 / sr)
    mask = ((f >= f_lo) & (f <= f_hi)).astype(float)
    # transições suaves
    mask *= 1.0 / (1.0 + (f_lo / np.maximum(f, 1e-3)) ** 4) / (1.0 + (np.maximum(f, 1e-3) / f_hi) ** 4)
    if slope != 0.0:
        mask *= (np.maximum(f, 20.0) / 1000.0) ** (slope / 6.02)
    x = np.fft.irfft(spec * mask, n)
    return (x / (np.std(x) + 1e-12)).astype(np.float32)


def reverb_ir(sr: int, rt60: float = 0.9, rng=None) -> np.ndarray:
    rng = rng or np.random.default_rng(7)
    n = int(sr * rt60)
    t = np.arange(n) / sr
    ir = rng.standard_normal(n) * np.exp(-6.9 * t / rt60)
    # absorção de agudos com o tempo
    for _ in range(3):
        ir = 0.5 * ir + 0.25 * (np.roll(ir, 1) + np.roll(ir, -1))
    ir[0] = 0.0
    return (ir / np.sqrt(np.sum(ir ** 2))).astype(np.float32)


def fft_convolve(x: np.ndarray, ir: np.ndarray) -> np.ndarray:
    n = x.shape[0] + ir.shape[0] - 1
    nfft = 1 << (n - 1).bit_length()
    y = np.fft.irfft(np.fft.rfft(x, nfft) * np.fft.rfft(ir, nfft), nfft)[: x.shape[0]]
    return y.astype(np.float32)


def soft_limit(x: np.ndarray, drive: float = 1.0) -> np.ndarray:
    return np.tanh(x * drive)


def write_wav(path, audio: np.ndarray, sr: int):
    """Grava WAV 16-bit PCM (mono ou estéreo) sem dependências externas."""
    import wave
    a = np.clip(audio, -1, 1)
    pcm = (a * 32767).astype("<i2")
    ch = 1 if a.ndim == 1 else a.shape[1]
    with wave.open(str(path), "wb") as w:
        w.setnchannels(ch); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(pcm.tobytes())
