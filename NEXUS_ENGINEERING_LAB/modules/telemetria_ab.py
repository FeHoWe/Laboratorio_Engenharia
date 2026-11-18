"""V120 — F1 Telemetry Lab (dados): comparação A×B ao longo da volta + importação de CSV com mapeamento de colunas, unidades e sincronização por distância.

Fontes aceitas: (1) dois carros pelo `lapsim` (SIMULAÇÃO; telemetria SIMULADA, não é de nenhuma equipe) ou (2) dois CSV SEUS já lidos (`ler_csv_mapeado`/`validacao_dados.ler_telemetria`),
ambos reamostrados numa grade comum de distância (`sincronizar`). Entregas: tempo acumulado, delta de tempo, aceleração longitudinal, zonas de frenagem, aceleração lateral
v²/R (só quando o raio da pista é conhecido, ou seja, nas simulações), tempo/delta por setor, maiores perdas/ganhos, consulta de um ponto da pista com A e B lado a lado.
Limites: aceleração lateral por CSV não é calculada (o CSV não traz o raio); delta de tempo de CSV sem coluna de tempo usa t = ∫ ds/v (aproximação trapezoidal).
Nada aqui é validação nem dado oficial; sinais: delta = B − A (positivo = B mais lento).
"""
from __future__ import annotations

import math

import numpy as np

from . import lapsim

LIM_FREIO = 2.0   # m/s² de desaceleração longitudinal que caracteriza “frenagem” (ajustável)


class TelemetriaABError(ValueError):
    pass


def _tempo(s, v):
    s, v = np.asarray(s, float), np.asarray(v, float)
    dt = 2.0 * np.diff(s) / (v[1:] + v[:-1])
    return np.concatenate([[0.0], np.cumsum(dt)])


def perfil_simulado(carro, pista=None, ds: float = 3.0) -> dict:
    r = lapsim.volta(carro, pista, ds)
    s, v = np.asarray(r.valores["s_m"], float), np.asarray(r.valores["v_ms"], float)
    R = np.asarray(lapsim._perfil(pista or lapsim.PISTA_EXEMPLO, ds), float)[: len(s)]
    n = min(len(s), len(R))
    s, v, R = s[:n], v[:n], R[:n]
    lat = np.where(R > 0, v ** 2 / np.where(R > 0, R, 1.0), 0.0)
    return {"fonte": "simulacao_lapsim", "classe": "SIMULACAO_NUMERICA", "s_m": s, "v_ms": v, "lat_ms2": lat, "t_s": _tempo(s, v), "ds": float(ds), "tempo_volta_s": float(r.valores["tempo_s"])}


def ler_csv_mapeado(texto: str, col_dist: str, col_vel: str, unidade_dist: str = "m", unidade_vel: str = "kmh", col_tempo: str | None = None, unidade_tempo: str = "s") -> dict:
    """CSV/;/tab com cabeçalho; você diz QUAL coluna é distância e velocidade e as unidades. Unidades: dist m|km|mi; vel kmh|ms|mph; tempo s|ms."""
    fd, fv, ft = {"m": 1.0, "km": 1000.0, "mi": 1609.344}, {"kmh": 1 / 3.6, "ms": 1.0, "mph": 0.44704}, {"s": 1.0, "ms": 1e-3}
    if unidade_dist not in fd or unidade_vel not in fv or unidade_tempo not in ft:
        raise TelemetriaABError("unidade desconhecida (dist: m|km|mi; vel: kmh|ms|mph; tempo: s|ms)")
    linhas = [ln for ln in str(texto).splitlines() if ln.strip() and not ln.strip().startswith("#")]
    if len(linhas) < 4:
        raise TelemetriaABError("telemetria com menos de 3 amostras")
    sep = ";" if ";" in linhas[0] else ("\t" if "\t" in linhas[0] else ",")
    cab = [h.strip() for h in linhas[0].split(sep)]
    for c in (col_dist, col_vel) + ((col_tempo,) if col_tempo else ()):
        if c not in cab:
            raise TelemetriaABError(f"coluna '{c}' não existe no cabeçalho ({', '.join(cab)})")
    i_s, i_v = cab.index(col_dist), cab.index(col_vel)
    i_t = cab.index(col_tempo) if col_tempo else None
    s, v, t = [], [], []
    for n, ln in enumerate(linhas[1:], 2):
        p = ln.split(sep)
        try:
            num = lambda x: float(x.strip().replace(",", ".")) if sep != "," else float(x)  # noqa: E731
            s.append(num(p[i_s]) * fd[unidade_dist]); v.append(num(p[i_v]) * fv[unidade_vel])
            if i_t is not None:
                t.append(num(p[i_t]) * ft[unidade_tempo])
        except (ValueError, IndexError):
            raise TelemetriaABError(f"linha {n}: valor inválido")
        if not (math.isfinite(s[-1]) and math.isfinite(v[-1])) or v[-1] <= 0:
            raise TelemetriaABError(f"linha {n}: velocidade deve ser > 0 e finita")
        if len(s) > 1 and s[-1] <= s[-2]:
            raise TelemetriaABError(f"linha {n}: a distância deve crescer")
    return {"s_m": s, "v_ms": v, "t_s": t or None}


