"""Diagnóstico de ambiente do NEXUS (Master Prompt §12).

Verifica Python, bibliotecas, OpenCASCADE, Gmsh, CalculiX, OpenFOAM, WSL2 e ParaView. Para cada item ausente informa claramente
e traz a instrução de instalação; `verify(nome)` refaz a checagem depois da instalação. NUNCA instala nada nem executa comandos
administrativos: só consulta. Um motor só aparece como PRONTO se foi realmente encontrado/importado.
"""
from __future__ import annotations

import importlib
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass


@dataclass
class Check:
    nome: str
    categoria: str          # python | biblioteca | motor
    ok: bool
    versao: str = ""
    detalhe: str = ""
    instalacao: str = ""
    obrigatorio: bool = False

    @property
    def estado(self) -> str:
        return "PRONTO" if self.ok else ("AUSENTE (obrigatório)" if self.obrigatorio else "NÃO INSTALADO")


def _run(cmd: list, timeout: float = 10) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        out = (r.stdout + r.stderr).strip().splitlines()
        return out[0][:100] if out else ""
    except Exception:
        return ""


def _lib(modname: str, pip: str, obrigatorio: bool, nota: str = "") -> Check:
    try:
        m = importlib.import_module(modname)
        return Check(modname, "biblioteca", True, str(getattr(m, "__version__", "")), nota, "", obrigatorio)
    except Exception as e:                                               # ImportError e OSError (libs nativas, ex.: libGLU)
        return Check(modname, "biblioteca", False, "", f"{type(e).__name__}: {str(e)[:120]}", f"pip install {pip}", obrigatorio)


def _is_wsl() -> bool:
    try:
        return "microsoft" in platform.release().lower() or "microsoft" in open("/proc/version").read().lower()
    except Exception:
        return False


def _check_wsl() -> Check:
    instr = "Windows 11 (PowerShell como administrador, por sua conta): wsl --install  — depois reinicie e instale uma distribuição (ex.: Ubuntu)."
    if os.name == "nt":
        exe = shutil.which("wsl")
        if exe:
            out = _run([exe, "--status"])
            return Check("WSL2", "motor", True, out, exe, "", False)
        return Check("WSL2", "motor", False, "", "wsl.exe não encontrado", instr)
    if _is_wsl():
        return Check("WSL2", "motor", True, platform.release(), "o NEXUS está rodando dentro do WSL", "", False)
    return Check("WSL2", "motor", False, "", "não é Windows (WSL só se aplica ao Windows 11)", instr)


def _check_exe(nome: str, cands: list[str], vargs: list, instr: str) -> Check:
    for c in cands:
        p = shutil.which(c)
        if p:
            return Check(nome, "motor", True, _run([p, *vargs]), p)
    if nome == "OpenFOAM" and os.name == "nt" and shutil.which("wsl"):
        out = _run(["wsl", "bash", "-lc", "which simpleFoam"])
        if out.startswith("/"):
            return Check(nome, "motor", True, "via WSL2", out)
    return Check(nome, "motor", False, "", "executável não encontrado no PATH", instr)


def _check_gmsh() -> Check:
    c = _lib("gmsh", "gmsh", False)
    if c.ok:
        c.categoria = "motor"
        c.nome = "Gmsh"
        return c
    exe = shutil.which("gmsh")
    if exe:
        return Check("Gmsh", "motor", True, _run([exe, "--version"]), f"executável {exe} (módulo Python indisponível: {c.detalhe})")
    c.categoria, c.nome = "motor", "Gmsh"
    c.instalacao = "pip install gmsh   (no Linux também: libGLU — ex. apt install libglu1-mesa)"
    return c


def _check_occ() -> Check:
    try:
        import OCP  # noqa: F401
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
        BRepPrimAPI_MakeBox(1, 1, 1).Shape()                              # prova funcional, não só import
        return Check("OpenCASCADE (OCP)", "motor", True, str(getattr(OCP, "__version__", "")), "teste de criação de sólido OK", "", True)
    except Exception as e:
        return Check("OpenCASCADE (OCP)", "motor", False, "", f"{type(e).__name__}: {str(e)[:120]}", "pip install cadquery-ocp", True)


