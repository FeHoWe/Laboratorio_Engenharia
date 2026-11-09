"""F1 clássicos (V2.8): Ferrari 312T (1975), McLaren MP4/4 (1988) e Lotus 72 (1970–75) — modelos de REFERÊNCIA a partir de medidas públicas.

HONESTIDADE: não há CAD público desses carros; a geometria é um modelo paramétrico simplificado (monocoque em loft, motor em blocos, asas por perfil, rodas,
suspensão de braços duplos), NÃO uma réplica. Dados e origem:
  Ferrari 312T  — ultimatecarpage/f1technical: comprimento 4143, largura 2030, altura 1275, entre-eixos 2518, bitolas 1510/1530, 575 kg, V12 a 180° 3,0 L, 5 marchas
                   (a 312T3 de 1974 tem outras medidas; aqui usei a 312T de 1975 da ultimatecarpage).
  McLaren MP4/4 — Wikipedia: entre-eixos 2875, bitolas 1824 (diant.) / 1670 (tras.) conforme a fonte, 540 kg, Honda RA168E V6 1,5 L turbo a 80°, 6 marchas.
                   Comprimento/largura/altura NÃO achei: largura e altura aqui são ESTIMADAS.
  Lotus 72      — Wikipedia/supercars: Cosworth DFV V8 3,0 L, Hewland FG400 5 marchas, freios internos (inboard), radiadores laterais, cunha.
                   Entre-eixos, bitolas, comprimento e massa NÃO foram encontrados: valores ESTIMADOS (marcados no código e na nota do projeto).
Diâmetro/largura dos pneus, posições internas, asas e carenagens: ILUSTRATIVOS em todos. Sem aerodinâmica, sem composição de massa; materiais não são atribuídos.
Eixos: x lateral (direita +), y longitudinal (eixo dianteiro em y=0, traseiro em y=WB; a frente aponta para -y), z para cima (solo z=0).
Animação: rodas giram; as dianteiras também esterçam (prescrito, não é dinâmica).
"""
from __future__ import annotations

import math
import sys
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from samples._common import L, at, g, group, write_step, RawNode  # noqa: E402
from samples.f1_2026 import wing_element, endplate  # noqa: E402

X, Y, Z = g.X, g.Y, g.Z

# ---- especificações (ESTIMADO/ILUSTRATIVO marcados)
SPECS = {
    "312t": dict(title="Ferrari 312T (1975)", WB=2518.0, TF=1510.0, TR=1530.0, RF=305.0, RR=340.0, WF=250.0, WR=400.0, nose=950.0, tail=405.0, tub_w=520.0, tub_h=420.0,
                 engine="boxer12", eng_len=720.0, gearbox="transversal", hoop=1275.0, inboard=False, wing_f=1000.0, wing_r=1000.0, sidepod=True),
    "mp44": dict(title="McLaren MP4/4 (1988)", WB=2875.0, TF=1824.0, TR=1670.0, RF=330.0, RR=350.0, WF=300.0, WR=450.0, nose=1050.0, tail=650.0, tub_w=520.0, tub_h=420.0,
                 engine="v6t", eng_len=560.0, gearbox="longitudinal", hoop=1100.0, inboard=False, wing_f=1300.0, wing_r=1000.0, sidepod=True),
    "lotus72": dict(title="Lotus 72 (1970–75)", WB=2500.0, TF=1600.0, TR=1580.0, RF=300.0, RR=345.0, WF=250.0, WR=420.0, nose=1100.0, tail=650.0, tub_w=500.0, tub_h=380.0,
                    engine="v8", eng_len=600.0, gearbox="longitudinal", hoop=1150.0, inboard=True, wing_f=1100.0, wing_r=1000.0, sidepod=True),
}
KEYS = {"312t": "f1_312t", "mp44": "f1_mp44", "lotus72": "f1_lotus72"}


def tyre(R, Rr, w):
    pts = [(-w / 2, Rr), (-w / 2, R - 18), (-w / 2 + 18, R), (w / 2 - 18, R), (w / 2, R - 18), (w / 2, Rr)]
    return g.revolve(pts, "x")


def rim(Rr, w, sign):
    barrel = g.cut(g.cyl(Rr, w * 0.8, at=(-w * 0.4, 0, 0), axis=X), g.cyl(Rr - 12, w * 0.8, at=(-w * 0.4, 0, 0), axis=X))
    web = g.cyl(Rr - 12, 10, at=(sign * (w * 0.4 - 10) if sign > 0 else -w * 0.4, 0, 0), axis=X)
    return g.clean(g.fuse(barrel, web))


