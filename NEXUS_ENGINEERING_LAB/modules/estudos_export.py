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

TIPOS = ("comparacao", "tornado", "otimizacao", "fatorial", "monte_carlo", "pareto", "stint", "validacao", "calibracao", "dinamica_lateral", "freio_termico")
_TITULO = {"comparacao": "Comparação A/B de volta", "tornado": "Sensibilidade (tornado)", "otimizacao": "Otimização de parâmetros",
           "fatorial": "Fatorial 2^k (efeitos e interações)", "monte_carlo": "Monte Carlo (propagação de incerteza)", "pareto": "Frente de Pareto", "stint": "Stint (várias voltas)", "validacao": "Validação com telemetria do usuário", "calibracao": "Calibração de parâmetros", "dinamica_lateral": "Dinâmica lateral linear (2 GDL)", "freio_termico": "Freios: energia e temperatura de disco"}
_CHAVE = {"comparacao": ("campos",), "tornado": ("linhas", "variacao_pct"), "otimizacao": ("parametros", "tempo_otimo_s"), "fatorial": ("ordenados", "execucoes"),
          "monte_carlo": ("correlacoes", "p95_s"), "pareto": ("frente", "objetivos"), "stint": ("linhas", "taxas_por_volta"), "validacao": ("metricas", "veredito"), "calibracao": ("parametros_calibrados", "numero_condicao"), "dinamica_lateral": ("varredura", "limitacoes"), "freio_termico": ("voltas", "energia_frenagem_MJ")}


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
    faltam = [k for k in _CHAVE[tipo] if not isinstance(estudo, dict) or k not in estudo]
    if faltam:
        raise ValueError(f"o estudo não parece ser do tipo '{tipo}' (falta '{faltam[0]}')")


def linhas_tabela(tipo: str, e: dict) -> tuple[list[str], list[list]]:
    _checar(tipo, e)
    if tipo == "comparacao":
        return (["campo", "A", "B", "B-A", "B-A [%]", "melhor"],
                [[k, d["A"], d["B"], d["delta"], d["delta_pct"], d["melhor"]] for k, d in e["campos"].items()])
    if tipo == "tornado":
        return (["parametro", "valor", "tempo(-x%) [s]", "tempo(+x%) [s]", "delta(-) [s]", "delta(+) [s]", "amplitude [s]"],
                [[r["campo"], r["valor"], r["t_menos_s"], r["t_mais_s"], r["d_menos_s"], r["d_mais_s"], r["amplitude_s"]] for r in e["linhas"]])
    if tipo == "fatorial":
        return (["fatores", "efeito_s"], [[" x ".join(r["fatores"]), r["efeito_s"]] for r in e["ordenados"]])
    if tipo == "monte_carlo":
        return (["estatistica", "valor"], [["n", e["n"]], ["semente", e["semente"]], ["tempo_base_s", e["tempo_base_s"]], ["media_s", e["media_s"]], ["desvio_s", e["desvio_s"]],
                                           ["p05_s", e["p05_s"]], ["p50_s", e["p50_s"]], ["p95_s", e["p95_s"]], ["min_s", e["min_s"]], ["max_s", e["max_s"]]]
                + [["correlacao_" + r["campo"], r["correlacao"]] for r in e["correlacoes"]])
    if tipo == "pareto":
        a, b = e["objetivos"]
        ks = list(e["frente"][0]["parametros"]) if e["frente"] else []
        return ([a, b, *ks, "equivalentes"], [[*p["objetivos"], *[p["parametros"][k] for k in ks], p.get("equivalentes", 0)] for p in e["frente"]])
    if tipo == "freio_termico":
        return (["volta", "T_pico_diant_C", "T_pico_tras_C", "T_media_diant_C", "T_media_tras_C", "T_fim_diant_C", "T_fim_tras_C"],
                [[x["volta"], x["T_pico_diant_C"], x["T_pico_tras_C"], x["T_media_diant_C"], x["T_media_tras_C"], x["T_fim_diant_C"], x["T_fim_tras_C"]] for x in e["voltas"]])
    if tipo == "dinamica_lateral":
        return (["U_ms", "tipo", "K_graus_por_g", "ganho_guinada_1_s", "estavel", "wn_rad_s", "zeta", "v_caracteristica_ms", "v_critica_ms"],
                [[g["velocidade_ms"], g["tipo"], g["gradiente_subesterco_graus_por_g"], g["ganho_guinada_1_por_s"], g["estavel"], g["wn_rad_s"], g["zeta"],
                  g["velocidade_caracteristica_ms"], g["velocidade_critica_ms"]] for g in e["varredura"]])
    if tipo == "calibracao":
        return (["parametro", "inicial", "calibrado", "incerteza_aprox"],
                [[k, e["valores_iniciais"][k], v, e["incerteza_aprox"].get(k)] for k, v in e["parametros_calibrados"].items()]
                + [["rmse_treino_antes_kmh", e["treino"]["rmse_antes_kmh"], e["treino"]["rmse_depois_kmh"], None], ["numero_condicao", None, e["numero_condicao"], None]]
                + ([["rmse_trecho_nao_usado_kmh", e["teste"]["rmse_antes_kmh"], e["teste"]["rmse_depois_kmh"], None]] if e["teste"] else []))
    if tipo == "validacao":
        m = e["metricas"]
        return (["item", "valor"], [[k, v] for k, v in m.items()] + [[f"setor_{x['setor']}_rmse_kmh", x["rmse_kmh"]] for x in e["setores"]]
                + [[f"criterio_{v['criterio']}", f"{v['valor']:.4g} <= {v['limite_seu']:g}: {'atende' if v['atende'] else 'NAO atende'}"] for v in e["veredito"]])
    if tipo == "stint":
        ks = list(e["taxas_por_volta"])
        return (["volta", "tempo_s", "acumulado_s", *ks], [[r["volta"], r["tempo_s"], r["acumulado_s"], *[r["parametros"][k] for k in ks]] for r in e["linhas"]])
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