def sincronizar(tel: dict, ds: float = 3.0, rotulo: str = "CSV do usuário") -> dict:
    """Reamostra uma telemetria (dict com s_m, v_ms ou v_kmh, t_s opcional) numa grade de distância regular de passo `ds` a partir de s0."""
    s = np.asarray(tel["s_m"], float)
    v = np.asarray(tel["v_ms"], float) if "v_ms" in tel else np.asarray(tel["v_kmh"], float) / 3.6
    if len(s) < 3 or ds <= 0:
        raise TelemetriaABError("telemetria curta ou ds inválido")
    g = np.arange(s[0], s[-1] + 1e-9, ds)
    vg = np.interp(g, s, v)
    t_tel = tel.get("t_s")
    tg = np.interp(g, s, np.asarray(t_tel, float)) - np.interp(g[0], s, np.asarray(t_tel, float)) if t_tel else _tempo(g, vg)
    return {"fonte": rotulo, "classe": "TELEMETRIA_DO_USUARIO", "s_m": g, "v_ms": vg, "lat_ms2": None, "t_s": tg, "ds": float(ds), "tempo_volta_s": float(tg[-1])}


def _zonas_freio(p: dict, lim: float) -> list[dict]:
    s, v = p["s_m"], p["v_ms"]
    a = np.concatenate([(v[1:] ** 2 - v[:-1] ** 2) / (2 * np.diff(s)), [0.0]])
    zonas, i, n = [], 0, len(s)
    while i < n:
        if a[i] <= -lim:
            j = i
            while j + 1 < n and a[j + 1] <= -lim:
                j += 1
            zonas.append({"s_inicio_m": float(s[i]), "s_fim_m": float(s[j + 1] if j + 1 < n else s[j]), "v_entrada_kmh": float(v[i] * 3.6), "v_saida_kmh": float(v[min(j + 1, n - 1)] * 3.6),
                          "desacel_max_ms2": float(-a[i:j + 1].min())})
            i = j + 1
        else:
            i += 1
    return zonas


