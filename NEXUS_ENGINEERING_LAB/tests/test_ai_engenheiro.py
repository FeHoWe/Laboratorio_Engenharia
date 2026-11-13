"""V106 Fase F — AI Engineer (ferramentas determinísticas)."""
import re
import pytest
from modules import ai_engenheiro as AI, gemeo_digital as G

EST = [{"nome": "FEA", "classe": "SIMULACAO_NUMERICA", "valores": {"vm_max_MPa": 123.4}, "premissas": ["material linear"], "limitacoes": ["Tet4 trava em flexão"], "componentes": []},
       {"nome": "ref", "classe": "VALIDADO", "valores": {"erro_pct": 1.5}, "componentes": []}]


def test_cinco_blocos_sem_material_e_sem_inventar(motor_project):
    d = AI.diagnostico(motor_project, EST)
    assert set(d) >= {"CALCULADO", "INTERPRETACAO", "HIPOTESE", "RECOMENDACAO", "INDISPONIVEL"}
    c = {x["item"]: x["valor"] for x in d["CALCULADO"]}
    assert c["pecas_com_material"] == 0 and c["massa_parcial_kg"] == 0 and c["FEA.vm_max_MPa"] == 123.4
    assert any(x["item"] == "massa total" and "não atribui automaticamente" in x["motivo"] for x in d["INDISPONIVEL"])
    assert any("Atribuir material" in r["texto"] and r["baseado_em"] for r in d["RECOMENDACAO"])
    assert any("NÃO validado" in r["texto"] and "FEA" in r["texto"] for r in d["RECOMENDACAO"]) and not any("'ref'" in r["texto"] for r in d["RECOMENDACAO"])
    assert any("LIMITAÇÃO" in h["premissa"] for h in d["HIPOTESE"])
    t = AI.texto(d)
    permitidos = {f"{x['valor']:.6g}" for x in d["CALCULADO"]}
    # números do bloco CALCULADO vêm só dos campos; nenhum valor fora deles aparece após '='
    assert set(re.findall(r"= ([\d.e+-]+)", t)) <= permitidos


def test_mudancas_geram_recomendacao_de_refazer(motor_project):
    antes = G.levantar(motor_project)
    folha = list(motor_project.components.leaves())[0]
    motor_project.components.set_material(folha.id, "Aço carbono", recursive=False)
    est = [{**EST[0], "componentes": [folha.id]}]
    d = AI.diagnostico(motor_project, est, estado_anterior=antes)
    assert d["mudancas"] and any("Refazer os estudos afetados" in r["texto"] and "FEA" in r["texto"] for r in d["RECOMENDACAO"])
    d2 = AI.diagnostico(motor_project, est, estado_anterior=G.levantar(motor_project))
    assert d2["mudancas"] == [] and not any("Refazer" in r["texto"] for r in d2["RECOMENDACAO"])


def test_responder_roteia_e_nao_improvisa(motor_project):
    d = AI.diagnostico(motor_project, EST)
    r = AI.responder("Qual é a massa do projeto?", d)
    assert r["reconhecida"] and "CALCULADO" in r["blocos"] and "INDISPONIVEL" in r["blocos"] and "massa_parcial_kg" in r["resposta"]
    r = AI.responder("quais as premissas e limitações do estudo?", d)
    assert "HIPOTESE" in r["blocos"] and "Tet4" in r["resposta"]
    r = AI.responder("qual a cor do carro do Hamilton?", d)
    assert r["reconhecida"] is False and r["resposta"].startswith("Não sei") and r["blocos"] == []
    assert AI.responder("quais estudos refazer?", AI.diagnostico(motor_project, []))["reconhecida"]
    sem = AI.diagnostico(motor_project, [])
    assert any(x["item"] == "resultados de estudos" for x in sem["INDISPONIVEL"])


def test_cli_diagnostico(motor_project, tmp_path):
    import io, json
    import nexus_cli
    arq = tmp_path / "m.nexus"
    from core.project_manager import ProjectManager as PM
    import core.cad_engine as CE
    PM(CE.CadEngine()).save(motor_project, str(arq))
    est = tmp_path / "e.json"; est.write_text(json.dumps(EST))
    buf = io.StringIO()
    assert nexus_cli.executar(["diagnostico", str(arq), "--estudos", str(est)], out=buf) == 0
    assert "== CALCULADO ==" in buf.getvalue() and "123.4" in buf.getvalue()
    buf = io.StringIO()
    assert nexus_cli.executar(["--json", "diagnostico", str(arq), "--pergunta", "cor do carro"], out=buf) == 0 and json.loads(buf.getvalue())["reconhecida"] is False
    assert nexus_cli.executar(["diagnostico", str(tmp_path / "nao.nexus")], out=io.StringIO()) == 1
