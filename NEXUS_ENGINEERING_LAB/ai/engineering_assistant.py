"""Engineering Assistant — módulo independente, NÃO IMPLEMENTADO (V4.0).

Interface prevista: receber uma pergunta e o contexto do projeto e devolver uma resposta
de um modelo de linguagem REAL. Enquanto não houver provedor configurado, o módulo
informa indisponibilidade; nunca devolve respostas prontas fingindo ser IA.
"""
from __future__ import annotations


class AssistantUnavailable(RuntimeError):
    pass


class EngineeringAssistant:
    planned_version = "V4.0"

    def is_available(self) -> bool:
        return False

    def ask(self, question: str, project_context: dict | None = None) -> str:
        raise AssistantUnavailable("O Engineering Assistant ainda não foi implementado (V4.0).")