def _check_gpu() -> Check:
    """Cria uma janela VTK fora da tela e lê o renderizador OpenGL: GPU real × renderização por software (lenta)."""
    try:
        from vtkmodules.vtkRenderingCore import vtkRenderWindow
        import vtkmodules.vtkRenderingOpenGL2  # noqa: F401
        rw = vtkRenderWindow()
        rw.SetOffScreenRendering(1)
        rw.Render()
        info = rw.ReportCapabilities()
        def pick(k):
            for ln in info.splitlines():
                if ln.strip().lower().startswith(k):
                    return ln.split(":", 1)[1].strip()
            return ""
        rend, ver = pick("opengl renderer"), pick("opengl version")
        if not rend:
            return Check("GPU / OpenGL", "motor", False, "", "não foi possível ler o renderizador OpenGL (sem contexto gráfico)",
                         "Atualize o driver da placa de vídeo; em servidor sem tela use QT_QPA_PLATFORM=offscreen")
        soft = any(w in rend.lower() for w in ("llvmpipe", "softpipe", "swrast", "generic", "software", "gdi"))
        if soft:
            return Check("GPU / OpenGL", "motor", False, ver, f"renderização POR SOFTWARE ({rend}) — funciona, porém lenta em montagens grandes",
                         "Instale/atualize o driver da GPU (NVIDIA/AMD/Intel); no WSL2 use WSLg com driver compatível")
        return Check("GPU / OpenGL", "motor", True, ver, f"renderizador: {rend}")
    except Exception as e:
        return Check("GPU / OpenGL", "motor", False, "", f"{type(e).__name__}: {str(e)[:120]}", "Verifique a instalação do VTK e o driver gráfico")


def run_all() -> list[Check]:
    py_ok = sys.version_info >= (3, 10)
    out = [Check("Python", "python", py_ok, platform.python_version(), sys.executable, "" if py_ok else "Instale Python ≥ 3.10", True)]
    out += [_lib("numpy", "numpy", True), _lib("scipy", "scipy", True), _lib("PySide6", "PySide6", True), _lib("vtk", "vtk", True),
            _lib("trimesh", "trimesh", False), _lib("reportlab", "reportlab", False), _lib("openpyxl", "openpyxl", False),
            _lib("meshio", "meshio", False), _lib("pyvista", "pyvista", False), _lib("cadquery", "cadquery", False)]
    out += [_check_occ(), _check_gmsh(),
            _check_exe("CalculiX", ["ccx", "ccx_2.21", "ccx_2.20"], ["-v"], "Instale CalculiX (ccx) e adicione ao PATH (Windows: binários do projeto CalculiX; Linux: apt install calculix-ccx)."),
            _check_exe("OpenFOAM", ["simpleFoam", "blockMesh"], ["-help"], "Instale OpenFOAM dentro do WSL2 (Windows 11) ou Docker; carregue o ambiente (source etc/bashrc)."),
            _check_wsl(), _check_gpu(),
            _check_exe("ParaView", ["pvpython", "paraview"], ["--version"], "Instale ParaView (paraview.org) e adicione ao PATH.")]
    return out


def verify(nome: str) -> Check:
    """Refaz a checagem de UM item (use depois de instalar)."""
    for c in run_all():
        if c.nome.lower() == nome.lower():
            return c
    raise KeyError(f"item desconhecido: {nome}")


def report_text(checks: list[Check] | None = None) -> str:
    checks = checks or run_all()
    lines = ["DIAGNÓSTICO DO AMBIENTE NEXUS (somente leitura — nada é instalado automaticamente)", ""]
    for cat, titulo in (("python", "Runtime"), ("biblioteca", "Bibliotecas Python"), ("motor", "Motores de engenharia")):
        lines.append(titulo)
        for c in (x for x in checks if x.categoria == cat):
            ver = f" [{c.versao}]" if c.versao else ""
            lines.append(f"  {'✔' if c.ok else '✘'} {c.nome}: {c.estado}{ver}" + (f" — {c.detalhe}" if c.detalhe else ""))
            if not c.ok and c.instalacao:
                lines.append(f"      como instalar: {c.instalacao}")
        lines.append("")
    faltam = [c.nome for c in checks if not c.ok and c.obrigatorio]
    lines.append("Obrigatórios ausentes: " + (", ".join(faltam) if faltam else "nenhum"))
    lines.append("Funcionalidades que dependem de motor ausente ficam como NÃO EXECUTADO; nenhum resultado é fabricado.")
    return "\n".join(lines)


if __name__ == "__main__":
    print(report_text())
