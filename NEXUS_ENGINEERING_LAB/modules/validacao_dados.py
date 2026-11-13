"""V30 — Validação do modelo de volta contra TELEMETRIA REAL SUA (CSV).

Fluxo: você fornece uma volta medida (distância × velocidade); o NEXUS roda o `lapsim` na mesma pista e compara.
Classes: sem tolerâncias suas → só métricas (SIMULACAO_NUMERICA, “não validado”). Com tolerâncias SUAS e todas atendidas → VALIDADO
**apenas para esta telemetria, esta pista e estas tolerâncias** (não generaliza para outras voltas, carros ou condições).
O NEXUS não define o que é “bom o bastante”: o critério é seu. Nenhum dado é inventado ou completado.
"""
from __future__ import annotations

import math
from pathlib import Path

from . import lapsim

_ALIAS_S = ("distancia_m", "distancia", "s_m", "s", "dist", "distance", "distance_m")
_ALIAS_V = ("v_kmh", "velocidade_kmh", "speed_kmh", "velocidade", "speed", "v_ms", "velocidade_ms", "speed_ms")


class TelemetriaError(ValueError):
    pass


def _norm(h):
    import re
    import unicodedata
    h = unicodedata.normalize("NFKD", h.strip().lower()).encode("ascii", "ignore").decode().replace("/", "")
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]", "_", h)).strip("_")


