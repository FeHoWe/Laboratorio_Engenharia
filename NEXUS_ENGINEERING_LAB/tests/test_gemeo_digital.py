"""V105 Fase F — gêmeo digital leve."""
import numpy as np
import pytest
from modules import gemeo_digital as G


def test_levantamento_diferenca_e_estudos(motor_project):
    p = motor_project
    a = G.levantar(p)
    folhas = list(p.components.leaves())
    assert len(a) == len(folhas) >= 2 and all(v["massa_kg"] is None for v in a.values())      # sem material: massa desconhecida, não inventada
    assert G.levantar(p) == a and G.diferenca(a, G.levantar(p)) == []                        # determinístico
    p.components.set_material(folhas[0].id, "Aço carbono", recursive=False)
    b = G.levantar(p)
    ev = G.diferenca(a, b)
    assert {e["tipo"] for e in ev} == {"material", "massa"} and all(e["id"] == folhas[0].id for e in ev) and b[folhas[0].id]["massa_kg"] > 0
    est = [{"nome": "FEA biela", "componentes": [folhas[0].id]}, {"nome": "FEA outra", "componentes": [folhas[1].id]}, {"nome": "Massa total", "componentes": []},
           {"nome": "antigo", "componentes": [folhas[0].id], "valores": {"vm": 1.0}}]
    an = G.estudos_afetados(ev, est)
    assert [e["estado"] for e in an] == ["REFAZER", "VIGENTE", "REFAZER", "REFAZER"] and an[0]["motivos"] == [f"{folhas[0].name}: massa", f"{folhas[0].name}: material"]
    assert est[0].get("estado") is None and an[3]["valores"] == {"vm": 1.0}                    # originais intactos, valores preservados
    t = G.texto(ev, an)
    assert "REFAZER" in t and "NÃO foram apagados" in t and G.texto([]).startswith("Nenhuma")


def test_posicao_removida_adicionada():
    a = {"x": {"id": "x", "nome": "P", "material": None, "massa_kg": 1.0, "posicao": [0, 0, 0], "geometria": "g"}}
    b = {"x": {**a["x"], "posicao": [1, 0, 0], "massa_kg": 1.0 + 1e-12}, "y": {"id": "y", "nome": "Q", "material": None, "massa_kg": None, "posicao": [0, 0, 0], "geometria": "h"}}
    assert [(e["tipo"], e["id"]) for e in G.diferenca(a, b, carimbo=False)] == [("posicao", "x"), ("adicionada", "y")]
    assert [e["tipo"] for e in G.diferenca(b, a, carimbo=False)] == ["posicao", "removida"]


def test_impressao_digital_de_malha():
    from types import SimpleNamespace as NS
    v = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]], float); f = np.array([[0, 1, 2], [0, 1, 3]])
    c = NS(shape=None, mesh=NS(vertices=v, faces=f))
    h0 = G._fp_geometria(c)
    assert G._fp_geometria(NS(shape=None, mesh=NS(vertices=v.copy(), faces=f))) == h0
    v2 = v.copy(); v2[3, 2] = 1.5
    assert G._fp_geometria(NS(shape=None, mesh=NS(vertices=v2, faces=f))) != h0
    assert G._fp_geometria(NS(shape=None, mesh=None)) == "sem_geometria"
