"""Ferramentas de análise de dados e de engenharia no estilo das usadas em equipes e cursos de automobilismo.

Inspiradas (não são cópias) em: MoTeC i2 / ATLAS (comparação de voltas por distância, canal de ganho/perda de tempo, canais matemáticos,
diagrama g-g, histogramas), OptimumLap / OpenLAP (varreduras de parâmetros e sensibilidade) e fluxos de projeto com Simulink
(otimização 1-D de uma relação de transmissão).

HONESTIDADE: tudo é calculado sobre o simulador quase-estático do NEXUS F1 com parâmetros ESTIMADOS — resultados mostram TENDÊNCIAS e
ordens de grandeza, não valores de uma equipe real. Os canais são sintéticos (não vêm de sensores).
"""
from __future__ import annotations

import ast
import math

import numpy as np

from .api import simulate_lap
from .config import AERO_PRESETS, CarConfig, Environment
from .laptime import G, LapResult

# ---------------------------------------------------------------------------------------------- comparação de voltas


def delta_time(ref: LapResult, cmp: LapResult, n: int = 400) -> dict:
    """Canal de ganho/perda de tempo ao longo da distância (como o 'time delta' do i2): Δ(s) = t_cmp(s) − t_ref(s).

    Positivo = `cmp` está atrás. Exige o mesmo circuito. O último ponto é a diferença de volta."""
    if ref.track.key != cmp.track.key:
        raise ValueError("A comparação por distância exige o mesmo circuito")
    L = min(ref.tel["s"][-1], cmp.tel["s"][-1])
    s = np.linspace(0.0, L, n)
    tr = np.interp(s, ref.tel["s"], ref.tel["t"])
    tc = np.interp(s, cmp.tel["s"], cmp.tel["t"])
    d = tc - tr
    return {"s": s, "delta": d, "final": float(d[-1]), "max_loss": float(d.max()), "max_gain": float(d.min()),
            "where_max_loss_m": float(s[int(d.argmax())]), "where_max_gain_m": float(s[int(d.argmin())])}


def segment_deltas(ref: LapResult, cmp: LapResult) -> list:
    """Diferença de tempo por segmento (reta/curva) entre duas voltas do mesmo circuito."""
    if ref.track.key != cmp.track.key:
        raise ValueError("Mesmo circuito necessário")
    out = []
    for a, b in zip(ref.segments, cmp.segments):
        out.append({"nome": a.get("name", a.get("id")), "tipo": a.get("kind"), "dt": b["time"] - a["time"], "t_ref": a["time"], "t_cmp": b["time"]})
    return out


# ---------------------------------------------------------------------------------------------- canais matemáticos
_FUN = {"sqrt": np.sqrt, "abs": np.abs, "sin": np.sin, "cos": np.cos, "tan": np.tan, "exp": np.exp, "log": np.log, "log10": np.log10,
        "min": np.minimum, "max": np.maximum, "clip": np.clip, "where": np.where, "sign": np.sign, "hypot": np.hypot,
        "deg": np.degrees, "rad": np.radians, "diff": lambda x: np.concatenate([[0.0], np.diff(x)]),
        "cumsum": np.cumsum, "mean": np.mean, "pi": math.pi, "g": G}
_OK = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Call, ast.Name, ast.Load, ast.Constant, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow,
       ast.USub, ast.UAdd, ast.Mod, ast.Compare, ast.Gt, ast.Lt, ast.GtE, ast.LtE, ast.Eq, ast.NotEq, ast.BoolOp, ast.And, ast.Or)


