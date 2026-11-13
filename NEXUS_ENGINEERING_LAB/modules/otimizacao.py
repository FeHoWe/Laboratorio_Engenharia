"""V7.0 — Sensibilidade (tornado) e otimização de parâmetros sobre a simulação de volta (`lapsim`).

Tudo é calculado pelo MESMO solver quase-estacionário (ponto material, μ constante, pista sintética). Nada vem de fora.
Limites que a saída repete: o resultado vale para ESTE modelo, não para o carro real; o otimizador devolve o melhor ponto
ENCONTRADO dentro das faixas que o usuário informou (heurística estocástica com semente fixa), não um ótimo global provado;
se o modelo for monótono no parâmetro (ex.: mais Cl·A sempre melhora o tempo), a solução cai na borda da faixa — isso é uma
propriedade do modelo, não uma recomendação de projeto. O acoplamento Cd·A↔Cl·A é um número SEU (`k_cda_por_cla`); o NEXUS não o inventa.
"""
from __future__ import annotations

from dataclasses import asdict, replace

from . import lapsim

CAMPOS = ("massa", "p_ice", "cda", "cla", "mu", "crr", "p_ers", "e_ers")


def _tempo(c, pista, ds):
    return float(lapsim.volta(c, pista, ds).valores["tempo_s"])


def _checar_campos(base, campos):
    if not campos:
        raise ValueError("informe ao menos um parâmetro")
    ok = set(asdict(base))
    for k in campos:
        if k not in ok:
            raise ValueError(f"parâmetro desconhecido: {k}")


def tornado(base: lapsim.Carro, campos=None, variacao_pct: float = 5.0, pista=None, ds: float = 3.0) -> dict:
    """Sensibilidade um-parâmetro-por-vez: cada campo vai a −x % e +x % (os demais ficam em `base`).
    Devolve linhas ordenadas pela amplitude |t(+x)−t(−x)| (maior primeiro). Campos com valor 0 são ignorados (variação relativa nula)."""
    if not 0 < variacao_pct <= 50:
        raise ValueError("variacao_pct deve estar em (0, 50]")
    campos = list(campos) if campos else [k for k in CAMPOS if getattr(base, k) != 0]
    _checar_campos(base, campos)
    t0 = _tempo(base, pista, ds)
    f = variacao_pct / 100.0
    linhas = []
    for k in campos:
        v0 = getattr(base, k)
        if v0 == 0:
            continue
        tm = _tempo(replace(base, **{k: v0 * (1 - f)}), pista, ds)
        tp = _tempo(replace(base, **{k: v0 * (1 + f)}), pista, ds)
        linhas.append({"campo": k, "valor": v0, "t_menos_s": tm, "t_mais_s": tp, "d_menos_s": tm - t0, "d_mais_s": tp - t0,
                       "amplitude_s": abs(tp - tm)})
    linhas.sort(key=lambda r: -r["amplitude_s"])
    return {"classe": "SIMULACAO_NUMERICA", "solver": "NEXUS-LapSim 1.0", "tempo_base_s": t0, "variacao_pct": variacao_pct, "linhas": linhas,
            "limitacoes": ["Sensibilidade local (um parâmetro por vez) em torno do ponto informado; não inclui interações.",
                           "Vale para o modelo simplificado (ponto material, μ constante, pista sintética), não para o carro real."]}


def otimizar(base: lapsim.Carro, limites: dict, pista=None, ds: float = 3.0, k_cda_por_cla: float | None = None,
             max_iter: int = 40, semente: int = 0) -> dict:
    """Minimiza o tempo de volta variando os campos de `limites` ({campo: (lo, hi)}) com evolução diferencial (semente fixa → repetível).
    `k_cda_por_cla` (opcional, SEU): Cd·A = Cd·A_base + k·(Cl·A − Cl·A_base) quando `cla` é variado — sem isso, Cl·A é “de graça”."""
    from scipy.optimize import differential_evolution
    _checar_campos(base, limites)
    nomes = list(limites)
    for k in nomes:
        lo, hi = limites[k]
        if not lo < hi:
            raise ValueError(f"faixa inválida para {k}: lo deve ser menor que hi")
    if k_cda_por_cla is not None and "cla" not in limites:
        raise ValueError("k_cda_por_cla só faz sentido se 'cla' estiver entre os parâmetros variados")

    def monta(x):
        mud = dict(zip(nomes, map(float, x)))
        if k_cda_por_cla is not None and "cla" in mud and "cda" not in mud:
            mud["cda"] = base.cda + k_cda_por_cla * (mud["cla"] - base.cla)
        return replace(base, **mud)

    avaliacoes = [0]

    def obj(x):
        avaliacoes[0] += 1
        return _tempo(monta(x), pista, ds)

    t0 = _tempo(base, pista, ds)
    r = differential_evolution(obj, [tuple(map(float, limites[k])) for k in nomes], seed=semente, maxiter=max_iter, popsize=8,
                               tol=1e-9, polish=False, updating="immediate", workers=1)
    melhor = monta(r.x)
    na_borda = [k for k, x in zip(nomes, r.x) if abs(x - limites[k][0]) < 1e-2 * (limites[k][1] - limites[k][0]) or abs(x - limites[k][1]) < 1e-2 * (limites[k][1] - limites[k][0])]
    lim = ["Melhor ponto ENCONTRADO por busca estocástica (semente fixa) dentro das faixas informadas; não é prova de ótimo global.",
           "Vale para o modelo simplificado (ponto material, μ constante, pista sintética), não para o carro real."]
    if na_borda:
        lim.append("Parâmetros na borda da faixa: " + ", ".join(na_borda) + " — o modelo é monótono neles (ou a faixa é estreita); não é recomendação de projeto.")
    if k_cda_por_cla is None and "cla" in nomes:
        lim.append("Cl·A foi variado SEM acoplamento com Cd·A (informe k_cda_por_cla para incluir o custo de arrasto).")
    return {"classe": "SIMULACAO_NUMERICA", "solver": "NEXUS-LapSim 1.0 + differential_evolution (scipy)", "tempo_base_s": t0,
            "tempo_otimo_s": float(r.fun), "ganho_s": t0 - float(r.fun), "parametros": {k: float(x) for k, x in zip(nomes, r.x)},
            "carro_otimo": asdict(melhor), "avaliacoes": avaliacoes[0], "na_borda": na_borda, "limitacoes": lim}


