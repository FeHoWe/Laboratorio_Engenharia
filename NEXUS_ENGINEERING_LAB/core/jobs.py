"""NEXUS CORE — fila de execução de processos externos/isolados (FEA, CFD, qualquer cálculo longo).

Princípios (Master Prompt §3): cada job roda em PROCESSO SEPARADO (uma falha/crash do solver não derruba o NEXUS), numa fila
com limite de paralelismo, com cancelamento, tempo limite, captura de log e leitura de progresso. A interface só consulta o estado
(`status`/`log_tail`) ou recebe callbacks — nunca bloqueia: `submit` retorna na hora.

Estados: QUEUED → RUNNING → DONE | FAILED | CANCELLED | TIMEOUT. Um solver ausente vira FAILED com a mensagem real; nada é mascarado.
"""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

STATES = ("QUEUED", "RUNNING", "DONE", "FAILED", "CANCELLED", "TIMEOUT")
_PROGRESS = re.compile(r"NEXUS_PROGRESS\s+([0-9]+(?:\.[0-9]+)?)")     # linha "NEXUS_PROGRESS 42.5" no stdout do processo
RESULT_MARK = "NEXUS_RESULT_JSON:"


@dataclass
class Job:
    name: str
    cmd: list
    cwd: Optional[str] = None
    timeout: Optional[float] = None
    env: Optional[dict] = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    state: str = "QUEUED"
    returncode: Optional[int] = None
    progress: float = 0.0
    error: str = ""
    created: float = field(default_factory=time.time)
    started: Optional[float] = None
    finished: Optional[float] = None
    _log: deque = field(default_factory=lambda: deque(maxlen=2000), repr=False)
    _proc: Optional[subprocess.Popen] = field(default=None, repr=False)
    _cancel: bool = field(default=False, repr=False)
    _done: threading.Event = field(default_factory=threading.Event, repr=False)
    on_update: Optional[Callable[["Job"], None]] = field(default=None, repr=False)

    @property
    def log(self) -> str:
        return "\n".join(self._log)

    def result(self):
        """JSON devolvido pelo processo (linha NEXUS_RESULT_JSON:{...}) ou None."""
        for line in reversed(self._log):
            if line.startswith(RESULT_MARK):
                return json.loads(line[len(RESULT_MARK):])
        return None

    def wait(self, timeout: Optional[float] = None) -> bool:
        return self._done.wait(timeout)

    @property
    def terminal(self) -> bool:
        return self.state in ("DONE", "FAILED", "CANCELLED", "TIMEOUT")


