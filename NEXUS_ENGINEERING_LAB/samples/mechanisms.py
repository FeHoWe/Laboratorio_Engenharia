"""Escolhe o mecanismo (animação) pelo conteúdo do projeto (motor 4 cil., F1 2026 e projetos V2.7) ou nenhum."""
from __future__ import annotations

from modules.kinematics import Mechanism


def build_mechanism(components) -> Mechanism:
    from samples.motor_mechanism import build_engine_mechanism
    mech = build_engine_mechanism(components)
    if mech.links:
        return mech
    from samples import extra_mechanisms as xm
    for fn in (xm.build_wankel_mechanism, xm.build_v12_mechanism, xm.build_robot_mechanism, xm.build_pump_mechanism, xm.build_wind_mechanism,
               xm.build_jet_mechanism, xm.build_crane_mechanism):
        mech = fn(components)
        if mech.links:
            return mech
    from samples.f1_mechanism import build_f1_mechanism
    return build_f1_mechanism(components)
