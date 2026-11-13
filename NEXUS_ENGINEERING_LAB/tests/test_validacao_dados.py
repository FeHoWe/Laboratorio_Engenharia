"""V30 — validação contra telemetria do usuário (dados sintéticos só nos testes)."""
import pytest
from dataclasses import replace
from modules import lapsim, validacao_dados as V

C = lapsim.Carro(800, 500e3, 1.0, 3.0, 1.6, p_ers=300e3, e_ers=4e6)


def telemetria_de(carro, ds=3.0, escala_v=1.0, escala_s=1.0, com_tempo=False):
    r = lapsim.volta(carro, None, ds)
    d = {"s_m": [s * escala_s for s in r.valores["s_m"]], "v_kmh": [v * 3.6 * escala_v for v in r.valores["v_ms"]], "t_s": None}
    if com_tempo:
        t, acc = [0.0], 0.0
        for i in range(len(d["s_m"]) - 1):
            acc += 2 * (d["s_m"][i + 1] - d["s_m"][i]) / ((d["v_kmh"][i] + d["v_kmh"][i + 1]) / 3.6); t.append(acc)
        d["t_s"] = t
    return d


def test_mesmo_carro_erro_quase_zero_e_validado_com_tolerancia_do_usuario():
    r = V.validar(C, telemetria_de(C), tolerancias={"rmse_kmh": 1.0, "tempo_pct_abs": 1.0})
    m = r["metricas"]
    assert m["rmse_kmh"] < 1e-6 and abs(m["vies_kmh"]) < 1e-6 and m["correlacao"] > 0.99999 and abs(m["tempo_pct"]) < 1.0
    assert r["classe"] == "VALIDADO" and all(v["atende"] for v in r["veredito"])
    assert any("não generaliza" in x for x in r["limitacoes"]) and "telemetria do usuário" in r["validacao_ref"] and "rmse_kmh <= 1" in r["validacao_ref"]


def test_telemetria_amostrada_diferente_do_solver_tem_erro_de_interpolacao_pequeno():
    m = V.validar(C, telemetria_de(C, ds=5.0))["metricas"]
    assert 0 < m["rmse_kmh"] < 3 and abs(m["tempo_pct"]) < 1


def test_sem_tolerancias_nunca_declara_validado():
    r = V.validar(C, telemetria_de(C))
    assert r["classe"] == "SIMULACAO_NUMERICA" and r["veredito"] == [] and r["validacao_ref"] == "" and any("NÃO é declarado validado" in x for x in r["limitacoes"])


def test_medicao_mais_rapida_gera_vies_negativo_e_reprova():
    r = V.validar(C, telemetria_de(C, escala_v=1.05), tolerancias={"rmse_kmh": 3.0})
    assert r["metricas"]["vies_kmh"] < -5 and r["metricas"]["tempo_pct"] > 3 and r["classe"] == "SIMULACAO_NUMERICA"
    assert not r["veredito"][0]["atende"] and any("NÃO foi atendido" in x for x in r["limitacoes"])


def test_carro_diferente_mede_diferenca_real():
    rapido = telemetria_de(replace(C, cla=4.0, mu=1.8))
    r = V.validar(C, rapido)
    assert r["metricas"]["vies_kmh"] < 0 and r["metricas"]["rmse_kmh"] > 3


def test_tempo_pela_coluna_e_pela_integral_concordam():
    a = V.validar(C, telemetria_de(C, com_tempo=True))["metricas"]
    b = V.validar(C, telemetria_de(C))["metricas"]
    assert a["tempo_medido_s"] == pytest.approx(b["tempo_medido_s"], rel=1e-9) and "coluna" in a["origem_tempo_medido"] and "integral" in b["origem_tempo_medido"]


def test_odometro_com_escala_errada_avisa_e_normaliza():
    t = telemetria_de(C, escala_s=1.06)
    r = V.validar(C, t)
    assert any("difere" in x for x in r["avisos"])
    n = V.validar(C, t, normalizar_distancia=True)
    assert n["metricas"]["rmse_kmh"] < r["metricas"]["rmse_kmh"] and n["metricas"]["rmse_kmh"] < 1.0 and any("reescalada" in x for x in n["avisos"])


def test_setores_e_texto():
    r = V.validar(C, telemetria_de(replace(C, mu=1.4)), setores=4)
    assert len(r["setores"]) == 4 and r["setores"][0]["de_m"] == pytest.approx(0, abs=4)
    assert "RMSE" in V.texto(r) and "por setor" in V.texto(r)


def test_leitura_csv_formatos_e_erros(tmp_path):
    csv = V.para_csv_exemplo(C)
    assert "NÃO é telemetria real" in csv.splitlines()[0]
    t = V.ler_telemetria(csv)
    assert len(t["s_m"]) > 500 and t["v_kmh"][0] > 0
    f = tmp_path / "t.csv"; f.write_text("Distância (m);Velocidade [km/h]\n0;100\n10;110\n20;120\n", encoding="utf-8")
    assert V.ler_telemetria(f)["v_kmh"] == [100.0, 110.0, 120.0]
    g = V.ler_telemetria("distance_m;speed_ms;time_s\n0;30;0\n10;31;0,33\n20;32;0,65")
    assert g["v_kmh"][0] == pytest.approx(108.0) and g["t_s"] == pytest.approx([0, 0.33, 0.65])
    for texto, msg in (("a,b\n1,2\n3,4", "cabeçalho"), ("distancia_m,v_kmh\n0,100", "vazia"), ("distancia_m,v_kmh\n0,100\n5,x\n9,3", "inválido"),
                       ("distancia_m,v_kmh\n0,100\n0,110\n9,3", "crescer"), ("distancia_m,v_kmh\n0,100\n5,0\n9,3", "> 0"), ("distancia_m,v_kmh\n0,100\n5,nan\n9,3", "não finito")):
        with pytest.raises(V.TelemetriaError, match=msg):
            V.ler_telemetria(texto)


def test_tolerancia_desconhecida_e_pouca_sobreposicao():
    with pytest.raises(ValueError, match="desconhecida"): V.validar(C, telemetria_de(C), tolerancias={"xx": 1})
    curta = {"s_m": [0.0, 5.0, 10.0], "v_kmh": [100.0, 100.0, 100.0], "t_s": None}
    with pytest.raises(V.TelemetriaError, match="insuficiente"): V.validar(C, curta)
