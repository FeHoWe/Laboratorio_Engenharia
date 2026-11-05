"""Animação do carro de F1 2026 de referência (V2.3): cenário de 720° com 4 trechos (frenagem → curva → aceleração), em que

  · o chassi faz mergulho/agachamento (arfagem), rolagem e afundamento por downforce (heave) — amplitudes ILUSTRATIVAS, exageradas ~3×;
  · a SUSPENSÃO articula de verdade: cada canto é um mecanismo duplo-A de 3 corpos resolvido numericamente (braços inferior/superior girando
    em torno dos seus pivôs, manga rígida entre as rótulas, barra de direção/tirante de comprimento constante, push/pull-rod, balancim e
    amortecedor telescópico); a roda é mantida no solo (altura do centro da roda), então camber e bitola variam como na geometria;
  · direção: a cremalheira se move ±30 mm, as rodas dianteiras esterçam pelos braços de direção, volante e capacete acompanham;
  · aerodinâmica ativa: flap dianteiro e elemento traseiro vão do modo curva (0) ao modo reta (blend=1) conforme a velocidade/curva;
  · 4 rodas giram (2 voltas por 360° de entrada), virabrequim 4×/rad, biela-pistões por mecanismo biela-manivela exato, rotores do turbo e
    disco de embreagem acompanham.

Só movimento prescrito, sem dinâmica de veículo, sem rigidez de mola/pneu, sem forças. O cenário (esterço, rolagem, mergulho) é uma história
plausível, NÃO uma simulação: roll, pitch e heave não saem de equações do veículo. Pontos de suspensão são plausíveis, não de um carro real.
"""
from __future__ import annotations

import functools
import math
import re

import numpy as np
from scipy.optimize import brentq

from modules.kinematics import Link, Mechanism, rotation_about, translation
from samples import f1_2026 as F

XAX, YAX, ZAX = np.array([1.0, 0, 0]), np.array([0, 1.0, 0]), np.array([0, 0, 1.0])
WHEEL_TURNS = 2.0                # voltas das rodas a cada 360° de entrada
CRANK_R = 4.0                    # rad do virabrequim por rad de entrada (8 voltas por ciclo de 720°)
TURBO_R = 12.0
RACK_MAX = 30.0                  # mm de curso da cremalheira (±)
HEAVE_MAX, PITCH_MAX, ROLL_MAX = 12.0, 0.9, 1.3          # mm, graus, graus (ilustrativos)
WHEEL_ANGLE_DEG = 110.0          # giro do volante a plena esterçada (ilustrativo)
TAB_STEP = 3.0
PITCH_C, ROLL_C = np.array([0.0, 1700.0, 300.0]), np.array([0.0, 0.0, 250.0])
HEAD_P = np.array([0.0, 1000.0, 560.0])
SIDE_KEY = {1: "R", -1: "L"}


def _stem(name: str) -> str:
    return re.sub(r"\s*#\d+$", "", name).strip()


# ------------------------------------------------------------------ cenário
def scenario(t: float) -> dict:
    """Sinais do cenário em função do ângulo de entrada ``t`` (°): s>0 = curva à esquerda."""
    s = math.sin(4 * math.pi * t / 720.0)
    blend = math.cos(math.pi * t / 180.0) ** 2                     # 1 = reta (modo baixo arrasto), 0 = curva (modo downforce)
    return {"s": s, "blend": blend, "rack": RACK_MAX * s, "roll": ROLL_MAX * s, "pitch": PITCH_MAX * math.sin(2 * math.pi * t / 180.0),
            "heave": -HEAVE_MAX * blend}


def body_pose(sc: dict) -> np.ndarray:
    return (translation((0, 0, sc["heave"])) @ rotation_about(PITCH_C, XAX, math.radians(sc["pitch"]))
            @ rotation_about(ROLL_C, YAX, math.radians(sc["roll"])))


