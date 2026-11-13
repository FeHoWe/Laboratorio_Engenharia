"""V103 (Fase D) — Comparação A/B de configurações de veículo através dos modelos EXISTENTES (volta, bicicleta, dinâmica lateral linear, freios).

Cada configuração é um dict com blocos opcionais:
  {"carro": {campos de lapsim.Carro}, "bicicleta": {campos de lapsim_bicicleta.CarroB}, "lateral": {massa,a,b,iz,cf,cr}, "U_ms": 40,
   "freios": {"disco_diant": {...}, "disco_tras": {...}, "freio_diant": 0.6, "voltas": 5}}
Só calcula os blocos presentes nas DUAS configurações; um bloco que só uma tem vira nota (“não comparável”), nunca um número inventado.
Cada métrica traz o modelo de origem e as hipóteses dele; nada aqui é um modelo novo. Diferença A→B = B − A (sinal explícito).
"""
from __future__ import annotations

from . import dinamica_lateral as DL, freio_termico as FT, lapsim, lapsim_bicicleta as LB

HIPOTESES = {
    "lapsim": "ponto material, μ único, pista conforme informada (sintética se omitida)",
    "bicicleta": "bicicleta com transferência longitudinal, SEM transferência lateral de carga",
    "lateral": "linear, ângulos pequenos, pneus lineares, velocidade constante; Cf/Cr SEUS",
    "freios": "1 nó térmico por eixo, propriedades SUAS; energia vinda do lapsim",
}


def _metricas(cfg: dict, pista, ds) -> dict:
    m = {}
    if cfg.get("carro"):
        r = lapsim.volta(lapsim.Carro(**cfg["carro"]), pista, ds)
        m["tempo_volta_lapsim_s"] = (r.valores["tempo_s"], "lapsim")
    if cfg.get("bicicleta"):
        r = LB.volta(LB.CarroB(**cfg["bicicleta"]), pista, ds)
        m["tempo_volta_bicicleta_s"] = (r.valores["tempo_s"], "bicicleta")
    if cfg.get("lateral"):
        p = DL.ParamsLat(**cfg["lateral"])
        g = DL.varredura_velocidade(p, [float(cfg.get("U_ms", 30.0))])[0]
        m["gradiente_subesterco_graus_por_g"] = (g["gradiente_subesterco_graus_por_g"], "lateral")
        m["ganho_guinada_1_por_s"] = (g["ganho_guinada_1_por_s"], "lateral")
        m["comportamento"] = (g["tipo"], "lateral")
    if cfg.get("freios") and cfg.get("carro"):
        f = cfg["freios"]
        r = FT.termica(lapsim.Carro(**cfg["carro"]), FT.Disco(**f["disco_diant"]), FT.Disco(**f["disco_tras"]), float(f.get("freio_diant", 0.6)), pista, ds, int(f.get("voltas", 5)))
        m["energia_frenagem_MJ"] = (r["energia_frenagem_MJ"], "freios")
        m["T_pico_freio_diant_C"] = (r["voltas"][-1]["T_pico_diant_C"], "freios")
        m["T_pico_freio_tras_C"] = (r["voltas"][-1]["T_pico_tras_C"], "freios")
    return m


def comparar(a: dict, b: dict, pista=None, ds: float = 3.0) -> dict:
    for nome, c in (("A", a), ("B", b)):
        if not isinstance(c, dict) or not any(c.get(k) for k in ("carro", "bicicleta", "lateral")):
            raise ValueError(f"configuração {nome}: informe ao menos um bloco (carro, bicicleta ou lateral)")
    ma, mb = _metricas(a, pista, ds), _metricas(b, pista, ds)
    linhas, notas = [], []
    for k in sorted(set(ma) | set(mb)):
        if k not in ma or k not in mb:
            notas.append(f"{k}: só calculado em {'A' if k in ma else 'B'} — não comparável (o bloco falta na outra configuração).")
            continue
        va, vb, modelo = ma[k][0], mb[k][0], ma[k][1]
        num = isinstance(va, (int, float)) and isinstance(vb, (int, float))
        linhas.append({"metrica": k, "A": va, "B": vb, "delta_B_menos_A": (vb - va) if num else None,
                       "delta_pct": (100.0 * (vb - va) / va) if num and va else None, "modelo": modelo, "hipoteses": HIPOTESES[modelo]})
    return {"classe": "SIMULACAO_NUMERICA", "solver": "NEXUS comparação A/B (lapsim, bicicleta, dinâmica lateral, freios)", "linhas": linhas, "notas": notas,
            "limitacoes": ["Cada métrica vale só para o modelo simplificado indicado; modelos diferentes NÃO devem ser somados nem tratados como o mesmo tempo de volta.",
                           "Parâmetros hipotéticos geram resultados hipotéticos: não representam um carro real nem dados de equipe.",
                           "Nada aqui é validação; veja `validar` com telemetria própria."]}


def texto(r: dict) -> str:
    L = [f"Comparação A/B — {r['classe']}", f"{'métrica':36}{'A':>14}{'B':>14}{'B−A':>12}  modelo"]
    for x in r["linhas"]:
        f = (lambda v: f"{v:14.5g}" if isinstance(v, (int, float)) else f"{str(v):>14}")
        L.append(f"{x['metrica']:36}{f(x['A'])}{f(x['B'])}{f(x['delta_B_menos_A']) if x['delta_B_menos_A'] is not None else ' ' * 12}  {x['modelo']}")
    return "\n".join(L + ["ℹ " + n for n in r["notas"]] + ["⚠ " + x for x in r["limitacoes"]])
