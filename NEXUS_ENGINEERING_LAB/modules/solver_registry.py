"""Detecção de solvers externos (OpenFOAM, CalculiX, Gmsh) — sem fabricar resultados."""
from __future__ import annotations
import shutil, subprocess
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

def detect(nome: str) -> SolverStatus:
    cands, vargs, hint = _SOLVERS[nome]
    for c in cands:
        p = shutil.which(c)
        if p:
            return SolverStatus(nome, True, p, _version(p, vargs), "PRONTO")
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