def _tub(sp):
    wb, w, h = sp["WB"], sp["tub_w"], sp["tub_h"]
    secs = [(-sp["nose"] * 0.35, w * 0.45, h * 0.55, 0, h * 0.62, 3.0), (wb * 0.12, w * 0.85, h * 0.9, 0, h * 0.62 + 40, 3.2), (wb * 0.42, w, h, 0, h * 0.62 + 60, 3.2), (wb * 0.62, w * 0.9, h * 0.85, 0, h * 0.62 + 50, 3.2)]
    tub = g.loft_y(secs)
    zc = h * 0.62 + 40
    cav = g.box(-w * 0.34, w * 0.34, wb * 0.08, wb * 0.43, zc - h * 0.30, zc + h)
    return g.clean(g.cut(tub, cav))


def _nose(sp):
    w, h = sp["tub_w"], sp["tub_h"]
    return g.loft_y([(-sp["nose"], 90, 70, 0, 140, 2.8), (-sp["nose"] * 0.6, w * 0.5, h * 0.45, 0, 170, 3.0), (-sp["nose"] * 0.35, w * 0.45, h * 0.55, 0, h * 0.62, 3.0)])


def _engine(sp):
    wb, el = sp["WB"], sp["eng_len"]
    y0 = wb * 0.62
    ez = 330.0
    kind = sp["engine"]
    ang = {"boxer12": 90.0, "v8": 45.0, "v6t": 40.0}[kind]
    tag = {"boxer12": "V12 boxer", "v8": "V8 DFV", "v6t": "V6 turbo"}[kind]
    parts = [(f"Bloco do motor {tag}", g.box(-110, 110, y0, y0 + el, ez - 100, ez + 30)), ("Carter de oleo", g.box(-100, 100, y0, y0 + el, ez - 150, ez - 100))]
    bank = g.move(g.rot(g.box(-55, 55, y0, y0 + el, 135, 300), Y, math.radians(ang)), (0, 0, ez))        # cilindros: eixo radial a partir do virabrequim
    parts.append(("Bancada de cilindros direita", bank))
    parts.append(("Bancada de cilindros esquerda", g.mirror_x(bank)))
    return parts


def _wing(span, chord, y, z, inc):
    return wing_element(span, chord, 0.11, 0.07, inc, y, z)


