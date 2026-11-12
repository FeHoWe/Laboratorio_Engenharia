"""Pneu de escova com FORÇA COMBINADA (longitudinal + lateral) — modelo isotrópico saturado pelo círculo de atrito.

Teoria (escova, distribuição parabólica de pressão): com rigidezes de escorregamento Cκ [N/unid. de κ] e Cα [N/rad], deslizamentos práticos
sx = κ/(1+κ), sy = tanα/(1+κ) e normalizados s' = (Cκ·sx, Cα·sy)/(3μFz), |s'| = √(sx'²+sy'²), a força total é
    F = μFz·(3s − 3s² + s³)  (s<1)  ou  μFz  (s ≥ 1),  na direção do vetor de deslizamento (oposta ao movimento relativo da banda).
Propriedades garantidas por teste: (1) em κ=0 reduz EXATAMENTE a `vehicle_lateral.pneu_fy`; (2) |F| ≤ μFz (círculo de atrito) sempre;
(3) tração/frenagem reduz a força lateral disponível; (4) simétrico em α e κ.
LIMITES: modelo teórico simplificado (μ constante, sem relaxamento, sem camber/temperatura/carga-dependência); parâmetros são do
USUÁRIO — não é um pneu real (para isso use dados Pacejka medidos). Ilustrativo até ser ajustado com ensaio.
"""
from __future__ import annotations

import math

KAPPA_MIN = -0.999


def forca_combinada(kappa: float, alpha: float, fz: float, c_alpha: float, c_kappa: float, mu: float) -> tuple[float, float]:
    """(Fx, Fy) em N. Fx>0 = tração (κ>0), Fy>0 para α>0. fz ≤ 0 → (0, 0)."""
    if fz <= 0.0:
        return 0.0, 0.0
    k = max(kappa, KAPPA_MIN)
    sx = k / (1.0 + k)
    sy = (math.tan(alpha) if abs(alpha) < math.pi / 2 - 1e-9 else math.copysign(1e9, alpha)) / (1.0 + k)
    nx, ny = c_kappa * sx / (3.0 * mu * fz), c_alpha * sy / (3.0 * mu * fz)
    s = math.hypot(nx, ny)
    if s == 0.0:
        return 0.0, 0.0
    f = mu * fz * ((3 * s - 3 * s * s + s ** 3) if s < 1.0 else 1.0)
    return f * nx / s, f * ny / s


def fy_disponivel(kappa: float, alpha: float, fz: float, c_alpha: float, c_kappa: float, mu: float) -> float:
    """Força lateral que sobra quando o pneu também transmite `kappa` (eixo de curva sob tração/frenagem)."""
    return forca_combinada(kappa, alpha, fz, c_alpha, c_kappa, mu)[1]


def envelope_fx_fy(fz: float, c_alpha: float, c_kappa: float, mu: float, n: int = 72, alpha_max: float = 0.4) -> list:
    """Varre κ∈[-0,6; 0,6] e α∈[-α_max; α_max] e devolve os pares (Fx, Fy) extremos — o contorno ('elipse') de força do pneu."""
    pts = []
    for i in range(n + 1):
        k = -0.6 + 1.2 * i / n
        for a in (-alpha_max, alpha_max, 0.0):
            pts.append(forca_combinada(k, a, fz, c_alpha, c_kappa, mu))
    return pts
