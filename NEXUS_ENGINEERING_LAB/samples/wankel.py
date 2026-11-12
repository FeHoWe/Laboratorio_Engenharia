"""Motor rotativo Wankel de 1 rotor (modelo de referência paramétrico) — V2.7.

Eixo excêntrico ao longo de Z. Carcaça com perfil de EPITROCOIDE x = R·cosα + e·cos3α, y = R·sinα + e·sin3α (R = raio dos vértices do rotor,
e = excentricidade); o rotor triangular gira em torno do centro excêntrico a θ/3 enquanto o centro orbita a θ — assim os 3 vértices (apex seals)
permanecem sobre a epitrocoide durante todo o ciclo (animação exata dessa relação cinemática).
HONESTIDADE: perfil de flanco do rotor simplificado (arcos com flecha pequena, sem rebaixo de câmara de combustão), sem engrenagem de sincronismo
detalhada, sem canais de refrigeração/óleo, sem vedações laterais/de canto. Modelo didático; não é projeto de motor.
"""
from __future__ import annotations
import math
from pathlib import Path
from samples._common import L, at, g, group, RawNode, write_step, ROOT

R, E, WID = 100.0, 14.0, 70.0          # R/e = 7,14 (faixa típica de motores rotativos)
TYPICAL: dict = {}


def epitrochoid(n=180):
    return [(R * math.cos(a) + E * math.cos(3 * a), R * math.sin(a) + E * math.sin(3 * a)) for a in (2 * math.pi * i / n for i in range(n))]


def rotor_profile(sag=8.0, per=14, rv=R - 6.0):
    """Triângulo curvilíneo com vértices a R do centro (0°,120°,240°) e flancos abaulados para fora (flecha sag)."""
    v = [(rv * math.cos(2 * math.pi * k / 3), rv * math.sin(2 * math.pi * k / 3)) for k in range(3)]
    pts = []
    for k in range(3):
        a, b = v[k], v[(k + 1) % 3]
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        d = math.hypot(mx, my); nx, ny = mx / d, my / d
        for i in range(per):
            t = i / per
            s = 4 * t * (1 - t) * sag
            pts.append((a[0] + (b[0] - a[0]) * t + nx * s, a[1] + (b[1] - a[1]) * t + ny * s))
    return pts


def build_wankel() -> RawNode:
    kids = []
    inner = epitrochoid()
    outer = [(x * 1.0 + 26 * x / math.hypot(x, y), y * 1.0 + 26 * y / math.hypot(x, y)) for x, y in inner]
    hz0 = -WID / 2
    housing = g.clean(g.extrude(outer, "xy", hz0, WID, holes=[inner]))
    kids.append(group("Carcaca", L("Carcaca do rotor (epitrocoide)", housing)))
    plate_r = R + E + 34
    plates = []
    for side, z0 in (("dianteira", hz0 - 18), ("traseira", hz0 + WID)):
        pl = g.cut(g.cyl(plate_r, 18, at=(0, 0, z0)), g.cyl(30, 18, at=(0, 0, z0)))
        plates.append(L(f"Tampa lateral {side}", g.clean(pl)))
    kids.append(group("Tampas laterais", *plates))
    # eixo excêntrico: munhões no centro, excêntrico em (E,0)
    shaft = [L("Eixo excentrico (munhao dianteiro)", g.cyl(24, 70, at=(0, 0, hz0 - 70))),
             L("Eixo excentrico (munhao traseiro)", g.cyl(24, 70, at=(0, 0, hz0 + WID))),
             L("Excentrico do eixo", g.cyl(46, WID, at=(E, 0, hz0))),
             L("Contrapeso dianteiro", g.cut(g.cyl(70, 14, at=(0, 0, hz0 - 32)), g.cyl(24, 14, at=(0, 0, hz0 - 32)), g.box(0, 80, -80, 80, hz0 - 32, hz0 - 18))),
             L("Contrapeso traseiro", g.cut(g.cyl(70, 14, at=(0, 0, hz0 + WID + 18)), g.cyl(24, 14, at=(0, 0, hz0 + WID + 18)), g.box(0, 80, -80, 80, hz0 + WID + 18, hz0 + WID + 32))),
             L("Volante do motor", g.cut(g.cyl(115, 26, at=(0, 0, hz0 + WID + 34)), g.cyl(24, 26, at=(0, 0, hz0 + WID + 34))))]
    kids.append(group("Eixo excentrico", *shaft))
    # rotor (centro em (E,0), vértices em 0°,120°,240°): furo central para o excêntrico + anel de engrenagem interna
    prof = [(x + E, y) for x, y in rotor_profile()]
    rotor = g.extrude(prof, "xy", hz0 + 4, WID - 8, holes=[[(E + 48 * math.cos(2 * math.pi * i / 36), 48 * math.sin(2 * math.pi * i / 36)) for i in range(36)]])
    kids.append(group("Rotor", L("Rotor triangular", g.clean(rotor))))
    seals = []
    for k in range(3):
        a = 2 * math.pi * k / 3
        ax, ay = E + (R - 4.4) * math.cos(a), (R - 4.4) * math.sin(a)       # centro da vedação em R-4.4 (ocupa R-6…R-2.8)
        seals.append(L(f"Vedacao de apice {k + 1}", g.rot(g.box(-1.6, 1.6, -3, 3, hz0 + 6, hz0 + WID - 6), g.Z, a, (0, 0, 0)), at(ax, ay, 0)))
    kids.append(group("Vedacoes de apice", *seals))
    # velas e dutos
    ign = []
    for k, ang in enumerate((50, 130)):
        a = math.radians(ang)
        r_in = math.hypot(R * math.cos(a) + E * math.cos(3 * a), R * math.sin(a) + E * math.sin(3 * a))
        ign.append(L(f"Vela de ignicao {k + 1}", g.orient_z_to(g.cyl(7, 46), (math.cos(a), math.sin(a), 0), (r_in * math.cos(a) * 0 + (R + E + 20) * math.cos(a), (R + E + 20) * math.sin(a), 0))))
    kids.append(group("Ignicao", *ign))
    kids.append(group("Dutos", L("Duto de admissao", g.tube((0, -(R + E + 4), 0), (0, -(R + E + 110), 0), 22, 17)),
                      L("Duto de escape", g.tube((-(R + E + 26), 0, 0), (-(R + E + 140), 0, 0), 24, 19))))
    return RawNode("Motor rotativo Wankel (1 rotor)", children=kids)


def write(path: Path) -> Path:
    return write_step(build_wankel, path)


if __name__ == "__main__":
    print("Gerado:", write(ROOT / "samples" / "wankel.step"))
