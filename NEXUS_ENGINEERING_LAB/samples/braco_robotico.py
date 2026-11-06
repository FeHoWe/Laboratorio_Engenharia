"""Braço robótico articulado de 6 eixos (modelo de referência) — V2.7.

Postura inicial vertical (braço ao longo de +Z). Eixos: J1 = Z pela origem (torre); J2 = Y em z=300 (ombro); J3 = Y em z=750 (cotovelo);
J4 = Z em z=750 (rolagem do antebraço); J5 = Y em z=1240 (punho); J6 = Z em z=1240 (flange). Alcance nominal ≈ 1,3 m.
Peças só ENCOSTAM (sem volumes sobrepostos); o punho 2 é uma esfera (junta esférica simplificada) para não colidir com o punho 1 ao girar.
HONESTIDADE: geometria simplificada (sem motores/redutores internos, cabos, limites reais de curso). A animação é um cenário PRESCRITO
(ângulos senoidais), não uma trajetória planejada nem dinâmica; a cinemática direta é o produto de exponenciais dos 6 eixos.
"""
from __future__ import annotations
from pathlib import Path
from samples._common import L, at, g, group, RawNode, write_step, ROOT

Z_SH, Z_EL, Z_WR = 300.0, 750.0, 1240.0
TYPICAL: dict = {}
JOINTS = [  # (nome, ponto, eixo, amplitude°, fase°)
    ("J1", (0, 0, 0), (0, 0, 1), 70, 0), ("J2", (0, 0, Z_SH), (0, 1, 0), 28, 40), ("J3", (0, 0, Z_EL), (0, 1, 0), 45, 120),
    ("J4", (0, 0, Z_EL), (0, 0, 1), 100, 200), ("J5", (0, 0, Z_WR), (0, 1, 0), 55, 280), ("J6", (0, 0, Z_WR), (0, 0, 1), 170, 330)]


def build_robo() -> RawNode:
    base = g.cyl(190, 120)
    turret = g.cyl(150, 80, at=(0, 0, 120))                                                   # topo em z=200
    shoulder = g.clean(g.fuse(g.box(-80, 80, -80, 80, 200, Z_SH), g.cyl(100, 160, at=(0, -80, Z_SH), axis=g.Y)))
    plates = [g.box(-60, 60, s * 80, s * 110, Z_SH, Z_EL) for s in (-1, 1)]                  # duas chapas laterais (garfo) fora do ombro
    upper = g.clean(g.fuse(*plates, g.box(-60, 60, -80, 80, 480, 520)))
    elbow = g.cut(g.cyl(85, 160, at=(0, -80, Z_EL), axis=g.Y), g.box(-60, 60, -60, 60, Z_EL, Z_EL + 100))
    fore = g.clean(g.fuse(g.box(-60, 60, -60, 60, Z_EL, Z_EL + 130), g.cyl(60, Z_WR - 58 - 82 - (Z_EL + 130), at=(0, 0, Z_EL + 130))))
    wrist1 = g.cyl(62, 82, at=(0, 0, Z_WR - 58 - 82))
    wrist2 = g.sphere(58, at=(0, 0, Z_WR))
    flange = g.clean(g.cut(g.cyl(55, 28, at=(0, 0, Z_WR + 58)), g.cyl(18, 28, at=(0, 0, Z_WR + 58))))
    zt = Z_WR + 58 + 28
    finger = lambda y: g.box(-10, 10, y - 8, y + 8, zt + 16, zt + 116)  # noqa: E731
    jaw = g.box(-14, 14, -60, 60, zt, zt + 16)
    kids = [group("Base", L("Base fixa", base)),
            group("J1 Torre", L("Torre giratoria", turret)),
            group("J2 Ombro", L("Carcaca do ombro", shoulder)),
            group("J2 Braco superior", L("Braco superior", upper)),
            group("J3 Cotovelo", L("Carcaca do cotovelo", elbow), L("Antebraco", fore)),
            group("J4 Punho 1", L("Punho 1 (rolagem)", wrist1)),
            group("J5 Punho 2", L("Punho 2 (arfagem)", wrist2)),
            group("J6 Ferramenta", L("Flange do eixo 6", flange), L("Base da garra", jaw), L("Dedo da garra 1", finger(-50)), L("Dedo da garra 2", finger(50)))]
    return RawNode("Braco robotico 6 eixos", children=kids)


def write(path: Path) -> Path:
    return write_step(build_robo, path)


if __name__ == "__main__":
    print("Gerado:", write(ROOT / "samples" / "braco_robotico.step"))
