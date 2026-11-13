import pytest
from core import atividade as A


@pytest.fixture(autouse=True)
def pasta(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path / "dados"))


def test_registra_lista_ordem_e_filtro():
    assert A.registrar("estudo", "tornado") and A.registrar("projeto", "abriu x", "/nao/existe.nexus") and A.registrar("estudo", "freio")
    u = A.ultimos(10)
    assert [d["texto"] for d in u] == ["freio", "abriu x", "tornado"]
    assert [d["texto"] for d in A.ultimos(10, "estudo")] == ["freio", "tornado"]


def test_limite_corrompida_e_projetos_existentes(tmp_path):
    for i in range(A.MAX + 20):
        A.registrar("estudo", str(i))
    assert len(A.ultimos(10_000)) == A.MAX and A.ultimos(1)[0]["texto"] == str(A.MAX + 19)
    p = A._arquivo(); p.write_text(p.read_text(encoding="utf-8") + "lixo\n", encoding="utf-8")
    assert len(A.ultimos(10_000)) == A.MAX                          # linha ruim ignorada
    real = tmp_path / "a.nexus"; real.write_text("x")
    A.registrar("projeto", "a", str(real)); A.registrar("projeto", "b", str(tmp_path / "sumiu.nexus")); A.registrar("projeto", "a de novo", str(real))
    assert A.projetos_recentes() == [str(real)]


def test_falha_de_gravacao_nao_levanta(monkeypatch, tmp_path):
    arq = tmp_path / "arquivo"; arq.write_text("x")
    monkeypatch.setenv("NEXUS_DATA_DIR", str(arq / "sub"))          # pai é arquivo → mkdir falha
    assert A.registrar("estudo", "x") is False and A.ultimos() == []
