"""Motor físico — NÃO IMPLEMENTADO (previsto para V2.0). Sem simulação falsa."""
from __future__ import annotations


class PhysicsEngine:
    available = False
    planned_version = "V2.0"

    def run(self, *args, **kwargs):
        raise NotImplementedError("Motor físico ainda não existe (previsto para a V2.0).")
