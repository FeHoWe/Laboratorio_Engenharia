"""Simulação de fadiga (V2.0): método de tensões nominais (vida infinita e vida finita), dano acumulado e molas helicoidais.

Escopo e honestidade (regras do projeto):
  * É uma ANÁLISE ANALÍTICA de tensão nominal — NÃO é elementos finitos. Ela não enxerga a geometria 3D do CAD: a seção, as
    cargas e os fatores de concentração (Kt, q) são informados pelo usuário.
  * O banco de materiais do NEXUS tem só densidades. As resistências (Su, Sy, Se', G) são SEMPRE digitadas pelo usuário a
    partir de norma/ensaio/folha de dados; nada é atribuído automaticamente. A única estimativa opcional é Se' = 0,5·Su
    (regra empírica para aços, Su ≤ 1400 MPa), que fica marcada como "estimativa" no resultado.
  * Coeficientes de Marin e a aproximação S-N seguem R. Budynas & J. Nisbett, "Shigley's Mechanical Engineering Design"
    (cap. 6 e 10); são valores de livro-texto para aço — confira se valem para o seu material e processo.
  * Dano acumulado: regra linear de Palmgren-Miner (sem efeito de sequência; ciclos abaixo do limite de fadiga contam zero).
Unidades: N, mm, MPa (N/mm²), N·mm.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

# --------------------------------------------------------------------------------------------- fatores de Marin (Shigley)
SURFACES = {                                    # ka = a·Su^b (Su em MPa)
    "Retificado": (1.58, -0.085),
    "Usinado ou laminado a frio": (4.51, -0.265),
    "Laminado a quente": (57.7, -0.718),
    "Forjado (bruto)": (272.0, -0.995),
}
RELIABILITY = {50.0: 1.000, 90.0: 0.897, 95.0: 0.868, 99.0: 0.814, 99.9: 0.753, 99.99: 0.702, 99.999: 0.659, 99.9999: 0.620}
LOAD_KC = {"Flexão": 1.0, "Axial": 0.85, "Torção": 0.59, "Combinado": 1.0}
CRITERIA = ("Goodman", "Gerber", "Soderberg", "ASME-elíptico")
LIFE_RULES = ("Goodman", "Gerber", "SWT")


def surface_factor(surface: str, su: float) -> float:
    a, b = SURFACES[surface]
    return a * su ** b


def size_factor(d_eq: float, axial: bool = False) -> float:
    """kb para flexão/torção rotativa (d em mm); carga axial pura → 1."""
    if axial or d_eq <= 0:
        return 1.0
    if d_eq < 2.79:
        return 1.0
    if d_eq <= 51.0:
        return 1.24 * d_eq ** -0.107
    return 1.51 * d_eq ** -0.157                    # 51–254 mm (acima disso é extrapolação; ver `warnings`)


def reliability_factor(percent: float) -> float:
    keys = sorted(RELIABILITY)
    if percent in RELIABILITY:
        return RELIABILITY[percent]
    if percent < keys[0] or percent > keys[-1]:
        raise ValueError("Confiabilidade fora de 50 … 99,9999 %")
    for lo, hi in zip(keys, keys[1:]):                # interpolação linear entre os valores tabelados (aproximação)
        if lo <= percent <= hi:
            return RELIABILITY[lo] + (RELIABILITY[hi] - RELIABILITY[lo]) * (percent - lo) / (hi - lo)
    raise ValueError("Confiabilidade inválida")


def fatigue_fraction(su: float) -> float:
    """f da curva S-N (σ a 10³ ciclos = f·Su). Aproximação da Fig. 6-18 do Shigley: 0,90 até 490 MPa, 0,77 a 1380 MPa."""
    if su <= 490.0:
        return 0.90
    if su >= 1380.0:
        return 0.77
    return 0.90 + (0.77 - 0.90) * (su - 490.0) / (1380.0 - 490.0)


# --------------------------------------------------------------------------------------------- material
@dataclass
class FatigueMaterial:
    name: str
    su: float                                    # resistência à tração (MPa), digitada
    sy: float                                    # escoamento (MPa), digitado
    se_prime: Optional[float] = None             # limite de fadiga de corpo de prova (MPa); None → estimar (steel) se permitido
    estimate_se: bool = False                    # permitir Se' = 0,5·Su (aço)
    has_knee: bool = True                        # aço: limite de fadiga em Nk; não ferrosos: False (sem limite → vida finita sempre)
    nk: float = 1.0e6                            # ciclos em que Se' vale (aço 1e6; não ferrosos tipicamente 5e8)
    f: Optional[float] = None                    # None → fatigue_fraction(Su)

    def resolved_se_prime(self) -> tuple[float, bool]:
        if self.se_prime is not None and self.se_prime > 0:
            return float(self.se_prime), False
        if self.estimate_se:
            return (0.5 * self.su if self.su <= 1400.0 else 700.0), True
        raise ValueError("Informe o limite de fadiga Se' do material ou marque a estimativa 0,5·Su (só para aço).")

    def validate(self) -> None:
        if self.su <= 0 or self.sy <= 0:
            raise ValueError("Su e Sy devem ser positivos (digite os valores da folha de dados do material).")
        if self.sy > self.su:
            raise ValueError("Sy não pode ser maior que Su.")
        if self.nk <= 1e3:
            raise ValueError("Nk deve ser maior que 10³.")


@dataclass
class MarinInputs:
    surface: str = "Usinado ou laminado a frio"
    d_eq: float = 0.0                            # diâmetro equivalente (mm) p/ kb (0 → kb = 1)
    load_type: str = "Combinado"                 # define kc
    temp_factor: float = 1.0                     # kd (do usuário)
    reliability_pct: float = 99.0
    misc_factor: float = 1.0                     # kf (corrosão, tensões residuais… do usuário)
    override_ka: Optional[float] = None


def endurance_limit(mat: FatigueMaterial, mar: MarinInputs) -> dict:
    """Se = ka·kb·kc·kd·ke·kf·Se' com todos os fatores devolvidos."""
    mat.validate()
    sep, estimated = mat.resolved_se_prime()
    ka = mar.override_ka if mar.override_ka else surface_factor(mar.surface, mat.su)
    kb = size_factor(mar.d_eq, axial=(mar.load_type == "Axial"))
    kc = LOAD_KC[mar.load_type]
    kd, ke, kf = mar.temp_factor, reliability_factor(mar.reliability_pct), mar.misc_factor
    warnings = []
    if mar.d_eq > 254:
        warnings.append("Diâmetro acima de 254 mm: kb extrapolado.")
    if mar.d_eq and mar.d_eq < 2.79:
        warnings.append("Diâmetro abaixo de 2,79 mm: kb = 1.")
    if estimated:
        warnings.append("Se' ESTIMADO (0,5·Su, regra empírica para aço) — prefira dado de ensaio.")
    if mar.load_type == "Axial":
        warnings.append("Carga axial: kc=0,85; a amplitude axial é dividida por 0,85 só no modo combinado (ver cálculo de tensões).")
    se = ka * kb * kc * kd * ke * kf * sep
    return {"se": se, "se_prime": sep, "estimated": estimated, "ka": ka, "kb": kb, "kc": kc, "kd": kd, "ke": ke, "kf": kf,
            "warnings": warnings}


