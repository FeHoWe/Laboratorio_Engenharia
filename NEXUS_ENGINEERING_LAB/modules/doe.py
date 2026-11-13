"""V11–V14 — Estudos estatísticos e multiobjetivo sobre a simulação de volta (`lapsim`).

  fatorial     V11  fatorial completo 2^k (k ≤ 6): efeitos principais E interações de 2 fatores no tempo de volta.
  monte_carlo  V12  propagação de incerteza: distribui os parâmetros que VOCÊ declarou (normal/uniforme em torno do valor-base) e mostra a distribuição do tempo.
  pareto       V13  grade de parâmetros → frente de Pareto (minimizar dois objetivos, por padrão tempo × energia elétrica usada).
  stint        V14  várias voltas com taxas de variação por volta INFORMADAS POR VOCÊ (massa, μ…) — não é modelo de combustível nem de pneu.

Honestidade: as incertezas e as taxas são SUAS (o NEXUS não as inventa); tudo é calculado pelo MESMO solver quase-estacionário
(ponto material, μ constante, pista sintética) e vale para este modelo, não para o carro real. O gerador pseudoaleatório (mulberry32) tem
semente fixa, é o mesmo do celular e torna Monte Carlo repetível. Correlação ≠ causalidade; percentis vêm da amostra (n finito).
"""
from __future__ import annotations

import itertools
import math
from dataclasses import asdict, replace

from . import lapsim

_MASC = 0xFFFFFFFF
CLASSE = "SIMULACAO_NUMERICA"
SOLVER = "NEXUS-LapSim 1.0"


def mulberry32(seed: int):
    """PRNG de 32 bits idêntico ao do celular (mulberry32). Devolve uma função sem argumentos → float em [0, 1)."""
    a = seed & _MASC

    def prox():
        nonlocal a
        a = (a + 0x6D2B79F5) & _MASC
        t = ((a ^ (a >> 15)) * (1 | a)) & _MASC
        t = ((t + (((t ^ (t >> 7)) * (61 | t)) & _MASC)) & _MASC) ^ t
        return ((t ^ (t >> 14)) & _MASC) / 4294967296.0
    return prox


def _tempo(c, pista, ds):
    return float(lapsim.volta(c, pista, ds).valores["tempo_s"])


def _campos_ok(base, campos):
    ok = set(asdict(base))
    for k in campos:
        if k not in ok:
            raise ValueError(f"parâmetro desconhecido: {k}")


# ------------------------------------------------------------------------------------------------------------------ V11
def fatorial(base: lapsim.Carro, campos, variacao_pct: float = 5.0, pista=None, ds: float = 3.0) -> dict:
    campos = list(campos or [])
    if not 1 <= len(campos) <= 6:
        raise ValueError("informe de 1 a 6 parâmetros (2^k execuções)")
    if len(set(campos)) != len(campos):
        raise ValueError("parâmetros repetidos")
    if not 0 < variacao_pct <= 50:
        raise ValueError("variacao_pct deve estar em (0, 50]")
    _campos_ok(base, campos)
    for k in campos:
        if getattr(base, k) == 0:
            raise ValueError(f"{k} vale 0: variação relativa nula")
    f = variacao_pct / 100.0
    corridas = []
    for sinais in itertools.product((-1, 1), repeat=len(campos)):
        c = replace(base, **{k: getattr(base, k) * (1 + s * f) for k, s in zip(campos, sinais)})
        corridas.append((sinais, _tempo(c, pista, ds)))
    n = len(corridas)
    t = [r[1] for r in corridas]
    media = sum(t) / n

    def efeito(sinal_fn):
        mais = [ti for (s, ti) in corridas if sinal_fn(s) > 0]
        menos = [ti for (s, ti) in corridas if sinal_fn(s) < 0]
        return sum(mais) / len(mais) - sum(menos) / len(menos)

    principais = [{"fatores": [k], "efeito_s": efeito(lambda s, i=i: s[i])} for i, k in enumerate(campos)]
    inter = []
    for i, j in itertools.combinations(range(len(campos)), 2):
        inter.append({"fatores": [campos[i], campos[j]], "efeito_s": efeito(lambda s, i=i, j=j: s[i] * s[j])})
    todos = sorted(principais + inter, key=lambda r: -abs(r["efeito_s"]))
    return {"classe": CLASSE, "solver": SOLVER, "variacao_pct": variacao_pct, "campos": campos, "execucoes": n, "tempo_medio_s": media,
            "tempo_min_s": min(t), "tempo_max_s": max(t), "principais": principais, "interacoes": inter, "ordenados": todos,
            "limitacoes": ["Efeito = média do tempo nas corridas com o fator em +x % menos a média com ele em −x %; a interação de 2 fatores usa o produto dos sinais dos dois.",
                           "Só níveis extremos (±x %): não detecta curvatura. Vale para o modelo simplificado, não para o carro real."]}


