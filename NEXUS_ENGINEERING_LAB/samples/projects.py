"""Registro dos projetos predefinidos do NEXUS (V2.2).

Cada projeto é gerado em B-rep real (OpenCascade), gravado como STEP e importado como qualquer outro modelo.
HONESTIDADE: são modelos de REFERÊNCIA/didáticos; nenhum material é atribuído sozinho — os "materiais típicos" só entram por pedido do usuário.
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent


@dataclass(frozen=True)
class ProjectDef:
    key: str
    title: str
    description: str
    module: str
    builder: str
    step_name: str
    note: str
    typical: dict = field(default_factory=dict, hash=False, compare=False)
    has_mechanism: bool = False

    @property
    def step_path(self) -> Path:
        return HERE / self.step_name

    def build(self):
        return getattr(importlib.import_module(self.module), self.builder)()

    def ensure_step(self) -> Path:
        if not self.step_path.exists():
            importlib.import_module(self.module).write(self.step_path)
        return self.step_path

    def material_for(self, part_name: str):
        best = None
        for prefix in self.typical:
            if part_name.startswith(prefix) and (best is None or len(prefix) > len(best)):
                best = prefix
        return self.typical[best] if best else None


def _typ(mod: str, name: str = "TYPICAL") -> dict:
    return getattr(importlib.import_module(mod), name)


def _f1_typical() -> dict:
    # Só o que o banco de materiais cobre. Fibra de carbono (monocoque, asas, assoalho) e freio carbono-carbono NÃO constam: ficam sem material.
    return {"Halo": "Titanium Ti-6Al-4V (Grade 5)", "Roda": "Aluminum alloy 360", "Pneu": "Rubber, hard",
            "Bloco": "Aluminum alloy 360", "Cabecote": "Aluminum alloy 360", "Pistao": "Aluminum alloy 2024-T6",
            "Virabrequim": "Aço-liga AISI 4140"}


def all_projects() -> list[ProjectDef]:
    from samples.motor_materials import TYPICAL as MOTOR
    return [
        ProjectDef("motor", "Motor 4 cilindros (DOHC, correia)", "Motor com virabrequim, bielas, comandos, correia dentada e válvulas animadas.",
                   "samples.motor_4_cilindros", "build_motor", "motor_4_cilindros.step",
                   "Modelo didático; vela e junta ficam sem material.", MOTOR, True),
        ProjectDef("f1", "Carro de F1 2026 (referência por regulamento)", "Monocoque, asas ativas, V6 híbrido, suspensão push/pull, Halo, rodas e freios.",
                   "samples.f1_2026", "build_f1", "f1_2026.step",
                   "Referência baseada no regulamento 2026 — não é CAD de equipe; dimensões de pneus/asas/internos não verificadas; sem compósitos no banco.",
                   _f1_typical(), True),
        ProjectDef("redutor", "Redutor de engrenagens 2 estágios (6:1)", "Carcaça, 3 eixos, 4 engrenagens evolventes engrazadas, rolamentos e parafusos.",
                   "samples.redutor", "build_redutor", "redutor_2_estagios.step",
                   "Evolvente simplificada; sem lubrificação, folgas de montagem ou rolamentos detalhados.", _typ("samples.redutor")),
        ProjectDef("suspensao", "Suspensão duplo A (quarto de carro)", "Pneu 225/45 R17, roda, cubo, disco, pinça, manga, braços, mola e amortecedor.",
                   "samples.suspensao", "build_suspensao", "suspensao_duplo_a.step",
                   "Geometria nominal; sem buchas, barra estabilizadora ou curso de suspensão.", _typ("samples.suspensao")),
        ProjectDef("ponte", "Ponte treliçada (Warren com montantes)", "6 painéis de 2 m, banzos, diagonais, contraventamentos e tabuleiro.",
                   "samples.ponte_trelicada", "build_ponte", "ponte_trelicada.step",
                   "Geometria de estudo; não dimensionada segundo norma.", _typ("samples.ponte_trelicada")),
    ]


def get(key: str) -> ProjectDef:
    for p in all_projects():
        if p.key == key:
            return p
    raise KeyError(key)


def project_for_name(name: str):
    """Identifica o projeto predefinido pelo nome do arquivo/projeto (stem do STEP)."""
    low = name.lower()
    for p in all_projects():
        if Path(p.step_name).stem.lower() == low:
            return p
    return None