# --------------------------------------------------------------------------------------------- seção e tensões nominais
@dataclass
class Section:
    kind: str = "Círculo cheio"                  # Círculo cheio | Tubo | Retângulo | Personalizada
    d: float = 0.0                               # círculo (mm) ou diâmetro externo do tubo
    di: float = 0.0                              # diâmetro interno do tubo
    b: float = 0.0                               # retângulo: largura (eixo neutro paralelo a b)
    h: float = 0.0                               # retângulo: altura (direção da flexão)
    A: float = 0.0                               # personalizada
    I: float = 0.0
    c: float = 0.0
    J: float = 0.0
    r: float = 0.0                               # raio para torção

    def props(self) -> dict:
        if self.kind == "Círculo cheio":
            d = self.d
            return {"A": math.pi * d * d / 4, "I": math.pi * d ** 4 / 64, "c": d / 2, "J": math.pi * d ** 4 / 32, "r": d / 2}
        if self.kind == "Tubo":
            do, di = self.d, self.di
            if not 0 <= di < do:
                raise ValueError("Tubo: 0 ≤ di < d externo.")
            return {"A": math.pi * (do ** 2 - di ** 2) / 4, "I": math.pi * (do ** 4 - di ** 4) / 64, "c": do / 2,
                    "J": math.pi * (do ** 4 - di ** 4) / 32, "r": do / 2}
        if self.kind == "Retângulo":
            return {"A": self.b * self.h, "I": self.b * self.h ** 3 / 12, "c": self.h / 2, "J": 0.0, "r": 0.0}
        return {"A": self.A, "I": self.I, "c": self.c, "J": self.J, "r": self.r}