def comparar(pa: dict, pb: dict, n_setores: int = 3, limites_setor_m: list[float] | None = None, lim_freio: float = LIM_FREIO) -> dict:
    sa, sb = np.asarray(pa["s_m"]), np.asarray(pb["s_m"])
    if len(sa) != len(sb) or not np.allclose(sa, sb, atol=1e-6):
        raise TelemetriaABError("A e B precisam estar na MESMA grade de distância (mesma pista e mesmo ds; use `sincronizar` para CSVs)")
    s = sa
    delta = np.asarray(pb["t_s"]) - np.asarray(pa["t_s"])
    comp = float(s[-1] - s[0])
    cortes = sorted(limites_setor_m) if limites_setor_m else [float(s[0] + comp * k / n_setores) for k in range(1, n_setores)]
    if any(not s[0] < c < s[-1] for c in cortes):
        raise TelemetriaABError("limites de setor fora da pista")
    bordas = [float(s[0])] + cortes + [float(s[-1])]
    setores = []
    for k in range(len(bordas) - 1):
        ta = float(np.interp(bordas[k + 1], s, pa["t_s"]) - np.interp(bordas[k], s, pa["t_s"]))
        tb = float(np.interp(bordas[k + 1], s, pb["t_s"]) - np.interp(bordas[k], s, pb["t_s"]))
        setores.append({"setor": k + 1, "s_ini_m": bordas[k], "s_fim_m": bordas[k + 1], "t_A_s": ta, "t_B_s": tb, "delta_s": tb - ta})
    d_trecho = np.diff(delta)
    ordem = np.argsort(d_trecho)
    janela = max(1, len(d_trecho) // 20)
    def _trecho(i): return {"s_m": float(s[i]), "delta_local_s": float(d_trecho[i])}
    return {"classe": "SIMULACAO_NUMERICA" if pa.get("classe") == pb.get("classe") == "SIMULACAO_NUMERICA" else "COMPARACAO_MISTA",
            "fontes": [pa.get("fonte"), pb.get("fonte")], "s_m": s.tolist(), "delta_t_s": delta.tolist(), "v_A_kmh": (np.asarray(pa["v_ms"]) * 3.6).tolist(), "v_B_kmh": (np.asarray(pb["v_ms"]) * 3.6).tolist(),
            "lat_A_ms2": None if pa.get("lat_ms2") is None else np.asarray(pa["lat_ms2"]).tolist(), "lat_B_ms2": None if pb.get("lat_ms2") is None else np.asarray(pb["lat_ms2"]).tolist(),
            "tempo_A_s": float(pa["t_s"][-1]), "tempo_B_s": float(pb["t_s"][-1]), "delta_volta_s": float(delta[-1]), "setores": setores,
            "frenagem_A": _zonas_freio(pa, lim_freio), "frenagem_B": _zonas_freio(pb, lim_freio),
            "maiores_ganhos_de_B": [_trecho(i) for i in ordem[:janela][:5]], "maiores_perdas_de_B": [_trecho(i) for i in ordem[::-1][:janela][:5]],
            "avisos": ["Delta = B − A (positivo: B mais lento).", "Telemetria simulada NÃO é telemetria de equipes; CSV é dado SEU e vale pela qualidade que ele tem.",
                       "Aceleração lateral só existe em simulações (usa o raio da pista)." if pa.get("lat_ms2") is None or pb.get("lat_ms2") is None else "Aceleração lateral = v²/R do raio da pista (cinemática)."]}


def ponto(res: dict, s_m: float) -> dict:
    """A e B lado a lado num ponto da pista (interpolação linear)."""
    s = np.asarray(res["s_m"])
    if not s[0] <= s_m <= s[-1]:
        raise TelemetriaABError(f"distância fora da pista ({s[0]:g}–{s[-1]:g} m)")
    f = lambda y: float(np.interp(s_m, s, y))  # noqa: E731
    out = {"s_m": float(s_m), "v_A_kmh": f(res["v_A_kmh"]), "v_B_kmh": f(res["v_B_kmh"]), "delta_t_s": f(res["delta_t_s"])}
    if res["lat_A_ms2"] is not None and res["lat_B_ms2"] is not None:
        out["lat_A_ms2"], out["lat_B_ms2"] = f(res["lat_A_ms2"]), f(res["lat_B_ms2"])
    return out


def texto(r: dict) -> str:
    L = [f"Telemetria A×B — {r['classe']} · A {r['tempo_A_s']:.3f} s · B {r['tempo_B_s']:.3f} s · Δ(B−A) {r['delta_volta_s']:+.3f} s", f"{'setor':>6}{'A [s]':>10}{'B [s]':>10}{'Δ [s]':>10}"]
    L += [f"{x['setor']:6d}{x['t_A_s']:10.3f}{x['t_B_s']:10.3f}{x['delta_s']:+10.3f}" for x in r["setores"]]
    L += [f"Frenagens: A {len(r['frenagem_A'])} · B {len(r['frenagem_B'])}"]
    L += ["⚠ " + a for a in r["avisos"]]
    return "\n".join(L)
