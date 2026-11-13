"""V100 — Receitas: executa vários estudos em lote a partir de um JSON e grava um dossiê reprodutível por passo + um resumo.

Formato: {"titulo": "...", "passos": [{"nome": "t1", "tipo": "tornado", "parametros": {...}, "nota": "..."}, ...]}   (tipos e parâmetros = os de `modules.dossie`)
Um passo que falha NÃO derruba os demais: é registrado com o erro e o código de saída fica 1. Nada é inventado: cada passo roda o mesmo solver, com as entradas que você escreveu.
Saída: pasta com `<nome>.dossie.json` por passo e `resumo.json` (+ `resumo.txt`). O resumo repete a classe de cada resultado e os avisos de reprodutibilidade.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import dossie

MAX_PASSOS = 200


class ReceitaError(ValueError):
    pass


def ler(caminho) -> dict:
    try:
        r = json.loads(Path(caminho).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ReceitaError(f"não foi possível ler a receita: {exc}")
    validar(r)
    return r


def validar(r) -> None:
    if not isinstance(r, dict) or not isinstance(r.get("passos"), list) or not r["passos"]:
        raise ReceitaError("receita deve ser um objeto com a lista não vazia 'passos'")
    if len(r["passos"]) > MAX_PASSOS:
        raise ReceitaError(f"receita com mais de {MAX_PASSOS} passos")
    nomes = set()
    for i, p in enumerate(r["passos"], 1):
        if not isinstance(p, dict) or p.get("tipo") not in dossie.TIPOS or not isinstance(p.get("parametros"), dict):
            raise ReceitaError(f"passo {i}: precisa de 'tipo' ({', '.join(dossie.TIPOS)}) e 'parametros' (objeto)")
        nome = re.sub(r"[^A-Za-z0-9_-]", "_", str(p.get("nome") or f"passo{i:02d}"))
        if nome in nomes:
            raise ReceitaError(f"passo {i}: nome repetido '{nome}'")
        nomes.add(nome)
        p["nome"] = nome


def executar(r: dict, pasta) -> dict:
    validar(r)
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    linhas = []
    for p in r["passos"]:
        try:
            d = dossie.criar(p["tipo"], p["parametros"], p.get("nota", ""))
            arq = dossie.salvar(d, pasta / f"{p['nome']}.dossie.json")
            res = d["resultado"]
            linhas.append({"nome": p["nome"], "tipo": p["tipo"], "ok": True, "classe": res.get("classe"), "sha256": d["sha256_resultado"], "arquivo": arq.name})
        except Exception as exc:  # noqa: BLE001 - um passo ruim não derruba o lote
            linhas.append({"nome": p["nome"], "tipo": p["tipo"], "ok": False, "erro": str(exc)})
    resumo = {"titulo": r.get("titulo", "receita"), "passos": linhas, "ok": all(x["ok"] for x in linhas), "ambiente": dossie.criar_ambiente(),
              "avisos": ["Cada dossiê prova reprodutibilidade, não validade do modelo.", "Resultados são SIMULACAO_NUMERICA/ANALITICO conforme cada passo; nada aqui é validação."]}
    (pasta / "resumo.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=1), encoding="utf-8")
    (pasta / "resumo.txt").write_text(texto(resumo), encoding="utf-8")
    return resumo


def texto(rs: dict) -> str:
    L = [f"Receita '{rs['titulo']}' — {sum(x['ok'] for x in rs['passos'])}/{len(rs['passos'])} passos ok · NEXUS {rs['ambiente']['nexus']}"]
    for x in rs["passos"]:
        L.append(f"  {'✔' if x['ok'] else '✘'} {x['nome']} ({x['tipo']}) " + (f"{x['classe']} sha256={x['sha256'][:12]}…" if x["ok"] else f"ERRO: {x['erro']}"))
    return "\n".join(L + ["⚠ " + a for a in rs["avisos"]])
