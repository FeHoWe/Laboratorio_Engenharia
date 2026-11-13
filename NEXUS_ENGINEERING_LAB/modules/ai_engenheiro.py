"""V106 (Fase F) — NEXUS AI Engineer: camada de FERRAMENTAS determinísticas que consulta os dados reais do projeto e organiza a resposta em cinco blocos.

Blocos (nunca misturados): CALCULADO (números vindos de módulos), INTERPRETACAO (regras do `intelligence`), HIPOTESE (premissas declaradas dos estudos),
RECOMENDACAO (cada uma cita os dados em que se apoia) e INDISPONIVEL (o que falta para responder). Esta camada NÃO usa IA generativa e NÃO inventa número:
todo número do texto vem de um campo do diagnóstico (teste confere). A camada generativa opcional continua em `intelligence_llm` (usa esses blocos como fatos).
`responder` roteia a pergunta por palavras-chave para os blocos existentes; se não reconhece, diz que não sabe em vez de improvisar.
"""
from __future__ import annotations

from . import gemeo_digital, intelligence


def diagnostico(project, estudos: list[dict] | None = None, estado_anterior: dict | None = None, clashes=None) -> dict:
    """`estudos`: [{'nome','classe','valores'{...},'premissas'[...],'limitacoes'[...],'componentes'[ids]}] (resultados já calculados, fornecidos por quem chama)."""
    estudos = list(estudos or [])
    estado = gemeo_digital.levantar(project)
    folhas = list(estado.values())
    com_mat = [f for f in folhas if f["material"]]
    calculado = [{"item": "pecas", "valor": len(folhas), "fonte": "projeto"},
                 {"item": "pecas_com_material", "valor": len(com_mat), "fonte": "projeto"},
                 {"item": "massa_parcial_kg", "valor": sum(f["massa_kg"] for f in com_mat if f["massa_kg"] is not None), "fonte": "component_inspector (só peças com material)"}]
    for e in estudos:
        for k, v in (e.get("valores") or {}).items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                calculado.append({"item": f"{e['nome']}.{k}", "valor": v, "fonte": f"estudo '{e['nome']}' ({e.get('classe', 'classe não informada')})"})
    par = intelligence.verificar_projeto(project, clashes)
    interp = [{"nivel": a.nivel, "texto": a.texto, "fonte": a.evidencia or "regras do NEXUS"} for a in par.achados]
    hip = [{"estudo": e["nome"], "premissa": x} for e in estudos for x in (e.get("premissas") or [])] + \
          [{"estudo": e["nome"], "premissa": "LIMITAÇÃO: " + x} for e in estudos for x in (e.get("limitacoes") or [])]
    ind, rec = [], []
    if len(com_mat) < len(folhas):
        faltam = [f["nome"] for f in folhas if not f["material"]]
        ind.append({"item": "massa total", "motivo": f"{len(faltam)} peça(s) sem material atribuído (o NEXUS não atribui automaticamente)"})
        rec.append({"texto": "Atribuir material às peças sem material para obter a massa total.", "baseado_em": [f"pecas_com_material={len(com_mat)} de {len(folhas)}"]})
    if not estudos:
        ind.append({"item": "resultados de estudos", "motivo": "nenhum resultado foi fornecido ao diagnóstico"})
    mud = []
    if estado_anterior is not None:
        mud = gemeo_digital.diferenca(estado_anterior, estado)
        an = gemeo_digital.estudos_afetados(mud, estudos)
        refazer = [e["nome"] for e in an if e["estado"] == "REFAZER"]
        if refazer:
            rec.append({"texto": "Refazer os estudos afetados por mudanças nas peças: " + ", ".join(refazer) + ".", "baseado_em": [f"{len(mud)} mudança(s) desde o levantamento anterior"]})
    for e in estudos:
        if str(e.get("classe", "")) not in ("VALIDADO",):
            rec.append({"texto": f"Tratar '{e['nome']}' como resultado NÃO validado ({e.get('classe', 'classe não informada')}); não usar para liberar projeto.", "baseado_em": [f"classe de '{e['nome']}'"]})
    return {"CALCULADO": calculado, "INTERPRETACAO": interp, "HIPOTESE": hip, "RECOMENDACAO": rec, "INDISPONIVEL": ind, "mudancas": mud,
            "aviso": "Diagnóstico por regras e ferramentas do NEXUS; sem IA generativa; números só vêm de módulos de cálculo."}


