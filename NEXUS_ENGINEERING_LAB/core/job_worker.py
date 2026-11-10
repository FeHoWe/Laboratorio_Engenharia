"""Processo-filho dos jobs Python: `python -m core.job_worker <módulo> <função> '<json dos argumentos>'`.

Imprime progresso opcional (linhas NEXUS_PROGRESS) e, no fim, uma linha NEXUS_RESULT_JSON:<json> com o retorno da função.
Qualquer exceção sai com código ≠ 0 e traceback no log (nada é silenciado).
"""
from __future__ import annotations

import importlib
import json
import sys

from core.jobs import RESULT_MARK


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("uso: core.job_worker <módulo> <função> <json>", file=sys.stderr)
        return 2
    mod, fn, raw = argv
    f = getattr(importlib.import_module(mod), fn)
    out = f(**json.loads(raw))
    print(RESULT_MARK + json.dumps(out, ensure_ascii=False, default=str), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
