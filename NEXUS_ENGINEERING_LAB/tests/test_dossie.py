"""V90 — dossiê reprodutível."""
import io, json
import pytest
import nexus_cli
from modules import dossie as D

CARRO = dict(massa=800.0, p_ice=500e3, cda=1.0, cla=3.0, mu=1.6, p_ers=300e3, e_ers=4e6)
PAR = {"tornado": {"carro": CARRO, "campos": ["massa", "mu"], "pct": 5},
       "volta": {"carro": CARRO},
       "montecarlo": {"carro": CARRO, "incertezas": {"mu": ["normal", 1]}, "n": 20, "semente": 3},
       "otimizacao": {"carro": CARRO, "faixas": {"mu": [1.5, 1.7]}, "iter": 3},
       "fatorial": {"carro": CARRO, "campos": ["massa", "mu"]},
       "stint": {"carro": CARRO, "voltas": 3, "taxas": {"massa": -2.0}},
       "freio_termico": {"carro": CARRO, "disco_diant": dict(massa=1.4, cp=800.0, area=0.045), "disco_tras": dict(massa=1.1, cp=800.0, area=0.04), "voltas": 2}}


@pytest.mark.parametrize("tipo", D.TIPOS)
def test_cria_verifica_reproduz(tipo, tmp_path):
    d = D.criar(tipo, PAR[tipo], "teste")
    p = D.salvar(d, tmp_path / "a.dossie.json")
    v = D.verificar(D.carregar(p))
    assert v["integro"] and v["reproduziu"] and all(v["ambiente_igual"].values())
    assert d["tipo"] == tipo and len(d["sha256_resultado"]) == 64 and "Reproduziu" in v["observacao"]


def test_entrada_diferente_muda_hash_e_adulteracao_detectada(tmp_path):
    a = D.criar("volta", PAR["volta"])
    b = D.criar("volta", {"carro": {**CARRO, "massa": 790.0}})
    assert a["sha256_resultado"] != b["sha256_resultado"]
    a["resultado"]["valores"]["tempo_s"] += 1.0                       # adultera o resultado guardado
    assert not D.verificar(a)["integro"]
    c = D.criar("volta", PAR["volta"]); c["parametros"]["carro"]["massa"] = 700.0   # adultera a entrada guardada
    v = D.verificar(c)
    assert v["integro"] and not v["reproduziu"] and "NÃO reproduziu" in v["observacao"]


def test_semente_importa_e_e_repetivel():
    a = D.criar("montecarlo", PAR["montecarlo"]); b = D.criar("montecarlo", PAR["montecarlo"])
    c = D.criar("montecarlo", {**PAR["montecarlo"], "semente": 4})
    assert a["sha256_resultado"] == b["sha256_resultado"] != c["sha256_resultado"]


def test_erros(tmp_path):
    with pytest.raises(D.DossieError, match="tipo desconhecido"): D.executar("xx", {})
    with pytest.raises(D.DossieError, match="carro"): D.executar("volta", {"carro": {"abc": 1}})
    (tmp_path / "x.json").write_text("{}")
    with pytest.raises(D.DossieError, match="não é um dossiê"): D.carregar(tmp_path / "x.json")
    with pytest.raises(D.DossieError, match="não foi possível ler"): D.carregar(tmp_path / "nao.json")


def test_texto_e_cli(tmp_path):
    d = D.criar("volta", PAR["volta"], "nota X")
    assert "nota X" in D.texto(d) and "reprodutibilidade" in D.texto(d)
    esp = tmp_path / "e.json"; esp.write_text(json.dumps({"tipo": "tornado", "parametros": PAR["tornado"], "nota": "cli"}))
    out = tmp_path / "e.dossie.json"
    buf = io.StringIO()
    assert nexus_cli.executar(["dossie", "criar", str(esp), "--saida", str(out)], out=buf) == 0 and out.exists()
    buf = io.StringIO()
    assert nexus_cli.executar(["--json", "dossie", "verificar", str(out)], out=buf) == 0
    assert json.loads(buf.getvalue())["reproduziu"] is True
    d2 = json.loads(out.read_text()); d2["parametros"]["carro"]["massa"] = 1.0 + d2["parametros"]["carro"]["massa"]; out.write_text(json.dumps(d2))
    assert nexus_cli.executar(["dossie", "verificar", str(out)], out=io.StringIO()) == 1
    assert nexus_cli.executar(["dossie", "verificar", str(tmp_path / "nao.json")], out=io.StringIO()) == 1
