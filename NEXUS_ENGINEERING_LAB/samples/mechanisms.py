"""Escolhe o mecanismo (animação) pelo conteúdo do projeto: motor 4 cilindros, carro F1 2026 ou nenhum."""
from __future__ import annotations

from modules.kinematics import Mechanism


def build_mechanism(components) -> Mechanism:
    from samples.motor_mechanism import build_engine_mechanism
    mech = build_engine_mechanism(components)
    if mech.links:
        return mech
    from samples.f1_mechanism import build_f1_mechanism
    return build_f1_mechanism(components)
