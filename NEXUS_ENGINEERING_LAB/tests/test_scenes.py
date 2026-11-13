"""Cenas salvas: captura, aplicação, persistência e robustez."""
import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication  # noqa: E402

from modules.scene_manager import Scene, SceneStore  # noqa: E402


def test_store_rules():
    st = SceneStore()
    st.add(Scene("A"))
    with pytest.raises(ValueError, match="Já existe"):
        st.add(Scene("A"))
    st.add(Scene("A", holo=False), replace=True)
    assert len(st) == 1 and st.get("A").holo is False
    with pytest.raises(ValueError):
        st.add(Scene("  "))
    st.add(Scene("B"))
    st.rename("B", "C")
    with pytest.raises(ValueError):
        st.rename("C", "A")
    assert st.names() == ["A", "C"] and st.remove("A") and not st.remove("zzz")
    again = SceneStore.from_list(st.to_list() + [{"lixo": 1, "name": None, "camera": 5}])
    assert again.names()[0] == "C"


@pytest.fixture
def win(engine):
    QApplication.instance() or QApplication([])
    from interface.main_window import MainWindow
    w = MainWindow(engine=engine)
    w.explode_bar.animate_check.setChecked(False)
    w.open_sample_engine(ask_split=False, background=False)
    yield w
    w.project.dirty = False
    w.close()


def _state(w):
    comps = w.project.components
    return ({n.id: tuple(np.round(n.offset, 6)) for n in comps.root.walk()},
            {n.id: n.visible for n in comps.root.walk()})


def test_scene_roundtrip_in_window(win):
    w = win
    w.explode_all()
    w.section_bar.enable_check.setChecked(True)
    w.section_bar.slider.setValue(300)
    cam = w.scene.renderer.GetActiveCamera()
    cam.SetPosition(500, -400, 300)
    w.project.components.set_visible(w.project.components.leaves()[0].id, False)
    before = _state(w)
    w.save_scene("Explodida + corte")

    w.project.assembly.restore()
    w.section_bar.enable_check.setChecked(False)
    w.project.components.show_all()
    cam.SetPosition(0, 0, 900)
    assert _state(w) != before

    missing = w.apply_scene("Explodida + corte")
    assert missing == 0
    assert _state(w) == before
    assert w.section_bar.enabled and w.section_bar.slider.value() == 300
    assert w.scene.section is not None and w.scene.section[0] == w.section_bar.axis
    assert np.allclose(cam.GetPosition(), (500, -400, 300))


def test_scene_survives_save_and_open(win, tmp_path):
    w = win
    w.explode_all()
    w.save_scene("S1")
    f = tmp_path / "c.nexus"
    w.project_manager.save(w.project, f)
    again = w.project_manager.open(f)
    assert again.scenes.names() == ["S1"]
    assert len(again.scenes.get("S1").offsets) > 10


def test_apply_ignores_vanished_ids(win):
    w = win
    sc = w.save_scene("X")
    sc.offsets["C9999"] = [1.0, 2.0, 3.0]
    sc.hidden.append("C8888")
    assert w.apply_scene("X") == 2
    assert w.apply_scene("nao existe") == -1


def test_pdf_report_with_scene_and_parts(win, tmp_path):
    w = win
    w.apply_typical_materials()
    w.explode_all()
    w.save_scene("Explodida")
    out = w.export_report(str(tmp_path / "r.pdf"), detail_parts=False)
    assert out and out.stat().st_size > 20_000
    data = out.read_bytes()
    assert data.startswith(b"%PDF")
    import re
    pages = len(re.findall(rb"/Type\s*/Page[^s]", data))
    assert 5 <= pages <= 16                     # capa + BOM(+totais) + relações de montagem + 1 cena
    full = w.export_report(str(tmp_path / "f.pdf"), detail_parts=True)
    assert len(re.findall(rb"/Type\s*/Page[^s]", full.read_bytes())) > pages + 10


def test_project_state_untouched_by_report(win, tmp_path):
    w = win
    w.explode_all()
    before = _state(w)
    w.save_scene("S")
    w.export_report(str(tmp_path / "r.pdf"), detail_parts=False)
    assert _state(w) == before                   # relatório não altera posições nem visibilidade


@pytest.mark.parametrize("lang,esperado", [("pt", "Lista de materiais"), ("en", "Bill of materials"), ("es", "Lista de materiales"),
                                          ("de", "Stückliste"), ("fr", "Nomenclature")])
def test_pdf_relatorio_traduzido(win, tmp_path, lang, esperado):
    """O PDF sai no idioma escolhido (fonte DejaVu: en/es/de/fr) e o idioma volta ao normal no fim."""
    import subprocess
    from core import i18n
    w = win
    w.apply_typical_materials()
    antes = i18n.idioma()
    i18n.definir_idioma(lang, salvar=False)
    try:
        out = w.export_report(str(tmp_path / f"r_{lang}.pdf"), detail_parts=False)
    finally:
        i18n.definir_idioma(antes, salvar=False)
    assert out and out.read_bytes().startswith(b"%PDF")
    t = subprocess.run(["pdftotext", str(out), "-"], capture_output=True, text=True).stdout
    if t:
        assert esperado in t
        if lang != "pt":
            assert "Lista de materiais (BOM)" not in t or lang == "es"


def test_pdf_chines_usa_fonte_cid(win, tmp_path):
    """Chinês: fonte CID padrão do PDF (não embutida); o arquivo é gerado e os números não mudam de formato (ponto decimal)."""
    from core import i18n
    from modules import report
    w = win
    w.apply_typical_materials()
    antes = i18n.idioma()
    i18n.definir_idioma("zh", salvar=False)
    try:
        out = w.export_report(str(tmp_path / "zh.pdf"), detail_parts=False)
        assert report.FONT in ("STSong-Light", "NexusCJK-zh") and report._num(1234.5) == "1,234.50"
    finally:
        i18n.definir_idioma(antes, salvar=False)
    b = out.read_bytes()
    assert out and b.startswith(b"%PDF") and (b"STSong-Light" in b or b"WenQuanYi" in b or b"NexusCJK" in b or b"/FontFile2" in b)


@pytest.mark.parametrize("lang,titulo", [("pt", "Verificação de consistência do projeto"), ("en", "Project consistency check"), ("de", "Prüfung der Projektkonsistenz")])
def test_pdf_inclui_verificacao_de_consistencia(win, tmp_path, lang, titulo):
    """V5.2 — o PDF do projeto traz o parecer de consistência (regras), com níveis e a ressalva 'não é IA generativa'."""
    import subprocess
    from core import i18n
    antes = i18n.idioma()
    i18n.definir_idioma(lang, salvar=False)
    try:
        out = win.export_report(str(tmp_path / f"c_{lang}.pdf"), detail_parts=False)
    finally:
        i18n.definir_idioma(antes, salvar=False)
    t = subprocess.run(["pdftotext", str(out), "-"], capture_output=True, text=True).stdout
    if t:
        assert titulo in t and ("[ATENCAO]" in t or "[INFO]" in t)
        assert "NAO_EXECUTADO" in t
