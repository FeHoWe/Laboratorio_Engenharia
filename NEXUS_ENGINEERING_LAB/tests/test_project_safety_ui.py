"""Integração da segurança de projeto (V4.0) na janela principal."""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from core import project_safety as ps


@pytest.fixture()
def janela(tmp_path, monkeypatch, engine):
    monkeypatch.setenv("NEXUS_RECOVERY_DIR", str(tmp_path / "rec"))
    QApplication.instance() or QApplication([])
    from interface.main_window import MainWindow
    w = MainWindow(config={}, engine=engine)
    yield w
    w.project.dirty = False
    w.close()


def test_autosave_so_com_alteracoes_e_recuperacao(janela, tmp_path):
    w = janela
    w.open_sample_engine(background=False)
    w.project.dirty = True
    assert w.autosave_agora() is True
    assert w.autosaver.arquivo.is_file()
    assert w.project.dirty is True                       # não altera o estado do usuário
    # simula queda: pid do processo anterior morto
    import json
    meta = json.loads(w.autosaver.meta.read_text()); meta["pid"] = 2 ** 22 + 12345
    w.autosaver.meta.write_text(json.dumps(meta))
    pend = ps.pendentes()
    assert len(pend) == 1
    w2 = type(w)(config={}, engine=w.engine)
    try:
        assert w2.verificar_recuperacao(lambda p: "abrir") == 1
        assert len(w2.project.components.leaves()) == len(w.project.components.leaves())
        assert w2.project.dirty is True
        assert ps.pendentes() == []
    finally:
        w2.project.dirty = False; w2.close()


def test_salvar_limpa_autosave_e_versoes(janela, tmp_path):
    w = janela
    w.open_sample_engine(background=False)
    w.project.dirty = True
    w.autosave_agora()
    assert w.autosaver.arquivo.is_file()
    assert w.save_project_as(str(tmp_path / "p.nexus"))
    assert not w.autosaver.arquivo.exists()
    assert w.registrar_versao("primeira") is True
    vs = ps.listar_versoes(w.project.path)
    assert len(vs) == 1 and vs[0]["nota"] == "primeira"
    from interface.safety_ui import VersoesDialog
    d = VersoesDialog(w)
    assert "iguais" in d.comparar()
    assert d.restaurar(confirmar=False) is True


def test_descartar_pendente(janela):
    w = janela
    w.open_sample_engine(background=False); w.project.dirty = True; w.autosave_agora()
    import json
    meta = json.loads(w.autosaver.meta.read_text()); meta["pid"] = 2 ** 22 + 999
    w.autosaver.meta.write_text(json.dumps(meta))
    assert w.verificar_recuperacao(lambda p: "descartar") == 0
    assert ps.pendentes() == []
