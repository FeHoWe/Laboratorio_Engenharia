"""Utilidades geométricas puras (somente NumPy).

Este módulo NÃO depende de OpenCascade, VTK nem Qt. Isso permite testar a
matemática do NEXUS isoladamente e trocar o motor CAD no futuro sem tocar aqui.

Convenções:
    * Unidades: milímetros (padrão do leitor STEP do OpenCascade).
    * Sistema de coordenadas: destro, Z para cima (convenção CAD).
    * Matrizes de transformação: 4x4 homogêneas (NumPy float64).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

import numpy as np

EPS = 1e-9


def vec3(x=0.0, y=0.0, z=0.0) -> np.ndarray:
    """Cria um vetor 3D float64."""
    return np.array([x, y, z], dtype=np.float64)


def normalize(v: Sequence[float], fallback: Optional[Sequence[float]] = None) -> np.ndarray:
    """Normaliza ``v``. Se o comprimento for ~0, devolve ``fallback`` (ou zeros)."""
    arr = np.asarray(v, dtype=np.float64)
    n = float(np.linalg.norm(arr))
    if n < EPS:
        return np.asarray(fallback, dtype=np.float64) if fallback is not None else np.zeros(3)
    return arr / n


def identity() -> np.ndarray:
    return np.eye(4, dtype=np.float64)


def translation_matrix(v: Sequence[float]) -> np.ndarray:
    m = identity()
    m[:3, 3] = np.asarray(v, dtype=np.float64)
    return m


def euler_from_matrix(m: np.ndarray) -> tuple[float, float, float]:
    """Extrai ângulos (rx, ry, rz) em graus de uma matriz de rotação.

    Convenção yaw-pitch-roll (a mesma do FreeCAD): R = Rz(rz) · Ry(ry) · Rx(rx).
    Qualquer escala uniforme presente na matriz é removida antes.
    """
    r = np.asarray(m, dtype=np.float64)[:3, :3].copy()
    scale = np.cbrt(abs(np.linalg.det(r)))
    if scale > EPS:
        r /= scale
    sy = -r[2, 0]
    if abs(sy) < 1.0 - 1e-9:
        ry = np.arcsin(sy)
        rx = np.arctan2(r[2, 1], r[2, 2])
        rz = np.arctan2(r[1, 0], r[0, 0])
    else:  # gimbal lock
        ry = np.copysign(np.pi / 2, sy)
        rx = np.arctan2(-r[1, 2], r[1, 1])
        rz = 0.0
    return tuple(float(np.degrees(a)) for a in (rx, ry, rz))  # type: ignore[return-value]


@dataclass(frozen=True)
class BoundingBox:
    """Caixa delimitadora alinhada aos eixos do mundo."""

    min: np.ndarray
    max: np.ndarray

    @property
    def center(self) -> np.ndarray:
        return (self.min + self.max) / 2.0

    @property
    def size(self) -> np.ndarray:
        """Dimensões (X, Y, Z)."""
        return self.max - self.min

    @property
    def diagonal(self) -> float:
        return float(np.linalg.norm(self.size))

    def translated(self, offset: Sequence[float]) -> "BoundingBox":
        o = np.asarray(offset, dtype=np.float64)
        return BoundingBox(self.min + o, self.max + o)

    @staticmethod
    def from_points(points: np.ndarray) -> "BoundingBox":
        pts = np.asarray(points, dtype=np.float64).reshape(-1, 3)
        if pts.size == 0:
            raise ValueError("Nenhum ponto para calcular a caixa delimitadora.")
        return BoundingBox(pts.min(axis=0), pts.max(axis=0))

    @staticmethod
    def union(boxes: Iterable[Optional["BoundingBox"]]) -> Optional["BoundingBox"]:
        valid = [b for b in boxes if b is not None]
        if not valid:
            return None
        return BoundingBox(
            np.min([b.min for b in valid], axis=0),
            np.max([b.max for b in valid], axis=0),
        )


def smooth_vertex_normals(vertices: np.ndarray, faces: np.ndarray) -> np.ndarray:
    """Normais por vértice (média ponderada pela área dos triângulos adjacentes)."""
    v = np.asarray(vertices, dtype=np.float64)
    f = np.asarray(faces, dtype=np.int64)
    normals = np.zeros_like(v)
    if len(f) == 0:
        return normals
    tri = v[f]
    face_n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])  # |n| = 2*área
    for k in range(3):
        np.add.at(normals, f[:, k], face_n)
    lengths = np.linalg.norm(normals, axis=1)
    lengths[lengths < EPS] = 1.0
    return normals / lengths[:, None]


def mesh_area(vertices: np.ndarray, faces: np.ndarray) -> float:
    """Área total de uma malha triangular."""
    v = np.asarray(vertices, dtype=np.float64)
    f = np.asarray(faces, dtype=np.int64)
    if len(f) == 0:
        return 0.0
    tri = v[f]
    return float(0.5 * np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1).sum())
