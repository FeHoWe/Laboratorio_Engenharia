"""V6.1 — CLI headless (nexus_cli.py)."""
import io, json
import pytest
import nexus_cli
from core.project_manager import ProjectManager


def run(*args):
    buf = io.StringIO()
    code = nexus_cli.executar(list(args), out=buf)
    return code, buf.getvalue()


def test_volta_texto_e_json():
    c, t = run("volta")
    assert c == 0 and "SIMULACAO_NUMERICA" in t and "SINTÉTICA" in t
    c, j = run("--json", "volta", "--carro", "massa=780")
    d = json.loads(j)
    assert c == 0 and d["classe"] == "SIMULACAO_NUMERICA" and d["valores"]["tempo_s"] < json.loads(run("--json", "volta")[1])["valores"]["tempo_s"]


def test_comparar_e_tornado_e_otimizar():
    c, t = run("comparar", "--b", "cla=3.4")
    assert c == 0 and "Parâmetros diferentes: cla" in t
    c, t = run("tornado", "--pct", "5")
    assert c == 0 and "amplitude" in t
    c, j = run("--json", "otimizar", "--faixa", "mu=1.5:1.7", "--iter", "4")
    assert c == 0 and 1.5 <= json.loads(j)["parametros"]["mu"] <= 1.7


@pytest.mark.parametrize("args", [("volta", "--carro", "foo=1"), ("volta", "--carro", "massa"), ("otimizar", "--faixa", "mu=2:1"), ("otimizar", "--faixa", "mu"), ("comparar", "--b", "x=abc"), ("verificar", "/nao/existe.nexus")])
def test_erros_viram_codigo_1(args):
    assert run(*args)[0] == 1


def test_sem_comando_ou_ajuda_nao_levanta():
    assert run()[0] == 1


def test_verificar_projeto(engine, motor_project, tmp_path):
    pm = ProjectManager(engine)
    f = pm.save(motor_project, tmp_path / "m.nexus")
    c, j = run("--json", "verificar", str(f))
    d = json.loads(j)
    assert c in (0, 2) and d["pior"] in ("INFO", "ATENCAO", "CRITICO") and d["achados"]
    assert (c == 2) == (d["pior"] == "CRITICO")


def test_doctor_json():
    c, j = run("--json", "doctor")
    assert c == 0 and any(x["nome"] == "Python" for x in json.loads(j))


def test_saida_exporta_arquivo(tmp_path):
    for cmd, extra in (("tornado", []), ("comparar", ["--b", "cla=3.4"]), ("otimizar", ["--faixa", "mu=1.5:1.7", "--iter", "3"])):
        for ext in ("csv", "json", "pdf"):
            f = tmp_path / f"{cmd}.{ext}"
            assert run(cmd, *extra, "--saida", str(f))[0] == 0 and f.stat().st_size > 50
    assert run("tornado", "--saida", str(tmp_path / "x.txt"))[0] == 1


def test_novos_comandos_e_pista(tmp_path):
    pista = tmp_path / "p.csv"
    pista.write_text("comprimento_m,raio_m\n800,0\n100,40\n500,0\n120,30\n", encoding="utf-8")
    c, t = run("volta", "--pista", str(pista))
    c2, t0 = run("volta")
    assert c == 0 and " 152" in t and "Pista informada por você" in t and "SINTÉTICA" not in t
    assert t != t0 and "SINTÉTICA" in t0
    assert run("volta", "--pista", str(tmp_path / "nao.csv"))[0] == 1
    c, t = run("fatorial", "--campos", "massa", "mu", "--pct", "5")
    assert c == 0 and "Fatorial 2^2" in t
    c, j = run("--json", "montecarlo", "--inc", "mu=normal:2", "massa=uniforme:1", "--n", "30", "--semente", "4")
    d = json.loads(j)
    assert c == 0 and d["n"] == 30 and d["p05_s"] <= d["p95_s"]
    c, t = run("pareto", "--grade", "e_ers=0,2e6,4e6")
    assert c == 0 and "Pareto" in t
    c, t = run("stint", "--voltas", "3", "--taxa", "massa=-2")
    assert c == 0 and "Stint" in t
    for ext in ("csv", "json", "pdf"):
        for cmd in (("fatorial", "--campos", "massa"), ("montecarlo", "--inc", "mu=normal:1", "--n", "10"), ("pareto", "--grade", "e_ers=0,4e6"), ("stint", "--voltas", "2", "--taxa", "massa=-1")):
            f = tmp_path / f"{cmd[0]}.{ext}"
            assert run(*cmd, "--saida", str(f))[0] == 0 and f.stat().st_size > 50
    for bad in (("fatorial", "--campos", "x"), ("montecarlo", "--inc", "mu=beta:1"), ("montecarlo", "--inc", "mu"), ("pareto", "--grade", "e_ers"), ("pareto", "--grade", "e_ers=1", "--objetivos", "tempo_s", "tempo_s"),
                ("stint", "--voltas", "0", "--taxa", "massa=1"), ("stint", "--voltas", "2", "--taxa", "massa")):
        assert run(*bad)[0] == 1
