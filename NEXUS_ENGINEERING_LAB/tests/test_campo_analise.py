"""V102 Fase C — campo de resultados e invalidação de estudos."""
import numpy as np
import pytest
from modules import campo_analise as CA, assinatura_estudo as AS, fea3d


def _viga():
    mesh = fea3d.box_mesh(100.0, 10.0, 10.0, 10, 2, 2)
    fixed = {i: (0, 1, 2) for i, p in enumerate(mesh.nodes) if p[0] < 1e-9}
    ext = [i for i, p in enumerate(mesh.nodes) if p[0] > 100 - 1e-9]
    loads = {i: (0.0, 0.0, -100.0 / len(ext)) for i in ext}
    u, vm, R, vol = fea3d.solve(mesh, 210000.0, 0.3, fixed, loads)
    cent = mesh.nodes[mesh.tets].mean(axis=1)
    return mesh, u, vm, cent


def test_regioes_criticas_na_viga_ficam_perto_do_engaste():
    mesh, u, vm, cent = _viga()
    r = CA.regioes_criticas(cent, vm, 0.8)
    assert r["n_elementos"] >= 1 and r["regioes"][0]["valor_max"] == pytest.approx(vm.max())
    assert r["regioes"][0]["centro"][0] < 30.0                       # tensão máxima de flexão no engaste (x=0), não na ponta
    assert sum(g["n_elementos"] for g in r["regioes"]) == r["n_elementos"] and all(vm[e] >= r["limiar"] for g in r["regioes"] for e in g["elementos"])
    assert CA.regioes_criticas(cent, vm, 1.0)["n_elementos"] >= 1


def test_regioes_separadas_viram_duas():
    c = np.array([[0, 0, 0], [1, 0, 0], [2, 0, 0], [100, 0, 0], [101, 0, 0], [102, 0, 0]], float)
    v = np.array([10, 9, 1, 8, 10, 1], float)
    r = CA.regioes_criticas(c, v, 0.75)
    assert len(r["regioes"]) == 2 and [g["n_elementos"] for g in r["regioes"]] == [2, 2]
    assert CA.regioes_criticas(c, np.zeros(6))["regioes"] == []


def test_consulta_deformada_e_escala():
    mesh, u, vm, cent = _viga()
    q = CA.consultar(mesh.nodes, np.linalg.norm(u, axis=1), [100, 5, 5], k=3)
    assert q[0]["distancia_mm"] <= q[1]["distancia_mm"] <= q[2]["distancia_mm"] and q[0]["valor"] > 0
    d = CA.deformada(mesh.nodes, u, 10.0)
    assert np.allclose(d["nos"], mesh.nodes + 10.0 * u) and "10×" in d["aviso"] and d["u_max_mm"] == pytest.approx(np.linalg.norm(u, axis=1).max())
    f = CA.fator_sugerido(mesh.nodes, u)
    assert np.linalg.norm(u * f, axis=1).max() == pytest.approx(0.1 * 100.0, rel=1e-9)
    e = CA.escala_de_cores(vm, maximo=vm.max() / 2)
    assert e["recortada"] and e["fora_da_escala"] > 0 and len(e["faixas"]) == 9
    assert not CA.escala_de_cores(vm)["recortada"]


def test_erros_campo():
    for f, args in ((CA.regioes_criticas, ([[0, 0, 0]], [1, 2])), (CA.regioes_criticas, ([[0, 0, 0]], [1.0], 0)), (CA.deformada, ([[0, 0, 0]], [[0, 0]])),
                    (CA.escala_de_cores, ([1.0, 2.0], 5, 5)), (CA.consultar, ([[0, 0, 0]], [1.0], [0, 0]))):
        with pytest.raises(ValueError): f(*args)
    with pytest.raises(ValueError, match="não finitos"): CA.escala_de_cores([1.0, float("nan")])


def test_assinatura_detecta_categoria_que_mudou_sem_apagar():
    ent = {"geometria": {"fp": "abc"}, "material": {"E": 210000.0, "nu": 0.3}, "contorno": {"fixos": [1, 2], "cargas": {"5": [0, 0, -100.0]}}, "malha": {"nx": 10}}
    s = AS.assinatura(ent)
    assert AS.comparar(s, AS.assinatura(ent))["estado"] == "VIGENTE"
    ent2 = {**ent, "material": {"E": 70000.0, "nu": 0.33}}
    c = AS.comparar(s, AS.assinatura(ent2))
    assert c["estado"] == "OBSOLETO" and c["mudou"] == ["material"] and "refaça" in c["motivo"]
    ent3 = {**ent, "contorno": {"fixos": [1, 2], "cargas": {"5": [0, 0, -101.0]}}, "malha": {"nx": 20}}
    assert AS.comparar(s, AS.assinatura(ent3))["mudou"] == ["contorno", "malha"]
    assert AS.comparar(s, AS.assinatura({**ent, "material": {"E": 210000.0 + 1e-6, "nu": 0.3}}))["estado"] == "VIGENTE"   # ruído abaixo de 9 dígitos
    assert AS.comparar(None, s)["estado"] == "SEM_VINCULO"
    with pytest.raises(ValueError, match="desconhecida"): AS.assinatura({"xx": 1})


def test_revisar_marca_sem_alterar_valores():
    ent = {"geometria": {"fp": "a"}, "material": {"E": 1.0}}
    res = [{"nome": "r1", "valores": {"vm": 5.0}, "assinatura": AS.assinatura(ent)}, {"nome": "antigo", "valores": {"vm": 9.0}}]
    obs = AS.revisar(res, AS.assinatura({"geometria": {"fp": "b"}, "material": {"E": 1.0}}))
    assert [r["nome"] for r in obs] == ["r1"] and res[0]["valores"] == {"vm": 5.0} and res[1]["estado_entradas"] == "SEM_VINCULO" and len(res) == 2