@dataclass
class LoadRange:
    """Faixa (mín, máx) de um esforço ao longo do ciclo: força axial (N), momento fletor (N·mm), torque (N·mm)."""
    axial: tuple[float, float] = (0.0, 0.0)
    bending: tuple[float, float] = (0.0, 0.0)
    torsion: tuple[float, float] = (0.0, 0.0)


@dataclass
class Concentration:
    """Kf = 1 + q·(Kt − 1) por tipo de esforço; ``kf_override`` (se dado) vale direto."""
    kt_axial: float = 1.0
    kt_bending: float = 1.0
    kt_torsion: float = 1.0
    q_axial: float = 1.0
    q_bending: float = 1.0
    q_torsion: float = 1.0
    kf_axial: Optional[float] = None
    kf_bending: Optional[float] = None
    kf_torsion: Optional[float] = None

    def kf(self, kind: str) -> float:
        ov = getattr(self, f"kf_{kind}")
        if ov is not None:
            return float(ov)
        kt, q = getattr(self, f"kt_{kind}"), getattr(self, f"q_{kind}")
        if not 0.0 <= q <= 1.0:
            raise ValueError("Sensibilidade ao entalhe q deve estar entre 0 e 1.")
        if kt < 1.0:
            raise ValueError("Kt deve ser ≥ 1.")
        return 1.0 + q * (kt - 1.0)


def _mean_alt(rng: tuple[float, float]) -> tuple[float, float]:
    lo, hi = rng
    return (hi + lo) / 2.0, abs(hi - lo) / 2.0


def nominal_stresses(sec: Section, load: LoadRange, kc: Concentration, combined_axial_factor: bool = True) -> dict:
    """Tensões equivalentes de von Mises (média e alternada), com Kf aplicado (Shigley, eqs. 6-55/6-56)."""
    p = sec.props()
    out = {"props": p, "warnings": []}
    parts = {}
    for kind, rng, area_fn in (("axial", load.axial, lambda x: x / p["A"] if p["A"] else _bad("A")),
                               ("bending", load.bending, lambda x: x * p["c"] / p["I"] if p["I"] else _bad("I")),
                               ("torsion", load.torsion, lambda x: x * p["r"] / p["J"] if p["J"] else _bad("J"))):
        m, a = _mean_alt(rng)
        if m == 0 and a == 0:
            parts[kind] = (0.0, 0.0)
            continue
        parts[kind] = (area_fn(m), area_fn(a))                      # (σm, σa) nominais
    kfa, kfb, kft = kc.kf("axial"), kc.kf("bending"), kc.kf("torsion")
    ax_div = 0.85 if combined_axial_factor else 1.0
    sa = (kfb * parts["bending"][1] + kfa * parts["axial"][1] / ax_div, kft * parts["torsion"][1])
    sm = (kfb * parts["bending"][0] + kfa * parts["axial"][0], kft * parts["torsion"][0])
    out["sigma_a"] = math.sqrt(sa[0] ** 2 + 3 * sa[1] ** 2)
    out["sigma_m"] = math.sqrt(sm[0] ** 2 + 3 * sm[1] ** 2)
    out["sigma_max"] = out["sigma_a"] + out["sigma_m"]
    out["nominal"] = parts
    out["kf"] = {"axial": kfa, "bending": kfb, "torsion": kft}
    if any(v[0] < 0 for v in parts.values()):
        out["warnings"].append("Tensão média de compressão: von Mises perde o sinal → tratada como tração (conservador).")
    out["warnings"].append("Kf também aplicado à tensão média (conservador).")
    return out


