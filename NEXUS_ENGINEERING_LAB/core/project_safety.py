"""Segurança de projetos (V4.0): salvamento automático, recuperação após encerramento inesperado, versões nomeadas e comparação.

* **Autosave**: `AutoSaver.gravar(project)` grava um ``.nexus`` de recuperação em ``<pasta>/<sessão>.nexus`` + ``<sessão>.json`` (nome, caminho
  original, pid, hora) SEM alterar o projeto aberto (caminho, `dirty`, histórico). Encerramento limpo → `limpar()` apaga os dois.
  Na próxima abertura, `pendentes()` lista as sessões cujo processo não existe mais (= encerramento inesperado) e `abrir_pendente()` as lê.
* **Versões**: `salvar_versao(path, nota)` copia o ``.nexus`` já salvo para ``<pasta>/versions/<nome>.<carimbo>__<nota>.nexus``;
  `listar_versoes`, `restaurar_versao` (guarda o estado atual como backup antes) e `comparar(a, b)` (acrescentados/removidos/renomeados/
  material/geometria/posição, lendo só o project.json e os CRC do ZIP — não precisa do OpenCascade).
* O formato ``.nexus`` NÃO muda: tudo aqui funciona com projetos existentes.
"""
from __future__ import annotations

import json
import os
import sys
import re
import shutil
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core import logs
from core.backup import backup_file
from core.project_manager import PROJECT_EXTENSION, Project, ProjectError, ProjectManager

_log = logs.get("project_safety")


def pasta_recuperacao() -> Path:
    p = Path(os.environ.get("NEXUS_RECOVERY_DIR") or (Path.home() / ".nexus_lab" / "recovery"))
    p.mkdir(parents=True, exist_ok=True)
    return p


_WINDOWS = sys.platform == "win32"
_STILL_ACTIVE = 259


def _pid_vivo_windows(pid: int, kernel32) -> bool:
    """Windows: NUNCA usar os.kill(pid, 0) — no Windows isso chama TerminateProcess e ENCERRARIA o processo. Consulta o código de saída."""
    import ctypes
    h = kernel32.OpenProcess(0x1000, False, pid)             # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return False
    try:
        codigo = ctypes.c_ulong(0)
        if not kernel32.GetExitCodeProcess(h, ctypes.byref(codigo)):
            return True                                       # não conseguiu consultar: assume vivo (nunca descarta uma sessão por engano)
        return codigo.value == _STILL_ACTIVE
    finally:
        kernel32.CloseHandle(h)


def _pid_vivo(pid: int) -> bool:
    if pid <= 0:
        return False
    if _WINDOWS:
        import ctypes
        return _pid_vivo_windows(pid, ctypes.windll.kernel32)   # type: ignore[attr-defined]
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


@dataclass
class Pendente:
    sessao: str
    nome: str
    caminho_original: str
    hora: str
    arquivo: Path


class AutoSaver:
    def __init__(self, manager: ProjectManager, pasta: Optional[Path] = None, sessao: Optional[str] = None) -> None:
        self.manager = manager
        self.pasta = Path(pasta) if pasta else pasta_recuperacao()
        self.pasta.mkdir(parents=True, exist_ok=True)
        self.sessao = sessao or f"s{os.getpid()}-{int(time.time())}"
        self.ultimo: Optional[float] = None

    @property
    def arquivo(self) -> Path:
        return self.pasta / f"{self.sessao}{PROJECT_EXTENSION}"

    @property
    def meta(self) -> Path:
        return self.pasta / f"{self.sessao}.json"

    def gravar(self, project: Project) -> Optional[Path]:
        """Grava o instantâneo de recuperação. Não toca em `project.path`, `dirty` nem no histórico. Devolve None se não havia nada a gravar."""
        if not project.components.leaves() and not project.dirty:
            return None
        antes = (project.path, project.dirty, len(project.history.entries))
        try:
            self.manager.save(project, self.arquivo, backup=False)
        finally:
            project.path, project.dirty = antes[0], antes[1]
            del project.history.entries[antes[2]:]
        self.meta.write_text(json.dumps({"sessao": self.sessao, "pid": os.getpid(), "nome": project.name,
                                         "caminho_original": str(antes[0] or ""), "hora": time.strftime("%Y-%m-%d %H:%M:%S")},
                                        ensure_ascii=False), encoding="utf-8")
        self.ultimo = time.time()
        return self.arquivo

    def limpar(self) -> None:
        for p in (self.arquivo, self.meta):
            try:
                p.unlink()
            except FileNotFoundError:
                pass