def build_classic(key: str) -> RawNode:
    sp = SPECS[key]
    WB, TF, TR, RF, RR, WF, WR = (sp[k] for k in ("WB", "TF", "TR", "RF", "RR", "WF", "WR"))
    kids = []
    chassis = [L("Monocoque", _tub(sp)), L("Nariz", _nose(sp))]
    hoop_z = sp["hoop"]
    chassis += [L("Santo Antonio (arco de capotamento)", g.tube((-100, WB * 0.5 + 60, sp["tub_h"] * 1.12 + 70), (-100, WB * 0.5 + 60, hoop_z), 22)),
                L("Santo Antonio direito", g.tube((100, WB * 0.5 + 60, sp["tub_h"] * 1.12 + 70), (100, WB * 0.5 + 60, hoop_z), 22)),
                L("Capacete do piloto (referencia)", g.sphere(130, at=(0, WB * 0.30, sp["tub_h"] * 0.62 + 160))),
                L("Volante", g.cyl(150, 18, at=(0, WB * 0.12 + 18, sp["tub_h"] * 0.62 + 150), axis=Y))]
    kids.append(group("Chassi", *chassis))
    kids.append(group("Motor", *[L(n, s) for n, s in _engine(sp)]))
    gb_y = WB - 160
    if sp["gearbox"] == "transversal":
        gb = g.cyl(150, 520, at=(-260, WB + 60, 330), axis=X)
    else:
        gb = g.box(-150, 150, WB * 0.62 + sp["eng_len"], WB + 110, 230, 420)
    kids.append(group("Transmissao", L("Caixa de cambio e diferencial", gb)))
    # carenagens laterais (radiadores/pontões)
    if sp["sidepod"]:
        xs0 = sp["tub_w"] / 2 + 6
        sp_shell = g.loft_y([(WB * 0.20, 200, 260, xs0 + 100, 260, 3.0), (WB * 0.38, 260, 280, xs0 + 130, 270, 3.0), (WB * 0.58, 160, 220, xs0 + 80, 260, 3.0)])
        kids.append(group("Carroceria", L("Pontao direito (radiador)", sp_shell), L("Pontao esquerdo (radiador)", g.mirror_x(sp_shell)),
                          L("Entrada de ar do motor", g.loft_y([(WB * 0.52, 150, 180, 0, hoop_z - 140, 2.6), (WB * 0.62, 190, 220, 0, hoop_z - 200, 2.8), (WB * 0.75, 130, 160, 0, 760, 2.8)]))))
    # asas
    fw = [L("Asa dianteira elemento principal", _wing(sp["wing_f"], 260, -sp["nose"] + 120, 12, 8)),
          L("Asa dianteira placa direita", g.move(endplate(-sp["nose"] + 120, -sp["nose"] + 390, 20, 160), (sp["wing_f"] / 2, 0, 0))),
          L("Asa dianteira placa esquerda", g.move(endplate(-sp["nose"] + 120, -sp["nose"] + 390, 20, 160), (-sp["wing_f"] / 2 - 10, 0, 0)))]
    kids.append(group("Asa dianteira", *fw))
    ry = WB + sp["tail"] - 150
    rw = [L("Asa traseira plano principal", _wing(sp["wing_r"], 330, ry, 760, 18)), L("Asa traseira flap", _wing(sp["wing_r"], 190, ry + 60, 880, 30)),
          L("Asa traseira placa direita", g.move(endplate(ry - 20, ry + 420, 620, 1000), (sp["wing_r"] / 2, 0, 0))),
          L("Asa traseira placa esquerda", g.move(endplate(ry - 20, ry + 420, 620, 1000), (-sp["wing_r"] / 2 - 10, 0, 0))),
          L("Apoio da asa traseira", g.box(-25, 25, ry + 120, ry + 180, 440, 735))]
    kids.append(group("Asa traseira", *rw))
    # eixos: rodas, cubos, discos, suspensão
    for front in (True, False):
        y, tr, R, Rr_w, w = (0.0, TF, RF, RF * 0.62, WF) if front else (WB, TR, RR, RR * 0.58, WR)
        nm = "dianteira" if front else "traseira"
        Rrim = Rr_w
        xc = tr / 2
        wheels, susp = [], []
        for s, sg in (("direita", 1), ("esquerda", -1)):
            c = (sg * xc, y, R)
            mir = (lambda sh: sh) if sg > 0 else g.mirror_x
            hub = g.cyl(34, w * 0.9 - 10, at=(-w * 0.5, 0, 0), axis=X)
            wheels += [L(f"Pneu {nm} {s}", g.move(mir(tyre(R, Rrim, w)), c)), L(f"Roda {nm} {s}", g.move(mir(rim(Rrim, w, 1)), c)), L(f"Cubo {nm} {s}", g.move(mir(hub), c))]
            if not (sp["inboard"] and front):
                disc = g.cut(g.cyl(Rrim * 0.72, 12, at=(-w * 0.3 - 6, 0, 0), axis=X), g.cyl(34, 12, at=(-w * 0.3 - 6, 0, 0), axis=X))
                wheels.append(L(f"Disco de freio {nm} {s}", g.move(mir(disc), c)))
            else:
                wheels.append(L(f"Disco de freio interno {nm} {s}", g.move(g.cut(g.cyl(115, 12, at=(-6, 0, 0), axis=X), g.cyl(30, 12, at=(-6, 0, 0), axis=X)), (sg * (sp["tub_w"] / 2 + 40), -270, 330))))
            up = (sg * (xc - w * 0.5 - 20), y, R)
            tub_x = sg * (225.0 if front else sp["tub_w"] / 2 + 20)
            for lvl, (zc, lab) in enumerate(((R + 150, "superior"), (R - 140, "inferior"))):
                for k, dy in enumerate((-170, 170)):
                    a0 = np.array((tub_x, y + dy * 0.8, zc * 0.85 + 50 if lvl == 0 else zc + 20), float)
                    b0 = np.array((up[0], up[1] + dy * 0.3, zc), float)
                    susp.append(L(f"Braco {lab} {nm} {s} {k + 1}", g.tube(a0, b0 - (b0 - a0) / np.linalg.norm(b0 - a0) * 24, 9)))
            susp.append(L(f"Manga de eixo {nm} {s}", g.tube((up[0], y, R - 140), (up[0], y, R + 150), 20)))
        kids.append(group(f"Rodas {nm}", *wheels))
        kids.append(group(f"Suspensao {nm}", *susp))
    return RawNode(f"{sp['title']} (modelo de referencia)", children=kids)


def _mk(key):
    def build():
        return build_classic(key)
    build.__name__ = f"build_{KEYS[key]}"
    return build


build_f1_312t, build_f1_mp44, build_f1_lotus72 = _mk("312t"), _mk("mp44"), _mk("lotus72")


def write_for(key, path):
    return write_step(lambda: build_classic(key), path)


def write_f1_312t(path):
    return write_for("312t", path)


def write_f1_mp44(path):
    return write_for("mp44", path)


def write_f1_lotus72(path):
    return write_for("lotus72", path)
