"""Log central do NEXUS (arquivo rotativo) — um só lugar para erros de jobs, solvers e migrações.

Destino padrão: ~/.nexus_engineering_lab/logs/nexus.log (1 MB × 5 arquivos). `setup()` é idempotente.
"""
from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

DEFAULT_DIR = Path.home() / ".nexus_engineering_lab" / "logs"
_FMT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def setup(folder: str | Path | None = None, level: int = logging.INFO) -> Path:
    d = Path(folder) if folder else DEFAULT_DIR
    d.mkdir(parents=True, exist_ok=True)
    path = d / "nexus.log"
    root = logging.getLogger("nexus")
    root.setLevel(level)
    for h in list(root.handlers):
        if getattr(h, "_nexus_file", False):
            root.removeHandler(h)
            h.close()
    h = logging.handlers.RotatingFileHandler(path, maxBytes=1_000_000, backupCount=5, encoding="utf-8")
    h.setFormatter(logging.Formatter(_FMT))
    h._nexus_file = True                                    # type: ignore[attr-defined]
    root.addHandler(h)
    root.propagate = False
    return path


def get(nome: str) -> logging.Logger:
    return logging.getLogger("nexus." + nome)


def tail(path: str | Path | None = None, n: int = 50) -> str:
    p = Path(path) if path else DEFAULT_DIR / "nexus.log"
    return "\n".join(p.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]) if p.exists() else ""
