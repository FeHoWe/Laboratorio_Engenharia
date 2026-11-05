"""Algoritmo de explosão virtual, animação e restauração."""
import itertools

import numpy as np
import pytest

from core.geometry import BoundingBox
from core.model import Component, ComponentKind
from modules.explode_engine import (ExplodeEngine, ExplodeParams, ease_in_out,
                                    interpolate_offsets)
from tests.conftest import find


# ---------------------------------------------------- árvore sintética (sem CAD)
def synthetic(centers, size=2.0):
    """Raiz com filhos-peça centrados nos pontos dados; devolve (root, bbox_fn)."""
    root = Component(id="R", name="raiz", kind=ComponentKind.ASSEMBLY)
    boxes = {}
    for i, c in enumerate(centers):
        part = Component(id=f"P{i}", name=f"p{i}")
        root.add_child(part)
        c = np.array(c, dtype=float)
        boxes[part.id] = BoundingBox(c - size / 2, c + size / 2)
    boxes["R"] = BoundingBox.union(boxes.values())
    return root, _lookup(boxes)


def _lookup(boxes):
    """bbox_fn do engine: aceita um Component (uso real) ou um id (conveniência dos testes)."""
    return lambda x: boxes.get(x.id if hasattr(x, "id") else x)


def unit(v):
    return v / np.linalg.norm(v)


def test_radial_direction_points_away_from_assembly_center():
    root, bbox = synthetic([(10, 0, 0), (-10, 0, 0), (0, 10, 0), (0, 0, 10)])
    center = bbox("R").center
    offs = ExplodeEngine(bbox).compute_offsets(root, ExplodeParams(factor=1.0))
    assert len(offs) == 4
    for part in root.children:
        rel = bbox(part.id).center - center
        assert np.dot(unit(offs[part.id]), unit(rel)) == pytest.approx(1.0)  # mesma direção radial
        assert np.linalg.norm(offs[part.id]) > 0


def test_farther_parts_move_farther_and_factor_scales_distance():
    # em 1D as duas peças das pontas ficam sempre à mesma distância do centro da caixa;
    # a do meio está mais perto e por isso se move menos
    root, bbox = synthetic([(0, 0, 0), (4, 0, 0), (20, 0, 0)])
    eng = ExplodeEngine(bbox)
    o1 = eng.compute_offsets(root, ExplodeParams(factor=1.0))
    o2 = eng.compute_offsets(root, ExplodeParams(factor=2.0))
    mags = {k: np.linalg.norm(v) for k, v in o1.items()}
    assert mags["P0"] == pytest.approx(mags["P2"]) and mags["P2"] > mags["P1"] > 0
    for k in o1:
        assert np.linalg.norm(o2[k]) == pytest.approx(2 * mags[k])  # linear no fator


def test_factor_zero_keeps_assembly_together():
    root, bbox = synthetic([(10, 0, 0), (-10, 0, 0)])
    offs = ExplodeEngine(bbox).compute_offsets(root, ExplodeParams(factor=0.0))
    assert all(np.allclose(v, 0) for v in offs.values())


def test_concentric_parts_get_deterministic_separation_on_main_axis():
    # três peças no MESMO centro, mais uma peça longa que define o eixo principal (X)
    root, bbox = synthetic([(0, 0, 0), (0, 0, 0), (0, 0, 0)])
    root_box = BoundingBox(np.array([-50.0, -5, -5]), np.array([50.0, 5, 5]))
    boxes = {"R": root_box, **{f"P{i}": BoundingBox(np.array([-1.0, -1, -1]), np.array([1.0, 1, 1]))
                               for i in range(3)}}
    eng = ExplodeEngine(_lookup(boxes))
    a = eng.compute_offsets(root, ExplodeParams())
    b = eng.compute_offsets(root, ExplodeParams())
    assert all(np.array_equal(a[k], b[k]) for k in a)              # determinístico
    vecs = [a[f"P{i}"] for i in range(3)]
    assert all(np.linalg.norm(v) > 0 for v in vecs)                 # nenhuma ficou parada
    assert all(abs(v[1]) < 1e-12 and abs(v[2]) < 1e-12 for v in vecs)  # só no eixo X
    assert np.sign(vecs[0][0]) != np.sign(vecs[1][0])               # sentidos alternados
    for u, v in itertools.combinations(vecs, 2):
        assert not np.allclose(u, v)                                # todas distintas


