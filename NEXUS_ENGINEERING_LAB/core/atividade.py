"""V110 — Histórico de atividade local (alimenta o Control Center). Arquivo JSON-lines, só no computador do usuário; nada é enviado a lugar nenhum.

Local: variável de ambiente NEXUS_DATA_DIR, senão `~/.nexus_lab/atividade.jsonl`. Falhar ao gravar NUNCA interrompe o programa (o histórico é conveniência).
Guarda no máximo MAX linhas (as mais recentes). Tipos usados: projeto, estudo, alerta.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

MAX = 500


def _arquivo() -> Path:
    base = os.environ.get("NEXUS_DATA_DIR")
    return (Path(base) if base else Path.home() / ".nexus_lab") / "atividade.jsonl"


def registrar(tipo: str, texto: str, caminho: str | None = None) -> bool:
    try:
        p = _arquivo()
        p.parent.mkdir(parents=True, exist_ok=True)
        linhas = p.read_text(encoding="utf-8").splitlines() if p.exists() else []
        linhas.append(json.dumps({"t": time.strftime("%Y-%m-%d %H:%M:%S"), "tipo": tipo, "texto": str(texto)[:300], "caminho": caminho}, ensure_ascii=False))
        p.write_text("\n".join(linhas[-MAX:]) + "\n", encoding="utf-8")
        return True
    except Exception:  # noqa: BLE001 - histórico é conveniência
        return False


def ultimos(n: int = 20, tipo: str | None = None) -> list[dict]:
    try:
        p = _arquivo()
        if not p.exists():
            return []
        out = []
        for ln in p.read_text(encoding="utf-8").splitlines():
            try:
                d = json.loads(ln)
            except ValueError:
                continue                                           # linha corrompida é ignorada, não derruba
            if isinstance(d, dict) and (tipo is None or d.get("tipo") == tipo):
                out.append(d)
        return out[-n:][::-1]
    except Exception:  # noqa: BLE001
        return []


def projetos_recentes(n: int = 8) -> list[str]:
    """Caminhos distintos dos projetos abertos/salvos mais recentemente que AINDA existem em disco."""
    vistos, out = set(), []
    for d in ultimos(MAX, "projeto"):
        c = d.get("caminho")
        if c and c not in vistos and Path(c).exists():
            vistos.add(c); out.append(c)
            if len(out) >= n:
                break
    return out