# ------------------------------------------------------------------ geometria auxiliar
def _unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def rot_between(u, v) -> np.ndarray:
    u, v = _unit(u), _unit(v)
    c = float(np.dot(u, v))
    if c > 1 - 1e-14:
        return np.eye(3)
    a = np.cross(u, v)
    s2 = float(np.dot(a, a))
    if s2 < 1e-24:                                          # opostos
        p = _unit(np.cross(u, [1, 0, 0]) if abs(u[0]) < 0.9 else np.cross(u, [0, 1, 0]))
        return 2 * np.outer(p, p) - np.eye(3)
    k = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + k + k @ k * ((1 - c) / s2)


def seg_map(a0, b0, a1, b1) -> np.ndarray:
    """Movimento rígido que leva o segmento (a0→b0) a (a1→b1) com rotação mínima (rolagem em torno do próprio eixo é livre)."""
    a0, b0, a1, b1 = (np.asarray(p, float) for p in (a0, b0, a1, b1))
    r = rot_between(b0 - a0, b1 - a1)
    m = np.eye(4)
    m[:3, :3] = r
    m[:3, 3] = a1 - r @ a0
    return m


def _apply(m, p):
    return (m @ np.append(np.asarray(p, float), 1.0))[:3]


class Corner:
    """Um canto do carro: duplo-A + manga + direção + push/pull-rod + balancim + amortecedor, resolvido no referencial do CORPO."""

    def __init__(self, front: bool, sign: int) -> None:
        self.front, self.sign = front, sign
        self.hp = h = F.corner_hp(front, sign)
        self.ax_lo, self.p_lo = _unit(h["lo_a"][0] - h["lo_a"][1]), h["lo_a"][1]
        self.ax_up, self.p_up = _unit(h["up_a"][0] - h["up_a"][1]), h["up_a"][1]
        self.a0 = _unit(h["up_u"] - h["lo_u"])

    def solve(self, z_target: float, rack_dx: float) -> dict:
        h = self.hp

        def stage(phi_l):
            lo = _apply(rotation_about(self.p_lo, self.ax_lo, phi_l), h["lo_u"])

            def fu(pu):
                return float(np.linalg.norm(_apply(rotation_about(self.p_up, self.ax_up, pu), h["up_u"]) - lo) - h["d_bj"])
            phi_u = brentq(fu, -0.45, 0.45, xtol=1e-13)
            up = _apply(rotation_about(self.p_up, self.ax_up, phi_u), h["up_u"])
            a1 = _unit(up - lo)
            rb = np.eye(4)
            rb[:3, :3] = rot_between(self.a0, a1)
            base = translation(lo) @ rb @ translation(-h["lo_u"])
            tr_a = h["tr_a"] + np.array([rack_dx, 0.0, 0.0]) if self.front else h["tr_a"]

            def fs(psi):
                u = rotation_about(lo, a1, psi) @ base
                return float(np.linalg.norm(_apply(u, h["tr_u"]) - tr_a) - h["L_tr"])
            psi = brentq(fs, -0.7, 0.7, xtol=1e-13)
            u = rotation_about(lo, a1, psi) @ base
            return u, phi_u, psi, tr_a

        phi_l = brentq(lambda p: _apply(stage(p)[0], h["C"])[2] - z_target, -0.35, 0.35, xtol=1e-13)
        u, phi_u, psi, tr_a = stage(phi_l)
        rod_u = _apply(u, h["rod_u"])

        def fr(pr):
            return float(np.linalg.norm(_apply(rotation_about(h["pr"], YAX, pr), h["A0"]) - rod_u) - h["L_rod"])
        psi_r = brentq(fr, -0.9, 0.9, xtol=1e-13)
        rk = rotation_about(h["pr"], YAX, psi_r)
        d1 = _apply(rk, h["D0"])
        out = {"U": u, "LA": rotation_about(self.p_lo, self.ax_lo, phi_l), "UA": rotation_about(self.p_up, self.ax_up, phi_u),
               "TR": seg_map(h["tr_a"], h["tr_u"], tr_a, _apply(u, h["tr_u"])),
               "PR": seg_map(h["rod_u"], h["A0"], rod_u, _apply(rk, h["A0"])), "RK": rk,
               "DB": seg_map(h["M"], h["D0"], h["M"], d1), "DR": seg_map(h["D0"], h["M"], d1, h["M"]),
               "phi_l": phi_l, "phi_u": phi_u, "psi": psi, "psi_r": psi_r}
        if not self.front:
            out["DS"] = seg_map(h["P_d"], h["H0"], h["P_d"], _apply(u, h["H0"]))
        return out


