"""NEXUS ENGINEERING ARSENAL (V2.5): biblioteca central de componentes reutilizáveis, versionados e compartilhada entre projetos.

Regras (PROMPT MASTER §10-§13):
- ID único NEXUS-COMP-000001; versões major.minor; NUNCA sobrescreve: toda modificação gera uma nova versão.
- Restaurar uma versão antiga cria uma NOVA versão com o conteúdo antigo (o histórico é preservado).
- Compatibilidade só é afirmada com interfaces declaradas; sem dados: "COMPATIBILIDADE NÃO VERIFICADA".
- Materiais/propriedades não são inventados: campo vazio = "PROPRIEDADE NÃO INFORMADA".
- Armazenamento SQLite (sem dependências novas). A geometria é a receita paramétrica (part_key + params) da biblioteca
  de peças, regenerável e exata; peças importadas (STEP) podem ser guardadas via `step_path`.
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

NOT_VERIFIED = "COMPATIBILIDADE NÃO VERIFICADA"
NOT_INFORMED = "PROPRIEDADE NÃO INFORMADA"
DEFAULT_CATEGORIES = [
    "Componentes mecânicos", "Componentes automotivos", "Componentes de robótica", "Componentes aerodinâmicos",
]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS categories(name TEXT PRIMARY KEY, custom INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS components(
    id TEXT PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
    created TEXT NOT NULL, parent_id TEXT, parent_version TEXT);
CREATE TABLE IF NOT EXISTS versions(
    comp_id TEXT NOT NULL, version TEXT NOT NULL, seq INTEGER NOT NULL, created TEXT NOT NULL,
    data TEXT NOT NULL, change TEXT NOT NULL, PRIMARY KEY(comp_id, version));
"""


class ArsenalError(Exception):
    pass


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _version_str(seq: int) -> str:
    return f"1.{seq - 1}"