def texto(d: dict) -> str:
    L = []
    for bloco in ("CALCULADO", "INTERPRETACAO", "HIPOTESE", "RECOMENDACAO", "INDISPONIVEL"):
        L.append(f"== {bloco} ==")
        itens = d[bloco]
        if not itens:
            L.append("  (nada)")
        for x in itens:
            if bloco == "CALCULADO":
                L.append(f"  {x['item']} = {x['valor']:.6g}  [fonte: {x['fonte']}]")
            elif bloco == "INTERPRETACAO":
                L.append(f"  [{x['nivel']}] {x['texto']}  [fonte: {x['fonte']}]")
            elif bloco == "HIPOTESE":
                L.append(f"  ({x['estudo']}) {x['premissa']}")
            elif bloco == "RECOMENDACAO":
                L.append(f"  {x['texto']}  [baseado em: {'; '.join(x['baseado_em'])}]")
            else:
                L.append(f"  {x['item']}: {x['motivo']}")
    return "\n".join(L + ["", d["aviso"]])


_ROTAS = (("massa", ("massa", "peso", "kg")), ("material", ("material", "materiais")), ("estudo", ("estudo", "resultado", "tensão", "tensao", "fea", "cfd", "volta")),
          ("mudanca", ("mudan", "alter", "refaz", "refazer", "obsolet")), ("premissa", ("premissa", "hipótese", "hipotese", "limita")), ("recomend", ("recomend", "sugest", "melhor", "próximo", "proximo")))


def responder(pergunta: str, d: dict) -> dict:
    """Roteia por palavra-chave para os blocos do diagnóstico. Devolve só conteúdo já existente nele, com o bloco de origem."""
    q = pergunta.lower()
    achou = [nome for nome, kws in _ROTAS if any(k in q for k in kws)]
    if not achou:
        return {"reconhecida": False, "resposta": "Não sei responder a isso com os dados do diagnóstico (massa, materiais, estudos, mudanças, premissas, recomendações).", "blocos": []}
    sel: list = []
    if "massa" in achou:
        sel += [("CALCULADO", x) for x in d["CALCULADO"] if x["item"] in ("pecas", "pecas_com_material", "massa_parcial_kg")] + [("INDISPONIVEL", x) for x in d["INDISPONIVEL"] if x["item"] == "massa total"]
    if "material" in achou:
        sel += [("INTERPRETACAO", x) for x in d["INTERPRETACAO"] if "material" in x["texto"].lower()] + [("INDISPONIVEL", x) for x in d["INDISPONIVEL"] if x["item"] == "massa total"]
    if "estudo" in achou:
        sel += [("CALCULADO", x) for x in d["CALCULADO"] if "." in x["item"]]
    if "mudanca" in achou:
        sel += [("RECOMENDACAO", x) for x in d["RECOMENDACAO"] if "Refazer" in x["texto"]] + [("CALCULADO", {"item": "mudancas", "valor": len(d["mudancas"]), "fonte": "gêmeo digital"})]
    if "premissa" in achou:
        sel += [("HIPOTESE", x) for x in d["HIPOTESE"]]
    if "recomend" in achou:
        sel += [("RECOMENDACAO", x) for x in d["RECOMENDACAO"]]
    vistos, blocos = set(), []
    for b, x in sel:
        k = (b, str(x))
        if k not in vistos:
            vistos.add(k); blocos.append((b, x))
    if not blocos:
        return {"reconhecida": True, "resposta": "O diagnóstico não tem dados para essa pergunta (veja o bloco INDISPONIVEL).", "blocos": []}
    sub = {"CALCULADO": [], "INTERPRETACAO": [], "HIPOTESE": [], "RECOMENDACAO": [], "INDISPONIVEL": []}
    for b, x in blocos:
        sub[b].append(x)
    return {"reconhecida": True, "resposta": texto({**sub, "mudancas": d["mudancas"], "aviso": d["aviso"]}), "blocos": [b for b, _ in blocos]}
