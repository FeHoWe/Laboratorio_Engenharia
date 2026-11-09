"""Mecanismos (animações PRESCRITAS) dos projetos adicionais V2.7: Wankel, V12, braço robótico, bomba, aerogerador, turbojato, guindaste.

Cada função acha as peças pelo NOME (como no motor de exemplo) e devolve um Mechanism vazio se o modelo não for o esperado.
As matemáticas têm espelho em JavaScript (descritores ``js``) para o visualizador de celular: rot, rx, rsn (rotação senoidal), tsn (translação senoidal),
orb (órbita do centro excêntrico) e vr/vs (biela/pistão de banco inclinado).
"""
from __future__ import annotations
import math
import re

import numpy as np

from modules.kinematics import Link, Mechanism, rotation_about, translation

X, Y, Z = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)


def _stem(name: str) -> str:
    return re.sub(r"\s*#\d+$", "", name).strip()


def _index(components) -> dict:
    out: dict = {}
    for l in components.leaves():
        out.setdefault(_stem(l.name), []).append(l)
    return out


def _ids(idx, *names):
    return [l.id for n in names for l in idx.get(n, [])]


# ------------------------------------------------------------------ Wankel
def build_wankel_mechanism(components) -> Mechanism:
    from samples.wankel import E
    idx = _index(components)
    mech = Mechanism("Motor Wankel — rotor a θ/3 sobre excêntrico", "Ângulo do eixo excêntrico (°)", 1080.0)
    if "Rotor triangular" not in idx:
        return mech
    shaft = _ids(idx, "Eixo excentrico (munhao dianteiro)", "Eixo excentrico (munhao traseiro)", "Excentrico do eixo", "Contrapeso dianteiro", "Contrapeso traseiro", "Volante do motor")
    mech.links.append(Link(shaft, lambda t: rotation_about((0, 0, 0), Z, math.radians(t)), "Eixo excêntrico (θ)", js={"t": "rot", "p": [0, 0, 0], "a": [0, 0, 1], "r": 1}))

    def rotor_fn(t):
        a = math.radians(t)
        return translation((E * (math.cos(a) - 1.0), E * math.sin(a), 0.0)) @ rotation_about((E, 0, 0), Z, a / 3.0)

    ids = _ids(idx, "Rotor triangular", "Vedacao de apice 1", "Vedacao de apice 2", "Vedacao de apice 3")
    mech.links.append(Link(ids, rotor_fn, "Rotor (θ/3 em torno do excêntrico) + vedações",
                           js={"t": "mul", "a": {"t": "orb", "e": E}, "b": {"t": "rot", "p": [E, 0, 0], "a": [0, 0, 1], "r": 1.0 / 3.0}}))
    mech.notes += ["Relação exata: vértices do rotor permanecem na epitrocoide da carcaça (R·e^{iθ/3} + e·e^{iθ}).",
                   "Um ciclo completo de 4 tempos por face = 3 voltas do eixo (1080°)."]
    return mech


# ------------------------------------------------------------------ V12
def build_v12_mechanism(components) -> Mechanism:
    from samples import v12 as V
    idx = _index(components)
    mech = Mechanism("Motor V12 60° — biela-manivela (2 bancos)", "Ângulo do virabrequim (°)", 720.0)
    if "Bloco do motor V12" not in idx:
        return mech
    crank = _ids(idx, *[n for n in idx if n.startswith(("Munhao principal", "Moente", "Braco")) or n in ("Ponta dianteira do virabrequim", "Polia do virabrequim", "Volante do motor", "Flange traseira do virabrequim")])
    mech.links.append(Link(crank, lambda t: rotation_about((0, 0, 0), X, math.radians(t)), "Virabrequim e acessórios", js={"t": "rx", "y": 0, "z": 0, "r": 1}))
    for b, tag in ((1, "D"), (-1, "E")):
        for i in range(V.NC):
            s0, (py0, pz0) = V.slider(i, b, 0.0)
            ay, az = V.bank_axis(b)
            d0 = (ay * s0 - py0, az * s0 - pz0); psi0 = math.atan2(d0[1], d0[0])

            def rod_fn(t, i=i, b=b, py0=py0, pz0=pz0, psi0=psi0, ay=ay, az=az):
                s, (py, pz) = V.slider(i, b, t)
                psi = math.atan2(az * s - pz, ay * s - py)
                return translation((0, py - py0, pz - pz0)) @ rotation_about((0, py0, pz0), X, psi - psi0)

            def sl_fn(t, i=i, b=b, s0=s0, ay=ay, az=az):
                s, _ = V.slider(i, b, t)
                return translation((0, ay * (s - s0), az * (s - s0)))

            d = {"r": V.RC, "ph": V.PHASES[i], "b": b, "hv": 30.0, "L": V.LROD}
            mech.links.append(Link(_ids(idx, f"Biela {tag}{i + 1}"), rod_fn, f"Biela {tag}{i + 1}", js={"t": "vr", **d}))
            mech.links.append(Link(_ids(idx, f"Pistao {tag}{i + 1}", f"Pino do pistao {tag}{i + 1}"), sl_fn, f"Pistão {tag}{i + 1}", js={"t": "vs", **d}))
    mech.notes.append("Cinemática biela-manivela exata por banco; sem válvulas/comandos neste modelo.")
    return mech


