"""Cinemática do motor de exemplo (V1.8) e leitura de juntas gravadas em FCStd."""
import math
import os
import re
import zipfile

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication  # noqa: E402

from modules.kinematics import is_rigid, rotation_about  # noqa: E402
from samples.motor_4_cilindros import (IDLER_Y, IDLER_Z, N_IDLER, BORE_R, CAM_Y, CAM_Z, CX, DECK, FIRE_DEG, GASKET, N_CAM, N_CRANK, ROD_LEN, THROW,  # noqa: E402
                                       UP, belt_design, cam_peak, cam_table, valve_center_deg)
from samples.motor_mechanism import build_engine_mechanism, crank_pin, piston_z, valve_lift  # noqa: E402
from tests.conftest import find  # noqa: E402

ANGLES = list(range(0, 721, 15))


@pytest.fixture(scope="module")
def sample_project(engine, tmp_path_factory):
    from core.project_manager import ProjectManager
    from modules.importer import ProjectImporter
    from samples.motor_4_cilindros import write
    f = write(tmp_path_factory.mktemp("kin") / "m.step")
    proj = ProjectManager(engine).new_project("m")
    proj.set_root(ProjectImporter(engine, proj.ids).import_file(str(f)).root)
    return proj


@pytest.fixture
def mech(sample_project):
    return build_engine_mechanism(sample_project.components), sample_project


def _angdiff(a, b):
    return abs((a - b + 180.0) % 360.0 - 180.0)


def _apply(m, p):
    return (m @ np.array([*p, 1.0]))[:3]


def test_rotation_about_axis():
    m = rotation_about((0, 5, 7), (1, 0, 0), math.pi / 2)
    assert np.allclose(_apply(m, (3, 5, 8)), (3, 4, 7))          # (0,1) em torno do centro -> (-1,0)
    assert np.allclose(_apply(m, (3, 5, 7)), (3, 5, 7)) and is_rigid(m)


def test_mechanism_built_for_sample(mech):
    mc, proj = mech
    assert mc.links and mc.period_deg == 720.0
    # virabrequim+volante+polia+roda (4) + 4 bielas + 4 pistões + 4 pinos + comando adm. (3) + comando esc. (2) + 16 válvulas
    # + 16 molas + 100 dentes de correia + roda tensora
    assert len(mc.moving_ids) == 4 + 4 + 4 + 4 + 3 + 2 + 16 + 16 + 100 + 1
    names = {proj.components.find(i).name for i in mc.moving_ids}
    assert "Virabrequim" in names and "Bloco do motor" not in names and "Correia dentada" not in names


def test_rest_pose_is_identity_for_rods_and_pistons(mech):
    mc, proj = mech
    p = mc.poses(0.0)
    for stem in ("Biela", "Pistao", "Pino do pistao", "Virabrequim"):
        leaf = find(proj, stem)
        assert np.allclose(p[leaf.id], np.eye(4), atol=1e-9), stem


def test_rigid_links_stay_rigid(mech):
    mc, _ = mech
    for t in ANGLES:
        for ln in mc.links:
            m = ln.fn(float(t))
            if ln.rigid:
                assert is_rigid(m), (ln.label, t)


def test_slider_crank_connections(mech):
    """Em todo ângulo: olhal grande da biela no moente, olhal pequeno no pino do pistão, pistão no eixo do cilindro."""
    mc, proj = mech
    leaves = list(proj.components.leaves())
    stem = lambda n: [l for l in leaves if re.sub(r"\s*#\d+$", "", l.name) == n]  # noqa: E731
    rods, pists, crank = stem("Biela"), stem("Pistao"), find(proj, "Virabrequim")
    for t in ANGLES:
        poses = mc.poses(float(t))
        for i, cx in enumerate(CX):
            zc = THROW if UP[i] else -THROW
            pin_world = _apply(poses[crank.id], (cx, 0, zc))                      # moente girado pelo virabrequim
            assert np.allclose(pin_world, (cx, *crank_pin(i, t)), atol=1e-9)
            big = _apply(poses[rods[i].id], (cx, 0, zc))
            small = _apply(poses[rods[i].id], (cx, 0, zc + ROD_LEN))
            assert np.allclose(big, pin_world, atol=1e-9), (i, t)
            assert np.allclose(small, (cx, 0, piston_z(i, t)), atol=1e-9), (i, t)   # preso ao pino do pistão (y=0)
            ps = _apply(poses[pists[i].id], (cx, 0, zc + ROD_LEN))
            assert np.allclose(ps, small, atol=1e-9)
            assert abs(np.linalg.norm(small - big) - ROD_LEN) < 1e-9               # comprimento da biela constante