def ler_telemetria(origem) -> dict:
    """CSV com cabeçalho. Colunas aceitas: distância (m) e velocidade (km/h por padrão; sufixo `_ms` = m/s). `tempo_s` opcional."""
    if isinstance(origem, Path) or (isinstance(origem, str) and "\n" not in origem and len(origem) < 4096 and Path(origem).is_file()):
        texto = Path(origem).read_text(encoding="utf-8-sig")
    else:
        texto = str(origem)
    linhas = [ln for ln in texto.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    if len(linhas) < 3:
        raise TelemetriaError("telemetria vazia ou com menos de 2 amostras")
    sep = ";" if linhas[0].count(";") >= linhas[0].count(",") and ";" in linhas[0] else ("\t" if "\t" in linhas[0] else ",")
    cab = [_norm(h) for h in linhas[0].split(sep)]
    ic = next((i for i, h in enumerate(cab) if h in _ALIAS_S), None)
    iv = next((i for i, h in enumerate(cab) if h in _ALIAS_V), None)
    if ic is None or iv is None:
        raise TelemetriaError("cabeçalho deve ter uma coluna de distância (distancia_m) e uma de velocidade (v_kmh ou v_ms); recebido: " + ", ".join(cab))
    it = next((i for i, h in enumerate(cab) if h in ("tempo_s", "tempo", "time", "time_s", "t")), None)
    ms = cab[iv].endswith("ms") or cab[iv] in ("velocidade", "speed") and False
    s, v, t = [], [], []
    for n, ln in enumerate(linhas[1:], 2):
        p = ln.split(sep)
        try:
            s.append(float(p[ic].replace(",", ".") if sep != "," else p[ic]))
            vv = float(p[iv].replace(",", ".") if sep != "," else p[iv])
            v.append(vv * 3.6 if ms else vv)
            if it is not None:
                t.append(float(p[it].replace(",", ".") if sep != "," else p[it]))
        except (ValueError, IndexError):
            raise TelemetriaError(f"linha {n}: valor inválido ('{ln.strip()}')")
        if not (math.isfinite(s[-1]) and math.isfinite(v[-1])):
            raise TelemetriaError(f"linha {n}: valor não finito")
        if v[-1] <= 0:
            raise TelemetriaError(f"linha {n}: velocidade deve ser > 0 (recebido {v[-1]:g} km/h)")
        if len(s) > 1 and s[-1] <= s[-2]:
            raise TelemetriaError(f"linha {n}: a distância deve crescer (recebido {s[-1]:g} após {s[-2]:g})")
    return {"s_m": s, "v_kmh": v, "t_s": t or None}


def _interp(x, xs, ys):
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    lo, hi = 0, len(xs) - 1
    while hi - lo > 1:
        m = (lo + hi) // 2
        if xs[m] <= x:
            lo = m
        else:
            hi = m
    return ys[lo] + (x - xs[lo]) / (xs[hi] - xs[lo]) * (ys[hi] - ys[lo])


def _tempo_de_perfil(s, v_kmh):
    return sum(2 * (s[i + 1] - s[i]) / ((v_kmh[i] + v_kmh[i + 1]) / 3.6) for i in range(len(s) - 1))


def validar(carro: lapsim.Carro, telemetria: dict, pista=None, ds: float = 3.0, tolerancias: dict | None = None,
            normalizar_distancia: bool = False, setores: int = 5) -> dict:
    """Compara a velocidade simulada com a medida em cada ponto da malha do simulador (a medida é interpolada linearmente).
    `tolerancias` (SUAS, opcionais): {'rmse_kmh': x, 'vies_kmh_abs': x, 'tempo_pct_abs': x, 'max_abs_kmh': x}. `normalizar_distancia`: reescala a distância medida
    para o comprimento simulado (use só se a pista medida é a mesma e o odômetro tem erro de escala)."""
    r = lapsim.volta(carro, pista, ds)
    s_sim, v_sim = r.valores["s_m"], [x * 3.6 for x in r.valores["v_ms"]]
    s_med, v_med = list(telemetria["s_m"]), list(telemetria["v_kmh"])
    if len(s_med) < 3:
        raise TelemetriaError("telemetria com menos de 3 amostras")
    s0 = s_med[0]
    s_med = [x - s0 for x in s_med]
    comp_sim, comp_med = s_sim[-1] + (s_sim[1] - s_sim[0]), s_med[-1] + s_med[-1] / (len(s_med) - 1)     # comprimento da volta = último ponto + 1 passo
    diff_pct = 100.0 * (comp_med - comp_sim) / comp_sim
    avisos = []
    if normalizar_distancia:
        k = comp_sim / comp_med
        s_med = [x * k for x in s_med]
        comp_med = comp_med * k
        avisos.append(f"Distância medida reescalada por {k:.5f} (escolha sua); confira se a pista é a mesma.")
    elif abs(diff_pct) > 1.0:
        avisos.append(f"O comprimento medido ({comp_med:.0f} m) difere {diff_pct:+.1f} % do simulado ({comp_sim:.0f} m): a comparação ponto a ponto pode estar deslocada "
                      "(pista diferente ou odômetro com escala errada — veja `normalizar_distancia`).")
    pts = [(s, vs, _interp(s, s_med, v_med)) for s, vs in zip(s_sim, v_sim) if s <= s_med[-1]]
    if len(pts) < 10:
        raise TelemetriaError("sobreposição insuficiente entre a telemetria e a pista simulada")
    err = [vs - vm for _, vs, vm in pts]
    n = len(err)
    vies = sum(err) / n
    rmse = math.sqrt(sum(e * e for e in err) / n)
    mae = sum(abs(e) for e in err) / n
    mx = max(err, key=abs)
    mm = sum(vm for *_, vm in pts) / n
    ms_ = sum(vs for _, vs, _ in pts) / n
    sxx = sum((vm - mm) ** 2 for *_, vm in pts)
    syy = sum((vs - ms_) ** 2 for _, vs, _ in pts)
    corr = sum((vm - mm) * (vs - ms_) for _, vs, vm in pts) / math.sqrt(sxx * syy) if sxx > 0 and syy > 0 else 0.0
    t_sim = r.valores["tempo_s"]
    t_med = telemetria["t_s"][-1] - telemetria["t_s"][0] if telemetria.get("t_s") else _tempo_de_perfil(s_med, v_med)
    origem_t = "coluna tempo_s da telemetria" if telemetria.get("t_s") else "integral de ds/v da velocidade medida"
    nsec = max(1, min(setores, n // 5))
    setor = []
    for k in range(nsec):
        a, b = k * n // nsec, (k + 1) * n // nsec
        e = err[a:b]
        setor.append({"setor": k + 1, "de_m": pts[a][0], "ate_m": pts[b - 1][0], "rmse_kmh": math.sqrt(sum(x * x for x in e) / len(e)), "vies_kmh": sum(e) / len(e)})
    met = {"n_pontos": n, "vies_kmh": vies, "rmse_kmh": rmse, "mae_kmh": mae, "max_abs_kmh": abs(mx), "correlacao": corr,
           "tempo_sim_s": t_sim, "tempo_medido_s": t_med, "tempo_pct": 100.0 * (t_sim - t_med) / t_med, "origem_tempo_medido": origem_t}
    classe, veredito = "SIMULACAO_NUMERICA", []
    if tolerancias:
        regras = {"rmse_kmh": ("rmse_kmh", rmse), "vies_kmh_abs": ("viés absoluto [km/h]", abs(vies)), "tempo_pct_abs": ("erro de tempo absoluto [%]", abs(met["tempo_pct"])),
                  "max_abs_kmh": ("erro máximo absoluto [km/h]", abs(mx))}
        for k in tolerancias:
            if k not in regras:
                raise ValueError(f"tolerância desconhecida: {k} (use {', '.join(regras)})")
        for k, lim in tolerancias.items():
            nome, val = regras[k]
            veredito.append({"criterio": k, "descricao": nome, "valor": val, "limite_seu": lim, "atende": val <= lim})
        if veredito and all(x["atende"] for x in veredito):
            classe = "VALIDADO"
    lim = ["Comparação de UMA volta medida com o modelo simplificado (ponto material, μ constante, sem vento/pneu/temperatura/inclinação).",
           "Velocidade medida interpolada linearmente na malha do simulador; erros de sincronismo de distância contam como erro do modelo."]
    if classe == "VALIDADO":
        lim.append("VALIDADO só para esta telemetria, esta pista e as tolerâncias que VOCÊ definiu; não generaliza para outras voltas, carros ou condições.")
    elif not tolerancias:
        lim.append("Sem tolerâncias suas, o resultado são apenas métricas: o modelo NÃO é declarado validado.")
    else:
        lim.append("Pelo menos um critério seu NÃO foi atendido: o modelo NÃO é validado para esta telemetria.")
    ref = (f"telemetria do usuário ({n} pontos comparados); critérios do usuário: " + "; ".join(f"{v['criterio']} <= {v['limite_seu']:g}" for v in veredito)) if classe == "VALIDADO" else ""
    return {"classe": classe, "solver": "NEXUS-LapSim 1.0", "validacao_ref": ref, "metricas": met, "setores": setor, "veredito": veredito, "avisos": avisos, "limitacoes": lim,
            "comparacao": {"s_m": [p[0] for p in pts], "v_sim_kmh": [p[1] for p in pts], "v_med_kmh": [p[2] for p in pts]}}


def texto(r: dict) -> str:
    m = r["metricas"]
    L = [f"Validação com telemetria — classe {r['classe']} ({m['n_pontos']} pontos)",
         f"  viés {m['vies_kmh']:+.2f} km/h · RMSE {m['rmse_kmh']:.2f} · MAE {m['mae_kmh']:.2f} · erro máx {m['max_abs_kmh']:.2f} km/h · correlação {m['correlacao']:.4f}",
         f"  tempo simulado {m['tempo_sim_s']:.3f} s × medido {m['tempo_medido_s']:.3f} s ({m['tempo_pct']:+.2f} %; medido por {m['origem_tempo_medido']})", "  por setor:"]
    L += [f"    {s['setor']}: {s['de_m']:.0f}–{s['ate_m']:.0f} m  RMSE {s['rmse_kmh']:.2f}  viés {s['vies_kmh']:+.2f} km/h" for s in r["setores"]]
    if r["veredito"]:
        L.append("  critérios seus:")
        L += [f"    {'✔' if v['atende'] else '✘'} {v['descricao']}: {v['valor']:.3f} (limite {v['limite_seu']:g})" for v in r["veredito"]]
    L += ["⚠ " + x for x in r["avisos"] + r["limitacoes"]]
    return "\n".join(L)


def para_csv_exemplo(carro: lapsim.Carro, pista=None, ds: float = 5.0) -> str:
    """Gera um CSV NO FORMATO esperado a partir do SIMULADOR (para testar o fluxo) — NÃO é telemetria real e vem marcado como tal."""
    r = lapsim.volta(carro, pista, ds)
    return "# MODELO DE FORMATO gerado pelo simulador — NÃO é telemetria real\ndistancia_m,v_kmh\n" + "".join(f"{s:.1f},{v * 3.6:.2f}\n" for s, v in zip(r.valores["s_m"], r.valores["v_ms"]))
