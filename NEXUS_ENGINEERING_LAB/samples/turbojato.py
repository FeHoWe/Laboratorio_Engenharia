"""Turbina a gás turbojato de fluxo axial (modelo de referência paramétrico) — V2.7.

Eixo ao longo de X: entrada com cone de ponta, compressor axial de 4 estágios (rotor + estator), câmara de combustão anular, turbina de 2 estágios,
eixo único (spool) e bocal. Todas as peças do rotor (spool) giram juntas na animação.
HONESTIDADE: lâminas retas inclinadas (sem torção aerodinâmica real), número de palhetas ilustrativo, sem injetores/ignição/rolamentos/sistema de óleo,
sem razão de pressão ou temperatura calculadas. Animação prescrita; não é análise termodinâmica.
"""
from __future__ import annotations
import math
from pathlib import Path
from samples._common import L, at, g, group, RawNode, write_step, ROOT

TYPICAL: dict = {}
HUB_R = 70.0
CASE_R = 190.0


def bladed_disc(x0, r_hub, r_tip, n, thick=14.0, chord=40.0, pitch_deg=25.0, width=12.0, bore=76.0):
    """Disco em anel (furo ``bore`` encosta no tambor/eixo) com ``n`` palhetas retas inclinadas, tudo fundido numa peça."""
    disc = g.cut(g.cyl(r_hub + 6, width, at=(x0, 0, 0), axis=g.X), g.cyl(bore, width, at=(x0, 0, 0), axis=g.X))
    blades = []
    for k in range(n):
        b = g.box(x0 - chord / 2 + width / 2, x0 + chord / 2 + width / 2, -thick / 2, thick / 2, r_hub, r_tip)
        b = g.rot(b, (0, 0, 1), math.radians(pitch_deg), (x0 + width / 2, 0, r_hub))    # inclinação em torno do eixo radial
        blades.append(g.rot(b, g.X, 2 * math.pi * k / n))
    return g.clean(g.fuse(disc, *blades))


def stator(x0, r_in, r_out, n, chord=20.0):
    """Anel externo (encostado na carcaça por dentro, raio ``r_out``) com palhetas fixas radiais."""
    vanes = [g.rot(g.box(x0, x0 + chord, -4, 4, r_in, r_out - 3), g.X, 2 * math.pi * k / n) for k in range(n)]
    ring_o = g.cut(g.cyl(r_out, chord, at=(x0, 0, 0), axis=g.X), g.cyl(r_out - 6, chord, at=(x0, 0, 0), axis=g.X))
    return g.clean(g.fuse(ring_o, *vanes))


def build_turbojato() -> RawNode:
    """Layout em X: cone -120…10 · tambor 10…340 · compressor 0…330 · combustor 330…600 · turbina 600…780 · bocal 780…980 · cone de exaustao 790…1010.
    Peças só encostam (contato) — sem volumes sobrepostos: tambor r36…76 sobre o eixo r36, discos encaixados no tambor, estatores na carcaça r190."""
    kids = []
    kids.append(group("Carcaca", L("Carcaca do compressor", g.revolve([(0, CASE_R + 8), (330, CASE_R + 8), (330, CASE_R), (0, CASE_R)], "x")),
                      L("Carcaca da camara de combustao", g.revolve([(330, CASE_R + 8), (600, CASE_R + 8), (600, CASE_R), (330, CASE_R)], "x")),
                      L("Carcaca da turbina", g.revolve([(600, CASE_R + 8), (780, CASE_R + 8), (780, CASE_R), (600, CASE_R)], "x")),
                      L("Bocal de exaustao", g.revolve([(780, CASE_R), (980, 120), (980, 128), (780, CASE_R + 8)], "x"))))
    rotor = [L("Cone de ponta", g.revolve([(-120, 0), (10, 76), (10, 0)], "x"))]
    for i in range(4):
        rotor.append(L(f"Disco e palhetas do compressor estagio {i + 1}", bladed_disc(20 + i * 80, 82 + i * 14, CASE_R - 3, 16 + 2 * i)))
    for i in range(2):
        rotor.append(L(f"Disco e palhetas da turbina estagio {i + 1}", bladed_disc(640 + i * 80, 120, CASE_R - 4, 20 + 2 * i, thick=10, chord=34, pitch_deg=-30, bore=36.0)))
    rotor.append(L("Eixo do spool", g.cyl(36, 780, at=(10, 0, 0), axis=g.X)))
    rotor.append(L("Tambor do compressor", g.revolve([(10, 76), (340, 76), (340, 36), (10, 36)], "x")))
    kids.append(group("Rotor (spool)", *rotor))
    st = [L(f"Estator do compressor {i + 1}", stator(56 + i * 80, 80, CASE_R, 20)) for i in range(3)]
    st.append(L("Estator da turbina", stator(678, 130, CASE_R, 18, chord=22.0)))
    kids.append(group("Estatores", *st))
    comb = g.cut(g.revolve([(345, 180), (595, 180), (595, 100), (345, 100)], "x"), g.revolve([(355, 170), (585, 170), (585, 110), (355, 110)], "x"))
    kids.append(group("Combustor", L("Camara de combustao anular", g.clean(comb)),
                      *[L(f"Injetor {k + 1}", g.rot(g.cyl(6, 40, at=(305, 0, 140), axis=g.X), g.X, 2 * math.pi * k / 10)) for k in range(10)]))
    kids.append(group("Bocal", L("Cone central da exaustao", g.cone(100, 0, 220, at=(790, 0, 0), axis=g.X))))
    return RawNode("Turbojato axial (compressor 4 estagios, turbina 2)", children=kids)


def write(path: Path) -> Path:
    return write_step(build_turbojato, path)


if __name__ == "__main__":
    print("Gerado:", write(ROOT / "samples" / "turbojato.step"))
