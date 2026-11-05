"""Animação do carro de F1 2026 de referência: rodas giram e os elementos ATIVOS das asas alternam modo curva ↔ modo reta.

Um ciclo (720° de entrada) vai de modo curva (máx. downforce) → modo reta (baixo arrasto) → modo curva. As rodas giram em ``WHEEL_TURNS``
voltas por ciclo, só para visualização (sem relação com velocidade real). Não há dinâmica de veículo, suspensão em curso nem direção.
"""
from __future__ import annotations

import math
import re

import numpy as np

from modules.kinematics import Link, Mechanism, rotation_about
from samples.f1_2026 import (AERO_FRONT_FLAP, AERO_REAR_FLAP, AXLE_Z, FRONT_FLAP_HINGE, REAR_FLAP_HINGE, WB)

XAX = (1.0, 0.0, 0.0)
WHEEL_TURNS = 2.0                 # voltas das rodas a cada 360° de entrada (4 voltas por ciclo de 720°)


def blend(t_deg: float) -> float:
    """0 = modo curva, 1 = modo reta, suave (aceleração contínua), periódico em 720°."""
    return 0.5 * (1.0 - math.cos(2.0 * math.pi * t_deg / 720.0))


def _stem(name: str) -> str:
    return re.sub(r"\s*#\d+$", "", name).strip()


def build_f1_mechanism(components) -> Mechanism:
    leaves = list(components.leaves())
    mech = Mechanism("Carro F1 2026 — rodas e aerodinâmica ativa", "Ciclo de animação (°) — 0 e 720 = modo curva, 360 = modo reta", 720.0)
    flap_f = [l for l in leaves if _stem(l.name) == "Asa dianteira flap ativo"]
    flap_r = [l for l in leaves if _stem(l.name) == "Asa traseira elemento ativo"]
    if not (flap_f and flap_r):
        return mech
    for axle, y in (("dianteiras", 0.0), ("traseiras", WB)):
        ids = [l.id for l in leaves if _stem(l.name).split(" ")[0] in ("Pneu", "Roda", "Cubo") + ("Disco",) and f"{'dianteira' if y == 0 else 'traseira'}" in l.name]
        if ids:
            mech.links.append(Link(ids, lambda t, y=y: rotation_about((0, y, AXLE_Z), XAX, math.radians(t) * WHEEL_TURNS), f"Rodas {axle}",
                                   js={"t": "rx", "y": y, "z": AXLE_Z, "r": WHEEL_TURNS}))
    for ids, (yh, zh), amp, label in ((flap_f, FRONT_FLAP_HINGE, AERO_FRONT_FLAP, "Flap ativo dianteiro"), (flap_r, REAR_FLAP_HINGE, AERO_REAR_FLAP, "Elemento ativo traseiro")):
        mech.links.append(Link([l.id for l in ids], lambda t, yh=yh, zh=zh, amp=amp: rotation_about((0, yh, zh), XAX, -math.radians(amp) * blend(t)), label,
                               js={"t": "rxcos", "y": yh, "z": zh, "amp": -amp}))
    mech.readout = lambda t: (f"Modo aerodinâmico: {blend(t) * 100:.0f}% reta · flap dianteiro −{AERO_FRONT_FLAP * blend(t):.1f}° · "
                              f"elemento traseiro −{AERO_REAR_FLAP * blend(t):.1f}° · rodas {t * WHEEL_TURNS / 360.0:.2f} voltas")
    mech.notes = ["Só os elementos ATIVOS das asas e as rodas se movem; o resto é fixo. Sem dinâmica de veículo, direção ou curso da suspensão.",
                  "Aberturas dos flaps (16° e 38°) são ILUSTRATIVAS; o regulamento define os modos mas não esses ângulos.",
                  "Rodas: 2 voltas por 360° de entrada, só para visualizar o giro."]
    return mech
