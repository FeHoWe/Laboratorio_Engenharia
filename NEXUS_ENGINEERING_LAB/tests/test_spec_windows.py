"""V110 Fase H — auditoria ESTÁTICA do nexus.spec (não prova que o executável funciona: isso exige Windows 11 real)."""
import ast
import pathlib

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SPEC = (RAIZ / "nexus.spec").read_text(encoding="utf-8")


def test_spec_e_python_valido():
    ast.parse(SPEC)


def test_pastas_lidas_em_execucao_estao_nos_dados():
    assert '"locales"' in SPEC                                      # core/i18n.py lê locales/*.json em tempo de execução
    assert 'nexus_f1", "data"' in SPEC or "nexus_f1/data" in SPEC
    assert '"assets"' in SPEC and '"samples"' in SPEC


def test_todo_pacote_python_de_primeiro_nivel_esta_coberto():
    pacotes = {p.parent.name for p in RAIZ.glob("*/__init__.py") if p.parent.name not in ("tests", "main")}
    faltam = sorted(n for n in pacotes if f'"{n}"' not in SPEC)
    assert not faltam, f"pacotes fora do nexus.spec: {faltam}"


def test_instalador_e_scripts_existem_e_dizem_nao_testado():
    for f in ("tools/empacotar_windows.bat", "tools/verificar_windows.bat", "tools/nexus_instalador.iss"):
        assert (RAIZ / f).is_file(), f
    assert "NÃO" in (RAIZ / "tools/empacotar_windows.bat").read_text(encoding="utf-8")


def test_roteiro_de_validacao_windows_existe_e_nao_declara_validado():
    t = (RAIZ / "docs" / "WINDOWS_VALIDACAO.md").read_text(encoding="utf-8")
    assert "NÃO VALIDADO" in t and "Windows 11" in t and t.count("- [ ]") >= 15
    assert "- [x]" not in t.lower()                                 # ninguém marca como feito por aqui
