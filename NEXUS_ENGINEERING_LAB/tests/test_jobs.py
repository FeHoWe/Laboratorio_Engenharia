"""NEXUS CORE: fila de processos isolados."""
import sys
import time
import pytest
from core.jobs import JobManager


PY = sys.executable


def test_success_log_progress_and_result():
    m = JobManager()
    j = m.submit_cmd("ok", [PY, "-c", "print('NEXUS_PROGRESS 40'); print('olá')"])
    assert j.wait(20) and j.state == "DONE" and j.returncode == 0 and j.progress == 100.0 and "olá" in j.log


def test_python_job_returns_json_and_crash_is_isolated():
    m = JobManager()
    ok = m.submit_python("soma", "tests.job_funcs", "soma", {"a": 2, "b": 3})
    bad = m.submit_python("erro", "tests.job_funcs", "explode", {})
    seg = m.submit_cmd("crash", [PY, "-c", "import os; os._exit(139)"])
    assert m.wait_all(30)
    assert ok.state == "DONE" and ok.result() == {"s": 5}
    assert bad.state == "FAILED" and "ValueError" in bad.log and "ValueError" in bad.error
    assert seg.state == "FAILED" and seg.returncode == 139            # falha de um processo não afeta os outros


def test_missing_executable_is_failed_not_hidden():
    j = JobManager().submit_cmd("x", ["nexus_solver_inexistente_xyz"])
    assert j.wait(10) and j.state == "FAILED" and "não foi possível iniciar" in j.error


def test_timeout_and_cancel():
    m = JobManager()
    t = m.submit_cmd("lento", [PY, "-c", "import time; time.sleep(30)"], timeout=0.5)
    c = m.submit_cmd("cancelar", [PY, "-c", "import time; print('go', flush=True); time.sleep(30)"])
    for _ in range(100):
        if "go" in c.log:
            break
        time.sleep(0.05)
    assert m.cancel(c.id)
    assert t.wait(15) and t.state == "TIMEOUT"
    assert c.wait(15) and c.state == "CANCELLED"
    assert not m.cancel(c.id)                                            # já terminou


def test_queue_respects_parallel_limit_and_cancel_queued():
    m = JobManager(max_parallel=1)
    a = m.submit_cmd("a", [PY, "-c", "import time; time.sleep(0.6)"])
    b = m.submit_cmd("b", [PY, "-c", "print(1)"])
    assert a.state == "RUNNING" and b.state == "QUEUED"
    assert m.cancel(b.id) and b.state == "CANCELLED"
    assert a.wait(10) and a.state == "DONE"


def test_callback_errors_do_not_break_manager():
    m = JobManager()
    def boom(j): raise RuntimeError("ui quebrou")
    j = m.submit_cmd("cb", [PY, "-c", "print(1)"], on_update=boom)
    assert j.wait(10) and j.state == "DONE"
    with pytest.raises(ValueError):
        JobManager(0)