def test_axis_mode_moves_only_along_axis_with_side_sign():
    root, bbox = synthetic([(10, 5, 5), (-10, -5, 2), (4, 0, 0)])
    offs = ExplodeEngine(bbox).compute_offsets(root, ExplodeParams(mode="axis_x", factor=1.0))
    assert all(abs(v[1]) < 1e-12 and abs(v[2]) < 1e-12 for v in offs.values())
    assert offs["P0"][0] > 0 and offs["P1"][0] < 0


def test_custom_direction_and_validation():
    root, bbox = synthetic([(10, 0, 0), (-10, 0, 0)])
    eng = ExplodeEngine(bbox)
    offs = eng.compute_offsets(root, ExplodeParams(mode="custom", direction=(0, 0, 3)))
    assert all(abs(v[0]) < 1e-12 and abs(v[1]) < 1e-12 for v in offs.values())
    with pytest.raises(ValueError, match="direção não nula"):
        eng.compute_offsets(root, ExplodeParams(mode="custom", direction=(0, 0, 0)))
    with pytest.raises(ValueError, match="direção não nula"):
        eng.compute_offsets(root, ExplodeParams(mode="custom"))
    with pytest.raises(ValueError, match="negativo"):
        eng.compute_offsets(root, ExplodeParams(factor=-1))
    with pytest.raises(ValueError, match="inválido"):
        eng.compute_offsets(root, ExplodeParams(mode="aleatorio"))


def test_hierarchy_subassembly_moves_as_block_then_opens_smaller():
    root = Component(id="R", name="raiz", kind=ComponentKind.ASSEMBLY)
    sub = root.add_child(Component(id="S", name="sub", kind=ComponentKind.ASSEMBLY))
    for i, x in enumerate((20, 24)):
        sub.add_child(Component(id=f"A{i}", name=f"a{i}"))
    root.add_child(Component(id="B", name="b"))
    box = lambda lo, hi: BoundingBox(np.array(lo, float), np.array(hi, float))
    boxes = {"A0": box((19, -1, -1), (21, 1, 1)), "A1": box((23, -1, -1), (25, 1, 1)),
             "S": box((19, -1, -1), (25, 1, 1)), "B": box((-21, -1, -1), (-19, 1, 1))}
    boxes["R"] = BoundingBox.union(boxes.values())
    eng = ExplodeEngine(_lookup(boxes))
    offs = eng.compute_offsets(root, ExplodeParams(factor=1.0))
    assert set(offs) == {"S", "B", "A0", "A1"}
    # nível 0 (S) > nível 1 (A0/A1): a abertura interna é menor que a do bloco
    assert np.linalg.norm(offs["S"]) > np.linalg.norm(offs["A0"])
    # efeito somado: deslocamento efetivo da peça = offset do ancestral + próprio
    sub.offset, root.children[0].children[0].offset = offs["S"], offs["A0"]
    assert np.allclose(sub.children[0].effective_offset(), offs["S"] + offs["A0"])
    flat = eng.compute_offsets(root, ExplodeParams(factor=1.0, recursive=False))
    assert set(flat) == {"S", "B"}


