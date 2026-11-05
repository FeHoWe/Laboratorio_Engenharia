"""Aerodinâmica e desempenho de veículo — cálculos ANALÍTICOS (V2.2).

HONESTIDADE: isto NÃO é CFD nem túnel de vento. São modelos clássicos de engenharia (atmosfera padrão ISA, forças por coeficientes,
linha sustentadora de Prandtl/Glauert, teoria de perfil fino). Todo coeficiente (CdA, ClA, Cd0 do perfil, atrito de pneu, potência…) é digitado
pelo usuário; o NEXUS não "adivinha" coeficientes da geometria 3D. Resultados valem tanto quanto as entradas e as hipóteses declaradas.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

G = 9.80665
R_AIR = 287.0528
GAMMA = 1.4


# ------------------------------------------------------------------ atmosfera padrão ISA (0–20 km)
def isa(h_m: float, dT: float = 0.0) -> dict:
    """Atmosfera padrão internacional. ``dT``: desvio de temperatura (K) somado à ISA. Válida de -500 m a 20 km."""
    if not -500.0 <= h_m <= 20000.0:
        raise ValueError("Altitude fora da faixa 0–20 km da ISA implementada.")
    T0, p0, L = 288.15, 101325.0, -0.0065
    if h_m <= 11000.0:
        T = T0 + L * h_m
        p = p0 * (T / T0) ** (-G / (L * R_AIR))
    else:
        T11 = T0 + L * 11000.0
        p11 = p0 * (T11 / T0) ** (-G / (L * R_AIR))
        T = T11
        p = p11 * math.exp(-G * (h_m - 11000.0) / (R_AIR * T11))
    T_act = T + dT
    rho = p / (R_AIR * T_act)
    mu = 1.458e-6 * T_act ** 1.5 / (T_act + 110.4)           # Sutherland
    return {"T": T_act, "p": p, "rho": rho, "mu": mu, "a": math.sqrt(GAMMA * R_AIR * T_act)}


def dynamic_pressure(rho: float, v: float) -> float:
    return 0.5 * rho * v * v


def force(coef_area: float, rho: float, v: float) -> float:
    """F = ½ ρ V² (C·A). ``coef_area`` = CdA ou ClA em m²."""
    return dynamic_pressure(rho, v) * coef_area


def reynolds(rho: float, v: float, length: float, mu: float) -> float:
    return rho * v * length / mu


def cf_flat_plate_turbulent(re: float) -> float:
    """Coeficiente de atrito médio de placa plana turbulenta (Schlichting): 0.455/(log10 Re)^2.58. Estimativa — válida 5e5<Re<1e9."""
    if re <= 0:
        raise ValueError("Re deve ser positivo.")
    return 0.455 / math.log10(re) ** 2.58


def bernoulli_cp(v_local: float, v_inf: float) -> float:
    """Cp = 1 − (V/V∞)² (incompressível, sem perdas — ideal para estimar sucção de difusor/venturi, não para esteira)."""
    return 1.0 - (v_local / v_inf) ** 2


# ------------------------------------------------------------------ desempenho do veículo
@dataclass
class Vehicle:
    mass: float                 # kg
    cda: float                  # m²  (arrasto)
    cla: float                  # m²  (sustentação NEGATIVA = downforce positivo, digite o valor positivo de downforce)
    power: float                # W  na roda (já com rendimento)
    mu_tyre: float              # coeficiente de atrito pneu–solo (suposto constante)
    crr: float = 0.012          # resistência de rolamento (digitado)
    rho: float = 1.225

    def drag(self, v: float) -> float:
        return force(self.cda, self.rho, v)

    def downforce(self, v: float) -> float:
        return force(self.cla, self.rho, v)

    def rolling(self, v: float) -> float:
        return self.crr * self.normal_load(v) if v > 0 else 0.0

    def normal_load(self, v: float) -> float:
        return self.mass * G + self.downforce(v)

    def power_required(self, v: float) -> float:
        return (self.drag(v) + self.rolling(v)) * v

    def top_speed(self) -> float:
        """Maior V com potência disponível = requerida (bisseção). Sem limite de tração/rotação."""
        lo, hi = 1.0, 200.0
        if self.power_required(hi) < self.power:
            return hi
        for _ in range(80):
            mid = 0.5 * (lo + hi)
            if self.power_required(mid) < self.power:
                lo = mid
            else:
                hi = mid
        return 0.5 * (lo + hi)

    def corner_speed(self, radius: float) -> float:
        """Velocidade máxima em curva plana de raio R: m V²/R = μ (m g + ½ρ V² ClA). inf se o downforce sozinho segura a curva."""
        if radius <= 0:
            raise ValueError("Raio deve ser positivo.")
        den = self.mass / radius - self.mu_tyre * 0.5 * self.rho * self.cla
        if den <= 0:
            return math.inf
        return math.sqrt(self.mu_tyre * self.mass * G / den)

    def braking_decel(self, v: float) -> float:
        """Desaceleração máxima (m/s²) com atrito total: μ·N/m + arrasto/m (ignora balanço de frenagem e transferência de carga)."""
        return (self.mu_tyre * self.normal_load(v) + self.drag(v)) / self.mass

    def accel(self, v: float) -> float:
        """Aceleração limitada pela potência (sem limite de tração)."""
        return (self.power / max(v, 1.0) - self.drag(v) - self.rolling(v)) / self.mass


def speed_sweep(veh: Vehicle, speeds_ms) -> list[dict]:
    rows = []
    for v in speeds_ms:
        rows.append({"v": v, "kmh": v * 3.6, "q": dynamic_pressure(veh.rho, v), "drag": veh.drag(v), "down": veh.downforce(v),
                     "p_req": veh.power_required(v), "ld": (veh.cla / veh.cda) if veh.cda else float("nan")})
    return rows


# ------------------------------------------------------------------ perfil fino (NACA 4 dígitos)
def naca4_alpha_l0(m: float, p: float) -> float:
    """Ângulo de sustentação nula (rad) da linha de curvatura NACA 4 dígitos pela teoria de perfil fino:
    α_L0 = −(1/π) ∫₀^π (dz/dx)(cosθ − 1) dθ, com x = (1−cosθ)/2. ``m`` = camber máx (fração da corda), ``p`` = posição (fração)."""
    if m <= 0:
        return 0.0
    th = np.linspace(0, math.pi, 4001)
    x = 0.5 * (1 - np.cos(th))
    dz = np.where(x < p, 2 * m / p ** 2 * (p - x), 2 * m / (1 - p) ** 2 * (p - x))
    f = dz * (np.cos(th) - 1.0)
    return float(-np.trapezoid(f, th) / math.pi)


@dataclass
class WingResult:
    cl: float
    cdi: float
    e: float
    ar: float
    area: float
    span: float
    cl_alpha: float


def lifting_line(span: float, chords, alpha_deg: float, alpha_l0_deg: float = 0.0, twist_deg=None, a0: float = 2 * math.pi,
                 n_terms: int = 40, h_ground: float | None = None) -> WingResult:
    """Linha sustentadora de Prandtl (série de Glauert) para asa reta, simétrica.

    ``chords``: função c(y) com y/(b/2) em [-1,1] (callable) — ou número (asa retangular).
    ``alpha_deg``: incidência geométrica da raiz; ``twist_deg``: função/numero de torção geométrica (graus) em y/(b/2) (None = sem torção).
    ``alpha_l0_deg``: ângulo de sustentação nula do perfil (digitado ou de naca4_alpha_l0). ``a0``: inclinação da curva do perfil (2π por perfil fino).
    ``h_ground``: altura do bordo de ataque ao solo (m) -> reduz CDi pelo fator de efeito solo de McCormick/Wieselsberger
    φ=(16h/b)²/(1+(16h/b)²) (APROXIMAÇÃO de aeronave; o chão de um F1 é bem mais complexo).
    """
    cfun = chords if callable(chords) else (lambda s, c=float(chords): c)
    tw = twist_deg if callable(twist_deg) else (lambda s, t=float(twist_deg or 0.0): t)
    N = n_terms
    th = (np.arange(1, N + 1) * math.pi / (2 * N))               # estações 0<θ<π/2 (simetria)
    s = np.cos(th)                                                # y/(b/2)
    c = np.array([cfun(float(v)) for v in s])
    alpha = np.radians(np.array([alpha_deg + tw(float(v)) for v in s]) - alpha_l0_deg)
    odd = np.arange(1, 2 * N, 2)
    mu = c * a0 / (4 * span)
    M = np.zeros((N, N))
    for i in range(N):
        for j, n in enumerate(odd):
            M[i, j] = math.sin(n * th[i]) * (n * mu[i] + math.sin(th[i])) 
    rhs = mu * alpha * np.sin(th)
    A = np.linalg.solve(M, rhs)
    # área e AR por integração da corda
    ys = np.linspace(-1, 1, 2001)
    cs = np.array([cfun(float(v)) for v in ys])
    area = float(np.trapezoid(cs, ys * span / 2))
    ar = span ** 2 / area
    cl = float(A[0] * math.pi * ar)
    delta = sum(int(n) * (A[j] / A[0]) ** 2 for j, n in enumerate(odd) if j > 0)
    cdi = cl ** 2 / (math.pi * ar) * (1 + delta)
    e = 1.0 / (1 + delta)
    if h_ground is not None:
        k = (16 * h_ground / span) ** 2
        cdi *= k / (1 + k)
        e = e / (k / (1 + k))
    cl_alpha = cl / math.radians(alpha_deg - alpha_l0_deg) if alpha_deg != alpha_l0_deg else float("nan")
    return WingResult(cl=cl, cdi=cdi, e=e, ar=ar, area=area, span=span, cl_alpha=cl_alpha)


def wing_forces(res: WingResult, rho: float, v: float, cd0: float = 0.0) -> dict:
    """Forças da asa em V. ``cd0`` = arrasto de perfil (digitado). Sinal: lift positivo; para asa invertida (downforce) o módulo é o downforce."""
    q = dynamic_pressure(rho, v)
    lift = q * res.area * res.cl
    drag = q * res.area * (cd0 + res.cdi)
    return {"q": q, "lift": lift, "drag": drag, "induced": q * res.area * res.cdi, "ld": lift / drag if drag else float("inf")}
