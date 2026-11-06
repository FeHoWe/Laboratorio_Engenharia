"""Rastreabilidade e classificação de resultados (honestidade técnica).

Todo resultado numérico do software carrega: classe, método, entradas, premissas,
limitações e versão do solver. Nenhuma classe "VALIDADO" é concedida sem
referência de validação informada.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
import json, time

CLASSES = {
    "ANALITICO": "Fórmula fechada / modelo simplificado; não é simulação 3D.",
    "SIMULACAO_NUMERICA": "Resultado de solver numérico executado de fato.",
    "VALIDADO": "Simulação comparada a referência (analítica/experimental) informada.",
    "NAO_EXECUTADO": "Solver ausente ou não rodou; nenhum número é apresentado.",
    "ANIMACAO_PRESCRITA": "Movimento imposto; não é dinâmica física.",
}

@dataclass
class TracedResult:
    nome: str
    classe: str
    metodo: str
    valores: dict = field(default_factory=dict)
    entradas: dict = field(default_factory=dict)
    premissas: list = field(default_factory=list)
    limitacoes: list = field(default_factory=list)
    solver: str = ""
    solver_versao: str = ""
    validacao_ref: str = ""
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self):
        if self.classe not in CLASSES:
            raise ValueError(f"classe inválida: {self.classe}")
        if self.classe == "VALIDADO" and not self.validacao_ref:
            raise ValueError("VALIDADO exige validacao_ref")
        if self.classe == "NAO_EXECUTADO" and self.valores:
            raise ValueError("NAO_EXECUTADO não pode conter valores")
        if self.classe == "SIMULACAO_NUMERICA" and not (self.solver and self.solver_versao):
            raise ValueError("SIMULACAO_NUMERICA exige solver e versão")

    def to_dict(self):
        d = asdict(self); d["classe_descricao"] = CLASSES[self.classe]; return d

    def to_json(self):
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
