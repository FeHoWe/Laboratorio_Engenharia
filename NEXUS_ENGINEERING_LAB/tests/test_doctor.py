from core import doctor


def test_report_covers_all_required_items_and_is_honest():
    cs = doctor.run_all()
    nomes = {c.nome for c in cs}
    for n in ("Python", "OpenCASCADE (OCP)", "Gmsh", "CalculiX", "OpenFOAM", "WSL2", "ParaView", "numpy", "PySide6"):
        assert n in nomes
    for c in cs:
        if not c.ok:
            assert c.instalacao, f"{c.nome} ausente sem instrução de instalação"
        assert c.estado in ("PRONTO", "NÃO INSTALADO", "AUSENTE (obrigatório)")
    t = doctor.report_text(cs)
    assert "somente leitura" in t and "como instalar" in t or all(c.ok for c in cs)


def test_missing_executable_never_reported_ready(monkeypatch):
    monkeypatch.setattr(doctor.shutil, "which", lambda x: None)
    c = doctor._check_exe("CalculiX", ["ccx"], ["-v"], "instale")
    assert not c.ok and c.estado == "NÃO INSTALADO" and c.instalacao == "instale"


def test_verify_and_unknown():
    assert doctor.verify("python").ok
    import pytest
    with pytest.raises(KeyError):
        doctor.verify("inexistente")


def test_broken_library_reports_error_instead_of_crashing(monkeypatch):
    def boom(name): raise OSError("libGLU.so.1 ausente")
    monkeypatch.setattr(doctor.importlib, "import_module", boom)
    c = doctor._lib("gmsh", "gmsh", False)
    assert not c.ok and "libGLU" in c.detalhe and c.instalacao == "pip install gmsh"
