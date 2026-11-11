"""Caminho Windows/WSL2 e GPU: lógica testada com Windows SIMULADO (monkeypatch). NÃO substitui teste em Windows 11 real."""
from modules import solver_registry as sr


def test_openfoam_shell_uses_wsl_on_windows(monkeypatch):
    monkeypatch.setattr(sr, "_windows", lambda: True)
    monkeypatch.setattr(sr.shutil, "which", lambda x: "C:\\Windows\\System32\\wsl.exe" if x.startswith("wsl") else None)
    sr._WSL_RC_CACHE.clear()
    monkeypatch.setattr(sr, "_wsl_run", lambda cmd, timeout=30: "/opt/openfoam2306/etc/bashrc")
    argv = sr.openfoam_shell("blockMesh")
    assert argv[:3] == ["wsl.exe", "bash", "-lc"] and "source '/opt/openfoam2306/etc/bashrc'" in argv[3] and argv[3].endswith("blockMesh")
    sr._WSL_RC_CACHE.clear()


def test_windows_without_wsl_openfoam_falls_back(monkeypatch):
    monkeypatch.setattr(sr, "_windows", lambda: True)
    monkeypatch.setattr(sr.shutil, "which", lambda x: None)
    sr._WSL_RC_CACHE.clear()
    assert sr.wsl_openfoam_bashrc() is None
    assert sr.openfoam_shell("x")[0] in ("sh", "bash")
    sr._WSL_RC_CACHE.clear()


def test_detect_openfoam_via_wsl(monkeypatch):
    monkeypatch.setattr(sr, "_windows", lambda: True)
    monkeypatch.setattr(sr.shutil, "which", lambda x: "wsl.exe" if x.startswith("wsl") else None)
    sr._WSL_RC_CACHE.clear()
    monkeypatch.setattr(sr, "_wsl_run", lambda cmd, timeout=30: "/opt/openfoam2306/etc/bashrc" if "echo" not in cmd else "v2306")
    st = sr.detect("OpenFOAM")
    assert st.instalado and "WSL2" in st.versao and "v2306" in st.versao
    sr._WSL_RC_CACHE.clear()


def test_gpu_check_reports_software_rendering_honestly():
    from core import doctor
    c = doctor._check_gpu()
    assert c.nome == "GPU / OpenGL"
    if not c.ok:
        assert c.instalacao and ("SOFTWARE" in c.detalhe or "contexto" in c.detalhe or c.detalhe)
    else:
        assert "renderizador" in c.detalhe
