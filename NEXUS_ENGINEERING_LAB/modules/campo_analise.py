"""V102 (Fase C) — Análise de campos de resultado (FEA) sobre a malha: regiões críticas, consulta por nó/elemento, malha deformada e escala de cores.

Funções puras sobre arrays NumPy; não resolvem nada (o solver é `fea3d`/CalculiX). Convenções: tensões em MPa, deslocamentos em mm.
Limite honesto: a tensão do Tet4 é CONSTANTE por elemento (não suavizada) e “região crítica” é só um recorte por limiar sobre o campo calculado:
não é critério de falha nem de projeto. O fator multiplicador da deformada é apenas visual e SEMPRE deve ser exibido ao usuário.
"""
from __future__ import annotations

import numpy as np


def _arr(x, nome):
    a = np.asarray(x, dtype=float)
    if a.ndim == 0 or a.size == 0 or not np.isfinite(a).all():
        raise ValueError(f"{nome}: vazio ou com valores não finitos")
    return a


def regioes_criticas(centros, valores, fracao_do_maximo: float = 0.8) -> dict:
    """Elementos com valor ≥ fração × máximo, agrupados em componentes conexos por proximidade (distância ≤ 2× a menor distância típica entre vizinhos)."""
    c, v = _arr(centros, "centros"), _arr(valores, "valores")
    if c.ndim != 2 or c.shape[1] != 3 or len(c) != len(v):
        raise ValueError("centros (n,3) e valores (n) devem ter o mesmo n")
    if not 0 < fracao_do_maximo <= 1:
        raise ValueError("fracao_do_maximo deve estar em (0, 1]")
    vmax = float(v.max())
    if vmax <= 0:
        return {"limiar": 0.0, "valor_max": vmax, "n_elementos": 0, "regioes": [], "avisos": ["campo sem valores positivos"]}
    lim = fracao_do_maximo * vmax
    idx = np.flatnonzero(v >= lim)
    from scipy.spatial import cKDTree
    t_all = cKDTree(c)
    d_nn = t_all.query(c, k=2)[0][:, 1]
    raio = 2.0 * float(np.median(d_nn[d_nn > 0])) if (d_nn > 0).any() else 0.0
    pts = c[idx]
    pai = list(range(len(idx)))

    def raiz(i):
        while pai[i] != i:
            pai[i] = pai[pai[i]]; i = pai[i]
        return i
    for i, j in cKDTree(pts).query_pairs(raio):
        pai[raiz(i)] = raiz(j)
    grupos: dict[int, list[int]] = {}
    for k in range(len(idx)):
        grupos.setdefault(raiz(k), []).append(int(idx[k]))
    regs = []
    for g in grupos.values():
        gv = v[g]
        regs.append({"n_elementos": len(g), "valor_max": float(gv.max()), "valor_medio": float(gv.mean()), "centro": [float(x) for x in c[g].mean(axis=0)], "elementos": sorted(g)})
    regs.sort(key=lambda r: -r["valor_max"])
    return {"limiar": float(lim), "valor_max": vmax, "n_elementos": int(len(idx)), "regioes": regs,
            "avisos": ["Região crítica = recorte por limiar sobre o campo calculado; não é critério de falha.", "Tensão por elemento (Tet4 constante, não suavizada)."]}


def consultar(pontos, valores, ponto, k: int = 1) -> list[dict]:
    """Valor(es) do campo nos `k` pontos (nós ou centros de elementos) mais próximos de `ponto`, com a distância (mm)."""
    p, v = _arr(pontos, "pontos"), _arr(valores, "valores")
    q = _arr(ponto, "ponto")
    if p.ndim != 2 or p.shape[1] != 3 or len(p) != len(v) or q.shape != (3,):
        raise ValueError("pontos (n,3), valores (n) e ponto (3) devem ser consistentes")
    k = max(1, min(int(k), len(p)))
    d = np.linalg.norm(p - q, axis=1)
    return [{"indice": int(i), "posicao": [float(x) for x in p[i]], "valor": float(v[i]), "distancia_mm": float(d[i])} for i in np.argsort(d)[:k]]


def deformada(nos, u, fator: float = 1.0) -> dict:
    """Nós deslocados `nos + fator·u`. O fator é só visual; devolvido junto para ser exibido."""
    n, d = _arr(nos, "nós"), _arr(u, "u")
    if n.shape != d.shape or n.ndim != 2 or n.shape[1] != 3:
        raise ValueError("nós e u devem ter forma (n,3)")
    if fator < 0:
        raise ValueError("fator deve ser ≥ 0")
    return {"nos": n + fator * d, "fator_visual": float(fator), "u_max_mm": float(np.linalg.norm(d, axis=1).max()),
            "aviso": f"Deformada ampliada {fator:g}× apenas para visualização; deslocamentos reais são {fator:g}× menores."}


def fator_sugerido(nos, u, fracao_do_tamanho: float = 0.1) -> float:
    """Fator visual que faz o maior deslocamento valer `fracao_do_tamanho` da maior dimensão da peça (1,0 se o deslocamento for nulo)."""
    n, d = _arr(nos, "nós"), _arr(u, "u")
    dim = float((n.max(axis=0) - n.min(axis=0)).max())
    um = float(np.linalg.norm(d, axis=1).max())
    return 1.0 if um <= 0 or dim <= 0 else fracao_do_tamanho * dim / um


def escala_de_cores(valores, minimo=None, maximo=None, n_faixas: int = 8) -> dict:
    """Limites e faixas da legenda. Sem limites do usuário usa [min, max] do campo; limites do usuário só recortam a COR, não os valores."""
    v = _arr(valores, "valores")
    lo = float(v.min()) if minimo is None else float(minimo)
    hi = float(v.max()) if maximo is None else float(maximo)
    if not lo < hi:
        raise ValueError("escala: mínimo deve ser menor que máximo")
    if not 2 <= n_faixas <= 64:
        raise ValueError("n_faixas deve estar entre 2 e 64")
    return {"minimo": lo, "maximo": hi, "faixas": [float(x) for x in np.linspace(lo, hi, n_faixas + 1)], "recortada": minimo is not None or maximo is not None,
            "fora_da_escala": int(((v < lo) | (v > hi)).sum())}