class Arsenal:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        self.db = sqlite3.connect(self.path)
        self.db.executescript(_SCHEMA)
        for c in DEFAULT_CATEGORIES:
            self.db.execute("INSERT OR IGNORE INTO categories(name, custom) VALUES(?, 0)", (c,))
        self.db.commit()

    # ---- categorias
    def categories(self) -> list[str]:
        return [r[0] for r in self.db.execute("SELECT name FROM categories ORDER BY custom, name")]

    def add_category(self, name: str) -> None:
        name = name.strip()
        if not name:
            raise ArsenalError("Nome de categoria vazio.")
        self.db.execute("INSERT OR IGNORE INTO categories(name, custom) VALUES(?, 1)", (name,))
        self.db.commit()

    # ---- criação / versões
    def _next_id(self) -> str:
        row = self.db.execute("SELECT id FROM components ORDER BY id DESC LIMIT 1").fetchone()
        n = int(row[0].rsplit("-", 1)[1]) + 1 if row else 1
        return f"NEXUS-COMP-{n:06d}"

    @staticmethod
    def _clean(data: dict) -> dict:
        d = {
            "part_key": data.get("part_key"),            # receita paramétrica da biblioteca (samples.library)
            "params": dict(data.get("params") or {}),
            "step_path": data.get("step_path"),          # alternativa: arquivo STEP guardado
            "material": data.get("material"),            # escolhido pelo usuário; None = não informado
            "interfaces": list(data.get("interfaces") or []),
            "references": list(data.get("references") or []),   # fontes técnicas
            "properties": dict(data.get("properties") or {}),   # {nome: {value, unit, origin}}; origin: documentado/medido/calculado/estimado
        }
        if not d["part_key"] and not d["step_path"]:
            raise ArsenalError("Informe part_key (biblioteca) ou step_path (STEP).")
        for k, p in d["properties"].items():
            if not isinstance(p, dict) or "value" not in p or not p.get("origin"):
                raise ArsenalError(f"Propriedade '{k}' precisa de value e origin (documentado/medido/calculado/estimado).")
        return d

    def add_component(self, name: str, category: str, data: dict, description: str = "") -> str:
        if category not in self.categories():
            raise ArsenalError(f"Categoria desconhecida: {category} (crie-a com add_category).")
        clean = self._clean(data)
        cid = self._next_id()
        self.db.execute("INSERT INTO components VALUES(?,?,?,?,?,NULL,NULL)", (cid, name, category, description, _now()))
        self.db.execute("INSERT INTO versions VALUES(?,?,?,?,?,?)",
                        (cid, "1.0", 1, _now(), json.dumps(clean), "Criação"))
        self.db.commit()
        return cid

    def _exists(self, cid: str) -> None:
        if not self.db.execute("SELECT 1 FROM components WHERE id=?", (cid,)).fetchone():
            raise ArsenalError(f"Componente inexistente: {cid}")

    def versions(self, cid: str) -> list[dict]:
        self._exists(cid)
        return [{"version": v, "seq": s, "created": c, "change": ch}
                for v, s, c, ch in self.db.execute(
                    "SELECT version, seq, created, change FROM versions WHERE comp_id=? ORDER BY seq", (cid,))]

    def latest_version(self, cid: str) -> str:
        return self.versions(cid)[-1]["version"]

    def get(self, cid: str, version: Optional[str] = None) -> dict:
        self._exists(cid)
        version = version or self.latest_version(cid)
        row = self.db.execute("SELECT data, created, change FROM versions WHERE comp_id=? AND version=?", (cid, version)).fetchone()
        if not row:
            raise ArsenalError(f"{cid} não tem a versão {version}")
        c = self.db.execute("SELECT name, category, description, created, parent_id, parent_version FROM components WHERE id=?", (cid,)).fetchone()
        out = json.loads(row[0])
        out.update(id=cid, version=version, name=c[0], category=c[1], description=c[2], created=c[3],
                   version_created=row[1], change=row[2], parent=(c[4], c[5]) if c[4] else None)
        if not out.get("material"):
            out["material_label"] = NOT_INFORMED
        else:
            out["material_label"] = out["material"]
        return out

    def modify(self, cid: str, change: str, **fields) -> str:
        """Gera uma NOVA versão (a anterior é preservada). Campos: params, material, interfaces, references, properties, part_key, step_path."""
        if not change.strip():
            raise ArsenalError("Descreva a modificação (histórico).")
        cur = self.get(cid)
        allowed = {"params", "material", "interfaces", "references", "properties", "part_key", "step_path"}
        bad = set(fields) - allowed
        if bad:
            raise ArsenalError(f"Campos inválidos: {sorted(bad)}")
        data = {k: cur[k] for k in allowed}
        data.update(fields)
        clean = self._clean(data)
        if clean == {k: cur[k] for k in clean}:
            raise ArsenalError("Nenhuma alteração em relação à versão atual.")
        seq = len(self.versions(cid)) + 1
        ver = _version_str(seq)
        self.db.execute("INSERT INTO versions VALUES(?,?,?,?,?,?)", (cid, ver, seq, _now(), json.dumps(clean), change))
        self.db.commit()
        return ver

    def compare(self, cid: str, va: str, vb: str) -> list[dict]:
        a, b = self.get(cid, va), self.get(cid, vb)
        diffs = []
        for key in ("part_key", "step_path", "material", "interfaces", "references"):
            if a[key] != b[key]:
                diffs.append({"campo": key, "de": a[key], "para": b[key]})
        for k in sorted(set(a["params"]) | set(b["params"])):
            if a["params"].get(k) != b["params"].get(k):
                diffs.append({"campo": f"params.{k}", "de": a["params"].get(k), "para": b["params"].get(k)})
        for k in sorted(set(a["properties"]) | set(b["properties"])):
            if a["properties"].get(k) != b["properties"].get(k):
                diffs.append({"campo": f"properties.{k}", "de": a["properties"].get(k), "para": b["properties"].get(k)})
        return diffs

    def restore(self, cid: str, version: str) -> str:
        """Restaurar = nova versão com o conteúdo antigo (nada é apagado)."""
        old = self.get(cid, version)
        latest = self.get(cid)
        keys = ("part_key", "step_path", "material", "interfaces", "references", "properties", "params")
        if all(old[k] == latest[k] for k in keys):
            raise ArsenalError("A versão atual já é idêntica à solicitada.")
        return self.modify(cid, f"Restaurada a partir da versão {version}", **{k: old[k] for k in keys})

    def duplicate(self, cid: str, new_name: str, category: Optional[str] = None, version: Optional[str] = None) -> str:
        """Cria variante/duplicata independente (novo ID); registra a origem."""
        src = self.get(cid, version)
        new_id = self.add_component(new_name, category or src["category"],
                                    {k: src[k] for k in ("part_key", "step_path", "material", "interfaces",
                                                         "references", "properties", "params")},
                                    f"Variante de {cid} v{src['version']}")
        self.db.execute("UPDATE components SET parent_id=?, parent_version=? WHERE id=?", (cid, src["version"], new_id))
        self.db.commit()
        return new_id

    def list_components(self, category: Optional[str] = None, text: str = "") -> list[dict]:
        q = "SELECT id, name, category FROM components"
        args: list = []
        conds = []
        if category:
            conds.append("category=?")
            args.append(category)
        if text:
            conds.append("(name LIKE ? OR description LIKE ?)")
            args += [f"%{text}%"] * 2
        if conds:
            q += " WHERE " + " AND ".join(conds)
        return [{"id": i, "name": n, "category": c, "latest": self.latest_version(i)}
                for i, n, c in self.db.execute(q + " ORDER BY id", args)]

    def instantiate(self, cid: str, version: Optional[str] = None, overrides: Optional[dict] = None) -> dict:
        """Cópia para uso num projeto: geometria + propriedades preservadas, parâmetros locais editáveis; a peça do arsenal NÃO muda."""
        c = self.get(cid, version)
        params = dict(c["params"])
        params.update(overrides or {})
        return {"part_key": c["part_key"], "step_path": c["step_path"], "params": params, "name": c["name"],
                "origin": f"{cid} v{c['version']}" + (" (com modificações locais)" if overrides else ""),
                "interfaces": c["interfaces"], "material": c["material"]}

    def close(self) -> None:
        self.db.close()


