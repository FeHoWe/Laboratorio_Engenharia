"""Sistema de regulamento técnico por temporada.

Cada temporada é um arquivo JSON independente (data/seasons/<id>.json). Novas
temporadas são criadas como NOVOS arquivos (``create_season``) sem alterar as
anteriores. Cada parâmetro carrega ``status`` e ``src``:

- regulation_reference : valor do regulamento FIA conforme conhecimento do autor; conferir no PDF.
- estimate             : parâmetro de engenharia do simulador (NÃO é dado oficial).
- unconfirmed          : sem especificação confirmada (v = null) -> a regra não é aplicada.
"""
from __future__ import annotations

import copy
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_PKG_DIR = Path(__file__).resolve().parent.parent
BUILTIN_DIR = _PKG_DIR / "data" / "seasons"
USER_DIR = Path(os.environ.get("NEXUS_F1_USER_DIR", Path.home() / ".nexus_f1")) / "seasons"


class RegulationError(Exception):
    """Configuração incompatível com o regulamento no modo regulamentar."""

    def __init__(self, violations: list["Violation"]):
        self.violations = violations
        super().__init__("; ".join(v.message for v in violations if v.severity == "error"))


@dataclass
class Violation:
    param: str
    message: str
    severity: str = "error"  # error | warning
    value: Any = None
    limit: Any = None
    status: str = ""  # status do limite (regulation_reference/estimate)


@dataclass
class Season:
    id: str
    name: str
    notes: str
    official_document: str
    params: dict[str, dict]
    compounds: dict
    path: Path | None = None

    def value(self, key: str, default=None):
        p = self.params.get(key)
        if not p or p.get("v") is None:
            return default
        return p["v"]

    def status(self, key: str) -> str:
        p = self.params.get(key)
        return p.get("status", "unconfirmed") if p else "unconfirmed"

    def source(self, key: str) -> str:
        p = self.params.get(key)
        return p.get("src", "") if p else ""

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "notes": self.notes,
                "official_document": self.official_document,
                "params": self.params, "compounds": self.compounds}


def _load(path: Path) -> Season:
    d = json.loads(path.read_text(encoding="utf-8"))
    return Season(d["id"], d["name"], d.get("notes", ""), d.get("official_document", ""),
                  d["params"], d["compounds"], path)


def list_seasons() -> dict[str, Season]:
    out: dict[str, Season] = {}
    for folder in (BUILTIN_DIR, USER_DIR):
        if folder.exists():
            for p in sorted(folder.glob("*.json")):
                try:
                    s = _load(p)
                    out[s.id] = s
                except Exception:  # arquivo inválido não derruba o app
                    continue
    return out


def get_season(season_id: str) -> Season:
    seasons = list_seasons()
    if season_id not in seasons:
        raise KeyError(f"Temporada '{season_id}' não encontrada. Disponíveis: {sorted(seasons)}")
    return seasons[season_id]


def create_season(new_id: str, base_id: str | None = None, overrides: dict | None = None,
                  name: str | None = None) -> Season:
    """Cria uma NOVA temporada (arquivo próprio) a partir de outra, sem tocar nas existentes."""
    seasons = list_seasons()
    if new_id in seasons:
        raise ValueError(f"A temporada '{new_id}' já existe; as existentes nunca são sobrescritas.")
    base = seasons[base_id] if base_id else next(iter(seasons.values()))
    d = copy.deepcopy(base.to_dict())
    d["id"] = new_id
    d["name"] = name or f"Temporada {new_id} (derivada de {base.id})"
    d["notes"] = f"Derivada de {base.id}. Revise todos os valores contra o regulamento oficial de {new_id}."
    for k, v in (overrides or {}).items():
        d["params"].setdefault(k, {"src": "definido pelo usuário"})
        d["params"][k]["v"] = v
        d["params"][k]["status"] = "estimate"
        d["params"][k]["src"] = "definido pelo usuário (não verificado)"
    USER_DIR.mkdir(parents=True, exist_ok=True)
    path = USER_DIR / f"{new_id}.json"
    path.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    return _load(path)