@functools.lru_cache(maxsize=1)
def _corners():
    return {(f, s): Corner(f, s) for f in (True, False) for s in (1, -1)}


@functools.lru_cache(maxsize=24)
def car_state(t: float) -> dict:
    """Todas as poses (referencial do MUNDO) em ``t`` (°)."""
    sc = scenario(t)
    B = body_pose(sc)
    Binv = np.linalg.inv(B)
    st = {"sc": sc, "B": B}
    for (front, sign), cor in _corners().items():
        key = ("F" if front else "R") + SIDE_KEY[sign]
        zt = _apply(Binv, cor.hp["C"])[2]
        r = cor.solve(zt, sc["rack"] if front else 0.0)
        st[key] = {k: (B @ v if isinstance(v, np.ndarray) and v.shape == (4, 4) else v) for k, v in r.items()}
    st["rack"] = B @ translation((sc["rack"], 0, 0))
    ax = (F.COLUMN_P1 - F.COLUMN_P0) / np.linalg.norm(F.COLUMN_P1 - F.COLUMN_P0)
    st["SW"] = B @ rotation_about(F.COLUMN_P1, ax, math.radians(WHEEL_ANGLE_DEG * sc["s"]))
    st["HD"] = B @ rotation_about(HEAD_P, ZAX, math.radians(10.0 * sc["s"]))
    st["FF"] = B @ rotation_about((0, F.FRONT_FLAP_HINGE[0], F.FRONT_FLAP_HINGE[1]), XAX, -math.radians(F.AERO_FRONT_FLAP * sc["blend"]))
    st["FRW"] = B @ rotation_about((0, F.REAR_FLAP_HINGE[0], F.REAR_FLAP_HINGE[1]), XAX, -math.radians(F.AERO_REAR_FLAP * sc["blend"]))
    return st


def wheel_angle_deg(t: float) -> float:
    """Esterçamento da roda dianteira esquerda (° , + = esquerda), a partir da pose real da manga."""
    u = car_state(t)["FL"]["U"]
    hd = u[:3, :3] @ np.array([0, -1.0, 0])
    b = car_state(t)["B"]
    hd = b[:3, :3].T @ hd if False else hd
    return math.degrees(math.atan2(-hd[0], -hd[1]))


# ------------------------------------------------------------------ biela-manivela (referencial do corpo)
def piston_local(t: float, j: int, sign: int) -> np.ndarray:
    phi = CRANK_R * math.radians(t)
    return translation(F.piston_pin(j, sign, phi) - F.piston_pin(j, sign, 0.0))


def rod_local(t: float, j: int, sign: int) -> np.ndarray:
    phi = CRANK_R * math.radians(t)
    return seg_map(F.crank_pin(j, 0.0, sign), F.piston_pin(j, sign, 0.0), F.crank_pin(j, phi, sign), F.piston_pin(j, sign, phi))


# ------------------------------------------------------------------ tabelas para o celular
def make_tab(fn, per: float, step: float = TAB_STEP) -> dict:
    n = int(math.ceil(per / step - 1e-9))
    step = per / n                                      # o passo divide exatamente o período
    d = []
    for i in range(n):
        m = fn(i * step)
        d.extend(round(float(x), 5) for x in m[:3, :].reshape(-1))
    return {"step": step, "per": per, "n": n, "d": d}