class JobManager:
    def __init__(self, max_parallel: int = 2) -> None:
        if max_parallel < 1:
            raise ValueError("max_parallel ≥ 1")
        self.max_parallel = max_parallel
        self._jobs: dict[str, Job] = {}
        self._queue: deque[str] = deque()
        self._lock = threading.RLock()
        self._running = 0

    # ---- API
    def submit(self, job: Job) -> Job:
        with self._lock:
            self._jobs[job.id] = job
            self._queue.append(job.id)
        self._pump()
        return job

    def submit_cmd(self, name: str, cmd: list, **kw) -> Job:
        return self.submit(Job(name=name, cmd=[str(c) for c in cmd], **kw))

    def submit_python(self, name: str, module: str, func: str, args: Optional[dict] = None, **kw) -> Job:
        """Executa `module.func(**args)` em um interpretador separado; o retorno (JSON-serializável) vira `job.result()`."""
        root = str(Path(__file__).resolve().parent.parent)
        env = dict(os.environ)
        env["PYTHONPATH"] = root + os.pathsep + env.get("PYTHONPATH", "")
        env.update(kw.pop("env", None) or {})
        cmd = [sys.executable, "-m", "core.job_worker", module, func, json.dumps(args or {})]
        return self.submit(Job(name=name, cmd=cmd, cwd=kw.pop("cwd", root), env=env, **kw))

    def get(self, job_id: str) -> Job:
        return self._jobs[job_id]

    def jobs(self) -> list[Job]:
        return list(self._jobs.values())

    def cancel(self, job_id: str) -> bool:
        j = self._jobs[job_id]
        with self._lock:
            if j.terminal:
                return False
            j._cancel = True
            if j.state == "QUEUED":
                try:
                    self._queue.remove(j.id)
                except ValueError:
                    pass
                self._finish(j, "CANCELLED", None, "cancelado antes de iniciar")
                return True
        self._kill(j)
        return True

    def wait_all(self, timeout: Optional[float] = None) -> bool:
        t0 = time.time()
        for j in self.jobs():
            left = None if timeout is None else max(0.0, timeout - (time.time() - t0))
            if not j.wait(left):
                return False
        return True

    # ---- internos
    def _pump(self) -> None:
        with self._lock:
            while self._running < self.max_parallel and self._queue:
                jid = self._queue.popleft()
                j = self._jobs[jid]
                if j.terminal:
                    continue
                self._running += 1
                j.state = "RUNNING"
                j.started = time.time()
                threading.Thread(target=self._run, args=(j,), daemon=True, name=f"nexus-job-{j.id}").start()

    def _notify(self, j: Job) -> None:
        if j.on_update:
            try:
                j.on_update(j)
            except Exception as e:                                         # callback da UI nunca derruba o gerenciador
                j._log.append(f"[NEXUS] erro no callback: {e}")

    def _kill(self, j: Job) -> None:
        p = j._proc
        if p is None or p.poll() is not None:
            return
        try:
            if os.name == "posix":
                os.killpg(os.getpgid(p.pid), signal.SIGTERM)
            else:
                p.terminate()
            try:
                p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                if os.name == "posix":
                    os.killpg(os.getpgid(p.pid), signal.SIGKILL)
                else:
                    p.kill()
        except (ProcessLookupError, PermissionError):
            pass

    def _finish(self, j: Job, state: str, rc: Optional[int], error: str = "") -> None:
        with self._lock:
            if j.terminal:
                return
            j.state, j.returncode, j.error, j.finished = state, rc, error, time.time()
            if state == "DONE":
                j.progress = 100.0
        j._done.set()
        self._notify(j)

    def _run(self, j: Job) -> None:
        self._notify(j)
        timer = None
        try:
            kw = dict(stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, cwd=j.cwd, env=j.env)
            if os.name == "posix":
                kw["start_new_session"] = True
            try:
                j._proc = subprocess.Popen(j.cmd, **kw)
            except (FileNotFoundError, PermissionError, OSError) as e:
                self._finish(j, "FAILED", None, f"não foi possível iniciar '{j.cmd[0]}': {e}")
                return
            timed_out = threading.Event()
            if j.timeout:
                def _to():
                    timed_out.set()
                    self._kill(j)
                timer = threading.Timer(j.timeout, _to)
                timer.daemon = True
                timer.start()
            for line in j._proc.stdout:
                line = line.rstrip("\n")
                j._log.append(line)
                m = _PROGRESS.search(line)
                if m:
                    j.progress = min(100.0, float(m.group(1)))
                    self._notify(j)
            rc = j._proc.wait()
            if j._cancel:
                self._finish(j, "CANCELLED", rc, "cancelado pelo usuário")
            elif timed_out.is_set():
                self._finish(j, "TIMEOUT", rc, f"excedeu {j.timeout:g} s")
            elif rc == 0:
                self._finish(j, "DONE", rc)
            else:
                tail = "\n".join(list(j._log)[-5:])
                self._finish(j, "FAILED", rc, f"código de saída {rc}\n{tail}")
        except Exception as e:                                             # nunca deixa o job "preso" em RUNNING
            self._finish(j, "FAILED", None, f"erro interno do gerenciador: {e}")
        finally:
            if timer:
                timer.cancel()
            with self._lock:
                self._running -= 1
            self._pump()
