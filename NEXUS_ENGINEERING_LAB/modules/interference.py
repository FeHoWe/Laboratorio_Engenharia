"""Verificação de interferência (colisão) estática entre componentes — B-rep exato (OpenCascade), V2.4.

Para cada par de peças cujas caixas se sobrepõem, calcula o volume da interseção booleana (BRepAlgoAPI_Common). Pares com volume >= ``min_volume`` (mm³)
são reportados. Toque de faces (volume 0) não conta como interferência.
HONESTIDADE: é verificação ESTÁTICA na pose atual do modelo (não varre o movimento); peças que se encaixam de propósito (interferência de montagem de
um rolamento, solda) aparecem como colisão — a decisão é sua. Resultados dependem da tolerância do B-rep importado.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Callable, Optional

from OCP.BRepAlgoAPI import BRepAlgoAPI_Common


@dataclass
class Clash:
    a_id: str
    a_name: str
    b_id: str
    b_name: str
    volume: float          # mm³


def find_interferences(components, min_volume: float = 1.0, ids: Optional[set] = None, progress: Optional[Callable[[int, int], None]] = None) -> list[Clash]:
    from samples import geo as g          # volume() e bbox()
    leaves = [l for l in components.leaves() if l.shape is not None and (ids is None or l.id in ids)]
    boxes = [g.bbox(l.shape) for l in leaves]
    pairs = []
    for i, j in itertools.combinations(range(len(leaves)), 2):
        a, b = boxes[i], boxes[j]
        if any(a[1][k] < b[0][k] + 1e-3 or b[1][k] < a[0][k] + 1e-3 for k in range(3)):
            continue
        pairs.append((i, j))
    out: list[Clash] = []
    for n, (i, j) in enumerate(pairs):
        if progress:
            progress(n, len(pairs))
        try:
            v = g.volume(BRepAlgoAPI_Common(leaves[i].shape, leaves[j].shape).Shape())
        except Exception:                                   # booleana pode falhar em geometria degenerada: ignora o par
            continue
        if v >= min_volume:
            out.append(Clash(leaves[i].id, leaves[i].name, leaves[j].id, leaves[j].name, float(v)))
    out.sort(key=lambda c: -c.volume)
    return out


def to_csv(clashes: list[Clash]) -> str:
    rows = ["peca_a;peca_b;volume_mm3"] + [f"{c.a_name};{c.b_name};{c.volume:.1f}" for c in clashes]
    return "\n".join(rows) + "\n"
