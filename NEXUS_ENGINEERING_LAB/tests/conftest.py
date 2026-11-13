"""Configuração do pytest: caminhos, Qt offscreen e fixtures compartilhadas."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from core.cad_engine import CadEngine  # noqa: E402
from core.project_manager import ProjectManager  # noqa: E402
from modules.importer import ProjectImporter  # noqa: E402
from tests import fixtures  # noqa: E402


@pytest.fixture(scope="session")
def engine():
    return CadEngine()


@pytest.fixture(scope="session")
def data_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("nexus_data")


@pytest.fixture(scope="session")
def step_file(engine, data_dir):
    return fixtures.write_engine_step(engine, data_dir / "motor.step")


@pytest.fixture(scope="session")
def stl_file(data_dir):
    return fixtures.write_two_body_stl(data_dir / "dois_corpos.stl")


@pytest.fixture(scope="session")
def obj_file(data_dir):
    return fixtures.write_two_object_obj(data_dir / "dois_objetos.obj")


@pytest.fixture(scope="session")
def fcstd_file(data_dir):
    return fixtures.write_fcstd(data_dir / "modelo.FCStd")


@pytest.fixture
def motor_project(engine, step_file):
    """Projeto novo com o motor de teste importado (estado limpo a cada teste)."""
    manager = ProjectManager(engine)
    project = manager.new_project("Motor")
    result = ProjectImporter(engine, project.ids).import_file(step_file)
    project.set_root(result.root)
    project.source_files.append(str(step_file))
    return project


def find(project, name):
    """Busca um componente pelo nome exato."""
    for n in project.components.all():
        if n.name == name:
            return n
    raise AssertionError(f"componente '{name}' não encontrado; existentes: "
                         f"{[n.name for n in project.components.all()]}")


def pytest_sessionfinish(session, exitstatus):
    """Encerramento ordenado dos recursos nativos (V3.8). Um `malloc(): unaligned tcache chunk detected` apareceu UMA vez no encerramento do
    interpretador (V3.7) e não reproduziu em execuções instrumentadas (MALLOC_CHECK_=3 + faulthandler: código 0). Esta limpeza — fechar janelas Qt,
    esvaziar a fila de eventos, coletar o lixo e finalizar o Gmsh — é MITIGAÇÃO PLAUSÍVEL, não correção comprovada (a causa nunca foi vista)."""
    import gc
    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            for w in list(app.topLevelWidgets()):
                w.close(); w.deleteLater()
            app.processEvents()
    except Exception:
        pass
    try:
        import gmsh
        if gmsh.isInitialized():
            gmsh.finalize()
    except Exception:
        pass
    gc.collect()


@pytest.fixture(autouse=True)
def _dados_isolados(tmp_path_factory, monkeypatch):
    """V110: o histórico de atividade nunca grava no ~/.nexus_lab real durante os testes."""
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path_factory.mktemp("nexus_dados")))
