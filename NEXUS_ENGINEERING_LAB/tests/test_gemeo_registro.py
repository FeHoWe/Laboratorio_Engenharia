"""V120 — Gêmeo digital 2.0: persistência no .nexus, estados, versões, restauração."""
import json
import zipfile
import pytest
from core.cad_engine import CadEngine
from core.project_manager import ProjectManager, FORMAT_VERSION
from modules import gemeo_registro as R


def _salvar_abrir(p, tmp_path, nome="p.nexus"):
    pm = ProjectManager(CadEngine()); arq = tmp_path / nome
    pm.save(p, str(arq), backup=False)
    return pm.open(arq), arq


def test_projeto_sem_registro_nao_grava_chave_e_abre_igual(motor_project, tmp_path):
    q, arq = _salvar_abrir(motor_project, tmp_path)
    assert "gemeo_digital" not in json.loads(zipfile.ZipFile(arq).read("project.json")) and q.gemeo == {"estudos": [], "levantamentos": []}


def test_persistencia_e_formato_inalterado(motor_project, tmp_path):
    p = motor_project; f = list(p.components.leaves())
    p.components.set_material(f[0].id, "Aço carbono", recursive=False)
    R.registrar_levantamento(p, "inicial")
    R.registrar_estudo(p, "FEA biela", "fea", "SIMULACAO_NUMERICA", [f[0].id], contorno={"fixos": [1]}, malha={"h": 2.0}, resumo={"vm": 100.0})
    q, arq = _salvar_abrir(p, tmp_path)
    doc = json.loads(zipfile.ZipFile(arq).read("project.json"))
    assert doc["nexus_format"] == FORMAT_VERSION == 1 and len(doc["gemeo_digital"]["estudos"]) == 1 and len(doc["gemeo_digital"]["levantamentos"]) == 1
    assert q.gemeo["estudos"][0]["nome"] == "FEA biela" and q.gemeo["estudos"][0]["resumo"] == {"vm": 100.0}
    assert R.estado_estudos(q)[0]["estado"] == "ATUALIZADO"                            # assinatura sobrevive ao ciclo salvar/abrir


def test_chave_corrompida_e_ignorada_sem_quebrar_abertura(motor_project, tmp_path):
    p = motor_project; R.registrar_levantamento(p)
    _, arq = _salvar_abrir(p, tmp_path)
    novo = tmp_path / "x.nexus"
    with zipfile.ZipFile(arq) as zin, zipfile.ZipFile(novo, "w") as zout:
        for it in zin.infolist():
            d = zin.read(it.filename)
            if it.filename == "project.json":
                j = json.loads(d); j["gemeo_digital"] = "lixo"; d = json.dumps(j).encode()
            zout.writestr(it, d)
    assert ProjectManager(CadEngine()).open(novo).gemeo == {"estudos": [], "levantamentos": []}


def test_estados_obsoleto_historico_incompleto(motor_project):
    p = motor_project; f = list(p.components.leaves())
    p.components.set_material(f[0].id, "Aço carbono", recursive=False)
    a = R.registrar_estudo(p, "E1", "fea", "SIMULACAO_NUMERICA", [f[0].id])
    assert R.estado_estudos(p)[0]["estado"] == "ATUALIZADO"
    p.components.set_material(f[0].id, "Alumínio 6061", recursive=False)
    e = R.estado_estudos(p)[0]
    assert e["estado"] == "OBSOLETO" and "material" in e["motivo"]
    b = R.registrar_estudo(p, "E1", "fea", "SIMULACAO_NUMERICA", [f[0].id])               # novo registro: o antigo vira HISTORICO, não some
    assert [x["estado"] for x in R.estado_estudos(p)] == ["HISTORICO", "ATUALIZADO"] and len(p.gemeo["estudos"]) == 2
    c = R.registrar_estudo(p, "E2", "massa", "ANALITICO", None)                            # projeto todo, há peças sem material
    assert R.estado_estudos(p)[2]["estado"] == "INCOMPLETO"