def _bad(name: str):
    raise ValueError(f"Propriedade de seção '{name}' é zero: defina a geometria da seção para esse esforço.")


# --------------------------------------------------------------------------------------------- critérios e vida
def safety_factors(sa: float, sm: float, se: float, su: float, sy: float) -> dict:
    """Coeficientes de segurança sobre linha de carga proporcional (σa/σm constante) e escoamento no 1º ciclo (Langer)."""
    if sa < 0 or sm < 0:
        raise ValueError("σa e σm equivalentes devem ser ≥ 0.")
    out = {}
    if sa == 0 and sm == 0:
        return {k: math.inf for k in (*CRITERIA, "Escoamento (Langer)")}
    out["Goodman"] = 1.0 / (sa / se + sm / su)
    out["Soderberg"] = 1.0 / (sa / se + sm / sy)
    out["ASME-elíptico"] = 1.0 / math.sqrt((sa / se) ** 2 + (sm / sy) ** 2)
    if sm == 0:
        out["Gerber"] = se / sa
    elif sa == 0:
        out["Gerber"] = su / sm
    else:
        out["Gerber"] = 0.5 * (su / sm) ** 2 * (sa / se) * (-1.0 + math.sqrt(1.0 + (2.0 * sm * se / (su * sa)) ** 2))
    out["Escoamento (Langer)"] = sy / (sa + sm)
    return out


def equivalent_reversed(sa: float, sm: float, su: float, rule: str = "Goodman") -> float:
    """σ alternada totalmente reversa equivalente (para entrar na curva S-N). ``inf`` se a média já rompe (σm ≥ Su)."""
    if rule == "Goodman":
        return math.inf if sm >= su else sa / (1.0 - sm / su)
    if rule == "Gerber":
        return math.inf if sm >= su else sa / (1.0 - (sm / su) ** 2)
    if rule == "SWT":
        return math.sqrt((sa + sm) * sa)
    raise ValueError(f"Regra desconhecida: {rule}")


@dataclass
class SNCurve:
    a: float
    b: float
    se: float
    sf1e3: float
    nk: float
    has_knee: bool

    def stress_at(self, n: float) -> float:
        return self.a * n ** self.b

    def life(self, sigma_ar: float) -> float:
        """Ciclos até a falha para σ alternada reversa ``sigma_ar``; ``inf`` abaixo do limite de fadiga (se houver)."""
        if sigma_ar <= 0:
            return math.inf
        if math.isinf(sigma_ar):
            return 0.0
        if self.has_knee and sigma_ar <= self.se:
            return math.inf
        return (sigma_ar / self.a) ** (1.0 / self.b)


def build_sn(mat: FatigueMaterial, se: float) -> SNCurve:
    f = mat.f if mat.f else fatigue_fraction(mat.su)
    sf = f * mat.su
    if se >= sf:
        raise ValueError("Se corrigido ≥ f·Su: a curva S-N degenera (confira Se', fatores de Marin e f).")
    b = -math.log10(sf / se) / (math.log10(mat.nk) - 3.0)
    a = sf / 1.0e3 ** b
    return SNCurve(a=a, b=b, se=se, sf1e3=sf, nk=mat.nk, has_knee=mat.has_knee)


