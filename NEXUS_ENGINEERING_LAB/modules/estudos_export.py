"""V8.0 — Exporta estudos de volta (A/B, sensibilidade, otimização) para CSV, JSON e PDF.

O arquivo repete a CLASSE do resultado, o solver, os parâmetros de entrada e as LIMITAÇÕES — nada é omitido nem “arredondado a favor”.
Tipos: 'comparacao' (comparacao.comparar_voltas), 'tornado' (otimizacao.tornado), 'otimizacao' (otimizacao.otimizar).
"""
from __future__ import annotations

import csv
import io
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path

TIPOS = ("comparacao", "tornado", "otimizacao")
_TITULO = {"comparacao": "Comparação A/B de volta", "tornado": "Sensibilidade (tornado)", "otimizacao": "Otimização de parâmetros"}


def _limpo(o):
    """Remove objetos pesados (resultados completos) e converte dataclasses para dict, deixando só dados serializáveis."""
    if is_dataclass(o) and not isinstance(o, type):
        return _limpo(asdict(o))
    if isinstance(o, dict):
        return {k: _limpo(v) for k, v in o.items() if not str(k).startswith("resultado_")}
    if isinstance(o, (list, tuple)):
        return [_limpo(v) for v in o]
    return o


def _checar(tipo, estudo):
    if tipo not in TIPOS:
        raise ValueError(f"tipo desconhecido: {tipo} (use {', '.join(TIPOS)})")
    chave = {"comparacao": "campos", "tornado": "linhas", "otimizacao": "parametros"}[tipo]
    if not isinstance(estudo, dict) or chave not in estudo:
        raise ValueError(f"o estudo não parece ser do tipo '{tipo}' (falta '{chave}')")


def linhas_tabela(tipo: str, e: dict) -> tuple[list[str], list[list]]:
    _checar(tipo, e)
    if tipo == "comparacao":
        return (["campo", "A", "B", "B-A", "B-A [%]", "melhor"],
                [[k, d["A"], d["B"], d["delta"], d["delta_pct"], d["melhor"]] for k, d in e["campos"].items()])
    if tipo == "tornado":
        return (["parametro", "valor", "tempo(-x%) [s]", "tempo(+x%) [s]", "delta(-) [s]", "delta(+) [s]", "amplitude [s]"],
                [[r["campo"], r["valor"], r["t_menos_s"], r["t_mais_s"], r["d_menos_s"], r["d_mais_s"], r["amplitude_s"]] for r in e["linhas"]])
    return (["parametro", "valor_otimo", "na_borda"], [[k, v, k in e["na_borda"]] for k, v in e["parametros"].items()])


def para_json(tipo: str, estudo: dict) -> str:
    _checar(tipo, estudo)
    return json.dumps({"tipo": tipo, "titulo": _TITULO[tipo], "gerado_em": datetime.now().isoformat(timespec="seconds"), "estudo": _limpo(estudo)},
                      ensure_ascii=False, indent=1)


def para_csv(tipo: str, estudo: dict) -> str:
    cab, linhas = linhas_tabela(tipo, estudo)
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["# " + _TITULO[tipo], f"classe={estudo.get('classe', '')}", f"solver={estudo.get('solver', '')}"])
    w.writerow(cab)
    w.writerows(linhas)
    for x in estudo.get("limitacoes", []):
        w.writerow(["# limitacao: " + x])
    return buf.getvalue()


def para_pdf(tipo: str, estudo: dict, caminho) -> Path:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from modules.report import FONT, FONT_B, _txt
    cab, linhas = linhas_tabela(tipo, estudo)
    st = getSampleStyleSheet()
    for n in ("Title", "Heading2", "BodyText"):
        st[n].fontName = FONT_B if n != "BodyText" else FONT
    fmt = lambda x: "—" if x is None else (f"{x:.5g}" if isinstance(x, float) else str(x))  # noqa: E731
    caminho = Path(caminho)
    doc = SimpleDocTemplate(str(caminho), pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm, bottomMargin=15 * mm, title=_TITULO[tipo])
    el = [Paragraph(_txt(_TITULO[tipo]), st["Title"]),
          Paragraph(_txt(f"Classe: {estudo.get('classe', '—')} · Solver: {estudo.get('solver', '—')} · Gerado em {datetime.now():%Y-%m-%d %H:%M}"), st["BodyText"]), Spacer(1, 4 * mm)]
    if tipo == "otimizacao":
        el += [Paragraph(_txt(f"Tempo base {estudo['tempo_base_s']:.3f} s → melhor encontrado {estudo['tempo_otimo_s']:.3f} s "
                               f"(ganho {estudo['ganho_s']:+.3f} s; {estudo['avaliacoes']} avaliações)"), st["BodyText"]), Spacer(1, 3 * mm)]
    if tipo == "tornado":
        el += [Paragraph(_txt(f"Tempo base {estudo['tempo_base_s']:.3f} s · variação ±{estudo['variacao_pct']:g} %"), st["BodyText"]), Spacer(1, 3 * mm)]
    t = Table([cab] + [[fmt(c) for c in ln] for ln in linhas], repeatRows=1)
    t.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), FONT), ("FONTNAME", (0, 0), (-1, 0), FONT_B), ("FONTSIZE", (0, 0), (-1, -1), 8),
                           ("GRID", (0, 0), (-1, -1), 0.3, colors.grey), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef3"))]))
    el += [t, Spacer(1, 5 * mm), Paragraph("Limitações", st["Heading2"])]
    el += [Paragraph(_txt("• " + x), st["BodyText"]) for x in estudo.get("limitacoes", [])]
    doc.build(el)
    return caminho


def exportar(tipo: str, estudo: dict, caminho) -> Path:
    """Formato pela extensão: .csv, .json ou .pdf."""
    p = Path(caminho)
    ext = p.suffix.lower()
    if ext == ".csv":
        p.write_text(para_csv(tipo, estudo), encoding="utf-8", newline="")
    elif ext == ".json":
        p.write_text(para_json(tipo, estudo), encoding="utf-8")
    elif ext == ".pdf":
        para_pdf(tipo, estudo, p)
    else:
        raise ValueError("extensão não suportada (use .csv, .json ou .pdf)")
    return p
