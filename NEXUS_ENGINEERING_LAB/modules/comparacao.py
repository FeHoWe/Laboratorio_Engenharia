"""V4.3 — Comparação A/B e varredura de parâmetro sobre a simulação de volta (`lapsim`).

Tudo é calculado pelo MESMO solver nas duas configurações (nenhum número vem de fora); a diferença é aritmética sobre os dois resultados rastreáveis.
`delta_tempo_ao_longo_da_pista` integra t(s)=Σ ds/v nas duas voltas (mesma pista e mesmo ds) e devolve tB(s) − tA(s): valor POSITIVO = B mais lento em
aquela distância. Limites herdados do lapsim: ponto material, μ constante, pista sintética, sem pneus reais — a diferença A−B vale para ESTE modelo, não
prevê a diferença no carro real.
"""
from __future__ import annotations

from dataclasses import asdict, replace

from . import lapsim

# campos escalares do resultado de volta e se "menor é melhor" (None = só informativo)
_SENTIDO = {"tempo_s": True, "v_media_kmh": False, "v_max_kmh": None, "v_min_kmh": False, "energia_ers_usada_MJ": None, "comprimento_m": None}
_ESCALARES = tuple(_SENTIDO)


def _tempo_acumulado(s, v, ds):
    t, out = 0.0, []
    n = len(v)
    for i in range(n):
        out.append(t)
        t += 2 * ds / (v[i] + v[(i + 1) % n])
    return out


def comparar_voltas(a: lapsim.Carro, b: lapsim.Carro, pista=None, ds: float = 2.0) -> dict:
    ra, rb = lapsim.volta(a, pista, ds), lapsim.volta(b, pista, ds)
    va, vb = ra.valores, rb.valores
    campos = {}
    for k in _ESCALARES:
        x, y = float(va[k]), float(vb[k])
        d = y - x
        melhor = None
        if _SENTIDO[k] is not None and abs(d) > 1e-12:
            melhor = ("B" if d < 0 else "A") if _SENTIDO[k] else ("B" if d > 0 else "A")
        campos[k] = {"A": x, "B": y, "delta": d, "delta_pct": (d / x * 100.0 if x else None), "melhor": melhor}
    ta, tb = _tempo_acumulado(va["s_m"], va["v_ms"], ds), _tempo_acumulado(vb["s_m"], vb["v_ms"], ds)
    dt = [y - x for x, y in zip(ta, tb)]
    i_ganho = min(range(len(dt)), key=lambda i: dt[i]); i_perda = max(range(len(dt)), key=lambda i: dt[i])
    mudancas = {k: {"A": getattr(a, k), "B": getattr(b, k)} for k in asdict(a) if getattr(a, k) != getattr(b, k)}
    return {
        "classe": ra.classe, "solver": f"{ra.solver} {ra.solver_versao}",
        "campos": campos, "parametros_diferentes": mudancas,
        "delta_tempo_ao_longo_da_pista": {"s_m": list(va["s_m"]), "delta_s": dt},
        "maior_ganho_de_B": {"s_m": va["s_m"][i_ganho], "delta_s": dt[i_ganho]},
        "maior_perda_de_B": {"s_m": va["s_m"][i_perda], "delta_s": dt[i_perda]},
        "resultado_A": ra, "resultado_B": rb,
        "premissas": ra.premissas,
        "limitacoes": ra.limitacoes + ["A diferença A−B vale para este modelo simplificado; não prevê a diferença no carro real."],
    }


def varrer_parametro(base: lapsim.Carro, campo: str, valores: list, pista=None, ds: float = 3.0) -> list[dict]:
    """Estudo de sensibilidade: tempo de volta para cada valor de `campo` (os demais parâmetros ficam em `base`)."""
    if campo not in asdict(base):
        raise ValueError(f"parâmetro desconhecido: {campo}")
    if not valores:
        raise ValueError("informe ao menos um valor")
    out = []
    for x in valores:
        r = lapsim.volta(replace(base, **{campo: float(x)}), pista, ds)
        out.append({"valor": float(x), "tempo_s": r.valores["tempo_s"], "v_max_kmh": r.valores["v_max_kmh"]})
    t0 = out[0]["tempo_s"]
    for o in out:
        o["delta_vs_primeiro_s"] = o["tempo_s"] - t0
    return out


def texto(c: dict) -> str:
    nome = {"tempo_s": "tempo de volta [s]", "v_media_kmh": "v média [km/h]", "v_max_kmh": "v máx [km/h]", "v_min_kmh": "v mín [km/h]",
            "energia_ers_usada_MJ": "energia elétrica usada [MJ]", "comprimento_m": "comprimento [m]"}
    L = [f"Comparação A/B — classe {c['classe']} ({c['solver']})", f"{'':32}{'A':>12}{'B':>12}{'B−A':>12}{'%':>9}  melhor"]
    for k, d in c["campos"].items():
        pct = "—" if d["delta_pct"] is None else f"{d['delta_pct']:+.2f}"
        L.append(f"{nome[k]:32}{d['A']:12.3f}{d['B']:12.3f}{d['delta']:+12.3f}{pct:>9}  {d['melhor'] or '—'}")
    if c["parametros_diferentes"]:
        L.append("\nParâmetros diferentes: " + "; ".join(f"{k}: {v['A']:g} → {v['B']:g}" for k, v in c["parametros_diferentes"].items()))
    else:
        L.append("\nA e B têm os mesmos parâmetros.")
    g, p = c["maior_ganho_de_B"], c["maior_perda_de_B"]
    L.append(f"Maior vantagem de B: {g['delta_s']:+.3f} s acumulados em s = {g['s_m']:.0f} m · maior desvantagem: {p['delta_s']:+.3f} s em s = {p['s_m']:.0f} m")
    L.append("\n" + "\n".join("⚠ " + x for x in c["limitacoes"]))
    return "\n".join(L)
