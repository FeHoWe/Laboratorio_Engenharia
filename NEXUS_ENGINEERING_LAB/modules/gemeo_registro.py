"""V120 — Gêmeo digital 2.0: registro PERSISTENTE (no `.nexus`) de levantamentos de peças e de estudos com suas assinaturas.

Armazenamento: chave opcional `gemeo_digital` no `project.json` (FORMAT_VERSION continua 1; projeto sem registro é gravado como antes; versões anteriores ignoram a chave).
- `registrar_levantamento`: guarda um retrato das peças (id, material, massa, posição, geometria) com rótulo e hora — versões comparáveis.
- `registrar_estudo`: guarda nome, tipo, classe, peças de que depende, assinatura por categoria (geometria e material vêm do projeto AGORA; contorno/malha/outros são os que você informar) e um resumo.
- `estado_estudos`: ATUALIZADO · OBSOLETO (diz o que mudou e em quais peças) · HISTORICO (substituído por estudo mais novo de mesmo nome) · INCOMPLETO (peça sem material).
- `painel`: estado por peça: ATUALIZADO, MODIFICADO, NECESSITA_NOVA_SIMULACAO, RESULTADO_HISTORICO, DADOS_INCOMPLETOS.
- `restaurar_materiais`: devolve às peças os materiais de um levantamento anterior (geometria NÃO é restaurada: o `.nexus` guarda a atual; use os backups do projeto para isso).
Nada é apagado: registros antigos permanecem. Contorno e malha não são recalculáveis a partir do projeto: só comparam se você registrar de novo.
"""
from __future__ import annotations

import time

from . import assinatura_estudo as AS, gemeo_digital as G

MAX_REGISTROS = 500


def _g(project) -> dict:
    if not hasattr(project, "gemeo") or not isinstance(project.gemeo, dict):
        project.gemeo = {"estudos": [], "levantamentos": []}
    project.gemeo.setdefault("estudos", []); project.gemeo.setdefault("levantamentos", [])
    return project.gemeo


def registrar_levantamento(project, rotulo: str = "") -> dict:
    g = _g(project)
    if len(g["levantamentos"]) >= MAX_REGISTROS:
        raise ValueError(f"limite de {MAX_REGISTROS} levantamentos atingido")
    reg = {"id": len(g["levantamentos"]) + 1, "t": time.strftime("%Y-%m-%d %H:%M:%S"), "rotulo": rotulo, "estado": G.levantar(project)}
    g["levantamentos"].append(reg)
    project.log("Levantamento do gêmeo digital", rotulo or f"#{reg['id']}")
    return reg


def _cats(estado: dict, componentes: list[str]) -> dict:
    ids = componentes or sorted(estado)
    faltam = [i for i in ids if i not in estado]
    if faltam:
        raise ValueError(f"peça(s) inexistente(s): {', '.join(faltam)}")
    return {"geometria": {i: estado[i]["geometria"] for i in ids}, "material": {i: estado[i]["material"] for i in ids}, "ids": ids}


def registrar_estudo(project, nome: str, tipo: str, classe: str, componentes: list[str] | None = None, contorno=None, malha=None, outros=None,
                     resumo: dict | None = None, dossie_sha256: str | None = None) -> dict:
    if not nome.strip():
        raise ValueError("nome do estudo vazio")
    g = _g(project)
    if len(g["estudos"]) >= MAX_REGISTROS:
        raise ValueError(f"limite de {MAX_REGISTROS} estudos atingido")
    c = _cats(G.levantar(project), list(componentes or []))
    ent = {"geometria": c["geometria"], "material": c["material"], "contorno": contorno, "malha": malha, "outros": outros}
    reg = {"id": len(g["estudos"]) + 1, "t": time.strftime("%Y-%m-%d %H:%M:%S"), "nome": nome.strip(), "tipo": tipo, "classe": classe, "componentes": c["ids"],
           "todo_o_projeto": not componentes, "assinatura": AS.assinatura(ent), "resumo": resumo or {}, "dossie_sha256": dossie_sha256,
           "material_completo": all(v for v in c["material"].values())}
    g["estudos"].append(reg)
    project.log("Estudo registrado no gêmeo digital", f"{reg['nome']} ({classe})")
    return reg


