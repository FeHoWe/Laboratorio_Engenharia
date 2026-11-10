import logging
import time
from core import backup, logs
from core.jobs import JobManager
from modules.result_trace import TracedResult
from modules.workspace import ProjectStore


def test_backup_rotation_and_restore(tmp_path):
    f = tmp_path / "a.txt"
    assert backup.backup_file(f) is None                      # inexistente → nada
    for i in range(7):
        f.write_text(f"v{i}"); backup.backup_file(f, keep=3); time.sleep(0.002)
    bks = sorted((tmp_path / "backups").glob("a.txt.*.bak"))
    assert len(bks) == 3 and bks[-1].read_text() == "v6" and f.read_text() == "v6"      # original intacto, só os 3 mais recentes
    f.write_text("estragado")
    assert backup.restore_latest(f) == bks[-1] and f.read_text() == "v6"
    assert any(x.read_text() == "estragado" for x in (tmp_path / "backups").glob("a.txt.*.bak"))   # o estado antes de restaurar também fica salvo


def test_project_save_creates_backup_of_previous_version(tmp_path):
    st = ProjectStore(tmp_path); p = st.create("p")
    assert not (tmp_path / "backups").exists()                # primeira gravação: nada para salvar
    st.attach_result(p, TracedResult("r", "ANALITICO", "m"))
    bks = list((tmp_path / "backups").glob("p.nexus.json.*.bak"))
    import json
    assert len(bks) == 1 and json.loads(bks[0].read_text())["results"] == []        # o backup guarda a versão ANTERIOR (sem o resultado novo)
    assert len(json.loads((tmp_path / "p.nexus.json").read_text())["results"]) == 1


def test_central_log_records_job_outcomes(tmp_path):
    path = logs.setup(tmp_path)
    try:
        m = JobManager()
        ok = m.submit_cmd("bom", ["python3", "-c", "print(1)"]); bad = m.submit_cmd("ruim", ["python3", "-c", "raise SystemExit(3)"])
        assert m.wait_all(30)
        for h in logging.getLogger("nexus").handlers: h.flush()
        t = logs.tail(path)
        assert "'bom' → DONE" in t and "'ruim' → FAILED" in t and "rc=3" in t
        assert path == tmp_path / "nexus.log"
        assert logs.setup(tmp_path) == path and sum(getattr(h, "_nexus_file", False) for h in logging.getLogger("nexus").handlers) == 1   # idempotente
    finally:
        for h in list(logging.getLogger("nexus").handlers):
            if getattr(h, "_nexus_file", False): logging.getLogger("nexus").removeHandler(h); h.close()
