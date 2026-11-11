"""Camada GENERATIVA OPCIONAL do NEXUS INTELLIGENCE (linguagem natural livre).

Princípios (para não quebrar a regra "nunca inventar número"):
1. Só funciona se o usuário tiver ANTHROPIC_API_KEY (ou passar um cliente) e CONFIRMAR o envio; os dados do parecer saem do computador.
2. O modelo recebe APENAS os fatos do parecer por regras (texto + campos). Instruções: não introduzir números, citar o campo, dizer "não sei".
3. A resposta é VERIFICADA: todo número nela precisa existir nos fatos ou na pergunta (inteiros ≤ 10 são tolerados). Se não, volta marcada
   `aprovada=False` com a lista dos números sem fundamento — a interface mostra o aviso e não apresenta como resultado do NEXUS.
Sem chave/biblioteca: devolve `disponivel=False` (o assistente por regras continua funcionando).
"""
from __future__ import annotations

import os
import re

MODELO_PADRAO = "claude-sonnet-5-5"
_NUM = re.compile(r"(?<![\w.])[-+]?\d+(?:[.,]\d+)?(?:[eE][-+]?\d+)?")

SISTEMA = (
    "Você é o assistente técnico do NEXUS Engineering Lab. Responda em português, de forma curta e técnica, USANDO SOMENTE os FATOS fornecidos. "
    "Regras: (1) NÃO introduza nenhum número que não esteja nos FATOS ou na pergunta; não faça contas novas com valores inventados. "
    "(2) Cite de qual campo vem cada afirmação. (3) Se os fatos não bastam, diga 'não há dado suficiente' e diga o que faltaria. "
    "(4) Não afirme que algo está validado/aprovado além do que a classe do resultado diz. (5) Você apoia a decisão, não a substitui."
)


def _norm(s: str) -> float | None:
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return None


def numeros(texto: str) -> list[float]:
    return [x for x in (_norm(m.group(0)) for m in _NUM.finditer(texto)) if x is not None]


def verificar_numeros(resposta: str, fatos: str, pergunta: str = "") -> list[str]:
    """Números da resposta sem lastro nos fatos/pergunta (comparação com tolerância de arredondamento 0,6 %)."""
    base = numeros(fatos) + numeros(pergunta)
    ruins = []
    for m in _NUM.finditer(resposta):
        v = _norm(m.group(0))
        if v is None:
            continue
        if float(v).is_integer() and abs(v) <= 10:
            continue
        if not any(abs(v - b) <= 0.006 * max(abs(b), 1e-12) or abs(v - b) < 1e-9 for b in base):
            ruins.append(m.group(0))
    return ruins


def _cliente():
    chave = os.environ.get("ANTHROPIC_API_KEY")
    if not chave:
        return None, "ANTHROPIC_API_KEY não definida"
    try:
        import anthropic
    except ImportError:
        return None, "biblioteca 'anthropic' não instalada (pip install anthropic)"
    return anthropic.Anthropic(api_key=chave), ""


def perguntar(pergunta: str, parecer, cliente=None, modelo: str = MODELO_PADRAO, max_tokens: int = 700) -> dict:
    fatos = parecer.texto() if hasattr(parecer, "texto") else str(parecer)
    if cliente is None:
        cliente, motivo = _cliente()
        if cliente is None:
            return {"disponivel": False, "motivo": motivo, "aprovada": False, "resposta": ""}
    msg = cliente.messages.create(model=modelo, max_tokens=max_tokens, system=SISTEMA,
                                  messages=[{"role": "user", "content": f"FATOS (parecer por regras do NEXUS):\n{fatos}\n\nPERGUNTA: {pergunta}"}])
    texto = "".join(getattr(b, "text", "") for b in getattr(msg, "content", []))
    ruins = verificar_numeros(texto, fatos, pergunta)
    return {"disponivel": True, "resposta": texto, "aprovada": not ruins, "numeros_sem_fundamento": ruins, "modelo": modelo,
            "aviso": "" if not ruins else "ATENÇÃO: a resposta contém números que NÃO estão nos resultados do NEXUS — não use como dado de engenharia."}
