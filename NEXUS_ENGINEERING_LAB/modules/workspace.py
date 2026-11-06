"""Projetos do usuário (criar/salvar/reabrir), histórico paramétrico e vitrine do Arsenal.

- Projeto = arquivo JSON versionado (esquema 1) com peças instanciadas do Arsenal/biblioteca.
- Histórico paramétrico: lista ordenada de operações `set_param` com undo/redo; o sólido
  é SEMPRE regenerado pela biblioteca a partir dos parâmetros (receita determinística).
- Rastreia o uso de componentes do Arsenal por projeto (bloqueia exclusão em uso).
"""
from __future__ import annotations
import json, time
from dataclasses import dataclass, field
from pathlib import Path
from .arsenal import Arsenal

SCHEMA = 1
_CATMAP = {"Fixadores": "Componentes mecânicos", "Rolamentos": "Componentes mecânicos", "Transmissão": "Componentes automotivos",
           "Estrutura": "Componentes mecânicos", "Molas": "Componentes automotivos"}


def seed_showcase(arsenal: Arsenal) -> list[str]:
    """Registra as peças paramétricas da biblioteca no Arsenal (idempotente por nome). Sem material atribuído."""
    from samples.library import PARTS
    existing = {c["name"] for c in arsenal.list_components()}
    ids = []
    for p in PARTS.values():
        if p.title in existing:
            continue
        ids.append(arsenal.add_component(p.title, _CATMAP.get(p.category, "Componentes mecânicos"),
                                         {"part_key": p.key, "params": p.defaults(), "material": None},
                                         description=p.note))
    return ids


@dataclass
class PartHistory:
    """Histórico paramétrico com undo/redo para uma peça da biblioteca."""
    part_key: str
    params: dict
    ops: list = field(default_factory=list)
    cursor: int = 0

    @classmethod
    def new(cls, part_key: str, **overrides):
        from samples.library import PARTS
        d = PARTS[part_key].defaults()
        h = cls(part_key, d)
        for k, v in overrides.items():
            h.set_param(k, v)
        return h

    def set_param(self, key: str, value: float):
        from samples.library import PARTS
        pd = PARTS[self.part_key]
        p = next((q for q in pd.params if q.key == key), None)
        if p is None:
            raise KeyError(f"Parâmetro desconhecido '{key}'")
        if not (p.lo <= value <= p.hi):
            raise ValueError(f"{p.label}: {value} fora de [{p.lo:g}, {p.hi:g}] {p.unit}")
        del self.ops[self.cursor:]
        self.ops.append({"key": key, "old": self.params[key], "new": value, "t": time.time()})
        self.params[key] = value; self.cursor += 1

    def undo(self):
        if self.cursor == 0: return False
        self.cursor -= 1; o = self.ops[self.cursor]; self.params[o["key"]] = o["old"]; return True

    def redo(self):
        if self.cursor >= len(self.ops): return False
        o = self.ops[self.cursor]; self.params[o["key"]] = o["new"]; self.cursor += 1; return True

    def build(self):
        from samples.library import PARTS
        return PARTS[self.part_key].make(**self.params)

    def to_dict(self):
        return {"part_key": self.part_key, "params": self.params, "ops": self.ops, "cursor": self.cursor}

    @classmethod
    def from_dict(cls, d):
        return cls(d["part_key"], dict(d["params"]), list(d["ops"]), d["cursor"])


class ProjectStore:
    def __init__(self, folder):
        self.dir = Path(folder); self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, name): return self.dir / (name + ".nexus.json")

    def create(self, name: str, descricao: str = "") -> dict:
        if not name or any(c in name for c in '/\\:*?"<>|'):
            raise ValueError("nome de projeto inválido")
        if self._path(name).exists():
            raise FileExistsError(f"Projeto '{name}' já existe")
        proj = {"schema": SCHEMA, "name": name, "description": descricao, "created": time.time(), "parts": [], "results": []}
        self.save(proj); return proj

    def save(self, proj: dict):
        proj["modified"] = time.time()
        tmp = self._path(proj["name"]).with_suffix(".tmp")
        tmp.write_text(json.dumps(proj, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self._path(proj["name"]))

    def open(self, name: str) -> dict:
        p = json.loads(self._path(name).read_text(encoding="utf-8"))
        if p.get("schema") != SCHEMA:
            raise ValueError("versão de esquema não suportada")
        return p

    def list(self) -> list[str]:
        return sorted(p.name[:-len(".nexus.json")] for p in self.dir.glob("*.nexus.json"))

    def delete(self, name: str, confirm: bool = False):
        if not confirm:
            raise PermissionError("Exclusão exige confirm=True")
        self._path(name).unlink()

    def add_from_arsenal(self, proj: dict, arsenal: Arsenal, cid: str, overrides=None) -> dict:
        inst = arsenal.instantiate(cid, overrides=overrides)
        inst["arsenal_id"] = cid
        proj["parts"].append(inst); self.save(proj); return inst

    def usage(self, cid: str) -> list[str]:
        return [n for n in self.list() if any(p.get("arsenal_id") == cid for p in self.open(n)["parts"])]

    def delete_arsenal_component(self, arsenal: Arsenal, cid: str, confirm: bool = False):
        arsenal.delete_component(cid, confirm=confirm, in_use_by=self.usage(cid))

    def attach_result(self, proj: dict, traced) -> None:
        proj["results"].append(traced.to_dict()); self.save(proj)