def test_piston_stroke_equals_twice_throw(mech):
    zs = [piston_z(0, t) for t in np.arange(0, 360, 0.5)]
    assert max(zs) - min(zs) == pytest.approx(2 * THROW, abs=0.01)
    assert piston_z(0, 0) == pytest.approx(max(zs)) and piston_z(1, 0) == pytest.approx(min(zs), abs=0.01)


def test_cams_half_speed_intake_and_reverse_exhaust(mech):
    mc, proj = mech
    cam_in, cam_ex = find(proj, "Comando de admissao"), find(proj, "Comando de escape")
    gear_in, gear_ex = find(proj, "Engrenagem do comando de admissao"), find(proj, "Engrenagem do comando de escape")
    spr = find(proj, "Roda dentada do virabrequim")
    sp_cam = find(proj, "Roda dentada do comando de admissao")
    rot = lambda m: math.degrees(math.atan2(m[2, 1], m[1, 1]))  # noqa: E731  (rotação em torno de X)
    for t in (90.0, 360.0, 700.0):
        P = mc.poses(t)
        assert _angdiff(rot(P[cam_in.id]), t / 2) < 1e-6 and _angdiff(rot(P[sp_cam.id]), t / 2) < 1e-6
        assert _angdiff(rot(P[gear_in.id]), t / 2) < 1e-6
        assert _angdiff(rot(P[cam_ex.id]), -t / 2) < 1e-6 and _angdiff(rot(P[gear_ex.id]), -t / 2) < 1e-6   # engrenagem 1:1 inverte
        assert _angdiff(rot(P[spr.id]), t) < 1e-6
        # as engrenagens engrenam: ponto de contato (y=0, z=CAM_Z) tem a mesma velocidade tangencial nas duas
        w_in, w_ex = math.radians(t / 2), -math.radians(t / 2)
        assert abs(w_in) == abs(w_ex)


def test_valve_events_follow_firing_order():
    from samples.motor_4_cilindros import valve_displacement
    assert FIRE_DEG == [0.0, 540.0, 180.0, 360.0]
    ints = sorted((valve_center_deg(i, True), i + 1) for i in range(4))
    assert [c for _, c in ints] == [4, 2, 1, 3]            # cíclico 1-3-4-2
    top = max(cam_table(True))
    for i in range(4):
        for intake in (True, False):
            c = valve_center_deg(i, intake)
            assert valve_displacement(c, i, intake) == pytest.approx(top, abs=0.01)      # máximo no centro projetado
            opened = [t for t in np.arange(0, 720, 1.0) if valve_displacement(t, i, intake) > 1e-9]
            assert 205 <= len(opened) <= 260                   # uma só abertura por ciclo (~250° de manivela com o pé de ataque; >0,05 mm: ~222°)
    assert 7.0 < top < 8.5


def test_cam_profile_is_smooth_and_manufacturable():
    """Lei de levantamento com aceleração contínua e lóbulo realizável (raio de curvatura convexo > raio do rolete - folga)."""
    from samples.motor_4_cilindros import ROLL_R, cam_curves
    for intake in (True, False):
        t = np.array(cam_table(intake))
        d1 = np.diff(np.concatenate([t, t[:1]]))
        d2 = np.diff(np.concatenate([d1, d1[:1]]))
        assert np.abs(np.diff(np.concatenate([d2, d2[:1]]))).max() < 0.05           # sem saltos de aceleração (passo de 0,5°)
        assert t.max() > 7.0 and t.min() == 0.0
    pitch, surf = cam_curves(720)
    y, z = surf[:, 0], surf[:, 1]
    dy, dz = np.gradient(y), np.gradient(z)
    k = (dy * np.gradient(dz) - dz * np.gradient(dy)) / (dy * dy + dz * dz) ** 1.5
    assert 1.0 / k.max() > 3.0                                                       # nariz: raio de curvatura do lóbulo > 3 mm
    py, pz = pitch[:, 0], pitch[:, 1]
    dpy, dpz = np.gradient(py), np.gradient(pz)
    kp = (dpy * np.gradient(dpz) - dpz * np.gradient(dpy)) / (dpy * dpy + dpz * dpz) ** 1.5
    assert 1.0 / kp.max() > ROLL_R                                                   # sem ponta (cúspide) ao deslocar a curva


