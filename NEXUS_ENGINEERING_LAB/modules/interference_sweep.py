"""Varredura de interferência DURANTE o movimento (V2.5): aplica a pose do mecanismo em cada ângulo e mede, por booleana exata (OpenCascade), a
sobreposição de cada par em que pelo menos uma peça se move. Reporta pares cuja sobreposição CRESCE em relação à pose estática do modelo.

HONESTIDADE: amostragem discreta (um ângulo pode escapar entre dois passos: use passo pequeno em regiões críticas); o movimento é o do mecanismo
prescrito (sem folgas, dinâmica, deformação ou tolerâncias); encaixes propositais aparecem como colisão; toque de faces (volume 0) não conta.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.gp import gp_Trsf


@dataclass
class SweepClash:
    a_id: str
    a_name: str
    b_id: str
    b_name: str
    base_volume: float      # mm³ na pose estática do modelo
    max_volume: float       # mm³ máximo durante o ciclo
    theta_at_max: float     # ° do maior volume
    first_theta: float      # ° da primeira amostra com sobreposição acima do mínimo


def _transformed(shape, m: np.ndarray):
    t = gp_Trsf()
    t.SetValues(m[0, 0], m[0, 1], m[0, 2], m[0, 3], m[1, 0], m[1, 1], m[1, 2], m[1, 3], m[2, 0], m[2, 1], m[2, 2], m[2, 3])
    return BRepBuilderAPI_Transform(shape, t, True).Shape()


def sweep(components, mechanism, thetas, min_volume: float = 1.0, progress: Optional[Callable[[int, int], None]] = None) -> list[SweepClash]:
    from samples import geo as g
    leaves = [l for l in components.leaves() if l.shape is not None]
    moving = mechanism.moving_ids
    base_box = {l.id: g.bbox(l.shape) for l in leaves}
    # volume estático dos pares candidatos (pelo menos uma peça móvel, caixas que se tocam em algum momento do ciclo são avaliadas lazy)
    base_cache: dict = {}

    def vol(a_shape, b_shape) -> float:
        try:
            return float(g.volume(BRepAlgoAPI_Common(a_shape, b_shape).Shape()))
        except Exception:                                   # booleana pode falhar em geometria degenerada
            return 0.0

    def overlap(a, b):
        return not any(a[1][k] < b[0][k] + 1e-3 or b[1][k] < a[0][k] + 1e-3 for k in range(3))

    by_id = {l.id: l for l in leaves}
    state: dict = {}
    total = len(thetas)
    for n, th in enumerate(thetas):
        if progress:
            progress(n, total)
        poses = mechanism.poses(float(th))
        shape_at, box_at = {}, {}
        for l in leaves:
            if l.id in moving and l.id in poses:
                s = _transformed(l.shape, poses[l.id])
                shape_at[l.id], box_at[l.id] = s, g.bbox(s)
            else:
                shape_at[l.id], box_at[l.id] = l.shape, base_box[l.id]
        for a, b in itertools.combinations(leaves, 2):
            if a.id not in moving and b.id not in moving:
                continue
            if not overlap(box_at[a.id], box_at[b.id]):
                continue
            key = (a.id, b.id)
            if key not in base_cache:
                base_cache[key] = vol(a.shape, b.shape) if overlap(base_box[a.id], base_box[b.id]) else 0.0
            v = vol(shape_at[a.id], shape_at[b.id])
            rec = state.setdefault(key, {"max": 0.0, "th": float(th), "first": None})
            if v > rec["max"]:
                rec["max"], rec["th"] = v, float(th)
            if v - base_cache[key] >= min_volume and rec["first"] is None:
                rec["first"] = float(th)
    out = []
    for (ai, bi), rec in state.items():
        base = base_cache.get((ai, bi), 0.0)
        if rec["max"] - base >= min_volume:
            out.append(SweepClash(ai, by_id[ai].name, bi, by_id[bi].name, base, rec["max"], rec["th"], rec["first"] if rec["first"] is not None else rec["th"]))
    out.sort(key=lambda c: -(c.max_volume - c.base_volume))
    return out


def to_csv(rows: list[SweepClash]) -> str:
    lines = ["peca_a;peca_b;volume_estatico_mm3;volume_maximo_mm3;angulo_do_maximo_graus;primeiro_angulo_graus"]
    for r in rows:
        lines.append(f"{r.a_name};{r.b_name};{r.base_volume:.1f};{r.max_volume:.1f};{r.theta_at_max:.1f};{r.first_theta:.1f}")
    return "\n".join(lines)
