"""Checagem de conformidade GEOMÉTRICA com limites do regulamento técnico de F1 (V2.8).

NÃO é homologação nem substitui a FIA/o scrutineering: só compara medidas do modelo/ do usuário com um conjunto PEQUENO de limites que
foram lidos em fontes públicas. Cada regra traz fonte e se foi VERIFICADA. Regras sem medida automática ficam "SEM_MEDIDA" (digite o valor).
Fonte principal: FIA 2027 F1 Regulations, Seção C (Técnica), emissão 04 (19/10/2026) — trecho C2/C3 lido; demais artigos NÃO lidos.
"""
from __future__ import annotations

from dataclasses import dataclass

EXEMPT_PREFIX = ("Pneu", "Roda", "Disco de freio", "Cubo", "Porca central", "Pinca", "Manga")      # ligados às rodas (C2.3.1 isenta pneus/rodas)

# (id, título, campo medido, operador, limite, anos, fonte, verificada)
RULES = [
    ("C2.3.1", "Meia-largura máxima (peças fora pneus/rodas)", "half_width_mm", "<=", 950.0, ("2026", "2027"), "FIA 2027 C2.3.1 (950 mm de Y=0); 2026: largura 1900 mm", True),
    ("C2.3.3", "Entre-eixos (XF=0 a XR=0)", "wheelbase_mm", "<=", 3400.0, ("2026", "2027"), "FIA 2027 C2.3.3", True),
    ("C2.3.5a", "Distância XA–XC (cockpit) mínima", "xa_xc_mm", ">=", 1830.0, ("2027",), "FIA 2027 C2.3.5", True),
    ("C2.3.5b", "Distância XA–XC (cockpit) máxima", "xa_xc_mm", "<=", 2030.0, ("2027",), "FIA 2027 C2.3.5", True),
    ("C2.3.6", "Antepara traseira XC–XPU mínima", "xc_xpu_mm", ">=", 360.0, ("2027",), "FIA 2027 C2.3.6", True),
    ("C3.6.1a", "Espessura da prancha (nominal 10 mm ±0,2)", "plank_mm", ">=", 9.8, ("2027",), "FIA 2027 C3.6.1", True),
    ("C3.6.1b", "Espessura da prancha (nominal 10 mm ±0,2)", "plank_mm", "<=", 10.2, ("2027",), "FIA 2027 C3.6.1", True),
    ("C3.10.1k-min", "Folga entre perfis da asa dianteira (mín.)", "front_gap_min_mm", ">=", 5.0, ("2027",), "FIA 2027 C3.10.1(k)", True),
    ("C3.10.1k-max", "Folga entre perfis da asa dianteira (máx.)", "front_gap_max_mm", "<=", 15.0, ("2027",), "FIA 2027 C3.10.1(k)", True),
    ("C3.11.1g-min", "Folga entre perfis da asa traseira (mín.)", "rear_gap_min_mm", ">=", 8.0, ("2027",), "FIA 2027 C3.11.1(g)", True),
    ("C3.11.1g-max", "Folga entre perfis da asa traseira (máx.)", "rear_gap_max_mm", "<=", 12.0, ("2027",), "FIA 2027 C3.11.1(g)", True),
    ("C4-2026", "Massa mínima (sem combustível, com piloto)", "mass_kg", ">=", 768.0, ("2026",), "Regulamento 2026 (valor usado no modelo F1 2026)", True),
    ("C4-2027", "Massa mínima 2027", "mass_kg", ">=", None, ("2027",), "C4 NÃO foi lido: informe o limite no campo 'limite de massa'", False),
    ("PU-ERS", "Implantação elétrica máxima (kW)", "ers_kw", "<=", 300.0, ("2027",), "Comunicado FIA / RaceTeq (maio/2026): 350 → 300 kW; texto C5 não lido", False),
]
FIELDS = sorted({r[2] for r in RULES})


@dataclass
class CheckResult:
    rule: str
    title: str
    field: str
    status: str          # CONFORME | NAO_CONFORME | SEM_MEDIDA | LIMITE_NAO_VERIFICADO
    value: float | None
    limit: float | None
    op: str
    source: str
    verified: bool


def check(season: str, measured: dict, mass_limit: float | None = None) -> list[CheckResult]:
    out = []
    for rid, title, fld, op, lim, years, src, ver in RULES:
        if season not in years:
            continue
        if rid == "C4-2027" and mass_limit is not None:
            lim = mass_limit
        v = measured.get(fld)
        if lim is None:
            st = "LIMITE_NAO_VERIFICADO"
        elif v is None:
            st = "SEM_MEDIDA"
        else:
            ok = v <= lim + 1e-9 if op == "<=" else v >= lim - 1e-9
            st = "CONFORME" if ok else "NAO_CONFORME"
        out.append(CheckResult(rid, title, fld, st, v, lim, op, src, ver))
    return out


def measure_model(parts) -> dict:
    """``parts``: [(nome, (xmin,ymin,zmin), (xmax,ymax,zmax))] em mm, convenção do modelo F1 (x lateral, y longitudinal, z acima)."""
    m: dict = {}
    hw = [max(abs(lo[0]), abs(hi[0])) for n, lo, hi in parts if not n.startswith(EXEMPT_PREFIX) and "Pneu" not in n]
    if hw:
        m["half_width_mm"] = max(hw)
    byname = {n: (lo, hi) for n, lo, hi in parts}
    f, r = byname.get("Pneu dianteira direita"), byname.get("Pneu traseira direita")
    if f and r:
        m["wheelbase_mm"] = abs((r[0][1] + r[1][1]) / 2 - (f[0][1] + f[1][1]) / 2)
    p = byname.get("Prancha de desgaste")
    if p:
        m["plank_mm"] = p[1][2] - p[0][2]
    return m