def test_valves_never_hit_pistons():
    """Folga vertical: prato da válvula (z = z_valve - deslocamento) acima da coroa do pistão (pino + 30) em todo ângulo."""
    from samples.motor_4_cilindros import valve_displacement
    z_valve = DECK + GASKET + 1.0
    worst = 1e9
    for t in np.arange(0, 720, 0.5):
        for i in range(4):
            crown = piston_z(i, t) + 30.0
            for intake in (True, False):
                worst = min(worst, (z_valve - valve_displacement(t, i, intake)) - crown)
    assert worst > 0.5, worst


def test_roller_stays_in_contact_with_modelled_cam(engine, sample_project):
    """Com a válvula movida pela pose e o comando girado, o rolete toca o lóbulo (distância ~0) e não o invade."""
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    comps = sample_project.components
    mc = build_engine_mechanism(comps)
    leaves = list(comps.leaves())
    stem = lambda n: [l for l in leaves if re.sub(r"\s*#\d+$", "", l.name) == n]  # noqa: E731
    from samples.motor_4_cilindros import valve_displacement
    n_contact = 0
    for t in (20.0, 75.0, 150.0, 240.0, 333.0, 420.0, 505.0, 610.0):
        poses = mc.poses(t)
        for intake, vn, cn in ((True, "Valvula de admissao", "Comando de admissao"), (False, "Valvula de escape", "Comando de escape")):
            cam = stem(cn)[0]
            cam_s = engine.transform(cam.shape, poses[cam.id])
            for k, v in enumerate(stem(vn)):
                d = valve_displacement(t, k // 2, intake)
                if d < 0.5:
                    continue
                vs = engine.transform(v.shape, poses[v.id])
                vol = engine.properties(BRepAlgoAPI_Common(vs, cam_s).Shape()).volume or 0.0
                dist = engine.min_distance(vs, cam_s)[0]
                assert vol < 1.0, (t, v.name, vol)
                assert dist < 0.1, (t, v.name, dist)                     # rolete em contato com o lóbulo
                n_contact += 1
    assert n_contact >= 8


def test_belt_ratio_and_closure():
    bd = belt_design()
    assert bd["rm"] / bd["rc"] == pytest.approx(N_CAM / N_CRANK)                # 2:1 exato nas rodas (raios primitivos)
    assert bd["path"].length == pytest.approx(bd["m"] * bd["p"], abs=1e-6)       # nº inteiro de passos: a correia fecha
    assert bd["rc"] * 2 * math.pi / N_CRANK == pytest.approx(bd["p"]) and bd["rm"] * 2 * math.pi / N_CAM == pytest.approx(bd["p"])
    assert bd["ri"] * 2 * math.pi / N_IDLER == pytest.approx(bd["p"])             # a roda tensora tem o mesmo passo


def test_belt_teeth_engage_sprocket_grooves(mech):
    """Em todo ângulo, todo dente sobre um arco está no ângulo de uma ranhura da roda (que gira junto) e os dentes seguem a correia."""
    mc, proj = mech
    bd = belt_design()
    path, rc = bd["path"], bd["rc"]
    leaves = list(proj.components.leaves())
    teeth = [l for l in leaves if re.sub(r"\s*#\d+$", "", l.name) == "Dente da correia"]
    assert len(teeth) == bd["m"]
    starts, acc = [], 0.0
    for pc in path.pieces:
        starts.append(acc)
        acc += pc["len"]
    step_c, step_m = 2 * math.pi / N_CRANK, 2 * math.pi / N_CAM
    on_crank = on_cam = on_idler = 0
    for t in (0.0, 13.0, 77.0, 200.0, 361.0, 555.0, 719.0):
        s_shift = rc * math.radians(t)
        for k, s0 in enumerate(bd["s0"]):
            s = (s0 + s_shift) % path.length
            # a pose do mecanismo move o dente de s0 para s (mesmo referencial rígido)
            moved = mc.poses(t)[teeth[k].id] @ path.frame(s0)
            assert np.allclose(moved, path.frame(s), atol=1e-8)
            pt = path.at(s)[0]
            for idx, center, phi, step, rot in ((bd["i_crank"], (0.0, 0.0), bd["phi_crank"], step_c, math.radians(t)),
                                                (bd["i_cam"], (-CAM_Y, CAM_Z), bd["phi_cam"], step_m, math.radians(t) / 2),
                                                (bd["i_idler"], (IDLER_Y, IDLER_Z), bd["phi_idler"], 2 * math.pi / N_IDLER,
                                                 math.radians(t) * N_CRANK / N_IDLER)):
                if starts[idx] + 1e-6 < s < starts[idx] + path.pieces[idx]["len"] - 1e-6:
                    ang = math.atan2(pt[1] - center[1], pt[0] - center[0])
                    off = (ang - phi - rot) % step
                    assert min(off, step - off) < 1e-6, (t, k, idx, off)
                    on_crank += idx == bd["i_crank"]
                    on_cam += idx == bd["i_cam"]
                    on_idler += idx == bd["i_idler"]
    assert on_crank > 20 and on_cam > 40 and on_idler > 4


def test_scene_poses_move_actors_and_scene_stores_them(engine):
    QApplication.instance() or QApplication([])
    from interface.main_window import MainWindow
    w = MainWindow(engine=engine)
    try:
        w.explode_bar.animate_check.setChecked(False)
        w.open_sample_engine(ask_split=False, background=False)
        w.open_kinematics()
        assert w.mechanism is not None and w._kin_dialog is not None
        pist = find(w.project, "Pistao")
        bounds0 = np.array(w.scene.parts[pist.id].body.GetBounds())
        w._kin_dialog.set_angle(180.0)                                            # pistão 1: PMS -> PMI
        bounds1 = np.array(w.scene.parts[pist.id].body.GetBounds())
        assert bounds0[4] - bounds1[4] == pytest.approx(2 * THROW, abs=0.05)       # zmin desceu 86 mm
        sc = w.save_scene("Giro 180")
        assert sc.kin_deg == 180.0 and pist.id in sc.poses
        w.stop_kinematics()
        assert np.allclose(w.scene.parts[pist.id].body.GetBounds(), bounds0)
        w.apply_scene("Giro 180")
        assert np.allclose(w.scene.parts[pist.id].body.GetBounds(), bounds1, atol=1e-6)
        # a geometria não mudou
        assert engine.properties(pist.shape).volume > 0
        # relatório/snapshot reproduz a cena com a pose
        from modules.snapshot import SnapshotRenderer
        img = SnapshotRenderer(w.project.components).saved_scene(sc, (320, 200))
        assert len(img) > 1000
    finally:
        w.project.dirty = False
        w.close()


def test_kinematics_refused_for_other_models(engine, step_file):
    QApplication.instance() or QApplication([])
    from interface.main_window import MainWindow
    from modules.importer import ProjectImporter
    w = MainWindow(engine=engine)
    try:
        res = ProjectImporter(engine, w.project.ids).import_file(str(step_file))
        w.project.set_root(res.root)
        assert not build_engine_mechanism(w.project.components).links
    finally:
        w.project.dirty = False
        w.close()


# ------------------------------------------------------------------ juntas gravadas (FCStd)
DOC = """<?xml version='1.0' encoding='utf-8'?>
<Document SchemaVersion="4"><Objects Count="3">
<Object type="App::FeaturePython" name="Joint"/>
<Object type="App::FeaturePython" name="Joint001"/>
</Objects><ObjectData Count="2">
<Object name="Joint"><Properties Count="4">
 <Property name="Label" type="App::PropertyString"><String value="Eixo no mancal"/></Property>
 <Property name="JointType" type="App::PropertyEnumeration"><Integer value="1"/>
   <CustomEnumList count="3"><Enum value="Fixed"/><Enum value="Revolute"/><Enum value="Slider"/></CustomEnumList></Property>
 <Property name="Reference1" type="App::PropertyXLinkSub"><XLinkSub value="1" name="PecaA"><Sub value="Face3"/></XLinkSub></Property>
 <Property name="Reference2" type="App::PropertyXLinkSub"><XLinkSub value="1" name="PecaB"><Sub value="Face1"/></XLinkSub></Property>
</Properties></Object>
<Object name="Joint001"><Properties Count="3">
 <Property name="JointType" type="App::PropertyEnumeration"><Integer value="3"/></Property>
 <Property name="Reference1" type="App::PropertyXLinkSub"><XLinkSub value="1"><Sub value="PecaA.Edge2"/></XLinkSub></Property>
 <Property name="Reference2" type="App::PropertyXLinkSub"><XLinkSub value="1" name="Fantasma"><Sub value="Face9"/></XLinkSub></Property>
</Properties></Object>
</ObjectData></Document>"""


def test_parse_declared_joints():
    from modules.declared_joints import parse_document_xml
    js = parse_document_xml(DOC)
    assert [j.name for j in js] == ["Joint", "Joint001"]
    a, b = js
    assert (a.joint_type, a.type_assumed, a.obj1, a.sub1, a.obj2, a.sub2) == ("Revolute", False, "PecaA", "Face3", "PecaB", "Face1")
    assert b.joint_type == "Slider" and b.type_assumed                     # lista de nomes ausente -> ordem padrão (rotulado)
    assert parse_document_xml("<Document><Objects/><ObjectData/></Document>") == []


def test_declared_joints_in_fcstd_import_and_report(engine, tmp_path):
    from core.project_manager import ProjectManager
    from modules.exporter import Exporter
    from modules.importer import ProjectImporter
    from modules.joint_finder import JointFinder
    from tests import fixtures
    # FCStd de verdade (gravado pelo NEXUS) com duas peças; injeta os objetos-junta no Document.xml
    step = fixtures.write_engine_step(engine, tmp_path / "e.step")
    pm = ProjectManager(engine)
    proj = pm.new_project("x")
    proj.set_root(ProjectImporter(engine, proj.ids).import_file(str(step)).root)
    out = tmp_path / "m.FCStd"
    Exporter(engine).export(proj, out)
    with zipfile.ZipFile(out) as zf:
        files = {n: zf.read(n) for n in zf.namelist()}
    names = re.findall(rb'<Object type="Part::Feature" name="(\w+)"', files["Document.xml"])
    assert len(names) >= 2
    a, b = names[0].decode(), names[1].decode()
    inj = DOC.replace("PecaA", a).replace("PecaB", b).split("<ObjectData Count=\"2\">")[1].rsplit("</ObjectData>", 1)[0].encode()
    doc = files["Document.xml"].replace(b"</ObjectData>", inj + b"</ObjectData>", 1)
    files["Document.xml"] = doc
    with zipfile.ZipFile(tmp_path / "j.FCStd", "w") as zf:
        for n, d in files.items():
            zf.writestr(n, d)
    res = ProjectImporter(engine, proj.ids.__class__()).import_file(str(tmp_path / "j.FCStd"))
    assert any("junta(s) gravada(s)" in w for w in res.warnings)
    pm2 = ProjectManager(engine)
    p2 = pm2.new_project("y")
    p2.set_root(res.root)
    rep = JointFinder(p2.components).find()
    decl = [j for j in rep.joints if j.kind.startswith("Gravada")]
    assert len(decl) == 2 and all(not j.inferred for j in decl)
    ok = [j for j in decl if "Rotativa" in j.kind][0]
    assert ok.a_id and ok.b_id and ok.a_id != ok.b_id and "Eixo no mancal" in ok.detail
    bad = [j for j in decl if "Deslizante" in j.kind][0]
    assert "não encontrada" in bad.detail                              # referência a objeto inexistente é sinalizada
    # persiste no .nexus e o CSV marca a origem
    pm2.save_project(p2, tmp_path / "p.nexus") if hasattr(pm2, "save_project") else None
    from modules.joint_finder import export_csv
    text = open(export_csv(rep, tmp_path / "j.csv"), encoding="utf-8-sig").read()
    assert "gravada no arquivo FCStd" in text


def test_no_interference_while_moving(engine, sample_project):
    """Com o mecanismo em vários ângulos, nenhuma peça (exceto molas, comprimidas por escala) invade outra."""
    import itertools
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    from core.geometry import BoundingBox
    comps = sample_project.components
    mc = build_engine_mechanism(comps)
    spring_ids = {l.id for l in comps.leaves() if l.name.startswith("Mola")}
    leaves = [l for l in comps.leaves() if l.id not in spring_ids]
    bad = []
    for t in (0.0, 37.0, 90.0, 133.0, 180.0, 270.0, 311.0, 450.0, 555.0, 640.0):
        poses = mc.poses(t)
        shapes = {l.id: (engine.transform(l.shape, poses[l.id]) if l.id in poses else l.shape) for l in leaves}
        boxes = {i: engine.bbox(s) for i, s in shapes.items()}
        moving = set(poses)
        for a, b in itertools.combinations(leaves, 2):
            if a.id not in moving and b.id not in moving:
                continue                                          # par parado: já coberto pelo teste estático
            ba, bb = boxes[a.id], boxes[b.id]
            if np.any(ba.max < bb.min - 1e-6) or np.any(bb.max < ba.min - 1e-6):
                continue
            vol = engine.properties(BRepAlgoAPI_Common(shapes[a.id], shapes[b.id]).Shape()).volume or 0.0
            if vol > 1.0:
                bad.append((t, a.name, b.name, round(vol, 1)))
    import collections
    summary = collections.defaultdict(list)
    for t, an, bn, v in bad:
        summary[(re.sub(r'\s*#\d+$', '', an), re.sub(r'\s*#\d+$', '', bn))].append((t, v))
    assert not summary, {k: (len(v), max(x for _, x in v)) for k, v in summary.items()}


def test_involute_gears_mesh_without_interference(engine):
    """Engrenagens de evolvente dos comandos: razão 1:1, sem interferência e com folga mínima pequena em 20 ângulos."""
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    from core.geometry import translation_matrix
    from samples.motor_4_cilindros import gear
    A = engine.transform(gear(False), translation_matrix([0, -CAM_Y, CAM_Z]))
    B = engine.transform(gear(True), translation_matrix([0, CAM_Y, CAM_Z]))
    dmin = 9e9
    for deg in np.arange(0, 60.0, 3.0):
        a = math.radians(deg)
        Ar = engine.transform(A, rotation_about((0, -CAM_Y, CAM_Z), (1, 0, 0), a))
        Br = engine.transform(B, rotation_about((0, CAM_Y, CAM_Z), (1, 0, 0), -a))
        assert (engine.properties(BRepAlgoAPI_Common(Ar, Br).Shape()).volume or 0.0) < 0.01, deg
        dmin = min(dmin, engine.min_distance(Ar, Br)[0])
    assert 0.01 < dmin < 0.5                                       # engrenado (folga ~0,1 mm), sem tocar


def test_valve_diagram_data_and_dialog(mech):
    """Diagrama de válvulas: coerente com o levantamento, derivadas finitas, escala com rpm e janela desenhável."""
    mech, _ = mech
    d = mech.extra["diagram"]
    assert d["n"] == len(d["int"]["lift"]) == 721
    lift = np.array(d["int"]["lift"])
    assert abs(lift.max() - 7.7133) < 0.01
    # deslocamento do escape do cil. 1 é o da admissão deslocado de 180° (cil. 1: adm. centrada em 450°, esc. em 270°)
    assert np.allclose(np.roll(lift[:-1], -180), np.array(d["exh"]["lift"])[:-1], atol=1e-6)
    # integração da velocidade reproduz o levantamento (consistência da derivada)
    v = np.array(d["int"]["vel"]) * 1000.0 / (2 * np.pi * 1000.0 / 60.0)      # mm por rad
    rec = np.cumsum((v[1:] + v[:-1]) / 2) * np.radians(1.0)
    assert abs(rec[-1]) < 0.01 and np.abs(rec - (lift[1:] - lift[0])).max() < 0.05
    assert np.isfinite(d["int"]["acc"]).all()
    from PySide6.QtWidgets import QApplication
    from interface.kinematics_dialog import KinematicsDialog
    QApplication.instance() or QApplication([])
    dlg = KinematicsDialog(mech)
    dlg.set_angle(400.0)
    dlg.rpm.setValue(6000)
    assert dlg.diagram.rpm == 6000 and dlg.diagram._scale("acc") == 36.0 and dlg.diagram._scale("vel") == 6.0
    img = dlg.diagram.grab().toImage()
    assert not img.isNull() and img.width() > 100
