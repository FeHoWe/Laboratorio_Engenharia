"""V107 (Fase G) — Relatório técnico consolidado do projeto: as 14 seções pedidas, sempre presentes; o que não foi informado diz “Não informado”.

Seções: identificação, objetivo, geometria, materiais, parâmetros, condições de contorno, método de cálculo, hipóteses, resultados, gráficos, imagens 3D,
limitações, critérios de validação, conclusão técnica. Os números vêm do levantamento do projeto (`gemeo_digital`) e dos estudos passados por quem chama;
o relatório NÃO calcula nem interpreta além do que os módulos entregam. Resultados são agrupados por CLASSE (ANALITICO / SIMULACAO_NUMERICA / VALIDADO / …) e nunca
misturados. A conclusão técnica é montada por regras a partir das classes e dos critérios informados: sem critério de validação documentado, nada é declarado validado.
Imagens/gráficos: só entram os arquivos que o usuário indicar (PNG/JPG existentes); o relatório não os gera.
Exportação: Markdown, JSON e PDF (reportlab).
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from . import gemeo_digital

SECOES = ("identificacao", "objetivo", "geometria", "materiais", "parametros", "contorno", "metodo", "hipoteses", "resultados", "graficos", "imagens_3d", "limitacoes",
          "criterios_validacao", "conclusao")
TITULOS = {"identificacao": "1. Identificação do projeto", "objetivo": "2. Objetivo do estudo", "geometria": "3. Geometria analisada", "materiais": "4. Materiais", "parametros": "5. Parâmetros",
           "contorno": "6. Condições de contorno", "metodo": "7. Método de cálculo", "hipoteses": "8. Hipóteses", "resultados": "9. Resultados", "graficos": "10. Gráficos",
           "imagens_3d": "11. Imagens 3D", "limitacoes": "12. Limitações", "criterios_validacao": "13. Critérios de validação", "conclusao": "14. Conclusão técnica"}
NI = "Não informado."
CLASSES = ("ANALITICO", "SIMULACAO_NUMERICA", "VALIDADO", "NAO_EXECUTADO", "ANIMACAO_PRESCRITA")


def montar(project, objetivo: str = "", estudos: list[dict] | None = None, criterios_validacao: list[str] | None = None, imagens: list[str] | None = None,
           graficos: list[str] | None = None, contorno: str = "", parametros: dict | None = None) -> dict:
    """`estudos`: [{'nome','classe','metodo','valores'{},'entradas'{},'premissas'[],'limitacoes'[],'validacao_ref'}]."""
    estudos = list(estudos or [])
    est = gemeo_digital.levantar(project)
    folhas = list(est.values())
    com_mat = [f for f in folhas if f["material"]]
    imgs_ok = [p for p in (imagens or []) if Path(p).is_file()]
    grf_ok = [p for p in (graficos or []) if Path(p).is_file()]
    aviso_arq = [f"arquivo não encontrado e ignorado: {p}" for p in list(imagens or []) + list(graficos or []) if not Path(p).is_file()]
    crit = [c for c in (criterios_validacao or []) if str(c).strip()]
    por_classe: dict[str, list[dict]] = {}
    for e in estudos:
        por_classe.setdefault(str(e.get("classe") or "NAO_CLASSIFICADO"), []).append(e)
    validados = [e for e in por_classe.get("VALIDADO", [])]
    sem_ref = [e["nome"] for e in validados if not e.get("validacao_ref")]
    concl = []
    if not estudos:
        concl.append("Nenhum estudo foi fornecido: não há resultado para concluir.")
    for cl, lst in por_classe.items():
        concl.append(f"{len(lst)} resultado(s) da classe {cl}: " + ", ".join(e["nome"] for e in lst) + ".")
    if validados and not crit:
        concl.append("Há resultado marcado VALIDADO, mas nenhum critério de validação foi documentado neste relatório: a marca não pôde ser confirmada aqui.")
    if sem_ref:
        concl.append("Resultado(s) VALIDADO sem referência de validação registrada: " + ", ".join(sem_ref) + ".")
    if estudos and not validados:
        concl.append("Nenhum resultado foi validado; use-os como estimativa, não para liberar projeto.")
    if len(com_mat) < len(folhas):
        concl.append(f"Massa parcial: {len(folhas) - len(com_mat)} de {len(folhas)} peça(s) sem material.")
    rel = {
        "identificacao": {"projeto": getattr(project, "name", ""), "arquivo": str(getattr(project, "path", "") or "(não salvo)"), "gerado_em": time.strftime("%Y-%m-%d %H:%M:%S"), "pecas": len(folhas)},
        "objetivo": objetivo.strip() or NI,
        "geometria": [{"peca": f["nome"], "id": f["id"], "impressao_digital": f["geometria"], "posicao": f["posicao"]} for f in folhas],
        "materiais": {"atribuidos": [{"peca": f["nome"], "material": f["material"], "massa_kg": f["massa_kg"]} for f in com_mat], "sem_material": [f["nome"] for f in folhas if not f["material"]],
                      "massa_parcial_kg": sum(f["massa_kg"] for f in com_mat if f["massa_kg"] is not None)},
        "parametros": parametros or ({"entradas_dos_estudos": {e["nome"]: e.get("entradas") for e in estudos if e.get("entradas")}} if any(e.get("entradas") for e in estudos) else NI),
        "contorno": contorno.strip() or NI,
        "metodo": sorted({str(e["metodo"]) for e in estudos if e.get("metodo")}) or NI,
        "hipoteses": sorted({p for e in estudos for p in (e.get("premissas") or [])}) or NI,
        "resultados": {cl: [{"nome": e["nome"], "valores": e.get("valores") or {}, "validacao_ref": e.get("validacao_ref") or ""} for e in lst] for cl, lst in por_classe.items()} or NI,
        "graficos": grf_ok or NI,
        "imagens_3d": imgs_ok or NI,
        "limitacoes": sorted({x for e in estudos for x in (e.get("limitacoes") or [])} | set(aviso_arq)) or NI,
        "criterios_validacao": crit or "Nenhum critério de validação documentado: nenhum resultado pode ser declarado validado por este relatório.",
        "conclusao": concl,
    }
    return rel


def para_json(rel: dict) -> str:
    return json.dumps(rel, ensure_ascii=False, indent=1, default=str)


def _md(v, nivel=0) -> list[str]:
    pad = "  " * nivel
    if isinstance(v, dict):
        out = []
        for k, x in v.items():
            if isinstance(x, (dict, list)) and x:
                out.append(f"{pad}- **{k}:**"); out += _md(x, nivel + 1)
            else:
                out.append(f"{pad}- **{k}:** {x if not isinstance(x, (dict, list)) else '—'}")
        return out
    if isinstance(v, list):
        out = []
        for x in v:
            if isinstance(x, (dict, list)):
                out.append(f"{pad}-"); out += _md(x, nivel + 1)
            else:
                out.append(f"{pad}- {x}")
        return out
    return [f"{pad}{v}"]


def para_markdown(rel: dict) -> str:
    L = [f"# Relatório técnico — {rel['identificacao']['projeto']}", ""]
    for s in SECOES:
        L += [f"## {TITULOS[s]}", ""] + _md(rel[s]) + [""]
    L.append("_Relatório gerado pelo NEXUS a partir de dados de módulos; não substitui revisão técnica._")
    return "\n".join(L)


def para_pdf(rel: dict, caminho) -> Path:
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer
    from xml.sax.saxutils import escape
    ss = getSampleStyleSheet()
    el = [Paragraph(escape(f"Relatório técnico — {rel['identificacao']['projeto']}"), ss["Title"])]
    for s in SECOES:
        el.append(Paragraph(escape(TITULOS[s]), ss["Heading2"]))
        for ln in _md(rel[s]):
            el.append(Paragraph(escape(ln.replace("**", "")).replace(" ", "&nbsp;", 0) or "&nbsp;", ss["BodyText"]))
        if s in ("graficos", "imagens_3d") and isinstance(rel[s], list):
            for p in rel[s]:
                try:
                    el += [Image(p, width=120 * mm, height=80 * mm, kind="proportional"), Spacer(1, 4 * mm)]
                except Exception:  # noqa: BLE001 - imagem ilegível: o caminho já está listado no texto
                    pass
    el.append(Paragraph("Relatório gerado pelo NEXUS a partir de dados de módulos; não substitui revisão técnica.", ss["Italic"]))
    p = Path(caminho)
    SimpleDocTemplate(str(p), pagesize=(210 * mm, 297 * mm), leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm, bottomMargin=15 * mm, title="Relatório técnico NEXUS").build(el)
    return p


def exportar(rel: dict, caminho) -> Path:
    p = Path(caminho)
    ext = p.suffix.lower()
    if ext == ".pdf":
        return para_pdf(rel, p)
    if ext == ".json":
        p.write_text(para_json(rel), encoding="utf-8"); return p
    if ext in (".md", ".markdown"):
        p.write_text(para_markdown(rel), encoding="utf-8"); return p
    raise ValueError("extensão não suportada: use .pdf, .json ou .md")
