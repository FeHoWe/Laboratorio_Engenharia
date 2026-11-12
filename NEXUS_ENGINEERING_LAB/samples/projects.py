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
            mod = importlib.import_module(self.module)
            (getattr(mod, "write_" + self.key, None) or mod.write)(self.step_path)
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
        ProjectDef("f1_2027", "Protótipo de F1 2027 (derivado do 2026)", "Modelo 2026 com as mudanças públicas de 2027: asa traseira 20 mm mais rasa e estai, piso/prancha 300 mm mais curtos, tanque maior; mesma animação de curva/frenagem.",
                   "samples.f1_2027", "build_f1_2027", "f1_2027.step",
                   "PROTÓTIPO ilustrativo: só as mudanças de regulamento encontradas em fontes públicas; massa mínima 2027 e tanque NÃO verificados; não é CAD de equipe.",
                   _f1_typical(), True),
        ProjectDef("f1_312t", "Ferrari 312T (1975) — F1 clássico", "Monocoque de alumínio, V12 boxer (flat-12), caixa transversal, asas e 4 rodas; rodas giram e as dianteiras esterçam.",
                   "samples.f1_classicos", "build_f1_312t", "f1_312t.step",
                   "Referência por dimensões públicas (entre-eixos 2518 mm, bitolas 1510/1530); formas simplificadas, internos e suspensão plausíveis, NÃO é CAD original da Ferrari.", {}, True),
        ProjectDef("f1_mp44", "McLaren MP4/4 (1988) — F1 clássico", "Monocoque, V6 turbo Honda, asas e 4 rodas; rodas giram e as dianteiras esterçam.",
                   "samples.f1_classicos", "build_f1_mp44", "f1_mp44.step",
                   "Entre-eixos 2875 mm e bitolas 1824/1670 de fontes públicas; largura/altura da cabine ESTIMADAS; NÃO é CAD original da McLaren.", {}, True),
        ProjectDef("f1_lotus72", "Lotus 72 (1970–75) — F1 clássico", "Cunha com radiadores laterais, V8 Cosworth DFV, asas e 4 rodas; rodas giram e as dianteiras esterçam.",
                   "samples.f1_classicos", "build_f1_lotus72", "f1_lotus72.step",
                   "Entre-eixos/bitolas ESTIMADOS a partir de fontes públicas (valores variam entre versões); formas simplificadas; NÃO é CAD original da Lotus.", {}, True),
        ProjectDef("cessna", "Cessna 172S Skyhawk (asa alta)", "Fuselagem, asa alta com montantes, flapes, ailerons, empenagem, trem e hélice bipá; hélice gira e superfícies oscilam.",
                   "samples.aeronaves", "build_cessna172", "cessna.step",
                   "Envergadura 11,0 m e área 16,2 m² de dados públicos; perfil e fuselagem simplificados; sem aerodinâmica/CFD nem carga estrutural.", {}, True),
        ProjectDef("spitfire", "Supermarine Spitfire (asa elíptica)", "Fuselagem, asa elíptica com flapes e ailerons, empenagem, trem e hélice de 3 pás.",
                   "samples.aeronaves", "build_spitfire", "spitfire.step",
                   "Dimensões públicas (9,12 m; 11,23 m; 22,5 m²); perfil, fuselagem e trem simplificados; sem aerodinâmica/CFD.", {}, True),
        ProjectDef("a320", "Airbus A320-200 (jato de linha)", "Fuselagem de corpo estreito, asa enflechada 25° com flapes e ailerons, empenagem, 2 nacelles (fan/núcleo/pilone) e trem triciclo.",
                   "samples.aeronaves", "build_a320", "a320.step",
                   "Dimensões públicas (37,6 m; 35,8 m; cauda 11,8 m); fan com 20 pás e núcleo simplificados; sem cabine/interior; sem CFD.", {}, True),
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