@dataclass
class FatigueResult:
    se: dict
    stress: dict
    factors: dict
    sigma_ar: float
    curve: SNCurve
    cycles: float
    infinite: bool
    low_cycle: bool
    warnings: list[str] = field(default_factory=list)

    def summary(self, criterion: str = "Goodman") -> str:
        n = self.factors.get(criterion)
        life = "vida infinita (σ equivalente ≤ Se)" if self.infinite else f"{self.cycles:,.0f} ciclos".replace(",", ".")
        return (f"σa' = {self.stress['sigma_a']:.1f} MPa · σm' = {self.stress['sigma_m']:.1f} MPa · Se = {self.se['se']:.1f} MPa · "
                f"n({criterion}) = {n:.2f} · σ_ar = {self.sigma_ar:.1f} MPa → {life}")


def analyze(mat: FatigueMaterial, mar: MarinInputs, sec: Section, load: LoadRange, conc: Concentration,
            life_rule: str = "Goodman") -> FatigueResult:
    se = endurance_limit(mat, mar)
    comb = mar.load_type == "Combinado"
    st = nominal_stresses(sec, load, conc, combined_axial_factor=comb)
    fac = safety_factors(st["sigma_a"], st["sigma_m"], se["se"], mat.su, mat.sy)
    curve = build_sn(mat, se["se"])
    sar = equivalent_reversed(st["sigma_a"], st["sigma_m"], mat.su, life_rule)
    cyc = curve.life(sar)
    warns = list(se["warnings"]) + list(st["warnings"])
    low = (not math.isinf(sar)) and sar > curve.sf1e3
    if low:
        warns.append("σ equivalente acima de f·Su: fadiga de baixo ciclo (< 10³) — fora da validade do método de tensões nominais.")
    if st["sigma_max"] > mat.sy:
        warns.append("σmax acima de Sy: escoamento local no 1º ciclo — o método elástico não vale (use deformação-vida).")
    if not mat.has_knee:
        warns.append("Material sem limite de fadiga: sempre há vida finita (a curva é extrapolada além de Nk).")
    return FatigueResult(se, st, fac, sar, curve, cyc, math.isinf(cyc), low, warns)


# --------------------------------------------------------------------------------------------- dano acumulado (Miner)
@dataclass
class Block:
    label: str
    sigma_a: float                               # equivalente de von Mises, MPa
    sigma_m: float
    cycles: float                                # ciclos por repetição do espectro


def miner(blocks: list[Block], mat: FatigueMaterial, curve: SNCurve, rule: str = "Goodman") -> dict:
    """Dano por repetição do espectro e vida em repetições. Ciclos com σ_ar ≤ Se não contam (não conservador)."""
    rows, damage = [], 0.0
    for b in blocks:
        if b.cycles < 0:
            raise ValueError("Número de ciclos negativo.")
        n = curve.life(equivalent_reversed(b.sigma_a, b.sigma_m, mat.su, rule))
        d = 0.0 if math.isinf(n) else (math.inf if n == 0 else b.cycles / n)
        rows.append({"label": b.label, "N": n, "damage": d, "sigma_ar": equivalent_reversed(b.sigma_a, b.sigma_m, mat.su, rule)})
        damage += d
    reps = math.inf if damage == 0 else 1.0 / damage
    total_cycles = sum(b.cycles for b in blocks)
    return {"rows": rows, "damage": damage, "repetitions": reps, "cycles_to_failure": reps * total_cycles,
            "notes": ["Regra linear de Miner (D = Σ n/N): sem efeito de sequência de cargas.",
                      "Ciclos abaixo do limite de fadiga têm dano zero (pode ser não conservador)."]}


def life_hours(cycles: float, frequency_hz: float) -> float:
    if frequency_hz <= 0:
        raise ValueError("Frequência deve ser positiva.")
    return cycles / frequency_hz / 3600.0