# ------------------------------------------------------------------------------------------------------------------ V12
def _percentil(ordenado, p):
    h = (len(ordenado) - 1) * p
    lo = math.floor(h)
    hi = min(lo + 1, len(ordenado) - 1)
    return ordenado[lo] + (h - lo) * (ordenado[hi] - ordenado[lo])


def _pearson(x, y):
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    if sxx <= 0 or syy <= 0:
        return 0.0
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / math.sqrt(sxx * syy)


def monte_carlo(base: lapsim.Carro, incertezas: dict, n: int = 300, semente: int = 1, pista=None, ds: float = 3.0) -> dict:
    """`incertezas`: {campo: (dist, pct)} com dist 'normal' (σ = pct % do valor-base) ou 'uniforme' (±pct %). Valores NÃO são sugeridos pelo NEXUS."""
    if not incertezas:
        raise ValueError("informe ao menos um parâmetro com incerteza")
    if not 2 <= n <= 20000:
        raise ValueError("n deve estar entre 2 e 20000")
    _campos_ok(base, incertezas)
    nomes = list(incertezas)
    for k, (dist, pct) in incertezas.items():
        if dist not in ("normal", "uniforme"):
            raise ValueError(f"distribuição desconhecida para {k}: {dist} (use normal ou uniforme)")
        if not 0 < pct <= 50:
            raise ValueError(f"pct de {k} deve estar em (0, 50]")
        if getattr(base, k) == 0:
            raise ValueError(f"{k} vale 0: incerteza relativa nula")
    rnd = mulberry32(semente)
    amostras = {k: [] for k in nomes}
    tempos = []
    for _ in range(n):
        mud = {}
        for k in nomes:
            dist, pct = incertezas[k]
            v0 = getattr(base, k)
            if dist == "normal":
                u1, u2 = rnd(), rnd()
                z = math.sqrt(-2.0 * math.log(max(u1, 1e-300))) * math.cos(2.0 * math.pi * u2)
                x = v0 * (1.0 + pct / 100.0 * z)
            else:
                x = v0 * (1.0 + pct / 100.0 * (2.0 * rnd() - 1.0))
            mud[k] = x
            amostras[k].append(x)
        tempos.append(_tempo(replace(base, **mud), pista, ds))
    s = sorted(tempos)
    media = sum(tempos) / n
    desvio = math.sqrt(sum((t - media) ** 2 for t in tempos) / (n - 1))
    corr = sorted(({"campo": k, "correlacao": _pearson(amostras[k], tempos)} for k in nomes), key=lambda r: -abs(r["correlacao"]))
    return {"classe": CLASSE, "solver": SOLVER, "n": n, "semente": semente, "incertezas": {k: list(v) for k, v in incertezas.items()},
            "tempo_base_s": _tempo(base, pista, ds), "media_s": media, "desvio_s": desvio, "min_s": s[0], "max_s": s[-1],
            "p05_s": _percentil(s, 0.05), "p50_s": _percentil(s, 0.50), "p95_s": _percentil(s, 0.95), "correlacoes": corr,
            "limitacoes": ["As incertezas são as que VOCÊ declarou (independentes entre si); o NEXUS não as estima nem valida.",
                           "Distribuição de uma amostra finita com semente fixa (repetível); correlação ≠ causalidade.",
                           "Vale para o modelo simplificado (ponto material, μ constante, pista sintética), não para o carro real."]}


# ------------------------------------------------------------------------------------------------------------------ V13
OBJETIVOS = ("tempo_s", "energia_ers_usada_MJ", "v_max_kmh", "v_media_kmh", "v_min_kmh")
_MIN = {"tempo_s": True, "energia_ers_usada_MJ": True, "v_max_kmh": False, "v_media_kmh": False, "v_min_kmh": False}