def validate(cfg, season: Season) -> list[Violation]:
    """Compara a configuração do carro com os limites da temporada."""
    v: list[Violation] = []

    def err(param, msg, value, key, severity="error"):
        v.append(Violation(param, msg, severity, value, season.value(key), season.status(key)))

    if cfg.season != season.id:
        v.append(Violation("season", f"Configuração pertence à temporada {cfg.season}, não {season.id}.",
                           "error", cfg.season, season.id, ""))
    m = season.value("min_mass_kg")
    if m is not None and cfg.mass_kg < m:
        err("mass_kg", f"Massa {cfg.mass_kg:.1f} kg abaixo do mínimo ({m} kg, sem combustível).", cfg.mass_kg, "min_mass_kg")
    r = season.value("max_rpm")
    if r is not None and cfg.redline_rpm > r:
        err("redline_rpm", f"Rotação máx. {cfg.redline_rpm:.0f} rpm acima do limite ({r} rpm).", cfg.redline_rpm, "max_rpm")
    g = season.value("max_gears")
    if g is not None and len(cfg.gear_ratios) > g:
        err("gear_ratios", f"{len(cfg.gear_ratios)} marchas; máximo {g}.", len(cfg.gear_ratios), "max_gears")
    k = season.value("mguk_max_kw")
    if k is not None and cfg.mguk_kw > k:
        err("mguk_kw", f"MGU-K {cfg.mguk_kw:.0f} kW acima do limite ({k} kW).", cfg.mguk_kw, "mguk_max_kw")
    h = season.value("ers_harvest_cap_mj")
    if h is not None and cfg.harvest_cap_mj > h:
        err("harvest_cap_mj", f"Recuperação {cfg.harvest_cap_mj} MJ/volta acima do limite ({h}).", cfg.harvest_cap_mj, "ers_harvest_cap_mj")
    d = season.value("ers_deploy_cap_mj")
    if d is not None and cfg.deploy_cap_mj > d:
        err("deploy_cap_mj", f"Entrega {cfg.deploy_cap_mj} MJ/volta acima do limite ({d}).", cfg.deploy_cap_mj, "ers_deploy_cap_mj")
    f = season.value("max_fuel_kg")
    if f is not None and cfg.fuel_start_kg > f:
        err("fuel_start_kg", f"Combustível {cfg.fuel_start_kg} kg acima do máximo ({f}).", cfg.fuel_start_kg, "max_fuel_kg")
    p = season.value("ice_pmax_kw_limit")
    if p is not None and cfg.ice_pmax_kw > p:
        err("ice_pmax_kw", f"Potência do motor {cfg.ice_pmax_kw:.0f} kW acima do teto plausível ({p} kW, estimado).",
            cfg.ice_pmax_kw, "ice_pmax_kw_limit", severity="warning")
    cda = season.value("aero_cda_range")
    if cda and not (cda[0] <= cfg.cda <= cda[1]):
        err("cda", f"Cd*A {cfg.cda:.2f} fora da faixa plausível {cda} (estimada; a FIA regula geometria).",
            cfg.cda, "aero_cda_range", severity="warning")
    cla = season.value("aero_cla_range")
    if cla and not (cla[0] <= cfg.cla <= cla[1]):
        err("cla", f"Cl*A {cfg.cla:.2f} fora da faixa plausível {cla} (estimada).",
            cfg.cla, "aero_cla_range", severity="warning")
    allowed = season.compounds.get("allowed", [])
    if cfg.compound not in allowed:
        v.append(Violation("compound", f"Composto '{cfg.compound}' não permitido em {season.id}: {allowed}.",
                           "error", cfg.compound, allowed, season.compounds.get("status", "")))
    return v


def check_regulatory(cfg, season: Season) -> list[Violation]:
    """Levanta RegulationError se houver erros (modo regulamentar)."""
    viol = validate(cfg, season)
    if any(x.severity == "error" for x in viol):
        raise RegulationError(viol)
    return viol
