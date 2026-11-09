"""Protótipo de F1 2027 (derivado do modelo de referência 2026) — V2.8.

HONESTIDADE: NÃO é o carro de nenhuma equipe nem o regulamento completo. Parte do modelo 2026 (samples/f1_2026.py) e aplica SÓ as mudanças de
2027 que encontrei em fontes públicas (The Race; FIA Seção C Técnica 2027 emissão 04, trecho C2/C3 lido; RaceTeq para a unidade de potência):
  • asa traseira ~20 mm mais rasa (elementos superiores rebaixados); suportes de rotação e asas de escapamento proibidos (não modelados);
  • novo estai (brace) entre os pilares da asa traseira, dentro de caixa 100×375×40 mm (C3.11.3(a)) — posição/forma ILUSTRATIVAS;
  • borda de ataque do assoalho / prancha: seção frontal da prancha de 900 → 600 mm (corte de 300 mm): piso e prancha recuados 300 mm; prancha com 10 mm de espessura (C3.6.1);
  • entre-eixos ≤ 3400 mm, meia-largura ≤ 950 mm (C2.3.1/C2.3.3) — iguais a 2026;
  • unidade de potência: +50 kW na combustão (mais fluxo de combustível), implantação elétrica 350 → 300 kW, divisão ≈ 50/50 → 60/40 e tanque
    maior — acordo de maio/2026 confirmado em comunicado da FIA; os números de C5/C6 NÃO foram lidos: o volume do tanque aqui é ILUSTRATIVO (+8 % em y).
Massa mínima de 2027: NÃO verificada (o modelo não afirma 768 kg). Aerodinâmica/CFD: nenhuma — geometria apenas.
Eixos como em 2026: x lateral, y longitudinal (frente em -y), z para cima.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.cad_engine import CadEngine, RawNode  # noqa: E402
from samples import f1_2026 as F  # noqa: E402
from samples import geo as g  # noqa: E402

PLANK_FRONT_CUT = 300.0         # mm: seção frontal da prancha 900 → 600
REAR_WING_SHALLOWER = 20.0      # mm
TANK_EXTRA = 0.08               # ILUSTRATIVO
TYPICAL: dict = {}


def _walk(n):
    yield n
    for c in n.children:
        yield from _walk(c)


def build_f1_2027() -> RawNode:
    root = F.build_f1()
    root.name = "Carro F1 2027 (prototipo de referencia)"
    nodes = {n.name: n for n in _walk(root) if n.shape is not None}
    # asa traseira 20 mm mais rasa: elementos superiores descem (intermediário metade, ativo todo)
    nodes["Asa traseira elemento intermediario"].shape = g.move(nodes["Asa traseira elemento intermediario"].shape, (0, 0, -REAR_WING_SHALLOWER / 2))
    nodes["Asa traseira elemento ativo"].shape = g.move(nodes["Asa traseira elemento ativo"].shape, (0, 0, -REAR_WING_SHALLOWER))
    # assoalho e prancha: borda de ataque recuada 300 mm
    pts = [(-720, 300 + PLANK_FRONT_CUT), (-780, 900), (-830, 1700), (-780, 3000), (-600, 3400), (600, 3400), (780, 3000), (830, 1700), (780, 900), (720, 300 + PLANK_FRONT_CUT)]
    nodes["Piso (assoalho plano)"].shape = g.extrude(pts, "xy", 40.0, 14.0)
    nodes["Prancha de desgaste"].shape = g.box(-150, 150, 520 + PLANK_FRONT_CUT, 3300, 30.0, 40.0)
    # tanque maior (ILUSTRATIVO): cresce para trás, sem invadir o cockpit
    nodes["Tanque de combustivel"].shape = g.box(-220, 220, 1650, 2030 + 380 * TANK_EXTRA, 110, 400)
    # novo estai da asa traseira entre os pilares (caixa 100×375×40: 375 em x, 100 em y, 40 em z), logo atrás do pilar central
    brace = g.box(-187.5, 187.5, 4180, 4280, 500, 540)
    wing = [c for c in _walk(root) if c.name == "Asa traseira"][0]
    wing.children.append(RawNode("Estai da asa traseira (brace 2027)", shape=brace, local_matrix=F.at()))
    return root


def write(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    CadEngine().write_step([build_f1_2027()], path)
    return path


if __name__ == "__main__":
    print("Gerado:", write(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "samples" / "f1_2027.step"))
