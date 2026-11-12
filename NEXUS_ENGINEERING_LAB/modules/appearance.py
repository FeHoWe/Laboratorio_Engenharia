"""Aparência VISUAL das peças (cor, metal, rugosidade, opacidade) a partir do NOME da peça e do projeto.

IMPORTANTE: é só estética para o visualizador realista. NÃO é o material de engenharia: não alimenta massa, BOM nem cálculo algum
(o NEXUS nunca atribui material automaticamente). O aspecto segue o que a peça costuma ser na realidade (pneu = borracha preta, vidro = translúcido…).
"""
from __future__ import annotations

import unicodedata

# (cor_hex, metal, rugosidade, opacidade)
_STEEL = ("#9aa3ad", 0.92, 0.32, 1.0)
_STEEL_DARK = ("#4a5058", 0.9, 0.38, 1.0)
_ALU = ("#c9d0d8", 0.95, 0.26, 1.0)
_CAST = ("#5d6168", 0.75, 0.55, 1.0)
_RUBBER = ("#17181a", 0.0, 0.92, 1.0)
_CARBON = ("#15181d", 0.55, 0.28, 1.0)
_GLASS = ("#7fb7d6", 0.1, 0.05, 0.38)
_BRASS = ("#c8a14a", 0.95, 0.3, 1.0)
_COPPER = ("#b86b45", 0.95, 0.3, 1.0)
_WHITE = ("#e9edf1", 0.15, 0.35, 1.0)
_SPRING = ("#c23b2b", 0.6, 0.4, 1.0)
_ZINC = ("#b9c0c8", 0.85, 0.4, 1.0)
_BLACK_PLASTIC = ("#202226", 0.05, 0.6, 1.0)

# palette por projeto: cor da pintura da carroceria / superfícies externas e acento
PAINT = {
    "f1": ("#0c7a9b", "#e8eef2"), "f1_2027": ("#0c7a9b", "#e8eef2"),
    "f1_312t": ("#c1121f", "#f1f1ee"), "f1_mp44": ("#cf2a22", "#f3f3f0"), "f1_lotus72": ("#14110f", "#c9a24a"),
    "cessna": ("#eef1f4", "#1d4f9d"), "spitfire": ("#55633a", "#8f9aa3"), "a320": ("#f1f3f6", "#20418a"),
}

_RULES = [  # (palavras-chave no nome sem acento, aparência | "paint" | "accent"); primeira que casar vence
    (("pneu", "tire"), _RUBBER), (("correia", "tensora"), ("#1b1c1e", 0.0, 0.85, 1.0)), (("cabo", "cabos"), ("#2a2d31", 0.5, 0.5, 1.0)),
    (("vidro", "parabrisa", "canopy", "visor", "capota transparente"), _GLASS),
    (("disco de freio", "disco", "tambor"), _STEEL_DARK), (("pinca", "sapata"), ("#c2332b", 0.5, 0.45, 1.0)),
    (("roda", "aro ", "rim"), _ALU), (("cubo", "manga de eixo", "rolamento", "mancal", "mancais"), _STEEL),
    (("mola", "helicoidal"), _SPRING), (("amortecedor",), ("#e0a31f", 0.7, 0.35, 1.0)),
    (("virabrequim", "biela", "eixo", "comando", "haste", "balancim", "pino", "munhao", "moente", "excentrico", "cremalheira", "pinhao", "coroa"), _STEEL),
    (("pistao", "cabecote", "carter", "carcaca", "tampa", "plenum", "caixa de cambio", "diferencial", "retrovisor"), _ALU),
    (("bloco", "bancada", "cilindros", "estator", "rotor", "epitrocoide", "camara", "fundacao"), _CAST),
    (("escape", "coletor", "ponteira", "turbina", "turbocompressor", "compressor", "voluta", "exaustao", "descarga"), ("#b8a58a", 0.9, 0.4, 1.0)),
    (("fan", "pa da helice", "helice", "pas"), ("#2a2d33", 0.7, 0.35, 1.0)), (("spinner", "carenagem da helice"), ("#d7dde3", 0.9, 0.2, 1.0)),
    (("radiador", "veneziana", "filtro"), ("#6b727a", 0.6, 0.5, 1.0)),
    (("parafuso", "porca", "arruela", "sextavado", "bucha", "flange", "luva"), _ZINC), (("engrenagem", "dente", "dentes", "polia", "garra", "gancho"), _STEEL),
    (("junta", "vedacao"), ("#3a2f2a", 0.0, 0.9, 1.0)), (("bateria", "mgu", "gerador"), ("#2d3f55", 0.4, 0.5, 1.0)),
    (("banco", "assento", "capacete", "piloto", "torso", "cabeca"), ("#2b2f36", 0.1, 0.8, 1.0)), (("halo", "arco", "santo antonio", "capotamento"), ("#2a2c30", 0.85, 0.35, 1.0)),
    (("prancha de desgaste", "plank"), ("#9c7b4e", 0.0, 0.85, 1.0)),
    (("tanque", "oleo", "combustivel"), ("#4b4f56", 0.4, 0.6, 1.0)),
    (("leme", "aileron", "flape", "flap", "profundor", "elemento"), "accent"),
    (("asa", "wing", "bargeboard", "cerca", "defletor", "cascata", "aleta", "difusor", "sidepod", "airbox", "aba", "beam", "piso", "assoalho", "assoalho plano",
      "nariz", "monocoque", "chassi", "cockpit", "cobertura", "capo", "dorsal", "shark", "fuselagem", "deriva", "estabilizador", "nacele", "nacela", "pilone",
      "carenagem", "cabine", "celula", "painel de instrumentos"), "paint"),
    (("mastro", "lanca", "torre", "plataforma", "contraventamento", "diagonal", "banzo", "travessa", "montante", "tirante", "viga", "cantoneira", "perfil", "pilar"),
     ("#d9a21b", 0.45, 0.5, 1.0)),
    (("tabuleiro", "pontao", "chapa", "placa", "base"), ("#7d838b", 0.5, 0.6, 1.0)),
]


def _norm(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


def appearance(project_key: str, part_name: str) -> tuple:
    """(cor_hex, metal, rugosidade, opacidade) — só visual."""
    n = " " + _norm(part_name) + " "
    paint, accent = PAINT.get(project_key, ("#8fa1b3", "#d9e1e8"))
    for keys, ap in _RULES:
        if any(" " + k.strip() + " " in n or k in n for k in keys):
            if ap == "paint":
                body = project_key in PAINT
                return (paint, 0.35 if body else 0.55, 0.28 if body else 0.4, 1.0) if body else (paint, 0.55, 0.4, 1.0)
            if ap == "accent":
                return (accent, 0.3, 0.35, 1.0)
            return ap
    return _STEEL