def estado_estudos(project) -> list[dict]:
    g = _g(project)
    atual = G.levantar(project)
    ultimo: dict[str, int] = {}
    for r in g["estudos"]:
        ultimo[r["nome"]] = r["id"]
    out = []
    for r in g["estudos"]:
        ids = list(atual) if r.get("todo_o_projeto") else r["componentes"]
        sumiu = [i for i in ids if i not in atual] if not r.get("todo_o_projeto") else []
        mat_falta = [i for i in ids if i in atual and not atual[i]["material"]]
        cat_atual = {"geometria": {i: atual[i]["geometria"] for i in ids if i in atual}, "material": {i: atual[i]["material"] for i in ids if i in atual}}
        # só geometria/material são recalculáveis; contorno/malha/outros ficam como foram registrados (iguais por construção)
        ass_atual = {**r["assinatura"], "geometria": AS._h(cat_atual["geometria"]), "material": AS._h(cat_atual["material"])}
        if r.get("todo_o_projeto"):
            ass_atual["geometria"] = AS._h({i: atual[i]["geometria"] for i in sorted(atual)}); ass_atual["material"] = AS._h({i: atual[i]["material"] for i in sorted(atual)})
        comp = AS.comparar(r["assinatura"], ass_atual)
        mudou_pecas = sorted({G_i for G_i in ids if G_i in atual and any(
            e["id"] == G_i for e in G.diferenca(_estado_no_registro(g, r), atual, carimbo=False))}) if _estado_no_registro(g, r) else []
        if r["id"] != ultimo[r["nome"]]:
            estado, motivo = "HISTORICO", f"substituído pelo registro #{ultimo[r['nome']]} do mesmo estudo"
        elif sumiu:
            estado, motivo = "OBSOLETO", f"peça(s) removida(s): {', '.join(sumiu)}"
        elif comp["estado"] == "OBSOLETO":
            estado, motivo = "OBSOLETO", comp["motivo"] + (f" (peças: {', '.join(mudou_pecas)})" if mudou_pecas else "")
        elif mat_falta or not r.get("material_completo", True):
            estado, motivo = "INCOMPLETO", "há peça sem material: massa e resultados dependentes ficam incompletos"
        else:
            estado, motivo = "ATUALIZADO", "geometria e material iguais aos do cálculo"
        out.append({**r, "estado": estado, "motivo": motivo})
    return out


def _estado_no_registro(g: dict, r: dict) -> dict | None:
    """Levantamento mais recente ANTERIOR ao estudo (para apontar quais peças mudaram); None se não houver."""
    cand = [l for l in g["levantamentos"] if l["t"] <= r["t"]]
    return cand[-1]["estado"] if cand else None


def painel(project) -> list[dict]:
    g = _g(project)
    atual = G.levantar(project)
    est = estado_estudos(project)
    ultimo_lev = g["levantamentos"][-1]["estado"] if g["levantamentos"] else None
    mod = {e["id"] for e in G.diferenca(ultimo_lev, atual, carimbo=False)} if ultimo_lev is not None else set()
    out = []
    for cid, p in atual.items():
        ref = [e for e in est if e.get("todo_o_projeto") or cid in e["componentes"]]
        if any(e["estado"] == "OBSOLETO" for e in ref):
            st = "NECESSITA_NOVA_SIMULACAO"
        elif not p["material"]:
            st = "DADOS_INCOMPLETOS"
        elif cid in mod:
            st = "MODIFICADO"
        elif ref and all(e["estado"] == "HISTORICO" for e in ref):
            st = "RESULTADO_HISTORICO"
        else:
            st = "ATUALIZADO"
        out.append({"id": cid, "nome": p["nome"], "estado": st, "estudos": [e["nome"] + f" #{e['id']} [{e['estado']}]" for e in ref]})
    return out


def comparar_levantamentos(project, a: int, b: int) -> list[dict]:
    g = _g(project)
    for n in (a, b):
        if not 1 <= n <= len(g["levantamentos"]):
            raise ValueError(f"levantamento #{n} inexistente (há {len(g['levantamentos'])})")
    return G.diferenca(g["levantamentos"][a - 1]["estado"], g["levantamentos"][b - 1]["estado"], carimbo=False)


def restaurar_materiais(project, n: int) -> list[dict]:
    """Volta os materiais das peças ao do levantamento #n. Só mexe em peças que ainda existem e cujo material registrado não era vazio. Devolve o que mudou (para desfazer, restaure outro levantamento)."""
    g = _g(project)
    if not 1 <= n <= len(g["levantamentos"]):
        raise ValueError(f"levantamento #{n} inexistente (há {len(g['levantamentos'])})")
    alvo = g["levantamentos"][n - 1]["estado"]
    atual = G.levantar(project)
    mud = []
    for cid, p in alvo.items():
        if cid in atual and p["material"] and p["material"] != atual[cid]["material"]:
            project.components.set_material(cid, p["material"], recursive=False)
            mud.append({"id": cid, "nome": p["nome"], "de": atual[cid]["material"], "para": p["material"]})
    if mud:
        project.log("Materiais restaurados do levantamento", f"#{n} ({len(mud)} peça(s))")
    return mud


def texto(project) -> str:
    est = estado_estudos(project)
    pn = painel(project)
    L = [f"Gêmeo digital — {len(pn)} peça(s), {len(est)} estudo(s) registrado(s), {len(_g(project)['levantamentos'])} levantamento(s)"]
    L += [f"  [{e['estado']}] #{e['id']} {e['nome']} ({e['classe']}) — {e['motivo']}" for e in est] or ["  (nenhum estudo registrado)"]
    L += ["Peças:"] + [f"  {p['nome']}: {p['estado']}" for p in pn]
    return "\n".join(L + ["Registros antigos não são apagados; contorno/malha só mudam o estado se você registrar o estudo de novo."])
