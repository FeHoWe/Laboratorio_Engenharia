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
        ProjectDef("f1", "Carro de F1 2026 (referência por regulamento)", "Monocoque oco, asas multielemento ativas, bargeboards, V6 com bielas, suspensão push/pull articulada, direção, Halo, rodas e freios; animação de curva/frenagem.",
                   "samples.f1_2026", "build_f1", "f1_2026.step",
                   "Referência baseada no regulamento 2026 — não é CAD de equipe; dimensões de pneus/asas/internos/suspensão não verificadas; cascas ocas encostam nos internos; sem compósitos no banco.",
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
        ProjectDef("wankel", "Motor rotativo Wankel (1 rotor)", "Carcaça de epitrocoide, rotor triangular com vedações de ápice, eixo excêntrico, contrapesos e volante; rotor a θ/3 (cinemática exata).",
                   "samples.wankel", "build_wankel", "wankel.step",
                   "Flancos do rotor simplificados, sem câmara de combustão, engrenagem de sincronismo, refrigeração nem vedações laterais.", {}, True),
        ProjectDef("v12", "Motor V12 a 60°", "Bloco em V, 12 pistões e 12 bielas (2 por moente), virabrequim de 6 moentes, cabeçotes, cárter e volante; biela-manivela animada.",
                   "samples.v12", "build_v12", "v12.step",
                   "Sem comando/válvulas/coletores/arrefecimento; bloco e cabeçotes simplificados; fases típicas de V12 60°.", {}, True),
        ProjectDef("braco", "Braço robótico de 6 eixos", "Base, torre, ombro, braço, cotovelo, antebraço, punho de 2 eixos, flange e garra; cinemática direta animada.",
                   "samples.braco_robotico", "build_robo", "braco_robotico.step",
                   "Sem motores/redutores/cabos; animação prescrita (senoidal), não é planejamento de trajetória.", {}, True),
        ProjectDef("bomba", "Bomba centrífuga com voluta", "Voluta, bocais, rotor fechado de 6 palhetas, eixo, mancais com rolamentos e base.",
                   "samples.bomba_centrifuga", "build_bomba", "bomba_centrifuga.step",
                   "Voluta e palhetas aproximadas; sem selo, curvas H–Q ou NPSH.", {}, True),
        ProjectDef("eolica", "Aerogerador de 3 pás", "Torre cônica de 60 m, nacela, gerador, multiplicadora, cubo e 3 pás NACA com torção; rotor animado.",
                   "samples.turbina_eolica", "build_eolica", "turbina_eolica.step",
                   "Perfil/corda/torção ilustrativos (sem BEM); sem sistema de passo e guinada.", {}, True),
        ProjectDef("turbojato", "Turbojato axial (compressor 4 estágios, turbina 2)", "Carcaça, cone de ponta, 4 estágios de compressor com estatores, combustor anular, 2 estágios de turbina, spool e bocal.",
                   "samples.turbojato", "build_turbojato", "turbojato.step",
                   "Lâminas retas inclinadas, sem rolamentos/óleo/combustível; animação prescrita; sem cálculo termodinâmico.", {}, True),
        ProjectDef("guindaste", "Guindaste torre treliçado", "Mastro de 8 módulos, plataforma giratória, cabine, lança de 30 m, contralança com contrapesos, carrinho e gancho.",
                   "samples.guindaste_torre", "build_guindaste", "guindaste_torre.step",
                   "Perfis tubulares simplificados, sem nós parafusados, sem dimensionamento por norma; giro e carrinho prescritos.", {}, True),
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
