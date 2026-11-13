"""V102 (Fase C/F) — Assinatura de um estudo e detecção de resultado OBSOLETO por mudança de geometria, material, condições de contorno ou malha.

`assinatura(entradas)` separa as entradas em categorias e guarda um hash de cada uma; `comparar(guardada, atual)` diz QUAIS categorias mudaram.
Nada é apagado: o resultado antigo continua válido para as entradas ANTIGAS; só deixa de valer para as atuais (estado OBSOLETO, com o motivo).
Categorias: geometria, material, contorno, malha, outros. Números são arredondados a 9 algarismos significativos antes do hash.
"""
from __future__ import annotations

import hashlib
import json

CATEGORIAS = ("geometria", "material", "contorno", "malha", "outros")


def _norm(x):
    if isinstance(x, float):
        return float(f"{x:.9g}")
    if isinstance(x, dict):
        return {str(k): _norm(v) for k, v in sorted(x.items(), key=lambda kv: str(kv[0]))}
    if isinstance(x, (list, tuple)):
        return [_norm(v) for v in x]
    return x


def _h(x) -> str:
    return hashlib.sha256(json.dumps(_norm(x), sort_keys=True, ensure_ascii=False, default=repr).encode("utf-8")).hexdigest()[:16]


def assinatura(entradas: dict) -> dict:
    """`entradas`: dict com chaves entre CATEGORIAS (valores quaisquer serializáveis). Categoria ausente = vazia (hash estável)."""
    desc = set(entradas) - set(CATEGORIAS)
    if desc:
        raise ValueError(f"categoria(s) desconhecida(s): {', '.join(sorted(map(str, desc)))} (use {', '.join(CATEGORIAS)})")
    return {c: _h(entradas.get(c)) for c in CATEGORIAS}


def comparar(guardada: dict, atual: dict) -> dict:
    if not isinstance(guardada, dict) or set(guardada) != set(CATEGORIAS):
        return {"estado": "SEM_VINCULO", "mudou": [], "motivo": "resultado sem assinatura de entradas: não afirmamos que vale para o estudo atual"}
    mudou = [c for c in CATEGORIAS if guardada[c] != atual.get(c)]
    if not mudou:
        return {"estado": "VIGENTE", "mudou": [], "motivo": "entradas idênticas às do cálculo"}
    return {"estado": "OBSOLETO", "mudou": mudou, "motivo": "mudou: " + ", ".join(mudou) + " — resultado refere-se às entradas anteriores; refaça o cálculo"}


def revisar(resultados: list[dict], atual: dict) -> list[dict]:
    """Anota cada resultado (dict com 'assinatura') com `estado_entradas`/`motivo_entradas` SEM remover nem alterar os valores. Devolve os que ficaram OBSOLETO."""
    obs = []
    for r in resultados:
        c = comparar(r.get("assinatura"), atual)
        r["estado_entradas"], r["motivo_entradas"] = c["estado"], c["motivo"]
        if c["estado"] == "OBSOLETO":
            obs.append(r)
    return obs
