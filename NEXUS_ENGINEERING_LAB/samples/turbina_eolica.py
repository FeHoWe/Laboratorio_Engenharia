"""Aerogerador de eixo horizontal de 3 pás (modelo de referência paramétrico) — V2.7.

Torre cônica (60 m), nacela, cubo com cone de ponta e 3 pás de perfil NACA com corda e torção variáveis (raio 1,5–40 m). Eixo do rotor ao longo de X,
cubo em (0, 0, 60 m). Unidades mm.
HONESTIDADE: perfil, corda e torção são ilustrativos (não são de um fabricante nem otimizados por BEM); sem gerador/multiplicadora internos, sem
sistema de passo/guinada detalhado. A rotação é animação prescrita. Estimativas de potência: use sua curva Cp em outra ferramenta.
"""
from __future__ import annotations
import math
from pathlib import Path
from samples._common import L, at, g, group, RawNode, write_step, ROOT

HUB_Z, TOWER_H, RB0, RB1 = 60000.0, 60000.0, 1450.0, 40000.0
TYPICAL: dict = {}


def blade():
    secs = []
    stations = [(0.00, 1500, 0.40, 18.0), (0.08, 4200, 0.25, 14.0), (0.25, 3600, 0.18, 8.0), (0.5, 2600, 0.15, 4.0), (0.75, 1500, 0.13, 1.5), (1.0, 250, 0.12, 0.0)]
    for t, chord, thick, twist in stations:
        r = RB0 + (RB1 - RB0) * t
        pts2 = g.airfoil(chord, thick, 0.03, 0.4, 14)
        a = math.radians(twist)
        sec = []
        for x, zz in pts2:
            x -= 0.3 * chord
            sec.append((x * math.cos(a) - zz * math.sin(a), x * math.sin(a) + zz * math.cos(a), r))
        secs.append([(p[1], p[0], p[2]) for p in sec])        # corda ao longo de Y, espessura ao longo de X, raio ao longo de Z
    return g.loft(secs)


def build_eolica() -> RawNode:
    """Layout em X (rotor à frente, x<0): ponta -4200 · cubo -3400…-1300 · nacela -1300…8000 · eixo -1300…0 · multiplicadora 0…1800 · gerador 1800…4000."""
    tower = g.revolve([(0, 2250), (HUB_Z - 1500, 1400), (HUB_Z - 1500, 0), (0, 0)], "z")             # termina no piso da nacela
    nac = g.cut(g.box(-1300, 8000, -1700, 1700, HUB_Z - 1500, HUB_Z + 1500),
                g.box(-1100, 7800, -1500, 1500, HUB_Z - 1300, HUB_Z + 2000), g.cyl(455, 400, at=(-1350, 0, HUB_Z), axis=g.X))
    cover = g.box(-1300, 8000, -1700, 1700, HUB_Z + 1500, HUB_Z + 1700)
    hub = g.revolve([(-4200, 0), (-3600, 800), (-3400, 1450), (-1300, 1450), (-1300, 0)], "x")
    hub = g.move(hub, (0, 0, HUB_Z))
    shaft = g.cyl(450, 1300, at=(-1300, 0, HUB_Z), axis=g.X)
    gear = g.box(0, 1800, -700, 700, HUB_Z - 700, HUB_Z + 700)
    gen = g.cyl(900, 2200, at=(1800, 0, HUB_Z), axis=g.X)
    kids = [group("Torre", L("Torre conica", tower)),
            group("Nacela", L("Carcaca da nacela", nac), L("Tampa da nacela", cover), L("Gerador", gen), L("Multiplicadora", gear)),
            group("Rotor", L("Cubo com cone de ponta", hub), L("Eixo principal", shaft))]
    b0 = blade()
    bl = []
    for k in range(3):
        bl.append(L(f"Pa {k + 1}", g.rot(g.move(b0, (-2350, 0, HUB_Z)), g.X, 2 * math.pi * k / 3, (0, 0, HUB_Z))))
    kids.append(group("Pas", *bl))
    return RawNode("Aerogerador 3 pas (eixo horizontal)", children=kids)


def write(path: Path) -> Path:
    return write_step(build_eolica, path)


if __name__ == "__main__":
    print("Gerado:", write(ROOT / "samples" / "turbina_eolica.step"))
