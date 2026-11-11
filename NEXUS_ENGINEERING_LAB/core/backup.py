"""Backups com carimbo de data antes de sobrescrever/alterar arquivos do usuário (projetos, Arsenal).

`backup_file` copia para `<pasta>/backups/<nome>.<AAAAmmdd-HHMMSS-micro>.bak` e mantém só os `keep` mais recentes. Nunca apaga o original.
"""
from __future__ import annotations

import hashlib
import shutil
import sqlite3
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


def _stamp() -> str:
    t = time.time()
    return time.strftime("%Y%m%d-%H%M%S", time.localtime(t)) + f"-{int((t % 1) * 1e6):06d}"


def _digest_sqlite(path: Path) -> str:
    """Impressão digital do CONTEÚDO lógico de um banco SQLite (dump), imune a mudanças só de layout/WAL."""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        h = hashlib.sha256()
        for line in con.iterdump():
            h.update(line.encode("utf-8"))
        return h.hexdigest()
    finally:
        con.close()


def backup_sqlite(path: str | Path, keep: int = 10, motivo: str = "", only_if_changed: bool = True) -> Optional[Path]:
    """Backup consistente de um banco SQLite pela API de backup do próprio SQLite (seguro com o banco aberto/em uso).

    Com `only_if_changed`, não cria cópia se o conteúdo é idêntico ao do backup mais recente (evita inundar a pasta a cada abertura).
    Mantém só os `keep` mais recentes. Nunca altera o original.
    """
    p = Path(path)
    if not p.is_file() or p.stat().st_size == 0:
        return None
    d = p.parent / "backups"
    d.mkdir(exist_ok=True)
    existentes = sorted(d.glob(p.name + ".*.bak"))
    if only_if_changed and existentes:
        try:
            if _digest_sqlite(p) == _digest_sqlite(existentes[-1]):
                return None
        except sqlite3.DatabaseError:
            pass                                          # backup anterior ilegível: cria um novo
    dst = d / f"{p.name}.{_stamp()}.bak"
    src = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    try:
        out = sqlite3.connect(dst)
        try:
            src.backup(out)
        finally:
            out.close()
    finally:
        src.close()
    for old in (sorted(d.glob(p.name + ".*.bak"))[:-keep] if keep > 0 else []):
        old.unlink()
    logs.get("backup").info("backup SQLite de %s → %s %s", p.name, dst.name, f"({motivo})" if motivo else "")
    return dst
