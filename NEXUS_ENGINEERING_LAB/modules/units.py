"""Sistema de unidades e rastreabilidade de origem (V2.5; PROMPT MASTER §2).

SI como base (m, kg, s, N, J, W, Pa, K, m³, kg/m³). Fatores exatos por definição quando existem (pol = 0,0254 m; lb = 0,45359237 kg; atm = 101325 Pa…).
``Quantity`` carrega o valor, a unidade e a ORIGEM do dado (documentado, medido, calculado, estimado, simulado, experimental ou não informado), com os
rótulos do PROMPT MASTER, para que resultados aproximados não sejam apresentados como medições.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass

# dimensão -> {unidade: (fator p/ base, deslocamento)}   valor_base = valor·fator + deslocamento
TABLE: dict[str, dict[str, tuple[float, float]]] = {
    "comprimento": {"m": (1.0, 0), "mm": (1e-3, 0), "cm": (1e-2, 0), "km": (1e3, 0), "in": (0.0254, 0), "ft": (0.3048, 0), "mi": (1609.344, 0)},
    "massa": {"kg": (1.0, 0), "g": (1e-3, 0), "t": (1e3, 0), "lb": (0.45359237, 0), "oz": (0.028349523125, 0)},
    "força": {"N": (1.0, 0), "kN": (1e3, 0), "kgf": (9.80665, 0), "lbf": (4.4482216152605, 0)},
    "pressão": {"Pa": (1.0, 0), "kPa": (1e3, 0), "MPa": (1e6, 0), "GPa": (1e9, 0), "bar": (1e5, 0), "atm": (101325.0, 0), "psi": (6894.757293168361, 0), "mmHg": (133.322387415, 0)},
    "energia": {"J": (1.0, 0), "kJ": (1e3, 0), "MJ": (1e6, 0), "kWh": (3.6e6, 0), "cal": (4.184, 0), "kcal": (4184.0, 0), "BTU": (1055.05585262, 0), "ft·lbf": (1.3558179483314004, 0)},
    "potência": {"W": (1.0, 0), "kW": (1e3, 0), "MW": (1e6, 0), "hp": (745.6998715822702, 0), "cv": (735.49875, 0)},
    "torque": {"N·m": (1.0, 0), "N·mm": (1e-3, 0), "kN·m": (1e3, 0), "kgf·m": (9.80665, 0), "lbf·ft": (1.3558179483314004, 0)},
    "velocidade": {"m/s": (1.0, 0), "km/h": (1 / 3.6, 0), "mph": (0.44704, 0), "kn": (1852 / 3600, 0), "ft/s": (0.3048, 0)},
    "aceleração": {"m/s²": (1.0, 0), "gn": (9.80665, 0), "ft/s²": (0.3048, 0)},
    "área": {"m²": (1.0, 0), "cm²": (1e-4, 0), "mm²": (1e-6, 0), "in²": (6.4516e-4, 0), "ft²": (0.09290304, 0)},
    "volume": {"m³": (1.0, 0), "L": (1e-3, 0), "mL": (1e-6, 0), "cm³": (1e-6, 0), "mm³": (1e-9, 0), "in³": (1.6387064e-5, 0), "gal(US)": (3.785411784e-3, 0)},
    "densidade": {"kg/m³": (1.0, 0), "g/cm³": (1e3, 0), "t/m³": (1e3, 0), "lb/ft³": (16.01846337396014, 0), "t/mm³": (1e12, 0)},
    "temperatura": {"K": (1.0, 0), "°C": (1.0, 273.15), "°F": (5 / 9, 459.67 * 5 / 9)},
    "ângulo": {"rad": (1.0, 0), "°": (math.pi / 180, 0), "rev": (2 * math.pi, 0), "mrad": (1e-3, 0)},
    "vel. angular": {"rad/s": (1.0, 0), "rpm": (2 * math.pi / 60, 0), "Hz": (2 * math.pi, 0), "°/s": (math.pi / 180, 0)},
    "viscosidade": {"Pa·s": (1.0, 0), "mPa·s": (1e-3, 0), "cP": (1e-3, 0), "poise": (0.1, 0)},
}


class UnitError(ValueError):
    pass


def dimension_of(unit: str) -> str:
    for d, units in TABLE.items():
        if unit in units:
            return d
    raise UnitError(f"Unidade desconhecida: '{unit}'")


def convert(value: float, src: str, dst: str) -> float:
    ds, dd = dimension_of(src), dimension_of(dst)
    if ds != dd:
        raise UnitError(f"Dimensões incompatíveis: {src} ({ds}) → {dst} ({dd})")
    fs, os_ = TABLE[ds][src]
    fd, od = TABLE[ds][dst]
    return ((value * fs + os_) - od) / fd


def export_table() -> str:
    return json.dumps({d: {u: list(v) for u, v in us.items()} for d, us in TABLE.items()}, ensure_ascii=False, separators=(",", ":"))


ORIGINS = {
    "documentado": "VALOR DOCUMENTADO", "medido": "VALOR MEDIDO", "calculado": "VALOR CALCULADO", "estimado": "VALOR ESTIMADO",
    "simulado": "RESULTADO SIMULADO", "experimental": "VALOR EXPERIMENTAL", "nao_informado": "PROPRIEDADE NÃO INFORMADA",
}


@dataclass(frozen=True)
class Quantity:
    value: float | None
    unit: str
    origin: str = "nao_informado"
    source: str = ""            # referência (norma, catálogo, ensaio, solver+versão…)

    def __post_init__(self):
        if self.origin not in ORIGINS:
            raise UnitError(f"Origem inválida '{self.origin}'. Use: {', '.join(ORIGINS)}")
        if self.value is None and self.origin != "nao_informado":
            raise UnitError("Valor ausente só é permitido com origem 'nao_informado' (não invente valores).")
        dimension_of(self.unit)

    def to(self, unit: str) -> "Quantity":
        if self.value is None:
            return Quantity(None, unit, self.origin, self.source)
        return Quantity(convert(self.value, self.unit, unit), unit, self.origin, self.source)

    @property
    def label(self) -> str:
        return ORIGINS[self.origin]

    def __str__(self) -> str:
        if self.value is None:
            return ORIGINS["nao_informado"]
        ref = f", {self.source}" if self.source else ""
        return f"{self.value:.6g} {self.unit} [{self.label}{ref}]"
