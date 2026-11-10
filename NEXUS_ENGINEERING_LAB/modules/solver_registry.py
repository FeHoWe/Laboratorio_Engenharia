"""Detecção de solvers externos (OpenFOAM, CalculiX, Gmsh) — sem fabricar resultados."""
from __future__ import annotations
import glob, os, shutil, subprocess
from dataclasses import dataclass

@dataclass
class SolverStatus:
    nome: str
    instalado: bool
    caminho: str = ""
    versao: str = ""
    estado: str = "NÃO INSTALADO"
    instrucao: str = ""

_SOLVERS = {
    "CalculiX": (["ccx", "ccx_2.21", "ccx_2.20"], ["-v"], "Instale CalculiX (ccx) e adicione ao PATH."),
    "OpenFOAM": (["simpleFoam", "blockMesh"], ["-help"], "Instale OpenFOAM (WSL/Docker no Windows) e carregue o ambiente."),
    "Gmsh": (["gmsh"], ["--version"], "pip install gmsh  (ou instale o Gmsh)."),
}

def _version(exe, args):
    try:
        r = subprocess.run([exe, *args], capture_output=True, text=True, timeout=10)
        out = (r.stdout + r.stderr).strip().splitlines()
        return out[0][:80] if out else ""
    except Exception:
        return ""

def openfoam_bashrc() -> str | None:
    """Caminho do `etc/bashrc` do OpenFOAM (necessário para executar solvers instalados por pacote). None se não achar."""
    cands = []
    if os.environ.get("WM_PROJECT_DIR"):
        cands.append(os.path.join(os.environ["WM_PROJECT_DIR"], "etc", "bashrc"))
    cands += ["/usr/share/openfoam/etc/bashrc", *sorted(glob.glob("/opt/openfoam*/etc/bashrc"), reverse=True),
              *sorted(glob.glob("/usr/lib/openfoam/openfoam*/etc/bashrc"), reverse=True),
              *sorted(glob.glob(os.path.expanduser("~/OpenFOAM/OpenFOAM-v*/etc/bashrc")), reverse=True)]
    return next((c for c in cands if os.path.isfile(c)), None)


def openfoam_shell(cmd: str) -> list:
    """Lista argv que executa `cmd` (sh) com o ambiente OpenFOAM carregado, se houver bashrc."""
    rc = openfoam_bashrc()
    return ["bash", "-c", f"source '{rc}' >/dev/null 2>&1; {cmd}"] if rc else ["sh", "-c", cmd]


def detect(nome: str) -> SolverStatus:
    cands, vargs, hint = _SOLVERS[nome]
    for c in cands:
        p = shutil.which(c)
        if p:
            ver = _version(p, vargs)
            if nome == "OpenFOAM":
                try:
                    r = subprocess.run(openfoam_shell("echo $WM_PROJECT_VERSION"), capture_output=True, text=True, timeout=15)
                    ver = ("OpenFOAM " + r.stdout.strip()) if r.stdout.strip() else ver
                except Exception:
                    pass
            return SolverStatus(nome, True, p, ver, "PRONTO")
    if nome == "Gmsh":
        try:
            import gmsh  # type: ignore
            return SolverStatus(nome, True, "python:gmsh", getattr(gmsh, "__version__", ""), "PRONTO")
        except Exception:
            pass
    return SolverStatus(nome, False, instrucao=hint)

def detect_all() -> dict:
    return {n: detect(n) for n in _SOLVERS}

def require(nome: str):
    """Levanta erro explícito se solver ausente (nunca devolve número falso)."""
    s = detect(nome)
    if not s.instalado:
        raise RuntimeError(f"{nome}: NÃO INSTALADO. {s.instrucao}")
    return s
