"""Explosão virtual de montagens (requisito 5.4).

Como o algoritmo funciona (sem nenhum deslocamento aleatório)
=============================================================
Para explodir um nó N (a montagem inteira, um grupo ou a raiz):

1. Centro da montagem ``C`` = centro da caixa delimitadora de N, na posição
   ORIGINAL (a explosão atual não influencia o cálculo, então explodir duas
   vezes dá o mesmo resultado).
2. Para cada filho direto ``i`` de N, centro geométrico ``c_i`` = centro da caixa
   delimitadora do filho (inclui todos os seus descendentes).
3. Direção de separação ``d_i``:
     * modo "radial": ``d_i = normalize(c_i - C)``
     * modo "axis_x/y/z" ou "custom": eixo escolhido; o sinal vem do lado em que o
       filho está em relação a ``C`` (as peças se afastam nos dois sentidos).
4. Magnitude: ``m_i = fator × ½ × diag(N) × (0,5 + 0,5 × r_i) × nivel^profundidade``
   onde ``r_i`` ∈ [0,1] é a distância relativa do filho ao centro (as mais
   distantes se afastam mais; as centrais ainda se movem o bastante para sair
   de dentro das outras). Isso preserva a ORDEM espacial da montagem.
5. Peças concêntricas (``c_i ≈ C``; ex.: virabrequim no centro do bloco) não têm
   direção radial. Elas recebem o eixo principal da montagem (o de maior
   extensão), alternando os sentidos +/− de forma determinística.
6. Resolução de interferências: peças ANINHADAS (ex.: virabrequim dentro do
   bloco) têm o mesmo centro do vizinho e, só com a direção radial, andariam
   juntas e continuariam interpenetradas. Por isso, entre irmãos cujas caixas
   ainda se sobrepõem, a MENOR sai pelo caminho mais curto (eixo e sentido de
   menor translação até liberar a outra), com uma folga (``clearance``). Em
   caixas iguais, cada uma se move metade, em sentidos opostos. É iterativo,
   determinístico e só usa translações. Com ``factor`` < 1 o efeito é reduzido
   proporcionalmente, de modo que o deslocamento é contínuo a partir de zero.
7. Hierarquia: se ``recursive`` e o filho for ele mesmo uma montagem/grupo, o
   algoritmo é reaplicado dentro dele, com magnitude reduzida por ``level_scale``
   a cada nível. Assim sub-montagens se afastam como bloco e depois se abrem.

Os resultados são ``offsets`` (deslocamentos PRÓPRIOS de cada nó). A geometria
original nunca é modificada: restaurar = zerar todos os offsets.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

from core.geometry import EPS, BoundingBox, normalize
from core.model import Component

BBoxFn = Callable[[Component], Optional[BoundingBox]]

AXES = {
    "axis_x": np.array([1.0, 0.0, 0.0]),
    "axis_y": np.array([0.0, 1.0, 0.0]),
    "axis_z": np.array([0.0, 0.0, 1.0]),
}
MODES = ("radial", "axis_x", "axis_y", "axis_z", "custom")


@dataclass
class ExplodeParams:
    factor: float = 1.0          # 0 = montada; 1 = separação "padrão"; >1 = mais afastada
    mode: str = "radial"
    direction: Optional[tuple[float, float, float]] = None  # modo "custom"
    level_scale: float = 0.55    # redução da distância a cada nível hierárquico
    recursive: bool = True
    clearance: float = 0.02      # folga entre peças separadas (fração da diagonal do nó)
    resolve_interference: bool = True

    def validate(self) -> None:
        if self.mode not in MODES:
            raise ValueError(f"Modo de explosão inválido: {self.mode}")
        if self.factor < 0:
            raise ValueError("O fator de explosão não pode ser negativo.")
        if self.mode == "custom":
            if self.direction is None or np.linalg.norm(self.direction) < EPS:
                raise ValueError("O modo personalizado exige uma direção não nula.")


class ExplodeEngine:
    def __init__(self, bbox_fn: BBoxFn) -> None:
        self._bbox = bbox_fn

    # ------------------------------------------------------------- núcleo
    def compute_offsets(self, node: Component, params: ExplodeParams) -> dict[str, np.ndarray]:
        """Offsets PRÓPRIOS dos descendentes de ``node`` (o próprio nó não se move)."""
        params.validate()
        result: dict[str, np.ndarray] = {}
        self._explode_children(node, params, depth=0, out=result)
        return result

    def _explode_children(self, node: Component, params: ExplodeParams, depth: int,
                          out: dict[str, np.ndarray]) -> None:
        kids = [(c, self._bbox(c)) for c in node.children]
        kids = [(c, b) for c, b in kids if b is not None]
        node_box = self._bbox(node)
        if not kids or node_box is None:
            return

        center = node_box.center
        diag = node_box.diagonal
        scale = params.factor * 0.5 * diag * (params.level_scale ** depth)
        main_axis = self._main_axis(node_box)

        centers = np.array([b.center for _, b in kids])
        rel = centers - center
        if params.mode in AXES or params.mode == "custom":
            axis = normalize(AXES[params.mode] if params.mode in AXES else params.direction)
            extent = rel @ axis                       # projeção com sinal
            max_extent = float(np.max(np.abs(extent))) or 1.0
        else:
            axis = None
            dist = np.linalg.norm(rel, axis=1)
            max_extent = float(np.max(dist)) or 1.0

        fallback_count = 0
        local: dict[str, np.ndarray] = {}
        for k, (child, _box) in enumerate(kids):
            if axis is not None:
                projection = float(extent[k])
                if abs(projection) < max(EPS, 1e-6 * diag):
                    sign = 1.0 if fallback_count % 2 == 0 else -1.0
                    boost = 1.0 + 0.5 * (fallback_count // 2)
                    fallback_count += 1
                    direction, r = axis * sign, 0.5 * boost
                else:
                    direction, r = axis * np.sign(projection), abs(projection) / max_extent
            else:
                d = float(np.linalg.norm(rel[k]))
                if d < max(EPS, 1e-6 * diag):       # concêntrica: usa eixo principal
                    sign = 1.0 if fallback_count % 2 == 0 else -1.0
                    boost = 1.0 + 0.5 * (fallback_count // 2)
                    fallback_count += 1
                    direction, r = main_axis * sign, 0.5 * boost
                else:
                    direction, r = rel[k] / d, d / max_extent
            local[child.id] = direction * scale * (0.5 + 0.5 * r)

        if params.resolve_interference and params.factor > 0:
            self._resolve_interferences(kids, local, diag * (params.level_scale ** depth), params)

        for child, _box in kids:
            out[child.id] = local[child.id]
            if params.recursive and child.children:
                self._explode_children(child, params, depth + 1, out)

    # Acima disso o custo O(n²) por iteração deixa de compensar; a explosão radial
    # básica continua valendo para esses níveis muito grandes.
    MAX_PAIRWISE = 400
    MAX_ITERATIONS = 40

    def _resolve_interferences(self, kids, offsets: dict[str, np.ndarray], diag: float,
                               params: ExplodeParams) -> None:
        """Afasta irmãos cujas caixas ainda se interpenetram (ver passo 6 do docstring)."""
        n = len(kids)
        if n < 2 or n > self.MAX_PAIRWISE:
            return
        ids = [c.id for c, _ in kids]
        boxes = [b for _, b in kids]
        volumes = [float(np.prod(np.maximum(b.size, 1e-12))) for b in boxes]
        tol = 1e-6 * max(diag, 1.0)
        gap = params.clearance * diag
        base = {i: offsets[i].copy() for i in ids}

        for _ in range(self.MAX_ITERATIONS):
            moved = False
            for i in range(n):
                for j in range(i + 1, n):
                    bi = boxes[i].translated(offsets[ids[i]])
                    bj = boxes[j].translated(offsets[ids[j]])
                    overlap = np.minimum(bi.max, bj.max) - np.maximum(bi.min, bj.min)
                    if not np.all(overlap > tol):
                        continue
                    equal = abs(volumes[i] - volumes[j]) <= 1e-9 * max(volumes[i], volumes[j])
                    # `small` é quem sai de dentro de `big` (em caixas iguais, i sai de j)
                    if volumes[j] < volumes[i] and not equal:
                        small_idx, big_idx, small, big = j, i, bj, bi
                    else:
                        small_idx, big_idx, small, big = i, j, bi, bj
                    best = None  # (distância, eixo, sinal) do menor deslocamento que libera
                    for a in range(3):
                        for dist, sign in ((big.max[a] - small.min[a], 1.0),
                                           (small.max[a] - big.min[a], -1.0)):
                            if best is None or dist < best[0] - 1e-12:
                                best = (dist, a, sign)
                    dist, a, sign = best
                    move = np.zeros(3)
                    move[a] = sign * (dist + gap)
                    if equal:
                        offsets[ids[small_idx]] = offsets[ids[small_idx]] + move / 2
                        offsets[ids[big_idx]] = offsets[ids[big_idx]] - move / 2
                    else:
                        offsets[ids[small_idx]] = offsets[ids[small_idx]] + move
                    moved = True
            if not moved:
                break

        strength = min(1.0, params.factor)   # contínuo em factor→0
        for i in ids:
            offsets[i] = base[i] + (offsets[i] - base[i]) * strength

    @staticmethod
    def _main_axis(box: BoundingBox) -> np.ndarray:
        axis = np.zeros(3)
        axis[int(np.argmax(box.size))] = 1.0
        return axis

    # ------------------------------------------------------------ casos de uso
    def explode_all(self, root: Component, params: ExplodeParams) -> dict[str, np.ndarray]:
        """Alvo para a montagem completa (todos os nós: os não-afetados ficam em zero)."""
        targets = self._zero_targets(root)
        targets.update(self.compute_offsets(root, params))
        return targets

    def explode_group(self, root: Component, group: Component, params: ExplodeParams) -> dict[str, np.ndarray]:
        """Explode apenas os filhos de ``group``; o restante da montagem fica como está."""
        targets = {n.id: np.array(n.offset) for n in root.walk()}
        for n in group.walk():
            if n is not group:
                targets[n.id] = np.zeros(3)
        targets.update(self.compute_offsets(group, params))
        return targets

    def separate_part(self, root: Component, part: Component, params: ExplodeParams) -> dict[str, np.ndarray]:
        """Separa UMA peça do restante, afastando-a do centro do seu grupo pai.

        A direção vem do modo (radial a partir do centro do pai, eixo ou personalizada);
        a distância usa o mesmo fator das demais explosões.
        """
        params.validate()
        targets = {n.id: np.array(n.offset) for n in root.walk()}
        parent = part.parent or root
        parent_box, part_box = self._bbox(parent), self._bbox(part)
        if parent_box is None or part_box is None:
            return targets
        rel = part_box.center - parent_box.center
        if params.mode in AXES or params.mode == "custom":
            axis = normalize(AXES[params.mode] if params.mode in AXES else params.direction)
            direction = axis * (np.sign(rel @ axis) or 1.0)
        else:
            direction = normalize(rel, fallback=self._main_axis(parent_box))
        magnitude = params.factor * 0.5 * parent_box.diagonal
        targets[part.id] = direction * magnitude
        return targets

    def restore(self, root: Component) -> dict[str, np.ndarray]:
        """Alvo de restauração: todos os offsets em zero."""
        return self._zero_targets(root)

    @staticmethod
    def _zero_targets(root: Component) -> dict[str, np.ndarray]:
        return {n.id: np.zeros(3) for n in root.walk()}


# -------------------------------------------------------------- animação (pura)
def ease_in_out(t: float) -> float:
    """Suavização cúbica (smoothstep): começa e termina devagar."""
    t = min(1.0, max(0.0, t))
    return t * t * (3.0 - 2.0 * t)


def interpolate_offsets(start: dict[str, np.ndarray], target: dict[str, np.ndarray],
                        t: float) -> dict[str, np.ndarray]:
    """Offsets intermediários entre ``start`` e ``target`` para o instante ``t`` ∈ [0,1]."""
    k = ease_in_out(t)
    out = {}
    for cid, goal in target.items():
        begin = start.get(cid, np.zeros(3))
        out[cid] = begin + (goal - begin) * k
    return out
