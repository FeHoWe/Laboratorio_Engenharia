"""Mecanismo do motor de exemplo: biela-manivela, correia dentada 2:1, engrenagens, comandos e válvulas (V1.9).

Eixos como em ``motor_4_cilindros``: virabrequim ao longo de X, cilindros ao longo de Z. A rotação positiva é a regra da
mão direita em torno de +X.
  * Correia: a roda do virabrequim (20 dentes) e a do comando de admissão (40) têm razão EXATA 2:1; os 96 dentes da correia
    são peças que percorrem o trajeto fechado (arcos + tangentes) com a velocidade tangencial das rodas; as ranhuras das
    rodas foram modeladas na fase dos dentes, então o encaixe se mantém em todo o giro.
  * A roda tensora dentada (18 dentes, apoio fixo) mantém o trajeto da correia com 3 rodas (100 dentes).
  * O comando de escape é movido por um par de engrenagens 1:1 e gira ao CONTRÁRIO (-θ/2), como em motores DOHC reais.
  * Válvulas: seguidor de ROLETE na ponta da haste; o deslocamento é calculado do contato entre a curva de passo do rolete e o
    lóbulo modelado (lei de levantamento polinomial H·(1-u²)³ somada a um "pé" largo e baixo que faz a válvula sair da folga suavemente, ambos contínuos até a aceleração), folga de 0,1 mm
    (ver ``cam_table``). É uma lei didática bem comportada, não o perfil de um motor de fabricante.
  * A mola é comprimida por ESCALA em Z apenas para ilustrar (não é movimento rígido).
"""
from __future__ import annotations

import math
import re

import numpy as np

from modules.kinematics import Link, Mechanism, rotation_about, scale_about, translation
from samples.motor_4_cilindros import (CAM_Y, CAM_Z, CX, FIRE_DEG, IDLER_Y, IDLER_Z, N_CRANK, N_IDLER, ROD_LEN, SPRING_Z0, SPRING_Z1, THROW, UP, belt_design,
                                        cam_lift, cam_peak, cam_table, valve_center_deg, valve_displacement)

XAX = (1.0, 0.0, 0.0)


def valve_lift(theta_deg: float, cyl: int, intake: bool) -> float:
    """Deslocamento absoluto (mm) da válvula, derivado do lóbulo modelado (0 = válvula fechada, com folga)."""
    return valve_displacement(theta_deg, cyl, intake)


def valve_diagram(cyl: int = 0, step: float = 1.0) -> dict:
    """Diagrama cinemático da válvula do cilindro ``cyl`` (admissão e escape) por ângulo de virabrequim, 0..720°.

    ``lift`` em mm; ``vel`` em m/s e ``acc`` em m/s² PARA 1000 rpm (a velocidade escala com rpm, a aceleração com rpm²).
    Só cinemática do levantamento prescrito: não inclui mola, massa, folga dinâmica nem flutuação.
    """
    th = np.arange(0.0, 720.0 + step / 2, step)
    r = np.radians(th)
    w = 2.0 * math.pi * 1000.0 / 60.0
    out = {"step": step, "n": len(th), "ref_rpm": 1000.0}
    for key, it in (("int", True), ("exh", False)):
        lift = np.array([valve_lift(t, cyl, it) for t in th])
        d1 = np.gradient(lift, r)
        out[key] = {"lift": [round(float(v), 4) for v in lift],
                    "vel": [round(float(v), 4) for v in d1 * w / 1000.0],
                    "acc": [round(float(v), 2) for v in np.gradient(d1, r) * w * w / 1000.0]}
    return out


def crank_pin(cyl: int, theta_deg: float) -> tuple[float, float]:
    """(y, z) do centro do moente do cilindro ``cyl`` para a manivela girada de theta (rotação em torno de +X)."""
    zc = THROW if UP[cyl] else -THROW
    t = math.radians(theta_deg)
    return -zc * math.sin(t), zc * math.cos(t)


def piston_z(cyl: int, theta_deg: float) -> float:
    """Altura (z) do centro do pino do pistão (biela-manivela centrada, sem desaxe)."""
    py, pz = crank_pin(cyl, theta_deg)
    return pz + math.sqrt(ROD_LEN ** 2 - py ** 2)


def _stem(name: str) -> str:
    return re.sub(r"\s*#\d+$", "", name).strip()