# ------------------------------------------------------------------ braço robótico
def _rsn(p, a, amp, ph):
    return lambda t: rotation_about(p, a, math.radians(amp * math.sin(math.radians(t + ph))))


def build_robot_mechanism(components) -> Mechanism:
    from samples.braco_robotico import JOINTS
    idx = _index(components)
    mech = Mechanism("Braço robótico 6 eixos — cenário prescrito", "Fase do ciclo (°)", 360.0)
    if "Torre giratoria" not in idx:
        return mech
    groups = [["Torre giratoria", "Carcaca do ombro"], ["Braco superior"], ["Carcaca do cotovelo", "Antebraco"], ["Punho 1 (rolagem)"], ["Punho 2 (arfagem)"],
              ["Flange do eixo 6", "Base da garra", "Dedo da garra 1", "Dedo da garra 2"]]
    descr = [{"t": "rsn", "p": list(p), "a": list(a), "amp": amp, "ph": ph, "f": 1} for _, p, a, amp, ph in JOINTS]
    for k, names in enumerate(groups):
        def fn(t, k=k):
            m = np.eye(4)
            for j in range(k + 1):
                _, p, a, amp, ph = JOINTS[j]
                m = m @ _rsn(p, a, amp, ph)(t)
            return m
        d = descr[k]
        for j in range(k - 1, -1, -1):
            d = {"t": "mul", "a": descr[j], "b": d}
        mech.links.append(Link(_ids(idx, *names), fn, f"Juntas J1…J{k + 1}", js=d))
    mech.notes.append("Ângulos senoidais prescritos por junta; cinemática direta (produto de exponenciais). Não é planejamento de trajetória.")
    return mech


# ------------------------------------------------------------------ rotações simples (bomba, eólica, turbojato)
def _spin(name, label, stems_fn, y=0.0, z=0.0, period=360.0):
    def build(components) -> Mechanism:
        idx = _index(components)
        mech = Mechanism(name, label, period)
        ids = stems_fn(idx)
        if not ids:
            return mech
        mech.links.append(Link(ids, lambda t: rotation_about((0, y, z), X, math.radians(t)), "Conjunto rotativo", js={"t": "rx", "y": y, "z": z, "r": 1}))
        return mech
    return build


build_pump_mechanism = _spin("Bomba centrífuga — rotor e eixo", "Ângulo do eixo (°)",
                             lambda idx: _ids(idx, "Rotor fechado (6 palhetas)", "Eixo da bomba", "Luva do eixo") if "Voluta" in idx else [])


def build_wind_mechanism(components) -> Mechanism:
    from samples.turbina_eolica import HUB_Z
    return _spin("Aerogerador — rotor", "Ângulo do rotor (°)",
                 lambda idx: _ids(idx, "Cubo com cone de ponta", "Eixo principal", "Pa 1", "Pa 2", "Pa 3") if "Torre conica" in idx else [], 0.0, HUB_Z)(components)


def build_jet_mechanism(components) -> Mechanism:
    def sel(idx):
        if "Carcaca do compressor" not in idx:
            return []
        return _ids(idx, *[n for n in idx if n.startswith(("Disco e palhetas", "Cone de ponta", "Eixo do spool", "Tambor do compressor"))])
    return _spin("Turbojato — spool", "Ângulo do eixo (°)", sel)(components)


# ------------------------------------------------------------------ guindaste
def build_crane_mechanism(components) -> Mechanism:
    idx = _index(components)
    mech = Mechanism("Guindaste torre — giro e carrinho", "Fase do ciclo (°)", 360.0)
    if "Coroa de giro" not in idx:
        return mech
    upper = [n for n in idx if n.startswith(("Coroa", "Plataforma", "Cabine", "Torre de cabos", "Banzo", "Diagonal da", "Diagonal lateral", "Travessa da", "Ponta da lanca", "Apoio da", "Contrapeso", "Tirante"))]
    upper = [n for n in upper if not n.startswith(("Diagonal do mastro", "Travessa do mastro", "Perna do mastro"))]
    slew = lambda t: rotation_about((0, 0, 0), Z, math.radians(100.0 * math.sin(math.radians(t))))   # noqa: E731
    sj = {"t": "rsn", "p": [0, 0, 0], "a": [0, 0, 1], "amp": 100.0, "ph": 0, "f": 1}
    mech.links.append(Link(_ids(idx, *upper), slew, "Giro da lança (±100°)", js=sj))
    trolley = _ids(idx, "Carrinho da lanca", "Cabo do gancho", "Bloco do gancho", "Gancho")
    mech.links.append(Link(trolley, lambda t: slew(t) @ translation((9000.0 * math.sin(math.radians(2 * t + 90)), 0, 0)),
                           "Carrinho + gancho", js={"t": "mul", "a": sj, "b": {"t": "tsn", "a": [1, 0, 0], "amp": 9000.0, "ph": 90, "f": 2}}))
    mech.notes.append("Giro ±100° e translação do carrinho prescritos (senoidais).")
    return mech