def _elementos(tipo: str, estudo: dict) -> list:
    """Flowables de um estudo (título, resumo, tabela, limitações) — usados no PDF individual e no consolidado."""
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
    el = [Paragraph(_txt(_TITULO[tipo]), st["Title"]),
          Paragraph(_txt(f"Classe: {estudo.get('classe', '—')} · Solver: {estudo.get('solver', '—')} · Gerado em {datetime.now():%Y-%m-%d %H:%M}"), st["BodyText"]), Spacer(1, 4 * mm)]
    if tipo == "otimizacao":
        el += [Paragraph(_txt(f"Tempo base {estudo['tempo_base_s']:.3f} s → melhor encontrado {estudo['tempo_otimo_s']:.3f} s "
                               f"(ganho {estudo['ganho_s']:+.3f} s; {estudo['avaliacoes']} avaliações)"), st["BodyText"]), Spacer(1, 3 * mm)]
    if tipo == "validacao":
        el += [Paragraph(_txt(f"Classe do resultado: {estudo['classe']} · " + " ".join(estudo.get("avisos", []))), st["BodyText"]), Spacer(1, 3 * mm)]
    if tipo == "stint":
        el += [Paragraph(_txt(f"{estudo['voltas']} voltas · total {estudo['total_s']:.3f} s · taxas por volta (SUAS): " + ", ".join(f"{k} {v:+g}" for k, v in estudo["taxas_por_volta"].items())), st["BodyText"]), Spacer(1, 3 * mm)]
    if tipo == "monte_carlo":
        el += [Paragraph(_txt("Incertezas declaradas (SUAS): " + "; ".join(f"{k}: {d} {p:g} %" for k, (d, p) in estudo["incertezas"].items())), st["BodyText"]), Spacer(1, 3 * mm)]
    if tipo == "tornado":
        el += [Paragraph(_txt(f"Tempo base {estudo['tempo_base_s']:.3f} s · variação ±{estudo['variacao_pct']:g} %"), st["BodyText"]), Spacer(1, 3 * mm)]
    t = Table([cab] + [[fmt(c) for c in ln] for ln in linhas], repeatRows=1)
    t.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), FONT), ("FONTNAME", (0, 0), (-1, 0), FONT_B), ("FONTSIZE", (0, 0), (-1, -1), 8),
                           ("GRID", (0, 0), (-1, -1), 0.3, colors.grey), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef3"))]))
    el += [t, Spacer(1, 5 * mm), Paragraph("Limitações", st["Heading2"])]
    el += [Paragraph(_txt("• " + x), st["BodyText"]) for x in estudo.get("limitacoes", [])]
    return el


def _doc(caminho, titulo):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate
    return SimpleDocTemplate(str(caminho), pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm, bottomMargin=15 * mm, title=titulo)


def para_pdf(tipo: str, estudo: dict, caminho) -> Path:
    caminho = Path(caminho)
    _doc(caminho, _TITULO[tipo]).build(_elementos(tipo, estudo))
    return caminho


def relatorio_consolidado(estudos, caminho, titulo: str = "Relatório de estudos NEXUS", contexto: str = "") -> Path:
    """Um PDF com vários estudos [(tipo, resultado), …]: capa com índice, aviso geral e uma seção por estudo. `contexto` é texto livre SEU (ex.: carro/pista usados)."""
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import PageBreak, Paragraph, Spacer
    from modules.report import FONT, FONT_B, _txt
    if not estudos:
        raise ValueError("informe ao menos um estudo")
    for tipo, e in estudos:
        _checar(tipo, e)
    st = getSampleStyleSheet()
    for n in ("Title", "Heading2"):
        st[n].fontName = FONT_B
    st["BodyText"].fontName = FONT
    el = [Paragraph(_txt(titulo), st["Title"]), Paragraph(_txt(f"Gerado em {datetime.now():%Y-%m-%d %H:%M} · {len(estudos)} estudo(s)"), st["BodyText"])]
    if contexto.strip():
        el.append(Paragraph(_txt("Contexto informado: " + contexto.strip()), st["BodyText"]))
    el += [Spacer(1, 4 * mm), Paragraph("Índice", st["Heading2"])]
    el += [Paragraph(_txt(f"{i}. {_TITULO[t]} — classe {e.get('classe', '—')}"), st["BodyText"]) for i, (t, e) in enumerate(estudos, 1)]
    el += [Spacer(1, 4 * mm), Paragraph("Aviso", st["Heading2"]),
           Paragraph(_txt("Todos os resultados vêm do simulador quase-estacionário simplificado do NEXUS (ponto material, μ constante); parâmetros, incertezas, taxas e pistas são "
                          "os informados por quem executou o estudo. Não representam o carro real nem foram validados contra dados de equipe."), st["BodyText"])]
    for t, e in estudos:
        el += [PageBreak()] + _elementos(t, e)
    caminho = Path(caminho)
    _doc(caminho, titulo).build(el)
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
