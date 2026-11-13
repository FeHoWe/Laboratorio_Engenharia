"""V8.0 — exportação de estudos."""
import json
import pytest
from dataclasses import replace
from modules import comparacao, lapsim, otimizacao as O, estudos_export as X

A = lapsim.Carro(800, 500e3, 1.0, 3.0, 1.6, p_ers=300e3, e_ers=4e6)


@pytest.fixture(scope="module")
def estudos():
    return {"comparacao": comparacao.comparar_voltas(A, replace(A, cla=3.4)), "tornado": O.tornado(A, ["massa", "mu"]),
            "otimizacao": O.otimizar(A, {"mu": (1.5, 1.7)}, max_iter=4)}


@pytest.mark.parametrize("tipo", X.TIPOS)
def test_json_csv_pdf(tipo, estudos, tmp_path):
    e = estudos[tipo]
    j = json.loads(X.para_json(tipo, e))
    assert j["tipo"] == tipo and j["estudo"]["classe"] == "SIMULACAO_NUMERICA" and not any(k.startswith("resultado_") for k in j["estudo"])
    csv = X.para_csv(tipo, e)
    assert csv.splitlines()[0].startswith("# ") and "# limitacao:" in csv
    for ext in ("csv", "json", "pdf"):
        p = X.exportar(tipo, e, tmp_path / f"s.{ext}")
        assert p.stat().st_size > 100
    assert (tmp_path / "s.pdf").read_bytes()[:5] == b"%PDF-"


def test_valores_do_csv_batem_com_o_estudo(estudos):
    cab, linhas = X.linhas_tabela("tornado", estudos["tornado"])
    assert linhas[0][0] == estudos["tornado"]["linhas"][0]["campo"] and linhas[0][-1] == estudos["tornado"]["linhas"][0]["amplitude_s"]


def test_erros(estudos, tmp_path):
    with pytest.raises(ValueError, match="tipo desconhecido"): X.para_json("x", {})
    with pytest.raises(ValueError, match="não parece"): X.para_csv("tornado", estudos["comparacao"])
    with pytest.raises(ValueError, match="extensão"): X.exportar("tornado", estudos["tornado"], tmp_path / "a.txt")