def pendentes(pasta: Optional[Path] = None) -> list[Pendente]:
    """Sessões de recuperação cujo processo já não existe (encerramento inesperado)."""
    d = Path(pasta) if pasta else pasta_recuperacao()
    out = []
    for m in sorted(d.glob("*.json")):
        try:
            info = json.loads(m.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        arq = d / f"{info.get('sessao', m.stem)}{PROJECT_EXTENSION}"
        if not arq.is_file() or _pid_vivo(int(info.get("pid", 0))):
            continue
        out.append(Pendente(info.get("sessao", m.stem), info.get("nome", ""), info.get("caminho_original", ""), info.get("hora", ""), arq))
    return out


def abrir_pendente(manager: ProjectManager, p: Pendente) -> Project:
    proj = manager.open(p.arquivo)
    proj.path = Path(p.caminho_original) if p.caminho_original else None     # "Salvar" volta ao arquivo de origem (ou pede um nome)
    proj.dirty = True
    return proj


def descartar_pendente(p: Pendente) -> None:
    for x in (p.arquivo, p.arquivo.with_suffix(".json")):
        try:
            x.unlink()
        except FileNotFoundError:
            pass


# ------------------------------------------------------------------------------------------------------------- versões
_NOTA = re.compile(r"[^0-9A-Za-zÀ-ÿ _.-]+")


def _dir_versoes(path: Path) -> Path:
    return path.parent / "versions"


def salvar_versao(path: str | Path, nota: str = "") -> Path:
    p = Path(path)
    if not p.is_file():
        raise ProjectError("Salve o projeto antes de registrar uma versão.")
    d = _dir_versoes(p); d.mkdir(exist_ok=True)
    t = time.time()
    carimbo = time.strftime("%Y%m%d-%H%M%S", time.localtime(t)) + f"-{int((t % 1) * 1e3):03d}"
    nota_limpa = "_".join(_NOTA.sub("", nota).split())[:40]
    dst = d / f"{p.stem}.{carimbo}__{nota_limpa}{PROJECT_EXTENSION}"
    shutil.copy2(p, dst)
    _log.info("versão registrada: %s", dst.name)
    return dst


def listar_versoes(path: str | Path) -> list[dict]:
    p = Path(path)
    out = []
    for f in sorted(_dir_versoes(p).glob(f"{p.stem}.*__*{PROJECT_EXTENSION}")):
        m = re.match(re.escape(p.stem) + r"\.(\d{8}-\d{6}-\d{3})__(.*)\.nexus$", f.name)
        if m:
            out.append({"arquivo": f, "carimbo": m.group(1), "nota": m.group(2).replace("_", " "), "bytes": f.stat().st_size})
    return out


def restaurar_versao(path: str | Path, versao: str | Path) -> Path:
    """Devolve a versão ao caminho do projeto; o estado atual vira backup (`backups/`) antes."""
    p, v = Path(path), Path(versao)
    if not v.is_file():
        raise ProjectError("Versão não encontrada.")
    backup_file(p, motivo="antes de restaurar versão")
    shutil.copy2(v, p)
    return p


def _indice(path: Path) -> tuple[dict, dict]:
    try:
        with zipfile.ZipFile(path) as zf:
            doc = json.loads(zf.read("project.json").decode("utf-8"))
            crc = {i.filename: i.CRC for i in zf.infolist()}
    except (zipfile.BadZipFile, KeyError, ValueError, OSError) as e:
        raise ProjectError(f"Projeto ilegível ({Path(path).name}): {e}") from e
    nos: dict = {}

    def walk(e: dict, pai: str) -> None:
        g = (e.get("geometry") or {}).get("file")
        nos[e["id"]] = {"nome": e["name"], "material": e.get("material"), "pai": pai, "geom": crc.get(g) if g else None,
                        "pos": [round(float(x), 9) for x in e.get("placement", [])], "visivel": e.get("visible", True)}
        for c in e.get("children", []):
            walk(c, e["id"])

    walk(doc["root"], "")
    return doc, nos


def comparar(a: str | Path, b: str | Path) -> dict:
    """Diferenças de `a` (antes) para `b` (depois). Só estrutura/material/geometria (CRC)/posição — sem interpretar a geometria."""
    da, na = _indice(Path(a)); db, nb = _indice(Path(b))
    r = {"acrescentados": [nb[i]["nome"] for i in nb if i not in na], "removidos": [na[i]["nome"] for i in na if i not in nb],
         "renomeados": [], "material": [], "geometria": [], "posicao": [], "movidos_de_pai": []}
    for i in na.keys() & nb.keys():
        x, y = na[i], nb[i]
        if x["nome"] != y["nome"]:
            r["renomeados"].append((x["nome"], y["nome"]))
        if x["material"] != y["material"]:
            r["material"].append((y["nome"], x["material"], y["material"]))
        if x["geom"] != y["geom"]:
            r["geometria"].append(y["nome"])
        if x["pos"] != y["pos"]:
            r["posicao"].append(y["nome"])
        if x["pai"] != y["pai"]:
            r["movidos_de_pai"].append(y["nome"])
    r["iguais"] = not any(r[k] for k in ("acrescentados", "removidos", "renomeados", "material", "geometria", "posicao", "movidos_de_pai"))
    return r
