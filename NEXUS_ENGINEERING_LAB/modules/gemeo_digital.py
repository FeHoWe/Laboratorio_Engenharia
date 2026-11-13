"""V105 (Fase F) — Gêmeo digital leve: estado rastreável de cada peça do projeto e detecção de estudos a refazer quando algo muda.

`levantar(project)` → por peça: id, nome, material, massa (kg, só se houver material), posição (offset) e impressão digital da geometria
(B-Rep via `result_store.fingerprint_shape`; malha por contagem + caixa + soma dos vértices). NÃO grava nada no `.nexus` nem altera o projeto.
`diferenca(antes, depois)` lista o que mudou por peça (geometria, material, massa, posição, adicionada, removida) com carimbo de tempo opcional.
`estudos_afetados(mudancas, estudos)`: cada estudo declara de quais peças depende (`componentes`; vazio = depende do projeto todo). Estudo afetado vira REFAZER;
os demais seguem vigentes. NUNCA apaga resultados: o histórico de mudanças e os estudos antigos continuam disponíveis para rastreabilidade.
"""
from __future__ import annotations

import hashlib
import time

import numpy as np

from . import result_store


def _fp_geometria(comp) -> str:
    if getattr(comp, "shape", None) is not None:
        try:
            return result_store.fingerprint_shape(comp.shape)
        except Exception:  # noqa: BLE001 - sem OCP/forma inválida: cai para vazio explícito
            return "indisponivel"
    m = getattr(comp, "mesh", None)
    if m is not None:
        v = np.round(np.asarray(m.vertices, float), 4)
        return hashlib.sha256(f"{len(v)}|{len(m.faces)}|{v.min(axis=0).tolist()}|{v.max(axis=0).tolist()}|{float(v.sum()):.4f}".encode()).hexdigest()[:16] if len(v) else "malha_vazia"
    return "sem_geometria"


def levantar(project) -> dict:
    from modules.component_inspector import ComponentInspector
    insp = ComponentInspector(project.components, project.materials)
    out = {}
    for leaf in project.components.leaves():
        rep = insp.inspect(leaf)
        out[leaf.id] = {"id": leaf.id, "nome": leaf.name, "material": leaf.material,
                        "massa_kg": (rep.mass / 1000.0) if rep.mass is not None else None,
                        "posicao": [round(float(x), 6) for x in leaf.offset], "geometria": _fp_geometria(leaf)}
    return out


def diferenca(antes: dict, depois: dict, carimbo: bool = True) -> list[dict]:
    t = time.strftime("%Y-%m-%d %H:%M:%S") if carimbo else None
    ev = []
    for cid in sorted(set(antes) | set(depois)):
        a, d = antes.get(cid), depois.get(cid)
        if a is None:
            ev.append({"id": cid, "nome": d["nome"], "tipo": "adicionada", "t": t}); continue
        if d is None:
            ev.append({"id": cid, "nome": a["nome"], "tipo": "removida", "t": t}); continue
        for campo, tipo in (("geometria", "geometria"), ("material", "material"), ("posicao", "posicao")):
            if a[campo] != d[campo]:
                ev.append({"id": cid, "nome": d["nome"], "tipo": tipo, "de": a[campo], "para": d[campo], "t": t})
        ma, md = a["massa_kg"], d["massa_kg"]
        if ma != md and not (ma is not None and md is not None and abs(ma - md) <= 1e-9 * max(abs(ma), 1.0)):
            ev.append({"id": cid, "nome": d["nome"], "tipo": "massa", "de": ma, "para": md, "t": t})
    return ev


def estudos_afetados(mudancas: list[dict], estudos: list[dict]) -> list[dict]:
    """Cada estudo: {'nome', 'componentes': [ids] (vazio = projeto todo), ...}. Devolve cópias anotadas com `estado` (REFAZER|VIGENTE) e `motivos`; não remove nem altera os originais."""
    ids = {m["id"] for m in mudancas}
    out = []
    for e in estudos:
        dep = set(e.get("componentes") or [])
        hit = [m for m in mudancas if (not dep) or m["id"] in dep]
        mot = sorted({f"{m['nome']}: {m['tipo']}" for m in hit})
        out.append({**e, "estado": "REFAZER" if hit else "VIGENTE", "motivos": mot})
    return out


def texto(mudancas: list[dict], anotados: list[dict] | None = None) -> str:
    if not mudancas:
        return "Nenhuma mudança nas peças desde o último levantamento."
    L = [f"{len(mudancas)} mudança(s):"] + [f"  {m['nome']}: {m['tipo']}" + (f" ({m.get('de')} → {m.get('para')})" if "de" in m else "") for m in mudancas]
    if anotados:
        L.append("Estudos:")
        L += [f"  [{e['estado']}] {e['nome']}" + (f" — {'; '.join(e['motivos'])}" if e["motivos"] else "") for e in anotados]
        L.append("Resultados antigos NÃO foram apagados: valem para o estado anterior das peças.")
    return "\n".join(L)
