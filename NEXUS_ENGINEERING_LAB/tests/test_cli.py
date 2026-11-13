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