def math_channel(res: LapResult, expr: str) -> np.ndarray:
    """Avalia uma expressão sobre os canais da volta (ex.: 'v*3.6', 'ax_g*ay_g', 'throttle*(1-brake)', 'p_ice/1e3').

    Avaliador seguro (AST): só aritmética, comparações e funções numéricas da lista; nada de atributos, índices ou imports."""
    tree = ast.parse(expr.strip(), mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, _OK):
            raise ValueError(f"Expressão não permitida: {type(node).__name__}")
        if isinstance(node, ast.Call) and not (isinstance(node.func, ast.Name) and node.func.id in _FUN and callable(_FUN[node.func.id])):
            raise ValueError("Função não permitida")
    env = {k: v for k, v in res.tel.items() if isinstance(v, np.ndarray) and v.ndim == 1}
    env.update(_FUN)
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id not in env:
            raise ValueError(f"Canal ou função desconhecido: {node.id}")
    out = eval(compile(tree, "<canal>", "eval"), {"__builtins__": {}}, env)   # noqa: S307 — AST validado acima
    out = np.asarray(out, float)
    return np.full(len(res.tel["s"]), float(out)) if out.ndim == 0 else out


def gg_diagram(res: LapResult, bins: int = 36) -> dict:
    """Pontos (ay, ax) em g e envelope (máx. |ax| por faixa de ay) — o 'círculo de aderência' efetivamente usado."""
    ay, ax = np.abs(res.tel["ay_g"]), res.tel["ax_g"]
    edges = np.linspace(0, max(ay.max(), 1e-6), bins + 1)
    up, dn = np.zeros(bins), np.zeros(bins)
    for i in range(bins):
        m = (ay >= edges[i]) & (ay <= edges[i + 1])
        if m.any():
            up[i], dn[i] = ax[m].max(), ax[m].min()
    return {"ay": res.tel["ay_g"], "ax": ax, "ay_centers": 0.5 * (edges[1:] + edges[:-1]), "ax_max": up, "ax_min": dn}


def histogram(res: LapResult, channel: str, bins: int = 20) -> dict:
    """Histograma ponderado pelo TEMPO (cada amostra vale seu dt), como nos histogramas de canal do i2/ATLAS."""
    x = math_channel(res, channel) if channel not in res.tel else np.asarray(res.tel[channel], float)
    h, e = np.histogram(x, bins=bins, weights=res.tel["dt"])
    return {"counts_s": h, "edges": e, "pct": 100.0 * h / max(h.sum(), 1e-12)}


def gear_usage(res: LapResult) -> dict:
    g = np.asarray(res.tel["gear"]).astype(int)
    return {int(k): float(res.tel["dt"][g == k].sum()) for k in np.unique(g)}


def throttle_brake_stats(res: LapResult) -> dict:
    dt, th, br = res.tel["dt"], res.tel["throttle"], res.tel["brake"]
    T = dt.sum()
    return {"acelerador_pleno_pct": float(100 * dt[th >= 0.98 * max(th.max(), 1e-9)].sum() / T), "freio_pct": float(100 * dt[br > 0.05].sum() / T),
            "coasting_pct": float(100 * dt[(th < 0.05) & (br < 0.05)].sum() / T)}


# ---------------------------------------------------------------------------------------------- varreduras e otimização
_PARAMS = {"mass_kg", "cda", "cla", "ice_pmax_kw", "mguk_kw", "final_drive", "brake_bias_front", "front_weight_frac", "cog_height_m",
           "aero_front_frac", "crr", "wheel_radius_m", "drivetrain_eff", "shift_rpm", "deploy_cap_mj"}


def _lap(track, car, env, fuel, ds):
    """Varreduras são exploratórias ("e se?"): rodam em modo EXPERIMENTAL (sem bloquear por regulamento). Conferir o regulamento à parte."""
    return simulate_lap(track, car.copy(mode="experimental"), env, fuel_kg=fuel, ds=ds).lap_time


def sweep(track: str, car: CarConfig, param: str, values, env: Environment | None = None, fuel_kg: float = 40.0, ds: float = 8.0) -> dict:
    """Tempo de volta para cada valor de um parâmetro (varredura 1-D, como no OptimumLap/OpenLAP)."""
    if param not in _PARAMS:
        raise ValueError(f"Parâmetro não varrível: {param}. Use um de {sorted(_PARAMS)}")
    vals = [float(v) for v in values]
    times = [_lap(track, car.copy(**{param: v}), env, fuel_kg, ds) for v in vals]
    k = int(np.argmin(times))
    return {"param": param, "values": vals, "lap_times": times, "best_value": vals[k], "best_time": times[k]}