def build_engine_mechanism(components) -> Mechanism:
    """Monta o mecanismo achando as peças do exemplo pelo NOME. Devolve Mechanism vazio se o modelo não for o exemplo."""
    leaves = list(components.leaves())

    def of(stem: str) -> list:
        return [l for l in leaves if _stem(l.name) == stem]

    rods, pists, pins = of("Biela"), of("Pistao"), of("Pino do pistao")
    mech = Mechanism("Motor 4 cilindros — biela-manivela", "Ângulo do virabrequim (°)", 720.0)
    if not (len(rods) == len(pists) == len(pins) == len(CX)) or not of("Virabrequim"):
        return mech

    crank_ids = [l.id for l in of("Virabrequim") + of("Volante do motor") + of("Polia do virabrequim") + of("Roda dentada do virabrequim")]
    mech.links.append(Link(crank_ids, lambda t: rotation_about((0, 0, 0), XAX, math.radians(t)), "Virabrequim e acessórios",
                           js={"t": "rx", "y": 0, "z": 0, "r": 1}))

    for i in range(len(CX)):
        zc = THROW if UP[i] else -THROW
        z0 = zc + ROD_LEN
        big0 = np.array([CX[i], 0.0, zc])

        def rod_fn(t, i=i, big0=big0):
            py, pz = crank_pin(i, t)
            zp = piston_z(i, t)
            alpha = math.atan2(py, zp - pz)            # inclinação da biela: (y,z) do eixo = (-sin α, cos α); vy = -py
            return translation((0, py, pz - big0[2])) @ rotation_about(big0, XAX, alpha)

        def slide_fn(t, i=i, z0=z0):
            return translation((0, 0, piston_z(i, t) - z0))

        mech.links.append(Link([rods[i].id], rod_fn, f"Biela {i + 1}", js={"t": "rod", "cx": CX[i], "zc": zc, "L": ROD_LEN}))
        mech.links.append(Link([pists[i].id, pins[i].id], slide_fn, f"Pistão {i + 1}", js={"t": "sl", "zc": zc, "L": ROD_LEN}))

    # comandos: admissão +θ/2 (correia 2:1), escape -θ/2 (engrenagem 1:1 com a admissão)
    ids_in = [l.id for l in of("Comando de admissao") + of("Roda dentada do comando de admissao") + of("Engrenagem do comando de admissao")]
    ids_ex = [l.id for l in of("Comando de escape") + of("Engrenagem do comando de escape")]
    mech.links.append(Link(ids_in, lambda t: rotation_about((0, -CAM_Y, CAM_Z), XAX, math.radians(t) / 2.0),
                           "Comando de admissão (θ/2)", js={"t": "rx", "y": -CAM_Y, "z": CAM_Z, "r": 0.5}))
    mech.links.append(Link(ids_ex, lambda t: rotation_about((0, CAM_Y, CAM_Z), XAX, -math.radians(t) / 2.0),
                           "Comando de escape (-θ/2)", js={"t": "rx", "y": CAM_Y, "z": CAM_Z, "r": -0.5}))

    # roda tensora (apoio fixo): gira na velocidade tangencial da correia, no mesmo sentido do virabrequim
    ratio = N_CRANK / N_IDLER
    mech.links.append(Link([l.id for l in of("Roda tensora dentada")],
                           lambda t: rotation_about((0, IDLER_Y, IDLER_Z), XAX, math.radians(t) * ratio),
                           f"Roda tensora ({N_CRANK}/{N_IDLER}·θ)", js={"t": "rx", "y": IDLER_Y, "z": IDLER_Z, "r": ratio}))

    # dentes da correia: cada um percorre o trajeto com a velocidade tangencial da roda do virabrequim
    bd = belt_design()
    teeth = of("Dente da correia")
    if len(teeth) == bd["m"]:
        path, rc = bd["path"], bd["rc"]
        for k, (tooth, s0) in enumerate(zip(teeth, bd["s0"])):
            f0inv = np.linalg.inv(path.frame(s0))
            mech.links.append(Link([tooth.id], lambda t, s0=s0, f0inv=f0inv: path.frame(s0 + rc * math.radians(t)) @ f0inv,
                                   f"Dente da correia {k + 1}", js={"t": "belt", "s0": round(float(s0), 6)}))
        mech.extra["belt"] = {"path": path.to_json(), "rc": rc}

    z_valve = None
    for intake, vstem, sstem in ((True, "Valvula de admissao", "Mola de valvula de admissao"),
                                 (False, "Valvula de escape", "Mola de valvula de escape")):
        valves, springs = of(vstem), of(sstem)
        if len(valves) != 2 * len(CX) or len(springs) != 2 * len(CX):
            continue
        for k in range(2 * len(CX)):
            cyl = k // 2
            d0 = valve_lift(0.0, cyl, intake)                       # o modelo já está na pose de θ=0
            mech.links.append(Link([valves[k].id], lambda t, c=cyl, it=intake, d0=d0: translation((0, 0, -(valve_lift(t, c, it) - d0))),
                                   f"{vstem} {k + 1}", js={"t": "valve", "c": valve_center_deg(cyl, intake), "x": 0 if intake else 1,
                                                           "pk": cam_peak(intake), "d0": d0}))
            bb = components.bbox(springs[k])
            base = np.array([(bb.min[0] + bb.max[0]) / 2, (bb.min[1] + bb.max[1]) / 2, SPRING_Z0])
            ln = SPRING_Z1 - SPRING_Z0
            mech.links.append(Link([springs[k].id],
                                   lambda t, c=cyl, it=intake, b=base, d0=d0, ln=ln: scale_about(b, (1, 1, (ln - valve_lift(t, c, it)) / (ln - d0))),
                                   f"{sstem} {k + 1} (compressão ilustrativa)", rigid=False,
                                   js={"t": "spring", "c": valve_center_deg(cyl, intake), "x": 0 if intake else 1, "pk": cam_peak(intake),
                                       "b": [round(float(x), 4) for x in base], "len": ln, "d0": d0}))
    mech.extra["diagram"] = valve_diagram(0)
    mech.extra["cam"] = {"int": [round(v, 5) for v in cam_table(True)], "exh": [round(v, 5) for v in cam_table(False)]}

    def readout(t: float) -> str:
        psi = t % 720.0
        pz = [piston_z(i, t) - ((THROW if UP[i] else -THROW) + ROD_LEN) for i in range(len(CX))]
        opened_i = [i + 1 for i in range(len(CX)) if valve_lift(t, i, True) > 0.05]
        opened_e = [i + 1 for i in range(len(CX)) if valve_lift(t, i, False) > 0.05]
        lifts = max(valve_lift(t, i, it) for i in range(len(CX)) for it in (True, False))
        return (f"Ciclo {psi:.0f}° / 720° · comando adm. {((t / 2.0) % 360.0):.0f}° · comando esc. {((-t / 2.0) % 360.0):.0f}°\n"
                "Pistões (Δz vs. θ=0, mm): " + "  ".join(f"P{i + 1} {d:+.1f}" for i, d in enumerate(pz)) + "\n"
                f"Válvulas abertas — admissão: cil. {opened_i or '—'} · escape: cil. {opened_e or '—'} · maior abertura {lifts:.2f} mm")
    mech.readout = readout
    mech.notes = [
        "Só movimentos prescritos: sem dinâmica, forças, contato, folgas de montagem nem atrito.",
        "Biela-manivela centrada (sem desaxe do pino); comprimento da biela e curso do modelo.",
        f"Correia: {bd['m']} dentes, roda do virabrequim com 20 e a do comando de admissão com 40 (2:1 exato). Comando de escape por "
        "engrenagens de evolvente 1:1 (módulo 2, 26 dentes, concordância de 0,3 mm no pé; gira ao contrário). Dentes da correia/rodas com perfil trapezoidal tipo HTD "
        "simplificado.",
        "Válvulas: seguidor de rolete; levantamento calculado do contato rolete×lóbulo (lei polinomial suave com pé de ataque, ~7,7 mm, folga 0,1 mm); "
        "não é o perfil de um motor de fabricante; seguidor sempre em contato (sem flutuação); a mola só é comprimida por escala (ilustração).",
        "Roda tensora dentada de apoio FIXO (sem mola, excêntrico ou amortecedor): é geometria e movimento, não há cálculo de tensão da correia; "
        "bloco, cabeçote e demais peças ficam parados.",
        "Diagrama de válvulas: velocidade e aceleração vêm da derivada numérica do levantamento prescrito (cinemática pura); "
        "o lóbulo tem um pé de ataque (rampa de folga) que evita pico de aceleração ao sair da folga de 0,1 mm.",
        "Ordem de ignição 1-3-4-2; θ=0 com os pistões 1 e 4 no PMS.",
    ]
    return mech
