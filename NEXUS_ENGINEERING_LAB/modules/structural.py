"""Testes estruturais ANALÍTICOS (V2.2): vigas, flambagem de coluna, parafuso pré-tensionado, torção, vaso de pressão, vibração.

HONESTIDADE: fórmulas clássicas de resistência dos materiais (Euler-Bernoulli, Euler/Johnson, Shigley, Roark). NÃO é elementos finitos:
não captura concentração de tensão, contato, plasticidade, geometria complexa. E, G, ρ e limites (Sy) são digitados pelo usuário
(o banco de materiais do NEXUS guarda só densidades). Unidades: mm, N, MPa (N/mm²), kg, s — coerentes entre si (massa em t no cálculo dinâmico é convertida).
"""
from __future__ import annotations

import math
from dataclasses import dataclass


# ------------------------------------------------------------------ propriedades de seção (mm)
@dataclass
class Section:
    area: float          # mm²
    inertia: float       # mm⁴ (eixo de flexão)
    c: float             # distância à fibra mais afastada, mm
    polar: float         # mm⁴ (J, só para seções circulares/tubulares)


def rect(b: float, h: float) -> Section:
    return Section(b * h, b * h ** 3 / 12, h / 2, float("nan"))


def circle(d: float) -> Section:
    return Section(math.pi * d * d / 4, math.pi * d ** 4 / 64, d / 2, math.pi * d ** 4 / 32)


def tube_round(d: float, t: float) -> Section:
    di = d - 2 * t
    if di <= 0:
        raise ValueError("Espessura maior que o raio.")
    return Section(math.pi * (d * d - di * di) / 4, math.pi * (d ** 4 - di ** 4) / 64, d / 2, math.pi * (d ** 4 - di ** 4) / 32)


def tube_rect(b: float, h: float, t: float) -> Section:
    bi, hi = b - 2 * t, h - 2 * t
    if bi <= 0 or hi <= 0:
        raise ValueError("Espessura grande demais para o tubo retangular.")
    return Section(b * h - bi * hi, (b * h ** 3 - bi * hi ** 3) / 12, h / 2, float("nan"))


def i_beam(b: float, h: float, tf: float, tw: float) -> Section:
    hw = h - 2 * tf
    if hw <= 0 or tw >= b:
        raise ValueError("Dimensões inválidas do perfil I.")
    return Section(2 * b * tf + hw * tw, (b * h ** 3 - (b - tw) * hw ** 3) / 12, h / 2, float("nan"))


# ------------------------------------------------------------------ vigas (Euler-Bernoulli)
BEAM_CASES = {
    "Em balanço — carga na ponta": "cant_end",
    "Em balanço — carga distribuída": "cant_udl",
    "Biapoiada — carga no meio": "ss_mid",
    "Biapoiada — carga distribuída": "ss_udl",
    "Engastada-apoiada — carga no meio": "fp_mid",
}


def beam(case: str, load: float, length: float, E: float, section: Section, yield_strength: float | None = None) -> dict:
    """``load``: N (carga pontual) ou N/mm (distribuída). Retorna flecha máx (mm), momento máx (N·mm), tensão de flexão máx (MPa)."""
    if length <= 0 or E <= 0 or section.inertia <= 0:
        raise ValueError("Comprimento, E e inércia devem ser positivos.")
    EI, L, P = E * section.inertia, length, load
    if case == "cant_end":
        defl, M = P * L ** 3 / (3 * EI), P * L
    elif case == "cant_udl":
        defl, M = P * L ** 4 / (8 * EI), P * L * L / 2
    elif case == "ss_mid":
        defl, M = P * L ** 3 / (48 * EI), P * L / 4
    elif case == "ss_udl":
        defl, M = 5 * P * L ** 4 / (384 * EI), P * L * L / 8
    elif case == "fp_mid":                       # engastada em x=0 e apoiada em x=L, carga em L/2 (Roark): δ_max≈0.009317 P L³/EI; M_max no engaste = 3PL/16
        defl, M = 0.009317 * P * L ** 3 / EI, 3 * P * L / 16
    else:
        raise KeyError(case)
    sigma = M * section.c / section.inertia
    out = {"deflection": abs(defl), "moment": abs(M), "sigma": abs(sigma), "stiffness": abs(P / defl) if defl else math.inf}
    if yield_strength:
        out["safety_factor"] = yield_strength / abs(sigma) if sigma else math.inf
    return out


# ------------------------------------------------------------------ flambagem de coluna
END_K = {"Articulada–articulada (K=1,0)": 1.0, "Engastada–livre (K=2,0)": 2.0, "Engastada–articulada (K=0,7)": 0.7, "Engastada–engastada (K=0,5)": 0.5}