# ------------------------------------------------------------------ com o motor real
def test_motor_explosion_and_exact_restoration(motor_project, engine):
    proj = motor_project
    comps, asm = proj.components, proj.assembly
    leaves = comps.leaves()
    rest_boxes = {l.id: comps.own_bbox(l) for l in leaves}
    shapes_before = {l.id: l.shape for l in leaves}

    asm.apply_offsets(asm.target_explode_all(ExplodeParams(factor=1.0)))
    assert asm.is_exploded()
    assert all(l.is_displaced() for l in leaves)   # TODAS as peças se moveram, inclusive a concêntrica

    # geometria original intacta durante a explosão
    for l in leaves:
        assert l.shape is shapes_before[l.id]
        assert np.allclose(comps.own_bbox(l).min, rest_boxes[l.id].min)
    # a posição exibida mudou
    moved = comps.displayed_bbox(comps.root)
    assert moved.diagonal > comps.bbox(comps.root).diagonal

    asm.restore()
    assert asm.verify_restored() and not asm.is_exploded()
    assert comps.displaced_ids() == []
    d = comps.displayed_bbox(comps.root)
    assert np.allclose(d.min, comps.bbox(comps.root).min) and np.allclose(d.max, comps.bbox(comps.root).max)


def test_explosion_is_idempotent_and_reduces_overlaps(motor_project):
    proj = motor_project
    comps, asm = proj.components, proj.assembly
    params = ExplodeParams(factor=1.5)
    t1 = asm.target_explode_all(params)
    asm.apply_offsets(t1)
    t2 = asm.target_explode_all(params)       # explodir de novo a partir do estado explodido
    assert all(np.allclose(t1[k], t2[k]) for k in t1)

    def overlaps(displaced):
        boxes = []
        for l in comps.leaves():
            b = comps.own_bbox(l)
            boxes.append(b.translated(l.effective_offset()) if displaced else b)
        n = 0
        for a, b in itertools.combinations(boxes, 2):
            if np.all(a.min < b.max - 1e-9) and np.all(b.min < a.max - 1e-9):
                n += 1
        return n
    asm.restore()
    before = overlaps(False)
    asm.apply_offsets(t1)
    after = overlaps(True)
    assert before > 0 and after == 0   # a explosão libera TODAS as interferências


def test_explode_group_only_affects_that_group(motor_project):
    from tests.conftest import find
    proj = motor_project
    asm = proj.assembly
    pistons = find(proj, "Pistoes")
    target = asm.target_explode_group(pistons.id, ExplodeParams(factor=1.0))
    asm.apply_offsets(target)
    displaced = {proj.components.get(i).name for i in proj.components.displaced_ids()}
    assert displaced == {"Pistao", "Pistao #2", "Pistao #3", "Pistao #4"}
    assert np.allclose(pistons.offset, 0)            # o grupo em si não se move
    with pytest.raises(ValueError, match="não é um grupo"):
        asm.target_explode_group(find(proj, "Bloco").id, ExplodeParams())


def test_separate_single_part(motor_project):
    proj = motor_project
    asm = proj.assembly
    bloco = find(proj, "Bloco")
    asm.apply_offsets(asm.target_separate_part(find(proj, "Pistao #3").id, ExplodeParams(factor=1.0)))
    assert [proj.components.get(i).name for i in proj.components.displaced_ids()] == ["Pistao #3"]
    assert np.allclose(bloco.offset, 0)
    asm.apply_offsets(asm.target_separate_part(bloco.id, ExplodeParams(mode="axis_z", factor=0.5)))
    assert set(proj.components.displaced_ids()) == {find(proj, "Pistao #3").id, bloco.id}
    with pytest.raises(ValueError, match="raiz"):
        asm.target_separate_part(proj.components.root.id, ExplodeParams())


# ------------------------------------------------------------------------ animação
def test_interpolation_endpoints_and_monotonic_easing():
    start = {"a": np.zeros(3)}
    target = {"a": np.array([10.0, 0, 0])}
    assert np.allclose(interpolate_offsets(start, target, 0.0)["a"], 0)
    assert np.allclose(interpolate_offsets(start, target, 1.0)["a"], target["a"])
    xs = [interpolate_offsets(start, target, t / 20)["a"][0] for t in range(21)]
    assert xs == sorted(xs) and xs[10] == pytest.approx(5.0)   # smoothstep simétrico
    assert ease_in_out(-1) == 0 and ease_in_out(5) == 1
    # início de um deslocamento diferente de zero (ex.: de explodido para restaurado)
    back = interpolate_offsets({"a": np.array([10.0, 0, 0])}, {"a": np.zeros(3)}, 0.5)["a"]
    assert back[0] == pytest.approx(5.0)