# ---------------------------------------------------------------- compatibilidade
def check_compatibility(a: dict, b: dict, clearance_tol_mm: float = 0.05) -> dict:
    """Compara interfaces DECLARADAS de duas peças.

    Interface: {"kind": "shaft"|"bore"|"thread_ext"|"thread_int", "d": mm, "id": "rótulo", ["pitch": mm]}.
    Resultado: status ∈ {"COMPATÍVEL (interfaces declaradas)", "INCOMPATÍVEL", NOT_VERIFIED} + motivos.
    Eixo/furo: compatíveis se |d_furo − d_eixo| ≤ tolerância informada (o ajuste real depende de tolerâncias que o usuário deve declarar).
    """
    ia, ib = a.get("interfaces") or [], b.get("interfaces") or []
    if not ia or not ib:
        return {"status": NOT_VERIFIED, "reasons": ["Uma das peças não possui interfaces declaradas."], "pairs": []}
    pair_kinds = {("shaft", "bore"), ("bore", "shaft"), ("thread_ext", "thread_int"), ("thread_int", "thread_ext")}
    pairs, reasons = [], []
    for x in ia:
        for y in ib:
            if (x.get("kind"), y.get("kind")) not in pair_kinds:
                continue
            dx, dy = float(x["d"]), float(y["d"])
            ok = abs(dx - dy) <= clearance_tol_mm
            if x["kind"].startswith("thread"):
                px, py = x.get("pitch"), y.get("pitch")
                if px is None or py is None:
                    pairs.append({"a": x.get("id"), "b": y.get("id"), "ok": None})
                    reasons.append(f"Rosca {x.get('id')}/{y.get('id')}: passo não informado → {NOT_VERIFIED}")
                    continue
                ok = ok and abs(float(px) - float(py)) < 1e-6
            pairs.append({"a": x.get("id"), "b": y.get("id"), "ok": ok})
            reasons.append(f"{x.get('id')} (Ø{dx:g}) × {y.get('id')} (Ø{dy:g}): {'OK' if ok else 'diâmetros/passo diferentes'}")
    if not pairs:
        return {"status": NOT_VERIFIED, "reasons": ["Nenhum par de interfaces complementares (eixo/furo, rosca) foi declarado."], "pairs": []}
    if any(p["ok"] is None for p in pairs):
        status = NOT_VERIFIED
    elif any(p["ok"] for p in pairs):
        status = "COMPATÍVEL (interfaces declaradas)"
    else:
        status = "INCOMPATÍVEL"
    return {"status": status, "reasons": reasons, "pairs": pairs}