def pareto(base: lapsim.Carro, grade: dict, objetivos=("tempo_s", "energia_ers_usada_MJ"), pista=None, ds: float = 3.0) -> dict:
    """Avalia TODAS as combinações da `grade` ({campo: [valores]}) e devolve a frente não-dominada entre os 2 objetivos.
    tempo/energia/v_min... : o NEXUS sabe qual é “melhor” (tempo, energia ↓; velocidades ↑); empates exatos não se dominam."""
    if not grade:
        raise ValueError("informe ao menos um parâmetro na grade")
    if len(objetivos) != 2 or any(o not in OBJETIVOS for o in objetivos) or objetivos[0] == objetivos[1]:
        raise ValueError(f"objetivos: dois distintos entre {', '.join(OBJETIVOS)}")
    _campos_ok(base, grade)
    nomes = list(grade)
    for k in nomes:
        if not grade[k]:
            raise ValueError(f"grade vazia para {k}")
    total = 1
    for k in nomes:
        total *= len(grade[k])
    if total > 2000:
        raise ValueError(f"grade com {total} pontos (máx. 2000)")
    pontos = []
    for combo in itertools.product(*(grade[k] for k in nomes)):
        c = replace(base, **{k: float(v) for k, v in zip(nomes, combo)})
        v = lapsim.volta(c, pista, ds).valores
        pontos.append({"parametros": {k: float(x) for k, x in zip(nomes, combo)}, "objetivos": [float(v[objetivos[0]]), float(v[objetivos[1]])]})
    sinal = [1.0 if _MIN[o] else -1.0 for o in objetivos]            # tudo vira “menor é melhor”

    def domina(a, b):
        fa = [s * x for s, x in zip(sinal, a["objetivos"])]
        fb = [s * x for s, x in zip(sinal, b["objetivos"])]
        return all(x <= y for x, y in zip(fa, fb)) and any(x < y for x, y in zip(fa, fb))

    for p in pontos:
        p["dominado"] = any(domina(q, p) for q in pontos if q is not p)
    frente, vistos = [], {}
    for p in sorted((p for p in pontos if not p["dominado"]), key=lambda p: sinal[0] * p["objetivos"][0]):
        chave = tuple(p["objetivos"])
        if chave in vistos:
            vistos[chave]["equivalentes"] += 1                  # mesmo par de objetivos: mantém o 1º e conta os demais
        else:
            p["equivalentes"] = 0
            vistos[chave] = p
            frente.append(p)
    return {"classe": CLASSE, "solver": SOLVER, "objetivos": list(objetivos), "pontos": pontos, "frente": frente, "avaliacoes": total,
            "limitacoes": ["Pontos com exatamente os mesmos objetivos aparecem uma vez na frente (campo `equivalentes` conta os demais).",
                           "Frente de Pareto SOBRE A GRADE informada (não há garantia de que existam pontos melhores fora dela).",
                           "Vale para o modelo simplificado, não para o carro real; a escolha entre pontos da frente é decisão de engenharia sua."]}


# ------------------------------------------------------------------------------------------------------------------ V14
def stint(base: lapsim.Carro, voltas: int, taxas_por_volta: dict, pista=None, ds: float = 3.0) -> dict:
    """Roda `voltas` voltas; antes da volta i (i = 0…n−1) cada parâmetro de `taxas_por_volta` vale base + i·taxa (linear, SUA taxa; ex.: massa −1,5 kg/volta)."""
    if not 1 <= voltas <= 200:
        raise ValueError("voltas deve estar entre 1 e 200")
    if not taxas_por_volta:
        raise ValueError("informe ao menos uma taxa por volta (o NEXUS não inventa degradação nem consumo)")
    _campos_ok(base, taxas_por_volta)
    linhas, acum = [], 0.0
    for i in range(voltas):
        c = replace(base, **{k: getattr(base, k) + i * r for k, r in taxas_por_volta.items()})
        t = _tempo(c, pista, ds)
        acum += t
        linhas.append({"volta": i + 1, "tempo_s": t, "acumulado_s": acum, "parametros": {k: getattr(c, k) for k in taxas_por_volta}})
    return {"classe": CLASSE, "solver": SOLVER, "voltas": voltas, "taxas_por_volta": dict(taxas_por_volta), "linhas": linhas, "total_s": acum,
            "melhor_volta": min(linhas, key=lambda r: r["tempo_s"])["volta"], "pior_volta": max(linhas, key=lambda r: r["tempo_s"])["volta"],
            "limitacoes": ["As taxas por volta são SUAS e lineares; isto NÃO é modelo de consumo de combustível nem de degradação de pneu.",
                           "Cada volta é quase-estacionária e independente (sem estado térmico/energético entre voltas); energia elétrica reinicia a cada volta.",
                           "Vale para o modelo simplificado, não para o carro real."]}


# ------------------------------------------------------------------------------------------------------------------ textos
def texto_fatorial(r):
    L = [f"Fatorial 2^{len(r['campos'])} ±{r['variacao_pct']:g} % — {r['execucoes']} execuções · tempo médio {r['tempo_medio_s']:.3f} s (faixa {r['tempo_min_s']:.3f}–{r['tempo_max_s']:.3f})",
         f"{'efeito':28}{'Δtempo [s]':>12}"]
    L += [f"{' × '.join(x['fatores']):28}{x['efeito_s']:+12.4f}" for x in r["ordenados"][:12]]
    return "\n".join(L + ["", *("⚠ " + x for x in r["limitacoes"])])


