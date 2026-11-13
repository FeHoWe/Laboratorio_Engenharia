"""V5.1 — portabilidade (Windows) verificada por SIMULAÇÃO nos limites do Linux: o que dá para testar sem uma máquina Windows."""
import ctypes
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from core import project_safety as ps

ROOT = Path(__file__).resolve().parent.parent


class _K32:
    """kernel32 falso: registra chamadas e devolve o código de saída configurado."""
    def __init__(self, abre=True, codigo=259, consulta_ok=True):
        self.abre, self.codigo, self.consulta_ok, self.fechou, self.terminou = abre, codigo, consulta_ok, False, False

    def OpenProcess(self, acesso, herda, pid):
        self.acesso = acesso
        return 1234 if self.abre else 0

    def GetExitCodeProcess(self, h, ptr):
        ctypes.cast(ptr, ctypes.POINTER(ctypes.c_ulong)).contents.value = self.codigo
        return 1 if self.consulta_ok else 0

    def CloseHandle(self, h):
        self.fechou = True

    def TerminateProcess(self, *a):
        self.terminou = True


def test_pid_vivo_windows_nao_encerra_o_processo_e_le_o_codigo_de_saida():
    k = _K32(codigo=259)
    assert ps._pid_vivo_windows(999, k) is True and k.fechou and not k.terminou
    assert k.acesso == 0x1000                                     # acesso mínimo de consulta, sem direito de encerrar
    assert ps._pid_vivo_windows(999, _K32(codigo=0)) is False     # processo terminou
    assert ps._pid_vivo_windows(999, _K32(abre=False)) is False   # pid inexistente
    assert ps._pid_vivo_windows(999, _K32(consulta_ok=False)) is True   # dúvida → considera vivo (não descarta sessão)


def test_pid_vivo_no_windows_nunca_chama_os_kill(monkeypatch):
    chamadas = []
    monkeypatch.setattr(os, "kill", lambda *a: chamadas.append(a))
    monkeypatch.setattr(ps, "_WINDOWS", True)
    monkeypatch.setattr(ctypes, "windll", type("W", (), {"kernel32": _K32(codigo=259)})(), raising=False)
    assert ps._pid_vivo(4321) is True
    assert chamadas == []


def test_pid_vivo_posix_continua_correto():
    assert ps._pid_vivo(os.getpid()) is True
    assert ps._pid_vivo(0) is False and ps._pid_vivo(-5) is False
    assert ps._pid_vivo(2 ** 22 + 77) is False


def test_job_worker_so_emite_ascii_mesmo_com_unicode_e_console_ascii(tmp_path):
    """No Windows o stdout do filho é cp1252: o resultado (μ, ⚠, CJK) tem de sair escapado em JSON."""
    mod = tmp_path / "modunicode.py"
    mod.write_text("def f():\n    return {'t': 'μ ⚠ 日本語 → Δ', 'n': 1}\n", encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": f"{tmp_path}{os.pathsep}{ROOT}", "PYTHONIOENCODING": "ascii", "PYTHONUTF8": "0"}
    r = subprocess.run([sys.executable, "-m", "core.job_worker", "modunicode", "f", "{}"], cwd=ROOT, env=env, capture_output=True)
    assert r.returncode == 0, r.stderr.decode(errors="replace")[-400:]
    from core.job_worker import RESULT_MARK
    linha = [ln for ln in r.stdout.decode("ascii").splitlines() if ln.startswith(RESULT_MARK)][0]
    assert json.loads(linha[len(RESULT_MARK):])["t"] == "μ ⚠ 日本語 → Δ"


def test_job_isolado_devolve_unicode_pelo_gerenciador(tmp_path):
    from core.jobs import JobManager
    mod = tmp_path / "modunicode2.py"
    mod.write_text("def f():\n    print('log com μ e 日本')\n    return {'t': 'Δ⚠'}\n", encoding="utf-8")
    jm = JobManager(1)
    j = jm.submit_python("unicode", "modunicode2", "f", {}, timeout=60, env={"PYTHONPATH": f"{tmp_path}{os.pathsep}{ROOT}"})
    j.wait(60)
    assert j.state == "DONE" and j.result()["t"] == "Δ⚠" and "μ" in j.log


def test_codigo_nao_usa_leitura_escrita_de_texto_sem_codificacao():
    """Trava de regressão: no Windows o padrão é cp1252 e corrompe/rejeita acentos, μ e CJK."""
    import ast
    ruins = []
    for d in ("core", "interface", "modules", "main", "nexus_f1"):
        for p in (ROOT / d).rglob("*.py"):
            for n in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in ("read_text", "write_text") and \
                        "encoding" not in {k.arg for k in n.keywords}:
                    ruins.append(f"{p.relative_to(ROOT)}:{n.lineno}")
    assert not ruins, ruins