# ------------------------------------------------- resolução de interferências (aninhadas)
def test_nested_part_is_pulled_out_of_its_container():
    """Eixo no MESMO centro do bloco, com o centro da montagem em outro lugar
    (um terceiro componente distante): só a direção radial os moveria JUNTOS."""
    root = Component(id="R", name="raiz", kind=ComponentKind.ASSEMBLY)
    for cid in ("bloco", "eixo", "pino"):
        root.add_child(Component(id=cid, name=cid))
    box = lambda lo, hi: BoundingBox(np.array(lo, float), np.array(hi, float))
    boxes = {"bloco": box((0, 0, 0), (100, 60, 40)), "eixo": box((0, 24, 14), (100, 36, 26)),
             "pino": box((300, 25, 15), (310, 35, 25))}
    boxes["R"] = BoundingBox.union(boxes.values())
    eng = ExplodeEngine(_lookup(boxes))

    without = eng.compute_offsets(root, ExplodeParams(resolve_interference=False))
    assert np.allclose(without["bloco"], without["eixo"])           # sem a etapa: andam juntos

    offs = eng.compute_offsets(root, ExplodeParams())
    rel = offs["eixo"] - offs["bloco"]
    assert np.count_nonzero(np.abs(rel) > 1e-9) == 1                # saiu por UM eixo (menor caminho)
    eixo = boxes["eixo"].translated(offs["eixo"])
    bloco = boxes["bloco"].translated(offs["bloco"])
    overlap = np.minimum(eixo.max, bloco.max) - np.maximum(eixo.min, bloco.min)
    assert not np.all(overlap > 1e-9)                               # liberou a interferência
    assert abs(rel[2]) > 26                                         # eixo Z = caminho mais curto (26 + folga)


def test_equal_concentric_boxes_split_symmetrically():
    root = Component(id="R", name="raiz", kind=ComponentKind.ASSEMBLY)
    for cid in ("a", "b"):
        root.add_child(Component(id=cid, name=cid))
    same = BoundingBox(np.array([0.0, 0, 0]), np.array([10.0, 10, 10]))
    boxes = {"a": same, "b": same, "R": same}
    eng = ExplodeEngine(_lookup(boxes))
    o1 = eng.compute_offsets(root, ExplodeParams())
    o2 = eng.compute_offsets(root, ExplodeParams())
    assert all(np.array_equal(o1[k], o2[k]) for k in o1)            # determinístico
    a = same.translated(o1["a"]); b = same.translated(o1["b"])
    assert not np.all((np.minimum(a.max, b.max) - np.maximum(a.min, b.min)) > 1e-9)


def test_interference_resolution_is_continuous_from_zero():
    root = Component(id="R", name="raiz", kind=ComponentKind.ASSEMBLY)
    for cid in ("bloco", "eixo"):
        root.add_child(Component(id=cid, name=cid))
    box = lambda lo, hi: BoundingBox(np.array(lo, float), np.array(hi, float))
    boxes = {"bloco": box((0, 0, 0), (100, 60, 40)), "eixo": box((0, 24, 14), (100, 36, 26))}
    boxes["R"] = BoundingBox.union(boxes.values())
    eng = ExplodeEngine(_lookup(boxes))
    tiny = eng.compute_offsets(root, ExplodeParams(factor=0.001))
    assert all(np.linalg.norm(v) < 0.5 for v in tiny.values())      # sem salto perto de zero
    zero = eng.compute_offsets(root, ExplodeParams(factor=0.0))
    assert all(np.allclose(v, 0) for v in zero.values())
