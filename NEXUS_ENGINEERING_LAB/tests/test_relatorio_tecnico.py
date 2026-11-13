"""V107 Fase G — relatório técnico consolidado."""
import json
import pytest
from modules import relatorio_tecnico as RT

EST = [{"nome": "FEA biela", "classe": "SIMULACAO_NUMERICA", "metodo": "Tet4 linear", "valores": {"vm_max_MPa": 123.4}, "entradas": {"E_MPa": 210000}, "premissas": ["material linear"],
        "limitacoes": ["Tet4 trava em flexão"]},
       {"nome": "viga analítica", "classe": "ANALITICO", "metodo": "Euler-Bernoulli", "valores": {"flecha_mm": 0.5}, "premissas": ["pequenas deformações"]}]


def test_catorze_secoes_sempre_presentes_e_nao_informado(motor_project):
    r = RT.montar(motor_project)
    assert list(r) == list(RT.SECOES) and len(RT.SECOES) == 14
    assert r["objetivo"] == RT.NI and r["contorno"] == RT.NI and r["metodo"] == RT.NI and r["resultados"] == RT.NI and r["graficos"] == RT.NI and r["imagens_3d"] == RT.NI
    assert "Nenhum critério de validação documentado" in r["criterios_validacao"] and r["conclusao"][0] == "Nenhum estudo foi fornecido: não há resultado para concluir."
    assert r["materiais"]["massa_parcial_kg"] == 0 and len(r["materiais"]["sem_material"]) == r["identificacao"]["pecas"] > 0
    assert any("sem material" in c for c in r["conclusao"])


def test_classes_nao_se_misturam_e_validado_exige_criterio(motor_project):
    est = EST + [{"nome": "ref", "classe": "VALIDADO", "valores": {"erro_pct": 1.0}, "validacao_ref": ""}]
    r = RT.montar(motor_project, "Verificar biela", est)
    assert set(r["resultados"]) == {"SIMULACAO_NUMERICA", "ANALITICO", "VALIDADO"} and r["resultados"]["ANALITICO"][0]["nome"] == "viga analítica"
    c = " ".join(r["conclusao"])
    assert "nenhum critério de validação foi documentado" in c and "sem referência de validação registrada: ref" in c
    r2 = RT.montar(motor_project, "x", est, criterios_validacao=["erro < 5 % contra ensaio X"])
    assert "nenhum critério" not in " ".join(r2["conclusao"]) and r2["criterios_validacao"] == ["erro < 5 % contra ensaio X"]
    assert sorted(r["hipoteses"]) == ["material linear", "pequenas deformações"] and r["metodo"] == ["Euler-Bernoulli", "Tet4 linear"] and "Tet4 trava em flexão" in r["limitacoes"]
    assert r["parametros"]["entradas_dos_estudos"] == {"FEA biela": {"E_MPa": 210000}}


def test_sem_validado_diz_estimativa(motor_project):
    assert any("Nenhum resultado foi validado" in c for c in RT.montar(motor_project, "x", EST)["conclusao"])


def test_exportacao_md_json_pdf_e_imagens(motor_project, tmp_path):
    png = tmp_path / "a.png"
    import base64
    png.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="))
    r = RT.montar(motor_project, "Obj", EST, imagens=[str(png), str(tmp_path / "sumiu.png")], contorno="engaste em x=0")
    assert r["imagens_3d"] == [str(png)] and any("sumiu.png" in x for x in r["limitacoes"])
    m = RT.exportar(r, tmp_path / "r.md").read_text(encoding="utf-8")
    assert all(t in m for t in RT.TITULOS.values()) and "engaste em x=0" in m and "123.4" in m
    j = json.loads(RT.exportar(r, tmp_path / "r.json").read_text(encoding="utf-8")); assert list(j) == list(RT.SECOES)
    assert RT.exportar(r, tmp_path / "r.pdf").read_bytes()[:5] == b"%PDF-"
    with pytest.raises(ValueError, match="extensão"): RT.exportar(r, tmp_path / "r.txt")


def test_cli_relatorio(motor_project, tmp_path):
    import io
    import nexus_cli
    import core.cad_engine as CE
    from core.project_manager import ProjectManager as PM
    arq = tmp_path / "m.nexus"; PM(CE.CadEngine()).save(motor_project, str(arq))
    est = tmp_path / "e.json"; est.write_text(json.dumps(EST))
    out = tmp_path / "r.pdf"; buf = io.StringIO()
    assert nexus_cli.executar(["--json", "relatorio", str(arq), "--saida", str(out), "--estudos", str(est), "--objetivo", "teste", "--criterio", "erro < 5 %"], out=buf) == 0
    d = json.loads(buf.getvalue()); assert d["secoes"] == list(RT.SECOES) and out.read_bytes()[:5] == b"%PDF-"
    assert nexus_cli.executar(["relatorio", str(arq), "--saida", str(tmp_path / "r.txt")], out=io.StringIO()) == 1
    assert nexus_cli.executar(["relatorio", str(tmp_path / "nao.nexus"), "--saida", str(out)], out=io.StringIO()) == 1