def column_buckling(E: float, section: Section, length: float, K: float, yield_strength: float) -> dict:
    """Carga crítica: Euler se λ ≥ λc=√(2π²E/Sy); senão parábola de Johnson. Retorna também o regime usado."""
    r = math.sqrt(section.inertia / section.area)
    lam = K * length / r
    lam_c = math.sqrt(2 * math.pi ** 2 * E / yield_strength)
    pe = math.pi ** 2 * E * section.inertia / (K * length) ** 2
    if lam >= lam_c:
        pcr, regime = pe, "Euler (coluna esbelta)"
    else:
        pcr, regime = section.area * yield_strength * (1 - yield_strength * lam ** 2 / (4 * math.pi ** 2 * E)), "Johnson (coluna intermediária)"
    return {"slenderness": lam, "slenderness_crit": lam_c, "p_euler": pe, "p_crit": pcr, "regime": regime, "r": r}


# ------------------------------------------------------------------ parafuso pré-tensionado (Shigley)
# d: (passo grosso mm, área de tensão At mm²) — ISO 898/261
BOLT_AT = {3: (0.5, 5.03), 4: (0.7, 8.78), 5: (0.8, 14.2), 6: (1.0, 20.1), 8: (1.25, 36.6), 10: (1.5, 58.0), 12: (1.75, 84.3),
           14: (2.0, 115.0), 16: (2.0, 157.0), 20: (2.5, 245.0), 24: (3.0, 353.0)}


def bolt_joint(d: int, torque_nm: float, k_nut: float, proof_strength: float, ext_load: float = 0.0, clamp_stiff_ratio: float = 4.0) -> dict:
    """Pré-carga por torque: Fi = T/(K d) (K=fator de torque, DIGITADO — 0,2 é valor de manual p/ seco, varia muito!). 
    ``clamp_stiff_ratio`` = km/kb (rigidez do material comprimido / do parafuso), digitado. Carga externa de tração Pe: fração C=kb/(kb+km)."""
    if d not in BOLT_AT:
        raise KeyError(f"M{d} não tabelado")
    At = BOLT_AT[d][1]
    fi = torque_nm * 1000.0 / (k_nut * d)
    C = 1.0 / (1.0 + clamp_stiff_ratio)
    f_bolt = fi + C * ext_load
    f_clamp = fi - (1 - C) * ext_load
    return {"At": At, "preload": fi, "preload_stress": fi / At, "proof_load": proof_strength * At, "preload_ratio": fi / (proof_strength * At),
            "C": C, "bolt_load": f_bolt, "bolt_stress": f_bolt / At, "clamp_load": f_clamp, "separation_load": fi / (1 - C) if C < 1 else math.inf,
            "n_proof": proof_strength * At / f_bolt if f_bolt else math.inf}


# ------------------------------------------------------------------ torção de eixo
def shaft_torsion(torque_nmm: float, d: float, length: float, G: float, d_in: float = 0.0) -> dict:
    sec_j = math.pi * (d ** 4 - d_in ** 4) / 32
    tau = torque_nmm * (d / 2) / sec_j
    theta = torque_nmm * length / (G * sec_j)
    return {"tau": tau, "theta_rad": theta, "theta_deg": math.degrees(theta), "stiffness": torque_nmm / theta if theta else math.inf, "J": sec_j}


# ------------------------------------------------------------------ vaso de pressão de parede fina
def thin_vessel(p: float, d_inner: float, t: float) -> dict:
    """Cilindro de parede fina (válido se t < d/20). Tensões em MPa para p em MPa."""
    r = d_inner / 2
    return {"hoop": p * r / t, "axial": p * r / (2 * t), "thin_ok": t < d_inner / 20}


# ------------------------------------------------------------------ vibração
def spring_mass_fn(k: float, m: float) -> float:
    """Frequência natural (Hz) de massa-mola: k em N/mm e m em kg."""
    return math.sqrt(k * 1000.0 / m) / (2 * math.pi)


def cantilever_fn(E: float, section: Section, length: float, density_kg_m3: float, mode: int = 1) -> float:
    """Frequência natural (Hz) do modo ``mode`` (1–3) de viga em balanço uniforme: f = (βL)²/(2π) √(EI/(ρA L⁴)). E em MPa, dimensões em mm."""
    bl = {1: 1.8751, 2: 4.6941, 3: 7.8548}[mode]
    EI = E * 1e6 * section.inertia * 1e-12    # N·m² (E MPa→Pa; mm⁴→m⁴)
    mass_per_len = density_kg_m3 * section.area * 1e-6   # kg/m
    L = length * 1e-3
    return bl ** 2 / (2 * math.pi) * math.sqrt(EI / (mass_per_len * L ** 4))
