"""Relatório PDF de RESULTADOS / laudo simplificado de peça (V3.6).

Uma seção por TracedResult: classe, método, entradas, valores, premissas, limitações e o parecer do NEXUS INTELLIGENCE (regras). Resultado NAO_EXECUTADO
aparece sem números. Com `laudo=True` acrescenta identificação da peça, aviso de que é ESTIMATIVA DE ENGENHARIA (não homologação, não ensaio, não
substitui responsável técnico) e campo em branco para o responsável. Nada aqui valida um resultado: a classe original é só repetida.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from . import intelligence as I
from .report import FONT, FONT_B, INK, CYAN, GRID, WARN


def _esc(x) -> str:
    return str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _fmt(v) -> str:
    return f"{v:.6g}" if isinstance(v, float) else _esc(v)


def gerar(resultados: list, caminho, titulo: str = "Relatório de resultados NEXUS", versao: str = "", laudo: bool = False,
          peca: str = "", responsavel: str = "") -> Path:
    if not resultados:
        raise ValueError("nenhum resultado para o relatório")
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Heading1"], fontName=FONT_B, textColor=INK, fontSize=18)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName=FONT_B, textColor=CYAN, fontSize=12, spaceBefore=8)
    b = ParagraphStyle("b", parent=ss["BodyText"], fontName=FONT, fontSize=9, leading=12)
    w = ParagraphStyle("w", parent=b, textColor=WARN)
    doc = SimpleDocTemplate(str(caminho), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm, title=titulo)
    S = [Paragraph(_esc(titulo), h1), Paragraph(f"NEXUS {_esc(versao)} · {datetime.now():%d/%m/%Y %H:%M}", b)]
    if laudo:
        S += [Spacer(1, 6), Paragraph(f"<b>Peça / item:</b> {_esc(peca or '(não informado)')}", b),
              Paragraph("ESTIMATIVA DE ENGENHARIA: este documento resume cálculos do NEXUS com os dados informados pelo usuário. NÃO é homologação, "
                        "NÃO é ensaio e NÃO substitui a análise de um responsável técnico. Materiais e cargas são do usuário.", w),
              Paragraph(f"<b>Responsável técnico:</b> {_esc(responsavel) or '______________________________'}", b)]
    for i, r in enumerate(resultados, 1):
        d = r.to_dict() if hasattr(r, "to_dict") else dict(r)
        S += [Paragraph(f"{i}. {_esc(d.get('nome', '?'))} — <b>{_esc(d.get('classe', '?'))}</b>", h2),
              Paragraph(f"Método: {_esc(d.get('metodo', ''))}" + (f" · solver: {_esc(d['solver'])} {_esc(d.get('solver_versao', ''))}" if d.get("solver") else ""), b)]
        if d.get("classe") == "NAO_EXECUTADO":
            S.append(Paragraph("NÃO EXECUTADO — nenhum número foi produzido.", w))
        for titulo_t, dic in (("Entradas", d.get("entradas")), ("Valores", d.get("valores"))):
            if dic and d.get("classe") != "NAO_EXECUTADO" or (titulo_t == "Entradas" and dic):
                rows = [[_esc(k), _fmt(v)] for k, v in dic.items() if not isinstance(v, (list, dict))]
                if rows:
                    t = Table([[titulo_t, ""]] + rows, colWidths=[70 * mm, 100 * mm])
                    t.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), FONT), ("FONTSIZE", (0, 0), (-1, -1), 8), ("GRID", (0, 0), (-1, -1), 0.25, GRID),
                                           ("FONTNAME", (0, 0), (0, 0), FONT_B), ("BACKGROUND", (0, 0), (-1, 0), CYAN), ("TEXTCOLOR", (0, 0), (-1, 0), INK)]))
                    S += [Spacer(1, 3), t]
        for lab, key in (("Premissas", "premissas"), ("Limitações", "limitacoes")):
            for x in d.get(key) or []:
                S.append(Paragraph(f"{lab[:-1] if False else lab}: {_esc(x)}", w if key == "limitacoes" else b))
        try:
            p = I.interpretar(d)
            S += [Spacer(1, 3), Paragraph("<b>Parecer (NEXUS INTELLIGENCE — por regras, não é IA generativa):</b>", b)]
            S += [Paragraph(_esc(l), b) for l in p.texto().splitlines() if l.strip()]
        except Exception as e:  # noqa: BLE001
            S.append(Paragraph(f"Parecer indisponível: {_esc(e)}", w))
        if i < len(resultados): S.append(Spacer(1, 6))
    doc.build(S)
    return Path(caminho)
