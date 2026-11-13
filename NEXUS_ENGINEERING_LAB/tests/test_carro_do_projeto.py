"""V50 — ponte projeto CAD → carro."""
import pytest
from modules import carro_do_projeto as P, lapsim


def _atribuir(project, material="Aço carbono"):
    project.components.set_material(project.components.root.id, material, recursive=True)


def test_sem_material_nao_inventa(motor_project):
    with pytest.raises(ValueError, match="não atribui automaticamente"):
        P.levantar(motor_project, 0, 100)


def test_com_material_massa_cg_e_pisos(motor_project):
    _atribuir(motor_project)
    r = P.levantar(motor_project, -50.0, 150.0)
    assert r["classe"] == "ANALITICO" and r["massa_kg"] > 0 and r["n_pecas_cad"] >= 1 and r["pecas_ignoradas"] == []
    assert r["pct_dianteiro"] + r["pct_traseiro"] == pytest.approx(100.0)
    assert r["a_m"] + r["b_m"] == pytest.approx(r["entre_eixos_m"]) and r["entre_eixos_m"] == pytest.approx(0.2)
    assert any("extra" in x for x in r["avisos"])
    assert r["massa_kg"] == pytest.approx(sum(m for _, m, _ in P.f1_mass.items_from_components(motor_project.components, motor_project.materials)))


def test_peca_sem_material_fica_de_fora_e_e_listada(motor_project):
    folhas = list(motor_project.components.leaves())
    assert len(folhas) >= 2
    motor_project.components.set_material(folhas[0].id, "Aço carbono", recursive=False)
    r = P.levantar(motor_project, -50.0, 150.0)
    assert r["n_pecas_cad"] == 1 and len(r["pecas_ignoradas"]) == len(folhas) - 1 and any("PISO" in x for x in r["avisos"])


def test_extras_do_usuario_entram_com_posicao(motor_project):
    _atribuir(motor_project)
    base = P.levantar(motor_project, 0.0, 100.0)
    ext = P.levantar(motor_project, 0.0, 100.0, extras=[("Piloto", 75.0, (0.0, 80.0, 20.0))])
    assert ext["massa_kg"] == pytest.approx(base["massa_kg"] + 75.0) and ext["n_extras"] == 1 and not any("Nenhuma massa extra" in x for x in ext["avisos"])
    assert ext["pct_traseiro"] > base["pct_traseiro"] or ext["pct_dianteiro"] != base["pct_dianteiro"]
    with pytest.raises(ValueError, match="extra"): P.levantar(motor_project, 0, 100, extras=[("x", -1, (0, 0, 0))])


def test_carro_recebe_so_a_massa_e_texto(motor_project):
    _atribuir(motor_project)
    r = P.levantar(motor_project, -50.0, 150.0, extras=[("Lastro", 700.0, (0, 50, 10))])
    base = lapsim.Carro(800, 500e3, 1.0, 3.0, 1.6)
    c = P.carro_do_projeto(base, r)
    assert c.massa == pytest.approx(r["massa_kg"]) and (c.p_ice, c.cda, c.cla, c.mu) == (base.p_ice, base.cda, base.cla, base.mu)
    assert "Levantamento" in P.texto(r)


def test_cg_fora_do_entre_eixos_avisa(motor_project):
    _atribuir(motor_project)
    r = P.levantar(motor_project, 5000.0, 5100.0)
    assert any("fora do entre-eixos" in x for x in r["avisos"])