def texto_mc(r):
    L = [f"Monte Carlo — n = {r['n']}, semente {r['semente']} ({r['classe']})", f"tempo base {r['tempo_base_s']:.3f} s · média {r['media_s']:.3f} · desvio {r['desvio_s']:.3f}",
         f"P5 {r['p05_s']:.3f} · P50 {r['p50_s']:.3f} · P95 {r['p95_s']:.3f} · mín {r['min_s']:.3f} · máx {r['max_s']:.3f}", "correlação com o tempo:"]
    L += [f"  {c['campo']:10}{c['correlacao']:+8.3f}" for c in r["correlacoes"]]
    return "\n".join(L + ["", *("⚠ " + x for x in r["limitacoes"])])


def texto_pareto(r):
    a, b = r["objetivos"]
    L = [f"Pareto — {r['avaliacoes']} pontos, {len(r['frente'])} na frente ({a} × {b})"]
    L += [f"  {a} = {p['objetivos'][0]:.3f}  {b} = {p['objetivos'][1]:.3f}   " + ", ".join(f"{k}={v:g}" for k, v in p["parametros"].items()) for p in r["frente"]]
    return "\n".join(L + ["", *("⚠ " + x for x in r["limitacoes"])])


def texto_stint(r):
    L = [f"Stint — {r['voltas']} voltas, total {r['total_s']:.3f} s (melhor volta {r['melhor_volta']}, pior {r['pior_volta']})"]
    L += [f"  volta {x['volta']:3d}  {x['tempo_s']:.3f} s   acumulado {x['acumulado_s']:.3f} s" for x in r["linhas"][:40]]
    return "\n".join(L + ["", *("⚠ " + x for x in r["limitacoes"])])


# ------------------------------------------------------------------------------------------------------------------ especificação em texto (interface)
EXEMPLOS = {"fatorial": "massa, mu, cla ; 5", "monte_carlo": "mu=normal:2, massa=uniforme:1 ; n=200 ; semente=1",
            "pareto": "e_ers=0,2,4,6 ; p_ers=100,300", "stint": "voltas=10 ; massa=-1.5 ; mu=-0.002"}


def executar_especificacao(estudo: str, texto: str, base: lapsim.Carro, pista=None, ds: float = 3.0, escala: dict | None = None) -> tuple[str, dict]:
    """Interpreta o texto da interface e roda o estudo. `escala` converte unidades da tela para o solver (ex.: {"p_ice": 1e3, "e_ers": 1e6}).
    Devolve (tipo_de_exportação, resultado). Erros de sintaxe viram ValueError com a forma esperada."""
    esc = escala or {}
    partes = [p.strip() for p in texto.split(";") if p.strip()]

    def kvs(itens):
        out = {}
        for it in itens:
            if "=" not in it:
                raise ValueError(f"use campo=valor (recebido '{it}'). Exemplo: {EXEMPLOS[estudo]}")
            k, v = it.split("=", 1)
            out[k.strip()] = v.strip()
        return out

    try:
        if estudo == "fatorial":
            campos = [c.strip() for c in partes[0].split(",") if c.strip()] if partes else []
            return "fatorial", fatorial(base, campos, float(partes[1]) if len(partes) > 1 else 5.0, pista, ds)
        if estudo == "monte_carlo":
            inc, n, semente = {}, 300, 1
            for it in (partes[0].split(",") if partes else []):
                k, r = it.split("=", 1)
                d, p = r.split(":", 1)
                inc[k.strip()] = (d.strip(), float(p))
            for k, v in kvs(partes[1:]).items():
                if k == "n": n = int(v)
                elif k == "semente": semente = int(v)
                else: raise ValueError(f"opção desconhecida: {k}")
            return "monte_carlo", monte_carlo(base, inc, n, semente, pista, ds)
        if estudo == "pareto":
            grade = {k: [float(x) * esc.get(k, 1.0) for x in v.split(",") if x.strip()] for k, v in kvs(partes).items()}
            return "pareto", pareto(base, grade, ("tempo_s", "energia_ers_usada_MJ"), pista, ds)
        if estudo == "stint":
            kv = kvs(partes)
            if "voltas" not in kv:
                raise ValueError("informe voltas=N")
            n = int(kv.pop("voltas"))
            return "stint", stint(base, n, {k: float(v) * esc.get(k, 1.0) for k, v in kv.items()}, pista, ds)
    except (IndexError, KeyError):
        raise ValueError(f"não consegui interpretar '{texto}'. Exemplo: {EXEMPLOS[estudo]}")
    except ValueError as exc:
        if "could not convert" in str(exc) or "invalid literal" in str(exc) or "not enough values" in str(exc) or "unpack" in str(exc):
            raise ValueError(f"não consegui interpretar '{texto}'. Exemplo: {EXEMPLOS[estudo]}")
        raise
    raise ValueError(f"estudo desconhecido: {estudo}")
