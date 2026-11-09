"""Massa, centro de gravidade, distribuição de peso e inércia a partir de massas pontuais (V2.8).

Entrada: itens (nome, massa kg, posição mm). Só entram peças COM material escolhido pelo usuário (regra do software). Lastro e piloto são
informados por você. Inércia = soma de massas pontuais (ignora a inércia própria de cada peça) — aproximação declarada.
Eixos: ``eixo_long`` = índice da coordenada longitudinal (1 = y no modelo F1), ``eixo_alt`` = altura (2 = z).
"""
from __future__ import annotations

import numpy as np


def balance(items, y_front: float, y_rear: float, eixo_long: int = 1, eixo_alt: int = 2) -> dict:
    items = [(n, float(m), np.asarray(p, float)) for n, m, p in items if m and m > 0]
    if not items:
        raise ValueError("sem itens com massa")
    M = sum(m for _, m, _ in items)
    cg = sum(m * p for _, m, p in items) / M
    wb = abs(y_rear - y_front)
    if wb <= 0:
        raise ValueError("entre-eixos deve ser positivo")
    sgn = 1.0 if y_rear > y_front else -1.0
    front_pct = 100.0 * (sgn * (y_rear - cg[eixo_long])) / wb          # fração sobre o eixo dianteiro
    I = np.zeros((3, 3))
    for _, m, p in items:
        d = (p - cg) / 1000.0
        I += m * ((d @ d) * np.eye(3) - np.outer(d, d))
    return {"massa_kg": M, "cg_mm": tuple(float(c) for c in cg), "pct_dianteiro": front_pct, "pct_traseiro": 100.0 - front_pct,
            "altura_cg_mm": float(cg[eixo_alt]), "inercia_kgm2": I.tolist(), "n_itens": len(items)}


def lastro_para_alvo(items, alvo_kg: float, pos_lastro, y_front: float, y_rear: float) -> dict:
    """Massa de lastro (na posição dada) que leva o total ao ``alvo_kg`` e o balanço resultante. Lastro negativo = já passa do alvo."""
    M = sum(m for _, m, _ in items if m)
    falta = alvo_kg - M
    if falta < 0:
        return {"lastro_kg": 0.0, "acima_do_alvo_kg": -falta, "balanco": balance(items, y_front, y_rear)}
    it = list(items) + [("Lastro", falta, pos_lastro)]
    return {"lastro_kg": falta, "acima_do_alvo_kg": 0.0, "balanco": balance(it, y_front, y_rear)}


def items_from_components(components, materials):
    """Itens a partir do projeto aberto (só peças com massa conhecida)."""
    from modules.component_inspector import ComponentInspector
    insp = ComponentInspector(components, materials)
    out = []
    for leaf in components.leaves():
        rep = insp.inspect(leaf)
        if rep.mass is not None and rep.centroid is not None:
            out.append((leaf.name, rep.mass / 1000.0, tuple(float(c) for c in rep.centroid)))
    return out