def sn_points(curve: SNCurve, n_lo: float = 1e3, n_hi: float = 1e8, count: int = 60) -> list[tuple[float, float]]:
    """Pontos (N, σ) da curva S-N para o gráfico; abaixo do joelho segue Basquin, depois patamar em Se (se houver)."""
    pts = []
    for i in range(count):
        n = 10 ** (math.log10(n_lo) + (math.log10(n_hi) - math.log10(n_lo)) * i / (count - 1))
        s = curve.stress_at(n)
        if curve.has_knee and n >= curve.nk:
            s = curve.se
        pts.append((n, s))
    return pts


# --------------------------------------------------------------------------------------------- molas helicoidais
@dataclass
class SpringInputs:
    wire_d: float                                # d (mm)
    coil_d: float                                # D médio (mm)
    active_coils: float                          # Na
    total_coils: float                           # Nt (para a altura sólida: Nt·d)
    installed_len: float                         # comprimento com a válvula fechada (mm)
    lift: float                                  # curso máximo da válvula (mm)
    preload_force: float                         # força com a válvula fechada (N), do usuário
    g_mpa: float                                 # módulo de cisalhamento do fio (MPa), do usuário
    density_g_cm3: float                         # do banco de materiais (escolha do usuário)
    su: float                                    # Su do fio (MPa), do usuário
    sse: float                                   # limite de fadiga em cisalhamento (MPa), do usuário (dado de ensaio/norma)
    ssu: Optional[float] = None                  # None → 0,67·Su (Shigley)


def spring_analysis(s: SpringInputs) -> dict:
    """Taxa, força, tensão de cisalhamento e coeficiente de segurança (Goodman em cisalhamento) + altura sólida e surto."""
    for name in ("wire_d", "coil_d", "active_coils", "total_coils", "g_mpa", "su", "sse", "density_g_cm3"):
        if getattr(s, name) <= 0:
            raise ValueError(f"Mola: '{name}' deve ser positivo.")
    c = s.coil_d / s.wire_d
    if c < 4 or c > 12:
        warn_c = [f"Índice de mola C = {c:.1f} fora de 4 … 12: fórmulas menos confiáveis."]
    else:
        warn_c = []
    k = s.g_mpa * s.wire_d ** 4 / (8.0 * s.coil_d ** 3 * s.active_coils)                    # N/mm
    f_min = s.preload_force
    f_max = f_min + k * s.lift
    ks = 1.0 + 0.5 / c
    kb = (4 * c + 2) / (4 * c - 3)
    cst = 8.0 * s.coil_d / (math.pi * s.wire_d ** 3)
    fa, fm = (f_max - f_min) / 2, (f_max + f_min) / 2
    tau_a, tau_m = kb * cst * fa, ks * cst * fm
    ssu = s.ssu if s.ssu else 0.67 * s.su
    n_f = 1.0 / (tau_a / s.sse + tau_m / ssu) if (tau_a or tau_m) else math.inf
    solid = s.total_coils * s.wire_d
    min_len = s.installed_len - s.lift
    clash = min_len - solid
    mass_kg = s.density_g_cm3 * 1e-3 * (math.pi * s.wire_d ** 2 / 4) * (math.pi * s.coil_d * s.total_coils) * 1e-3
    # frequência natural (surto), extremos fixos: fn = (d / (2π·D²·Na))·sqrt(G / (2ρ))  [mm, MPa, kg/mm³ → Hz]
    rho = s.density_g_cm3 * 1e-6                                                             # kg/mm³
    fn = (s.wire_d / (2 * math.pi * s.coil_d ** 2 * s.active_coils)) * math.sqrt(s.g_mpa * 1e6 / (2 * rho * 1e9)) * 1e3
    return {"C": c, "k": k, "f_min": f_min, "f_max": f_max, "tau_a": tau_a, "tau_m": tau_m, "n_f": n_f, "ssu": ssu,
            "solid_len": solid, "min_len": min_len, "clearance_to_solid": clash, "mass_kg": mass_kg, "fn_hz": fn,
            "max_rpm_13x": fn / 13.0 * 2.0 * 60.0, "warnings": warn_c + (["Mola chega à altura sólida!"] if clash <= 0 else [])}
