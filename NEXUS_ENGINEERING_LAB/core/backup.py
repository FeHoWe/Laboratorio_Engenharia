"""Backups com carimbo de data antes de sobrescrever/alterar arquivos do usuário (projetos, Arsenal).

`backup_file` copia para `<pasta>/backups/<nome>.<AAAAmmdd-HHMMSS-micro>.bak` e mantém só os `keep` mais recentes. Nunca apaga o original.
"""
from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Optional

from core import logs


def backup_file(path: str | Path, keep: int = 10, motivo: str = "") -> Optional[Path]:
    p = Path(path)
    if not p.is_file():
        return None
    d = p.parent / "backups"
    d.mkdir(exist_ok=True)
    t = time.time()
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(t)) + f"-{int((t % 1) * 1e6):06d}"
    dst = d / f"{p.name}.{stamp}.bak"
    shutil.copy2(p, dst)
    antigos = sorted(d.glob(p.name + ".*.bak"))
    for old in antigos[:-keep] if keep > 0 else []:
        old.unlink()
    logs.get("backup").info("backup de %s → %s %s", p.name, dst.name, f"({motivo})" if motivo else "")
    return dst


def restore_latest(path: str | Path) -> Optional[Path]:
    """Restaura o backup mais recente por cima de `path` (antes guarda o estado atual como backup)."""
    p = Path(path)
    bks = sorted((p.parent / "backups").glob(p.name + ".*.bak"))
    if not bks:
        return None
    backup_file(p, motivo="antes de restaurar")
    shutil.copy2(bks[-1], p)
    return bks[-1]