# ------------------------------------------------------------------ F1 clássicos (V2.8)
CLASSIC_STEER_DEG = 20.0   # esterço máximo ILUSTRATIVO das rodas dianteiras


def build_classic_mechanism(components) -> Mechanism:
    """As 4 rodas giram o mesmo nº de voltas por ciclo e as dianteiras esterçam senoidalmente. Cenário prescrito, sem dinâmica."""
    from samples.f1_classicos import SPECS
    idx = _index(components)
    mech = Mechanism("F1 clássico — rodas e esterço (prescrito)", "Ângulo de rotação (°)", 360.0)
    if "Santo Antonio (arco de capotamento)" not in idx or "Pneu dianteira direita" not in idx:
        return mech
    tag = next((k for k in idx if k.startswith("Bloco do motor ")), "")
    sp = SPECS[{"V12 boxer": "312t", "V6 turbo": "mp44", "V8 DFV": "lotus72"}[tag[len("Bloco do motor "):]]] if tag else None
    if sp is None:
        return mech
    WB, TF, TR, RF, RR = sp["WB"], sp["TF"], sp["TR"], sp["RF"], sp["RR"]
    turns = 2.0
    for front in (True, False):
        y, R, tr = (0.0, RF, TF) if front else (WB, RR, TR)
        ratio = turns   # mesmo nº de voltas nos 4 pneus (periódico); NÃO respeita a diferença de raio entre eixos
        axle = "dianteira" if front else "traseira"
        for sgn, side in ((1, "direita"), (-1, "esquerda")):
            ids = _ids(idx, *[f"{p} {axle} {side}" for p in ("Pneu", "Roda", "Cubo", "Disco de freio", "Disco de freio interno")])
            xw = sgn * tr / 2.0
            spin = {"t": "rx", "y": y, "z": R, "r": ratio}
            sf = lambda t, y=y, R=R, ratio=ratio: rotation_about((0, y, R), X, math.radians(t * ratio))  # noqa: E731
            if front:
                st = lambda t, xw=xw, y=y: rotation_about((xw, y, 0.0), Z, math.radians(CLASSIC_STEER_DEG * math.sin(math.radians(t))))  # noqa: E731
                fn = lambda t, st=st, sf=sf: st(t) @ sf(t)  # noqa: E731
                js = {"t": "mul", "a": {"t": "rsn", "p": [xw, y, 0.0], "a": [0.0, 0.0, 1.0], "amp": CLASSIC_STEER_DEG, "ph": 0, "f": 1}, "b": spin}
                label = f"Roda dianteira {side}: giro + esterço"
            else:
                fn, js, label = sf, spin, f"Roda traseira {side}: giro"
            mech.links.append(Link(ids, fn, label, js=js))
    mech.notes.append("As 4 rodas dão 2 voltas por ciclo (igual nos dois eixos, então NÃO é rolagem sem deslizamento com raios diferentes) e esterço senoidal de ±20°: ILUSTRATIVOS. Sem suspensão, sem dinâmica.")
    return mech


# ------------------------------------------------------------------ aeronaves (V2.8)
def build_aircraft_mechanism(components) -> Mechanism:
    """Hélice/fan girando e superfícies de comando oscilando (prescrito). Dados em samples.aeronaves.MECH (preenchido ao construir)."""
    from samples import aeronaves as A
    idx = _index(components)
    key = "a320" if "Fan direito" in idx else "spitfire" if "Pa da helice 3" in idx else "cessna" if "Pa da helice 1" in idx else None
    mech = Mechanism("Aeronave — rotação e superfícies de comando (prescrito)", "Fase do ciclo (°)", 360.0)
    if key is None:
        return mech
    if key not in A.MECH:
        A.BUILDERS[key]()   # registra MECH
    spec = A.MECH[key]
    for names, (py, pz), ratio in spec["spin"]:
        ids = _ids(idx, *names)
        if ids:
            mech.links.append(Link(ids, lambda t, py=py, pz=pz, ratio=ratio: rotation_about((0, py, pz), X, math.radians(t * ratio)), "Hélice / fan",
                                   js={"t": "rx", "y": float(py), "z": float(pz), "r": float(ratio)}))
    for names, p, a, amp, ph in spec["surf"]:
        ids = _ids(idx, *names)
        if not ids:
            continue
        p, a = np.asarray(p, float), np.asarray(a, float)
        mech.links.append(Link(ids, _rsn(p, a, amp, ph), "Superfície de comando",
                               js={"t": "rsn", "p": [float(v) for v in p], "a": [float(v) for v in a], "amp": float(amp), "ph": float(ph), "f": 1}))
    mech.notes.append("Deflexões senoidais ILUSTRATIVAS das superfícies; hélice/fan em rotação constante. Não é dinâmica de voo nem aerodinâmica.")
    return mech
