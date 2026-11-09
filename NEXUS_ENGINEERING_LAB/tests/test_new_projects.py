"""Projetos V2.7: Wankel, V12, braço robótico, bomba centrífuga, aerogerador, turbojato e guindaste torre.

Cada projeto: constrói, escreve STEP, reimporta, nomes únicos, volumes > 0, mecanismo rígido e periódico. Casos com solução analítica
conhecida (Wankel: vértice sobre a epitrocoide; V12: curso = 2·raio da manivela e biela de comprimento constante). A checagem de
interferência por OpenCascade (lenta) roda só com NEXUS_SLOW=1 para V12 e guindaste.
"""
from __future__ import annotations

import itertools
import math
import os

import numpy as np
import pytest

from core.cad_engine import CadEngine
from modules.importer import ProjectImporter
from samples import geo as g
from samples.mechanisms import build_mechanism
from samples.projects import get

KEYS = ["wankel", "v12", "braco", "bomba", "eolica", "turbojato", "guindaste", "f1_2027", "f1_312t", "f1_mp44", "f1_lotus72", "cessna", "spitfire", "a320"]
N_MIN = {"wankel": 17, "v12": 71, "braco": 12, "bomba": 13, "eolica": 10, "turbojato": 29, "guindaste": 140, "f1_2027": 194, "f1_312t": 58, "f1_mp44": 58, "f1_lotus72": 58, "cessna": 26, "spitfire": 23, "a320": 34}
_CACHE: dict = {}


def _imported(key):
    if key not in _CACHE:
        res = ProjectImporter(CadEngine()).import_file(get(key).ensure_step())

        class C:
            def leaves(self_inner):
                return list(res.root.leaves())
        _CACHE[key] = (C(), res)
    return _CACHE[key]


@pytest.mark.parametrize("key", KEYS)
def test_project_builds_and_reimports(key):
    comps, _ = _imported(key)
    leaves = comps.leaves()
    assert len(leaves) >= N_MIN[key]
    names = [l.name for l in leaves]
    assert len(set(names)) == len(names), "nomes de peça duplicados"
    assert get(key).has_mechanism


@pytest.mark.parametrize("key", KEYS)
def test_mechanism_rigid_and_periodic(key):
    comps, _ = _imported(key)
    mech = build_mechanism(comps)
    assert mech.links, key
    for link in mech.links:
        assert link.ids, (key, link.label)
        assert link.js is not None
        for t in (0.0, 37.0, 123.4, 359.0, 540.0, 719.0):
            m = np.array(link.fn(t))
            assert np.all(np.isfinite(m))
            r = m[:3, :3]
            assert np.allclose(r @ r.T, np.eye(3), atol=1e-9) and abs(np.linalg.det(r) - 1) < 1e-9, (key, link.label, t)
        assert np.allclose(link.fn(0.0), link.fn(mech.period_deg), atol=1e-6), (key, link.label, "não periódico")


def test_wankel_apex_stays_on_epitrochoid():
    from samples.wankel import E, R
    mech = build_mechanism(_imported("wankel")[0])
    assert mech.period_deg == 1080.0
    rotor = [l for l in mech.links if "Rotor" in l.label][0]
    for k in range(3):
        v0 = np.array([E + R * math.cos(2 * math.pi * k / 3), R * math.sin(2 * math.pi * k / 3), 0.0, 1.0])
        for t in (0.0, 50.0, 200.0, 555.0, 1000.0):
            a = math.radians(t)
            exp = E * np.exp(1j * a) + R * np.exp(1j * (a / 3 + 2 * math.pi * k / 3))      # epitrocoide: R e^{iφ}+E e^{i3φ}, φ=θ/3+2πk/3
            p = np.array(rotor.fn(t)) @ v0
            assert abs((p[0] + 1j * p[1]) - exp) < 1e-9


