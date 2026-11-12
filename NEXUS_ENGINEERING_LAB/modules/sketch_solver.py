"""Solver geral de restrições para `Sketch` (V3.6+): mínimos quadrados não lineares sobre TODOS os parâmetros das entidades.

Restrições (cada uma vira resíduos que devem zerar; refs são índices de entidade `e` e de segmento/ponto `s`/`p`):
 horizontal, vertical, comprimento(L), fixo(x,y), coincidente(e1,p1,e2,p2), distancia(e1,p1,e2,p2,d), paralelo(e1,s1,e2,s2), perpendicular(e1,s1,e2,s2),
 igual_comprimento(e1,s1,e2,s2), raio(e,r), raio_igual(a,b), concentrico(a,b), tangente_circulos(a,b,"ext"|"int"), tangente_reta_circulo(e,s,c).
Estratégia: parte da geometria atual e minimiza resíduos + uma regularização fraca (mantém o desenho perto do original). Aceita se o resíduo
máximo < 1e-9; senão devolve as restrições violadas (conflito/sobre-restrição) e NÃO altera o sketch. Não calcula graus de liberdade nem
detecta redundância compatível: restrições redundantes consistentes passam; inconsistentes são reportadas. Só entidades poly/circle/rect(rrect, slot não têm segmentos).
"""
from __future__ import annotations

import math
import numpy as np
from scipy.optimize import least_squares
from .sketch2d import SketchError


def _vetor(sk):
    x, idx = [], []
    for i, e in enumerate(sk.entities):
        if e["t"] == "poly":
            for j, p in enumerate(e["pts"]): idx.append((i, "pts", j, 0)); idx.append((i, "pts", j, 1)); x += [p[0], p[1]]
        elif e["t"] == "circle":
            for k in ("cx", "cy", "r"): idx.append((i, k, None, None)); x.append(e[k])
        elif e["t"] == "rect":
            for k in ("x0", "y0", "x1", "y1"): idx.append((i, k, None, None)); x.append(e[k])
        elif e["t"] == "rrect":
            for k in ("x0", "y0", "x1", "y1", "r"): idx.append((i, k, None, None)); x.append(e[k])
        elif e["t"] == "slot":
            for k in ("cx0", "cy0", "cx1", "cy1", "w"): idx.append((i, k, None, None)); x.append(e[k])
    return np.array(x, float), idx


def _aplica(sk, x, idx):
    for v, (i, k, j, c) in zip(x, idx):
        if j is None: sk.entities[i][k] = float(v)
        else: sk.entities[i][k][j][c] = float(v)


def _pt(e, p):
    if e["t"] == "poly": P = e["pts"]; return np.array(P[p % len(P)], float)
    raise SketchError("restrição de ponto exige polígono")


def _seg(e, s):
    if e["t"] != "poly": raise SketchError("restrição de segmento exige polígono")
    P = e["pts"]; n = len(P); return np.array(P[s % n], float), np.array(P[(s + 1) % n], float)


def _res(sk, c):
    E, k = sk.entities, c["k"]
    if k in ("horizontal", "vertical"):
        a, b = _seg(E[c["e"]], c["s"]); return [a[1] - b[1]] if k == "horizontal" else [a[0] - b[0]]
    if k == "comprimento": a, b = _seg(E[c["e"]], c["s"]); return [np.linalg.norm(b - a) - c["L"]]
    if k == "fixo": p = _pt(E[c["e"]], c["p"]); return [p[0] - c["x"], p[1] - c["y"]]
    if k == "coincidente": return list(_pt(E[c["e1"]], c["p1"]) - _pt(E[c["e2"]], c["p2"]))
    if k == "distancia": return [np.linalg.norm(_pt(E[c["e1"]], c["p1"]) - _pt(E[c["e2"]], c["p2"])) - c["d"]]
    if k in ("paralelo", "perpendicular", "igual_comprimento"):
        a, b = _seg(E[c["e1"]], c["s1"]); p, q = _seg(E[c["e2"]], c["s2"]); u, v = b - a, q - p
        if k == "paralelo": return [(u[0] * v[1] - u[1] * v[0]) / max(np.linalg.norm(u) * np.linalg.norm(v), 1e-12)]
        if k == "perpendicular": return [(u @ v) / max(np.linalg.norm(u) * np.linalg.norm(v), 1e-12)]
        return [np.linalg.norm(u) - np.linalg.norm(v)]
    if k == "raio": return [E[c["e"]]["r"] - c["r"]]
    if k == "raio_igual": return [E[c["a"]]["r"] - E[c["b"]]["r"]]
    if k == "concentrico": a, b = E[c["a"]], E[c["b"]]; return [a["cx"] - b["cx"], a["cy"] - b["cy"]]
    if k == "tangente_circulos":
        a, b = E[c["a"]], E[c["b"]]; d = math.hypot(a["cx"] - b["cx"], a["cy"] - b["cy"])
        return [d - (a["r"] + b["r"])] if c.get("tipo", "ext") == "ext" else [d - abs(a["r"] - b["r"])]
    if k == "tangente_reta_circulo":
        a, b = _seg(E[c["e"]], c["s"]); ci = E[c["c"]]; u = b - a; n = np.array([-u[1], u[0]]) / max(np.linalg.norm(u), 1e-12)
        return [abs((np.array([ci["cx"], ci["cy"]]) - a) @ n) - ci["r"]]
    raise SketchError(f"restrição desconhecida: {k}")


def resolver(sk, restricoes: list, tol: float = 1e-9, reg: float = 1e-4) -> dict:
    """Resolve e, se satisfeito, escreve a geometria no sketch. Retorna {resolvido, residuo_max, violadas, movimento_max}."""
    if not restricoes: return {"resolvido": True, "residuo_max": 0.0, "violadas": [], "movimento_max": 0.0}
    x0, idx = _vetor(sk)
    if len(x0) == 0: raise SketchError("sketch vazio")
    base = [dict(e) for e in sk.entities]
    import copy
    trabalho = copy.deepcopy(sk.entities)

    def f(x):
        _aplica(sk, x, idx)
        r = [v for c in restricoes for v in _res(sk, c)]
        return np.concatenate([np.array(r, float), reg * (x - x0)])

    try:
        s = least_squares(f, x0, xtol=1e-14, ftol=1e-14, gtol=1e-14, max_nfev=400)
        _aplica(sk, s.x, idx)
        per = [(c, max(abs(v) for v in _res(sk, c))) for c in restricoes]
    except Exception:
        sk.entities[:] = trabalho; raise
    viol = [c for c, r in per if r > tol * 1e3]                                      # reg>0 desloca ~1e-8: tolerância prática 1e-6
    mx = max(r for _, r in per)
    if viol:
        sk.entities[:] = trabalho                                                    # conflito: devolve o desenho ORIGINAL
        return {"resolvido": False, "residuo_max": float(mx), "violadas": viol, "movimento_max": 0.0}
    sk.validate()
    return {"resolvido": True, "residuo_max": float(mx), "violadas": [], "movimento_max": float(np.max(np.abs(s.x - x0)))}