def test_painel_levantamentos_e_restauracao(motor_project):
    p = motor_project; f = list(p.components.leaves())
    for x in f:
        p.components.set_material(x.id, "Aço carbono", recursive=False)
    R.registrar_levantamento(p, "v1")
    R.registrar_estudo(p, "E1", "fea", "SIMULACAO_NUMERICA", [f[0].id])
    assert {x["estado"] for x in R.painel(p)} == {"ATUALIZADO"}
    p.components.set_material(f[0].id, "Alumínio 6061", recursive=False)
    st = {x["id"]: x["estado"] for x in R.painel(p)}
    assert st[f[0].id] == "NECESSITA_NOVA_SIMULACAO" and st[f[1].id] == "ATUALIZADO"
    R.registrar_levantamento(p, "v2")
    ev = R.comparar_levantamentos(p, 1, 2)
    assert {e["tipo"] for e in ev} == {"material", "massa"} and all(e["id"] == f[0].id for e in ev)
    mud = R.restaurar_materiais(p, 1)
    assert [m["id"] for m in mud] == [f[0].id] and mud[0]["para"] == "Aço carbono"
    assert R.estado_estudos(p)[0]["estado"] == "ATUALIZADO" and len(p.gemeo["levantamentos"]) == 2    # histórico preservado
    assert R.restaurar_materiais(p, 1) == []
    assert "Gêmeo digital" in R.texto(p)


def test_erros(motor_project):
    p = motor_project
    with pytest.raises(ValueError, match="nome"): R.registrar_estudo(p, " ", "x", "ANALITICO")
    with pytest.raises(ValueError, match="inexistente"): R.registrar_estudo(p, "a", "x", "ANALITICO", ["nao-existe"])
    with pytest.raises(ValueError, match="inexistente"): R.comparar_levantamentos(p, 1, 2)
    with pytest.raises(ValueError, match="inexistente"): R.restaurar_materiais(p, 3)


def test_cli_gemeo(motor_project, tmp_path):
    import io
    import nexus_cli
    _, arq = _salvar_abrir(motor_project, tmp_path)
    buf = io.StringIO()
    assert nexus_cli.executar(["--json", "gemeo", str(arq)], out=buf) == 0 and json.loads(buf.getvalue())["levantamentos"] == 0
    novo = tmp_path / "n.nexus"; buf = io.StringIO()
    assert nexus_cli.executar(["--json", "gemeo", str(arq), "--levantar", "cli", "--saida", str(novo)], out=buf) == 0 and json.loads(buf.getvalue())["levantamentos"] == 1
    assert json.loads(zipfile.ZipFile(novo).read("project.json"))["gemeo_digital"]["levantamentos"][0]["rotulo"] == "cli"
    assert "gemeo_digital" not in json.loads(zipfile.ZipFile(arq).read("project.json"))     # original intacto
    assert nexus_cli.executar(["gemeo", str(arq), "--levantar", "x"], out=io.StringIO()) == 1


def test_ai_responder_gemeo(motor_project, tmp_path):
    import io
    import nexus_cli
    from modules import ai_engenheiro as AE
    p, arq = _salvar_abrir(motor_project, tmp_path)
    r0 = AE.responder_gemeo("quais estudos estão obsoletos?", p)
    assert set(r0["blocos"]) == {"CALCULADO", "INTERPRETADO", "HIPOTESE", "RECOMENDACAO", "NAO_DISPONIVEL"} and "nenhum estudo foi registrado" in r0["resposta"]
    R.registrar_estudo(p, "e1", "fea", "SIMULACAO_NUMERICA", None)
    assert "INCOMPLETO" in AE.responder_gemeo("estudos obsoletos?", p)["resposta"]  # peças sem material: nunca atribuído automaticamente
    buf = io.StringIO()
    assert nexus_cli.executar(["diagnostico", str(arq), "--pergunta", "quais estudos estão obsoletos?"], out=buf) == 0 and "[NAO_DISPONIVEL]" in buf.getvalue()
