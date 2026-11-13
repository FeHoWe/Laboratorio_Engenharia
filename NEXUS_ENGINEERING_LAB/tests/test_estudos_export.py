"""V8.0 — exportação de estudos."""
import json
import pytest
from dataclasses import replace
from modules import comparacao, freio_termico as FT, lapsim, doe, validacao_dados as VD, dinamica_lateral as DL, calibracao as KB, otimizacao as O, estudos_export as X

A = lapsim.Carro(800, 500e3, 1.0, 3.0, 1.6, p_ers=300e3, e_ers=4e6)


@pytest.fixture(scope="module")
def estudos():
    return {"comparacao": comparacao.comparar_voltas(A, replace(A, cla=3.4)), "tornado": O.tornado(A, ["massa", "mu"]),
            "otimizacao": O.otimizar(A, {"mu": (1.5, 1.7)}, max_iter=4), "fatorial": doe.fatorial(A, ["massa", "mu"]),
            "monte_carlo": doe.monte_carlo(A, {"mu": ("normal", 1)}, 12, 2), "pareto": doe.pareto(A, {"e_ers": [0, 2e6, 4e6]}),
            "stint": doe.stint(A, 3, {"massa": -2.0}),
            "dinamica_lateral": {"classe": "ANALITICO", "solver": "linear", "varredura": DL.varredura_velocidade(DL.ParamsLat(800, 1.6, 1.7, 900, 120e3, 140e3), [20, 40]),
                                 "limitacoes": ["modelo linear"]},
            "freio_termico": FT.termica(A, FT.Disco(1.4, 800.0, 0.045), FT.Disco(1.1, 800.0, 0.04), 0.6, voltas=3),
            "calibracao": KB.calibrar(A, {"mu": (1.2, 1.9)}, VD.ler_telemetria(VD.para_csv_exemplo(replace(A, mu=1.5))), frac_treino=0.7),
            "validacao": VD.validar(A, VD.ler_telemetria(VD.para_csv_exemplo(A)), tolerancias={"rmse_kmh": 5})}


@pytest.mark.parametrize("tipo", X.TIPOS)
def test_json_csv_pdf(tipo, estudos, tmp_path):
    e = estudos[tipo]
    j = json.loads(X.para_json(tipo, e))
    assert j["tipo"] == tipo and j["estudo"]["classe"] in ("SIMULACAO_NUMERICA", "VALIDADO", "ANALITICO") and not any(k.startswith("resultado_") for k in j["estudo"])
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


def test_relatorio_consolidado(estudos, tmp_path):
    p = X.relatorio_consolidado([(t, estudos[t]) for t in X.TIPOS], tmp_path / "r.pdf", contexto="carro de exemplo, pista sintética")
    b = p.read_bytes()
    assert b[:5] == b"%PDF-" and len(b) > 5000
    um = X.para_pdf("stint", estudos["stint"], tmp_path / "u.pdf")
    assert um.stat().st_size < p.stat().st_size                     # o consolidado carrega todas as seções
    with pytest.raises(ValueError, match="ao menos"): X.relatorio_consolidado([], tmp_path / "x.pdf")
    with pytest.raises(ValueError, match="não parece"): X.relatorio_consolidado([("tornado", estudos["stint"])], tmp_path / "x.pdf")
