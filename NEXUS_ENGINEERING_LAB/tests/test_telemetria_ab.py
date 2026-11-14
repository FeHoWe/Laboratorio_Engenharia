"""V120 — F1 Telemetry Lab (dados): A×B, CSV mapeado, sincronização."""
import numpy as np
import pytest
from modules import lapsim, telemetria_ab as T

A = lapsim.Carro(800, 500e3, 1.0, 3.0, 1.6, p_ers=300e3, e_ers=4e6)
B = lapsim.Carro(780, 500e3, 1.0, 3.0, 1.6, p_ers=300e3, e_ers=4e6)


def test_ab_simulado_delta_setores_e_coerencia():
    pa, pb = T.perfil_simulado(A), T.perfil_simulado(B)
    assert pa["t_s"][-1] == pytest.approx(pa["tempo_volta_s"], rel=2e-3)              # tempo acumulado ≈ tempo do solver (trapézio vs. passo do solver)
    r = T.comparar(pa, pb)
    assert r["classe"] == "SIMULACAO_NUMERICA" and r["delta_volta_s"] < 0                # B mais leve → mais rápido (delta B−A negativo)
    assert sum(x["delta_s"] for x in r["setores"]) == pytest.approx(r["delta_volta_s"], abs=1e-9) and len(r["setores"]) == 3
    assert r["delta_volta_s"] == pytest.approx(pb["t_s"][-1] - pa["t_s"][-1])
    assert r["lat_A_ms2"] is not None and max(r["lat_A_ms2"]) > 5 and len(r["frenagem_A"]) >= 3 and all(z["v_saida_kmh"] < z["v_entrada_kmh"] for z in r["frenagem_A"])
    assert len(r["maiores_perdas_de_B"]) >= 1 and "Δ(B−A)" in T.texto(r)
    p = T.ponto(r, 1500.0); assert p["v_A_kmh"] > 0 and "lat_A_ms2" in p
    with pytest.raises(T.TelemetriaABError): T.ponto(r, 1e9)


def test_setores_do_usuario_e_erros():
    pa, pb = T.perfil_simulado(A), T.perfil_simulado(B)
    r = T.comparar(pa, pb, limites_setor_m=[500, 2000])
    assert [round(x["s_fim_m"]) for x in r["setores"]] == [500, 2000, 3501] or r["setores"][0]["s_fim_m"] == 500.0
    with pytest.raises(T.TelemetriaABError, match="fora da pista"): T.comparar(pa, pb, limites_setor_m=[10 ** 6])
    with pytest.raises(T.TelemetriaABError, match="MESMA grade"): T.comparar(pa, T.perfil_simulado(B, ds=5.0))


def test_csv_mapeado_unidades_e_sincronizacao():
    csv = "dist_km;vel_mph;tempo_ms\n0;100;0\n0,5;110;10000\n1,0;120;19000\n1,5;130;28000"
    t = T.ler_csv_mapeado(csv, "dist_km", "vel_mph", "km", "mph", "tempo_ms", "ms")
    assert t["s_m"] == [0.0, 500.0, 1000.0, 1500.0] and t["v_ms"][0] == pytest.approx(44.704) and t["t_s"] == [0.0, 10.0, 19.0, 28.0]
    g = T.sincronizar(t, ds=100.0)
    assert g["s_m"][0] == 0 and g["s_m"][-1] == 1500 and g["tempo_volta_s"] == pytest.approx(28.0) and g["classe"] == "TELEMETRIA_DO_USUARIO"
    for bad, msg in ((("a,b\n1,2\n2,3\n3,4", "x", "b"), "não existe"), (("a,b\n1,2\n2,3\n3,4", "a", "b", "xx"), "unidade")):
        with pytest.raises(T.TelemetriaABError, match=msg): T.ler_csv_mapeado(*bad)
    with pytest.raises(T.TelemetriaABError, match="cresc"): T.ler_csv_mapeado("a,b\n1,10\n1,11\n2,12\n3,13", "a", "b", "m", "ms")
    with pytest.raises(T.TelemetriaABError, match="> 0"): T.ler_csv_mapeado("a,b\n1,0\n2,3\n3,4\n4,5", "a", "b", "m", "ms")


def test_dois_csv_comparados_sem_aceleracao_lateral():
    def csv(k):
        return "d,v\n" + "\n".join(f"{x},{20 + k + 0.01 * x}" for x in range(0, 1001, 10))
    ta = T.sincronizar(T.ler_csv_mapeado(csv(0), "d", "v", "m", "ms"), 5.0, "A"); tb = T.sincronizar(T.ler_csv_mapeado(csv(1), "d", "v", "m", "ms"), 5.0, "B")
    r = T.comparar(ta, tb, 2)
    assert r["classe"] == "COMPARACAO_MISTA" and r["delta_volta_s"] < 0 and r["lat_A_ms2"] is None and "Telemetria simulada NÃO" in " ".join(r["avisos"])
    assert "lat_A_ms2" not in T.ponto(r, 500.0)


def test_cli_telemetria_ab(tmp_path):
    import io, json, nexus_cli
    for n, k in (("a", 0), ("b", 1)):
        (tmp_path / f"{n}.csv").write_text("d,v\n" + "\n".join(f"{x},{70 + 3 * k + 0.02 * x}" for x in range(0, 1001, 10)))
    out = io.StringIO()
    rc = nexus_cli.executar(["--json", "telemetria-ab", "--csv-a", str(tmp_path / "a.csv"), "--csv-b", str(tmp_path / "b.csv"), "--col-dist", "d", "--col-vel", "v", "--ds", "5"], out=out)
    d = json.loads(out.getvalue())
    assert rc == 0 and d["delta_volta_s"] < 0 and len(d["setores"]) == 3
    assert nexus_cli.executar(["telemetria-ab", "--csv-a", "nao.csv", "--csv-b", "x", "--col-dist", "d", "--col-vel", "v"], out=io.StringIO()) == 1