def build_f1_mechanism(components) -> Mechanism:
    leaves = list(components.leaves())
    by_name = {_stem(l.name): l.id for l in leaves}
    mech = Mechanism("Carro F1 2026 — suspensão, direção, aerodinâmica ativa e motor", "Ciclo de animação (°): 4 curvas alternadas (esq./dir.), 180° cada", 720.0)
    if "Balancim dianteira direita" not in by_name or "Cremalheira (barra) de direcao" not in by_name:
        return mech                                           # modelo antigo (V2.2): sem mecanismo completo
    tabs: dict = {}
    links: list = []
    used: set = set()

    def add(names, fn, label, js, tabkey=None, tabfn=None, per=720.0):
        ids = [by_name[n] for n in names if n in by_name]
        if not ids:
            return
        used.update(ids)
        if tabkey and tabkey not in tabs:
            tabs[tabkey] = make_tab(tabfn or fn, per)
        links.append(Link(ids, fn, label, js=js))

    tab = lambda k: {"t": "tab", "k": k}                       # noqa: E731
    for (front, sign), cor in _corners().items():
        key = ("F" if front else "R") + SIDE_KEY[sign]
        nm = "dianteira" if front else "traseira"
        sd = "direita" if sign > 0 else "esquerda"
        hp = cor.hp
        lab = f"{'Dianteira' if front else 'Traseira'} {sd}"
        sel = lambda k, key=key: (lambda t: car_state(t)[key][k])           # noqa: E731
        spin = lambda t, hp=hp: rotation_about(hp["C"], XAX, WHEEL_TURNS * math.radians(t))
        wheel_names = [f"{p} {nm} {sd}" for p in ("Pneu", "Roda", "Disco de freio", "Cubo", "Porca central")]
        add(wheel_names, lambda t, s=sel, sp=spin: s("U")(t) @ sp(t), f"Rodas {lab}",
            {"t": "mul", "a": tab("U" + key), "b": {"t": "rx", "y": float(hp["C"][1]), "z": float(hp["C"][2]), "r": WHEEL_TURNS}}, "U" + key, sel("U"))
        add([f"Manga de eixo {nm} {sd}", f"Pinca de freio {nm} {sd}"], sel("U"), f"Manga e pinça {lab}", tab("U" + key))
        add([f"Braco inferior {nm} {sd} {i}" for i in (1, 2)], sel("LA"), f"Braço inferior {lab}", tab("LA" + key), "LA" + key, sel("LA"))
        add([f"Braco superior {nm} {sd} {i}" for i in (1, 2)], sel("UA"), f"Braço superior {lab}", tab("UA" + key), "UA" + key, sel("UA"))
        add([f"Barra de direcao {nm} {sd}" if front else f"Tirante de convergencia traseiro {sd}"], sel("TR"), f"Direção/convergência {lab}", tab("TR" + key), "TR" + key, sel("TR"))
        rodname = f"{'Barra de acionamento (push-rod)' if front else 'Barra de tracao (pull-rod)'} {nm} {sd}"
        add([rodname], sel("PR"), f"{'Push' if front else 'Pull'}-rod {lab}", tab("PR" + key), "PR" + key, sel("PR"))
        add([f"Balancim {nm} {sd}"], sel("RK"), f"Balancim {lab}", tab("RK" + key), "RK" + key, sel("RK"))
        add([f"Amortecedor corpo {nm} {sd}"], sel("DB"), f"Amortecedor (corpo) {lab}", tab("DB" + key), "DB" + key, sel("DB"))
        add([f"Amortecedor haste {nm} {sd}"], sel("DR"), f"Amortecedor (haste) {lab}", tab("DR" + key), "DR" + key, sel("DR"))
        if not front:
            add([f"Semi-eixo {sd}"], sel("DS"), f"Semi-eixo {lab}", tab("DS" + key), "DS" + key, sel("DS"))
    add(["Cremalheira (barra) de direcao"], lambda t: car_state(t)["rack"], "Cremalheira", tab("RACK"), "RACK", lambda t: car_state(t)["rack"])
    add(["Volante"], lambda t: car_state(t)["SW"], "Volante", tab("SW"), "SW", lambda t: car_state(t)["SW"])
    add(["Capacete do piloto (referencia)"], lambda t: car_state(t)["HD"], "Cabeça do piloto", tab("HD"), "HD", lambda t: car_state(t)["HD"])
    add(["Asa dianteira flap ativo"], lambda t: car_state(t)["FF"], "Flap ativo dianteiro", tab("FF"), "FF", lambda t: car_state(t)["FF"])
    add(["Asa traseira elemento ativo"], lambda t: car_state(t)["FRW"], "Elemento ativo traseiro", tab("FRW"), "FRW", lambda t: car_state(t)["FRW"])
    tabs["B"] = make_tab(lambda t: car_state(t)["B"], 720.0)
    Bfn = lambda t: car_state(t)["B"]                          # noqa: E731
    crank_p = [0.0, 0.0, float(F.EZ)]
    crank_fn = lambda t: rotation_about((0, 0, F.EZ), YAX, CRANK_R * math.radians(t))     # noqa: E731
    add(["Virabrequim", "Volante de embreagem"], lambda t: Bfn(t) @ crank_fn(t), "Virabrequim e embreagem",
        {"t": "mul", "a": tab("B"), "b": {"t": "rot", "p": crank_p, "a": [0, 1, 0], "r": CRANK_R}})
    add(["Rotor do compressor", "Rotor da turbina"], lambda t: Bfn(t) @ rotation_about((0, 0, 470), YAX, TURBO_R * math.radians(t)), "Rotor do turbo",
        {"t": "mul", "a": tab("B"), "b": {"t": "rot", "p": [0.0, 0.0, 470.0], "a": [0, 1, 0], "r": TURBO_R}})
    for s, sg in (("direito", 1), ("esquerdo", -1)):
        for j in range(3):
            pk, rk = f"PIS{SIDE_KEY[sg]}{j}", f"ROD{SIDE_KEY[sg]}{j}"
            tabs[pk] = make_tab(lambda t, j=j, sg=sg: piston_local(t, j, sg), 90.0)
            tabs[rk] = make_tab(lambda t, j=j, sg=sg: rod_local(t, j, sg), 90.0)
            add([f"Pistao {s} {j + 1}"], lambda t, j=j, sg=sg: Bfn(t) @ piston_local(t, j, sg), f"Pistão {s} {j + 1}", {"t": "mul", "a": tab("B"), "b": tab(pk)})
            add([f"Biela {s} {j + 1}"], lambda t, j=j, sg=sg: Bfn(t) @ rod_local(t, j, sg), f"Biela {s} {j + 1}", {"t": "mul", "a": tab("B"), "b": tab(rk)})
    rest = [l.id for l in leaves if l.id not in used]
    links.insert(0, Link(rest, Bfn, "Corpo (chassi, carroceria, asas fixas, PU, câmbio)", js=tab("B")))
    mech.links = links
    mech.extra = {"tabs": tabs}
    mech.readout = lambda t: (f"Roda dianteira esterçada {wheel_angle_deg(t):+.1f}° · rolagem {scenario(t)['roll']:+.2f}° · arfagem {scenario(t)['pitch']:+.2f}° · "
                              f"heave {scenario(t)['heave']:+.1f} mm · modo reta {scenario(t)['blend'] * 100:.0f}% · flap diant. −{F.AERO_FRONT_FLAP * scenario(t)['blend']:.1f}° · "
                              f"elem. tras. −{F.AERO_REAR_FLAP * scenario(t)['blend']:.1f}°")
    mech.notes = ["Movimento prescrito (sem dinâmica): esterço, rolagem, mergulho e afundamento são um CENÁRIO ilustrativo, exagerado ~3×.",
                  "A suspensão é resolvida cinematicamente (pontos de fixação plausíveis, não de um carro real); sem buchas, sem rigidez de mola/pneu.",
                  "Aberturas dos flaps (16° e 38°) são ILUSTRATIVAS; o regulamento define os modos, não esses ângulos.",
                  "Rodas: 2 voltas por 360° de entrada; motor: 8 voltas do virabrequim por ciclo — só para visualizar, sem relação com velocidade real.",
                  "Biela-manivela exato (biela de 145,5 mm ilustrativa); V6 simplificado, sem comando, válvulas ou ordem de ignição real."]
    return mech