def test_v12_stroke_and_constant_rod_length():
    from samples import v12 as V
    comps, _ = _imported("v12")
    mech = build_mechanism(comps)
    for b in (1, -1):
        for i in range(V.NC):
            ss = [V.slider(i, b, t)[0] for t in np.linspace(0, 720, 721)]
            assert max(ss) - min(ss) == pytest.approx(2 * V.RC, abs=1e-6)
            ay, az = V.bank_axis(b)
            for t in (0.0, 91.0, 333.0):
                s, (py, pz) = V.slider(i, b, t)
                assert math.hypot(ay * s - py, az * s - pz) == pytest.approx(V.LROD, abs=1e-9)
    # a pose da biela leva o pé ao pino do pistão (corpo rígido de comprimento L)
    rod_links = [l for l in mech.links if l.label.startswith("Biela")]
    assert len(rod_links) == 12
    ay, az = V.bank_axis(1)
    s0, _ = V.slider(0, 1, 0.0)
    link = [l for l in mech.links if l.label == "Biela D1"][0]
    for t in (40.0, 170.0, 300.0):
        s, _ = V.slider(0, 1, t)
        p = np.array(link.fn(t)) @ np.array([0.0, ay * s0, az * s0, 1.0])
        assert p[1] == pytest.approx(ay * s, abs=1e-9) and p[2] == pytest.approx(az * s, abs=1e-9)


def test_crane_trolley_stays_on_jib():
    from samples.guindaste_torre import JIB_L
    mech = build_mechanism(_imported("guindaste")[0])
    trolley = [l for l in mech.links if "Carrinho" in l.label][0]
    xs = [(np.array(trolley.fn(t)) @ np.array([12000.0, 0, 0, 1.0]))[0] for t in (0.0,)]
    assert xs[0] == pytest.approx(12000.0 + 9000.0, abs=1e-6)         # θ=0: giro nulo, deslocamento 9000·sen(90°)
    amp = [12000.0 + 9000.0 * math.sin(math.radians(2 * t + 90)) for t in np.linspace(0, 360, 361)]
    assert 250 < min(amp) and max(amp) < JIB_L


def test_robot_flange_pose_is_product_of_joints():
    from samples.braco_robotico import JOINTS
    from modules.kinematics import rotation_about
    mech = build_mechanism(_imported("braco")[0])
    last = mech.links[-1]
    for t in (10.0, 200.0):
        m = np.eye(4)
        for _, p, a, amp, ph in JOINTS:
            m = m @ rotation_about(p, a, math.radians(amp * math.sin(math.radians(t + ph))))
        assert np.allclose(last.fn(t), m, atol=1e-9)


def _clashes(key, limit_vol=1.0):
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    mod = __import__(get(key).module, fromlist=["x"])
    root = [getattr(mod, n) for n in dir(mod) if n.startswith("build_") and n != "build_data"][0]()
    leaves = []

    def walk(n):
        if n.shape is not None:
            m = n.local_matrix
            leaves.append((n.name, g.move(n.shape, (m[0, 3], m[1, 3], m[2, 3]))))
        for c in n.children:
            walk(c)
    walk(root)
    bb = [g.bbox(s) for _, s in leaves]
    bad = []
    for i, j in itertools.combinations(range(len(leaves)), 2):
        a, b = bb[i], bb[j]
        if any(a[1][k] <= b[0][k] + 1e-6 or b[1][k] <= a[0][k] + 1e-6 for k in range(3)):
            continue
        if g.volume(BRepAlgoAPI_Common(leaves[i][1], leaves[j][1]).Shape()) > limit_vol:
            bad.append((leaves[i][0], leaves[j][0]))
    return bad


@pytest.mark.parametrize("key", ["wankel", "braco", "bomba", "eolica", "turbojato"])
def test_no_unintended_overlaps(key):
    assert _clashes(key) == []


@pytest.mark.skipif(not os.environ.get("NEXUS_SLOW"), reason="lento (use NEXUS_SLOW=1)")
@pytest.mark.parametrize("key", ["v12", "guindaste"])
def test_no_unintended_overlaps_slow(key):
    assert _clashes(key) == []
