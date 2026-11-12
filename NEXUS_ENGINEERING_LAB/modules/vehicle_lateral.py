"""Dinâmica lateral de veículo — modelo de uma pista (bicicleta) com transferência de carga lateral e pneu de escova.

Complementa `vehicle_dynamics.py` (longitudinal 1D). Classe dos resultados: ANALITICO (modelo reduzido, NÃO multicorpo,
NÃO um carro real validado). Todos os parâmetros são informados pelo usuário; `exemplo_ilustrativo()` existe só para
demonstração e é rotulado como ILUSTRATIVO.

Convenções (SAE simplificada): x à frente, y à esquerda, r = velocidade de guinada, δ = esterçamento, β = ângulo de
deriva do CG. Ângulos de deriva por eixo (forças positivas para a esquerda com α>0):
    α_f = δ − β − a·r/V          α_r = −β + b·r/V
Pneu (modelo de escova / Fiala): com θ = C/(3·μ·Fz) e σ = |tan α|,
    Fy = μ·Fz·(3θσ − 3(θσ)² + (θσ)³)   se θσ < 1,   senão  Fy = μ·Fz
(rigidez de curva C = dFy/dα em α→0 constante por pneu; saturação no atrito μ·Fz).
Transferência de carga lateral (Milliken): momento de rolagem M = m·ay·h_r, h_r = h − centro de rolagem médio;
parcela geométrica pelo centro de rolagem de cada eixo + parcela elástica pela distribuição de rigidez de rolagem.
Hipóteses: pequenos ângulos no equilíbrio, sem transferência longitudinal em curva, sem cambagem/convergência,
sem dinâmica de rolagem/arfagem (rolagem em regime), velocidade constante, pista plana, Ackermann ignorado.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .result_trace import TracedResult

G = 9.80665


@dataclass
class VeiculoLateral:
    m: float                  # massa total [kg]
    iz: float                 # inércia de guinada [kg·m²]
    a: float                  # CG → eixo dianteiro [m]
    b: float                  # CG → eixo traseiro [m]
    h: float                  # altura do CG [m]
    tf: float                 # bitola dianteira [m]
    tr: float                 # bitola traseira [m]
    c_f: float                # rigidez de curva por PNEU dianteiro [N/rad]
    c_r: float                # rigidez de curva por PNEU traseiro [N/rad]
    mu_f: float = 1.5         # atrito de pico dianteiro
    mu_r: float = 1.5         # atrito de pico traseiro
    k_roll_f: float = 60000.0   # rigidez de rolagem dianteira [N·m/rad]
    k_roll_r: float = 40000.0   # rigidez de rolagem traseira [N·m/rad]
    h_rc_f: float = 0.05      # altura do centro de rolagem dianteiro [m]
    h_rc_r: float = 0.08      # altura do centro de rolagem traseiro [m]
    cla: float = 0.0          # ClA [m²] (downforce = ½ρ·ClA·V²)
    frac_dt_aero: float = 0.5  # fração do downforce no eixo dianteiro
    rho: float = 1.225
    sens_mu_f: float = 0.0    # V3.8: sensibilidade do μ à carga, dianteiro (fração de perda de μ por +100% de carga sobre a estática). 0 = μ constante
    sens_mu_r: float = 0.0    # idem traseiro

    def validar(self) -> None:
        pos = dict(m=self.m, iz=self.iz, a=self.a, b=self.b, h=self.h, tf=self.tf, tr=self.tr, c_f=self.c_f, c_r=self.c_r,
                   mu_f=self.mu_f, mu_r=self.mu_r, k_roll_f=self.k_roll_f, k_roll_r=self.k_roll_r)
        for k, v in pos.items():
            if not (v > 0 and math.isfinite(v)):
                raise ValueError(f"parâmetro '{k}' deve ser positivo e finito")
        if self.cla < 0 or not 0 <= self.frac_dt_aero <= 1:
            raise ValueError("ClA ≥ 0 e fração aerodinâmica dianteira em [0,1]")
        if self.h_rc_f < 0 or self.h_rc_r < 0:
            raise ValueError("altura do centro de rolagem não pode ser negativa")
        if not (0.0 <= self.sens_mu_f <= 0.8 and 0.0 <= self.sens_mu_r <= 0.8):
            raise ValueError("sensibilidade do μ à carga deve estar em [0, 0.8]")

    @property
    def L(self) -> float:
        return self.a + self.b


def exemplo_ilustrativo() -> VeiculoLateral:
    """ILUSTRATIVO — valores genéricos de carro esportivo leve, NÃO medidos de nenhum veículo real."""
    return VeiculoLateral(m=1200.0, iz=1800.0, a=1.15, b=1.35, h=0.50, tf=1.50, tr=1.50, c_f=45000.0, c_r=45000.0,
                          mu_f=1.2, mu_r=1.2)


# ---------------------------------------------------------------- pneu e eixo
MU_PISO = 0.2   # μ_ef nunca cai abaixo de 20% do nominal (evita extrapolação sem sentido do modelo linear)


def mu_efetivo(mu: float, sens: float, fz: float, fz_ref: float) -> float:
    """V3.8 — μ do pneu em função da carga: μ_ef = μ·max(1 − sens·(Fz/Fz_ref − 1), 0.2).

    `mu` é o atrito nominal NA carga estática de referência `fz_ref` (por pneu, sem aero). `sens` é a queda fracionária de μ quando a carga
    DOBRA (ex.: 0.10 → μ cai 10% com +100% de carga; ganho abaixo da referência). Modelo linear e ILUSTRATIVO: a sensibilidade real vem de
    ensaio do pneu (ajuste por CSV). sens = 0 → μ constante (comportamento anterior, exato)."""
    if sens == 0.0 or fz_ref <= 0.0:
        return mu
    return mu * max(1.0 - sens * (fz / fz_ref - 1.0), MU_PISO)


def fz_ref_eixo(v: "VeiculoLateral", eixo: str) -> float:
    """Carga estática por pneu do eixo [N] (sem aerodinâmica) — referência do μ nominal."""
    return v.m * G * (v.b if eixo == "f" else v.a) / v.L / 2.0


def pneu_fy(alpha: float, fz: float, c: float, mu: float, sens: float = 0.0, fz_ref: float = 0.0) -> float:
    """Força lateral [N] do pneu de escova (positiva para α>0). fz ≤ 0 (pneu levantado) → 0.
    Opcional (V3.8): `sens`/`fz_ref` ativam a sensibilidade do μ à carga (ver `mu_efetivo`); padrão = μ constante."""
    if fz <= 0.0:
        return 0.0
    mu = mu_efetivo(mu, sens, fz, fz_ref)
    th = c / (3.0 * mu * fz)
    s = abs(math.tan(alpha)) if abs(alpha) < math.pi / 2 - 1e-9 else 1e9
    x = th * s
    f = mu * fz * (3 * x - 3 * x * x + x ** 3) if x < 1.0 else mu * fz
    return math.copysign(f, alpha)


def cargas_eixos(v: VeiculoLateral, vel: float, ay: float) -> dict:
    """Cargas verticais por pneu [N] em regime a ay (m/s², positivo = curva à esquerda: carga vai para a direita)."""
    L = v.L
    df = 0.5 * v.rho * v.cla * vel * vel
    fzf0 = v.m * G * v.b / L + df * v.frac_dt_aero
    fzr0 = v.m * G * v.a / L + df * (1 - v.frac_dt_aero)
    h_rc = (v.h_rc_f * v.b + v.h_rc_r * v.a) / L                  # centro de rolagem médio no CG
    hr = v.h - h_rc
    m_roll = v.m * ay * hr
    kt = v.k_roll_f + v.k_roll_r
    dzf = (v.m * ay * (v.b / L) * v.h_rc_f + m_roll * v.k_roll_f / kt) / v.tf
    dzr = (v.m * ay * (v.a / L) * v.h_rc_r + m_roll * v.k_roll_r / kt) / v.tr
    # CORREÇÃO V3.7: quando a transferência passa de metade da carga do eixo a roda interna levanta (Fz=0) e a externa recebe NO MÁXIMO a carga
    # total do eixo (antes a externa passava de fz0 e o eixo "ganhava" aderência — só ocorria com roda levantando, caso extremo).
    def par(fz0, dz):
        a, b = fz0 / 2 + dz, fz0 / 2 - dz           # a = lado que recebe carga, b = lado que perde
        return (min(a, fz0), max(b, 0.0)) if dz >= 0 else (max(a, 0.0), min(b, fz0))
    f_i, f_e = par(fzf0, dzf); r_i, r_e = par(fzr0, dzr)
    return {"f_int": f_i, "f_ext": f_e, "r_int": r_i, "r_ext": r_e, "dzf": dzf, "dzr": dzr, "fzf": fzf0, "fzr": fzr0}


def fy_eixo(v: VeiculoLateral, eixo: str, alpha: float, vel: float, ay: float) -> float:
    cg = cargas_eixos(v, vel, ay)
    c, mu, sens = (v.c_f, v.mu_f, v.sens_mu_f) if eixo == "f" else (v.c_r, v.mu_r, v.sens_mu_r)
    f1, f2 = (cg["f_int"], cg["f_ext"]) if eixo == "f" else (cg["r_int"], cg["r_ext"])
    zr = fz_ref_eixo(v, eixo)
    return pneu_fy(alpha, max(f1, 0.0), c, mu, sens, zr) + pneu_fy(alpha, max(f2, 0.0), c, mu, sens, zr)


def fy_max_eixo(v: VeiculoLateral, eixo: str, vel: float, ay: float) -> float:
    cg = cargas_eixos(v, vel, ay)
    mu, sens = (v.mu_f, v.sens_mu_f) if eixo == "f" else (v.mu_r, v.sens_mu_r)
    f1, f2 = (cg["f_int"], cg["f_ext"]) if eixo == "f" else (cg["r_int"], cg["r_ext"])
    zr = fz_ref_eixo(v, eixo)
    return sum(mu_efetivo(mu, sens, z, zr) * z for z in (max(f1, 0.0), max(f2, 0.0)))


def alpha_para_forca(v: VeiculoLateral, eixo: str, fy_req: float, vel: float, ay: float) -> float | None:
    """Inverte Fy_eixo(α) por bisseção (monótona até saturar). None se fy_req excede a capacidade do eixo."""
    if fy_req > fy_max_eixo(v, eixo, vel, ay) * (1 - 1e-9):
        return None
    lo, hi = 0.0, math.radians(60)
    if fy_eixo(v, eixo, hi, vel, ay) < fy_req:
        return None
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if fy_eixo(v, eixo, mid, vel, ay) < fy_req:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# ---------------------------------------------------------------- regime permanente
def regime_curva(v: VeiculoLateral, vel: float, raio: float) -> dict:
    """Curva permanente de raio `raio` a `vel`: esterçamento δ, deriva β, α por eixo, cargas e gradiente de subesterço.

    Retorna {'saturado': True, ...} se a aderência não sustenta a curva (sem números de esterçamento inventados).
    """
    v.validar()
    if vel <= 0 or raio <= 0:
        raise ValueError("velocidade e raio devem ser positivos")
    ay = vel * vel / raio
    L = v.L
    fyf, fyr = v.m * ay * v.b / L, v.m * ay * v.a / L
    af = alpha_para_forca(v, "f", fyf, vel, ay)
    ar = alpha_para_forca(v, "r", fyr, vel, ay)
    cg = cargas_eixos(v, vel, ay)
    out = {"ay_ms2": ay, "ay_g": ay / G, "fy_f": fyf, "fy_r": fyr, "cargas": cg}
    if af is None or ar is None:
        out.update(saturado=True, eixo_saturado=("frente" if af is None else "traseira") if not (af is None and ar is None) else "ambos")
        return out
    delta = af - ar + L / raio
    beta = v.b / raio - ar
    k = (af - ar) / ay
    out.update(saturado=False, alpha_f=af, alpha_r=ar, delta=delta, beta=beta, k_subesterco=k,
               comportamento="subesterçante" if k > 1e-9 else ("sobresterçante" if k < -1e-9 else "neutro"))
    return out


def ay_limite(v: VeiculoLateral, vel: float) -> dict:
    """Maior aceleração lateral sustentável a `vel` e qual eixo satura primeiro (limite de aderência)."""
    v.validar()
    lo, hi = 0.0, 8.0 * G
    for _ in range(80):
        ay = 0.5 * (lo + hi)
        fyf, fyr = v.m * ay * v.b / v.L, v.m * ay * v.a / v.L
        ok = fyf <= fy_max_eixo(v, "f", vel, ay) and fyr <= fy_max_eixo(v, "r", vel, ay)
        lo, hi = (ay, hi) if ok else (lo, ay)
    ay = lo
    fyf, fyr = v.m * ay * v.b / v.L, v.m * ay * v.a / v.L
    rf = fyf / max(fy_max_eixo(v, "f", vel, ay), 1e-9)
    rr = fyr / max(fy_max_eixo(v, "r", vel, ay), 1e-9)
    return {"ay_ms2": ay, "ay_g": ay / G, "utilizacao_frente": rf, "utilizacao_traseira": rr,
            "limite": "subesterço (frente satura primeiro)" if rf >= rr else "sobresterço (traseira satura primeiro)"}


def skidpad(v: VeiculoLateral, raio: float) -> dict:
    """Velocidade máxima em curva de raio constante (ponto fixo de V² / R = ay_lim(V), com downforce)."""
    if raio <= 0:
        raise ValueError("raio deve ser positivo")
    vel = math.sqrt(0.5 * G * raio)
    for _ in range(200):
        a = ay_limite(v, vel)["ay_ms2"]
        vn = math.sqrt(a * raio)
        if abs(vn - vel) < 1e-9:
            vel = vn
            break
        vel = 0.5 * (vel + vn)
    r = ay_limite(v, vel)
    return {"v_ms": vel, "v_kmh": vel * 3.6, "ay_g": r["ay_g"], "limite": r["limite"], "tempo_volta_s": 2 * math.pi * raio / vel}


def gradiente_subesterco_linear(v: VeiculoLateral) -> float:
    """K = (Wf/Cαf − Wr/Cαr)/g [rad/(m/s²)] — fórmula fechada (pneus lineares, sem transferência de carga, sem aero).

    Wf, Wr = pesos estáticos por eixo [N]; Cα = rigidez de curva do EIXO (2 pneus).
    """
    wf, wr = v.m * G * v.b / v.L, v.m * G * v.a / v.L
    return (wf / (2 * v.c_f) - wr / (2 * v.c_r)) / G


# ---------------------------------------------------------------- domínio do tempo
def degrau_esterco(v: VeiculoLateral, vel: float, delta: float, t_final: float = 3.0, dt: float = 0.001, t_step: float = 0.1) -> list:
    """Resposta a degrau de esterçamento (RK4, velocidade constante). Estados: vy (deriva lateral) e r.

    Cargas verticais usam ay = V·(β̇ + r) ≈ aceleração lateral instantânea (quase-estática, sem dinâmica de rolagem).
    Retorna lista de (t, vy, r, ay, beta).
    """
    v.validar()
    if vel <= 0 or dt <= 0 or t_final <= 0:
        raise ValueError("vel, dt e t_final devem ser positivos")

    def deriv(vy, r, d):
        beta = math.atan2(vy, vel)
        af = d - beta - v.a * r / vel
        ar = -beta + v.b * r / vel
        # ay depende de Fy (implícito): usa estimativa da iteração anterior via ponto fixo curto
        ay = vel * r
        for _ in range(3):
            fyf = fy_eixo(v, "f", af, vel, ay)
            fyr = fy_eixo(v, "r", ar, vel, ay)
            ay = (fyf + fyr) / v.m
        fyf = fy_eixo(v, "f", af, vel, ay)
        fyr = fy_eixo(v, "r", ar, vel, ay)
        vy_dot = (fyf + fyr) / v.m - vel * r
        r_dot = (v.a * fyf - v.b * fyr) / v.iz
        return vy_dot, r_dot, (fyf + fyr) / v.m, beta

    vy = r = 0.0
    t = 0.0
    out = [(0.0, 0.0, 0.0, 0.0, 0.0)]
    n = int(round(t_final / dt))
    for _ in range(n):
        d = delta if t >= t_step - 1e-12 else 0.0
        k1 = deriv(vy, r, d)
        k2 = deriv(vy + 0.5 * dt * k1[0], r + 0.5 * dt * k1[1], d)
        k3 = deriv(vy + 0.5 * dt * k2[0], r + 0.5 * dt * k2[1], d)
        k4 = deriv(vy + dt * k3[0], r + dt * k3[1], d)
        vy += dt * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0]) / 6
        r += dt * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1]) / 6
        t += dt
        _, _, ay, beta = deriv(vy, r, d)
        out.append((t, vy, r, ay, beta))
    return out


# ---------------------------------------------------------------- resultado rastreável
def resumo_curva(v: VeiculoLateral, vel: float, raio: float, ilustrativo: bool = False) -> TracedResult:
    reg = regime_curva(v, vel, raio)
    lim = ay_limite(v, vel)
    vals = {"ay_g": reg["ay_g"], "saturado": reg["saturado"], "ay_limite_g": lim["ay_g"], "limite": lim["limite"],
            "transferencia_carga_frente_N": reg["cargas"]["dzf"], "transferencia_carga_traseira_N": reg["cargas"]["dzr"]}
    if not reg["saturado"]:
        vals.update(delta_deg=math.degrees(reg["delta"]), beta_deg=math.degrees(reg["beta"]), k_subesterco_deg_por_g=math.degrees(reg["k_subesterco"]) * G,
                    comportamento=reg["comportamento"])
    prem = ["modelo de uma pista (bicicleta)", "pneu de escova com C e μ informados", "transferência de carga lateral em regime (Milliken)",
            "velocidade constante, pista plana, sem cambagem/convergência, sem dinâmica de rolagem",
            f"μ {'constante' if not (v.sens_mu_f or v.sens_mu_r) else 'com sensibilidade linear à carga (sens_mu_f=%g, sens_mu_r=%g) — ILUSTRATIVA se não vier de ensaio' % (v.sens_mu_f, v.sens_mu_r)}"]
    if ilustrativo:
        prem.append("PARÂMETROS ILUSTRATIVOS — não representam veículo real")
    return TracedResult(nome="Curva em regime (modelo bicicleta)", classe="ANALITICO",
                        metodo="Equilíbrio de forças/momento por eixo com inversão do pneu de escova e transferência de carga",
                        valores=vals, entradas={**v.__dict__, "vel_ms": vel, "raio_m": raio}, premissas=prem,
                        limitacoes=["não é multicorpo", "não substitui ensaio nem dados de pneu reais (Pacejka/TTC)",
                                    "sem dinâmica longitudinal acoplada (círculo de atrito não aplicado em curva+tração)"])