def sensitivity(track: str, car: CarConfig, params=None, rel: float = 0.02, env: Environment | None = None, fuel_kg: float = 40.0, ds: float = 8.0) -> list:
    """Sensibilidade do tempo de volta a variações relativas de ±rel em cada parâmetro (diferença central).

    Retorna [{param, valor, d_lap_por_pct (s por +1 %), ...}] ordenado por impacto. Positivo = piora o tempo."""
    params = params or ["mass_kg", "cda", "cla", "ice_pmax_kw", "mguk_kw", "final_drive", "cog_height_m", "crr", "drivetrain_eff"]
    base = _lap(track, car, env, fuel_kg, ds)
    rows = []
    for p in params:
        v0 = getattr(car, p)
        up = _lap(track, car.copy(**{p: v0 * (1 + rel)}), env, fuel_kg, ds)
        dn = _lap(track, car.copy(**{p: v0 * (1 - rel)}), env, fuel_kg, ds)
        rows.append({"param": p, "valor": v0, "d_lap_por_pct": (up - dn) / (2 * rel * 100.0), "lap_menos": dn, "lap_mais": up, "base": base})
    return sorted(rows, key=lambda r: -abs(r["d_lap_por_pct"]))


def aero_level_car(car: CarConfig, level: float) -> CarConfig:
    """Interpola entre o pacote 'low_drag' (0) e 'high_downforce' (1) — coeficientes ESTIMADOS dos presets."""
    a, b = AERO_PRESETS["low_drag"], AERO_PRESETS["high_downforce"]
    mix = lambda k: a[k] + (b[k] - a[k]) * float(level)  # noqa: E731
    return car.copy(cda=mix("cda"), cla=mix("cla"), aero_front_frac=mix("front"), aero_preset="custom")


def optimize_aero(track: str, car: CarConfig, env: Environment | None = None, fuel_kg: float = 40.0, ds: float = 8.0, n: int = 11) -> dict:
    """Nível de asa (0 = baixo arrasto … 1 = alta carga) que minimiza o tempo neste circuito — ex.: Monza × Mônaco."""
    lv = np.linspace(0, 1, n)
    t = [_lap(track, aero_level_car(car, x), env, fuel_kg, ds) for x in lv]
    k = int(np.argmin(t))
    return {"levels": lv.tolist(), "lap_times": t, "best_level": float(lv[k]), "best_time": t[k]}


def optimize_param(track: str, car: CarConfig, param: str, lo: float, hi: float, env: Environment | None = None, fuel_kg: float = 40.0,
                   ds: float = 8.0, tol: float = 1e-3, max_iter: int = 30) -> dict:
    """Busca por seção áurea do valor de `param` em [lo, hi] que minimiza o tempo (ex.: relação final). Assume função unimodal."""
    if param not in _PARAMS or not lo < hi:
        raise ValueError("Parâmetro inválido ou intervalo vazio")
    f = lambda x: _lap(track, car.copy(**{param: x}), env, fuel_kg, ds)  # noqa: E731
    phi = (math.sqrt(5) - 1) / 2
    a, b = lo, hi
    c, d = b - phi * (b - a), a + phi * (b - a)
    fc, fd = f(c), f(d)
    n = 2
    while (b - a) > tol * max(abs(b), 1.0) and n < max_iter + 2:
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - phi * (b - a); fc = f(c)
        else:
            a, c, fc = c, d, fd
            d = a + phi * (b - a); fd = f(d)
        n += 1
    x = 0.5 * (a + b)
    return {"param": param, "best_value": x, "best_time": f(x), "evaluations": n + 1, "interval": [lo, hi]}