def otimizar_1d(base: lapsim.Carro, campo: str, lo: float, hi: float, pista=None, ds: float = 3.0, tol_rel: float = 1e-6, max_iter: int = 80) -> dict:
    """Minimiza o tempo de volta variando UM parâmetro em [lo, hi] por seção áurea (determinística, sem sorteio; mesmo algoritmo do celular).
    Assume tempo(x) unimodal na faixa; se for monótono, termina na borda. Não é prova de ótimo global."""
    _checar_campos(base, [campo])
    if not lo < hi:
        raise ValueError("faixa inválida: lo deve ser menor que hi")
    g = (5 ** 0.5 - 1) / 2
    f = lambda x: _tempo(replace(base, **{campo: float(x)}), pista, ds)  # noqa: E731
    a, b = float(lo), float(hi)
    c, d = b - g * (b - a), a + g * (b - a)
    fc, fd = f(c), f(d)
    n = 2
    for _ in range(max_iter):
        if (b - a) <= tol_rel * (hi - lo):
            break
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - g * (b - a); fc = f(c)
        else:
            a, c, fc = c, d, fd
            d = a + g * (b - a); fd = f(d)
        n += 1
    x = 0.5 * (a + b)
    t = f(x); t_lo, t_hi = f(lo), f(hi)
    if t_lo <= t:
        x, t = float(lo), t_lo
    if t_hi < t:
        x, t = float(hi), t_hi
    t0 = _tempo(base, pista, ds)
    borda = abs(x - lo) < 1e-3 * (hi - lo) or abs(x - hi) < 1e-3 * (hi - lo)
    lim = ["Seção áurea determinística; assume tempo unimodal na faixa; não é prova de ótimo global.",
           "Vale para o modelo simplificado (ponto material, μ constante, pista sintética), não para o carro real."]
    if borda:
        lim.append(f"{campo} ficou na borda da faixa — o modelo é monótono nele (ou a faixa é estreita); não é recomendação de projeto.")
    return {"classe": "SIMULACAO_NUMERICA", "solver": "NEXUS-LapSim 1.0 + secao aurea", "campo": campo, "valor_otimo": x, "tempo_base_s": t0, "tempo_otimo_s": t,
            "ganho_s": t0 - t, "avaliacoes": n + 3, "na_borda": [campo] if borda else [], "parametros": {campo: x}, "limitacoes": lim}


def texto_tornado(t: dict) -> str:
    L = [f"Sensibilidade ±{t['variacao_pct']:g} % — tempo base {t['tempo_base_s']:.3f} s ({t['classe']}, {t['solver']})",
         f"{'parâmetro':12}{'valor':>14}{'Δ(−)[s]':>11}{'Δ(+)[s]':>11}{'amplitude[s]':>14}"]
    for r in t["linhas"]:
        L.append(f"{r['campo']:12}{r['valor']:14.5g}{r['d_menos_s']:+11.3f}{r['d_mais_s']:+11.3f}{r['amplitude_s']:14.3f}")
    L.append("\n" + "\n".join("⚠ " + x for x in t["limitacoes"]))
    return "\n".join(L)


def texto_otimizacao(o: dict) -> str:
    L = [f"Otimização — {o['classe']} ({o['solver']})", f"tempo base {o['tempo_base_s']:.3f} s → melhor encontrado {o['tempo_otimo_s']:.3f} s (ganho {o['ganho_s']:+.3f} s, {o['avaliacoes']} avaliações)"]
    L += [f"  {k} = {v:.5g}" for k, v in o["parametros"].items()]
    L.append("\n" + "\n".join("⚠ " + x for x in o["limitacoes"]))
    return "\n".join(L)
