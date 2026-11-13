"""V80 — energia de frenagem e térmica de disco."""
import math
import pytest
from modules import lapsim, freio_termico as F

C = lapsim.Carro(800, 500e3, 1.0, 3.0, 1.6, p_ers=300e3, e_ers=4e6)
DF = F.Disco(massa=1.4, cp=800.0, area=0.045)
DR = F.Disco(massa=1.1, cp=800.0, area=0.040)


def test_energia_de_frenagem_confere_com_energia_cinetica_numa_frenagem_isolada():
    # perfil: desacelera de 80 para 20 m/s sem arrasto/rolamento → E = ½ m (v0² − v1²)
    c = lapsim.Carro(1000, 1e5, 0.0, 0.0, 1.0, crr=0.0)
    ds = 1.0
    v, s = [], []
    x, vel = 0.0, 80.0
    while vel > 20.0:
        v.append(vel); s.append(x)
        vel = math.sqrt(max(vel ** 2 - 2 * 8.0 * ds, 400.0)); x += ds
    v.append(20.0); s.append(x)
    P = F.potencia_de_frenagem(c, s + [x + ds], v + [20.0])[: len(v) - 1]
    E = sum(p * 2 * ds / (v[i] + v[i + 1]) for i, p in enumerate(P))
    assert E == pytest.approx(0.5 * 1000 * (80 ** 2 - 20 ** 2), rel=2e-2)


def test_sem_troca_de_calor_a_temperatura_sobe_E_sobre_mcp():
    d = F.Disco(massa=1.4, cp=800.0, area=1e-9, h0=0.0, h1=0.0, emissividade=0.0)
    r = F.termica(C, d, F.Disco(massa=1.1, cp=800.0, area=1e-9, h0=0.0, h1=0.0, emissividade=0.0), freio_diant=0.6, voltas=1)
    dT_esperado = r["energia_diant_MJ"] * 1e6 / (1.4 * 800.0)
    assert r["voltas"][0]["T_fim_diant_C"] - 25.0 == pytest.approx(dT_esperado, rel=5e-3)
    dT_tras = r["energia_tras_MJ"] * 1e6 / (1.1 * 800.0)
    assert r["voltas"][0]["T_fim_tras_C"] - 25.0 == pytest.approx(dT_tras, rel=5e-3)


def test_repartição_e_conservacao():
    r = F.termica(C, DF, DR, 0.7, voltas=1)
    assert r["energia_diant_MJ"] + r["energia_tras_MJ"] == pytest.approx(r["energia_frenagem_MJ"]) and r["energia_diant_MJ"] == pytest.approx(0.7 * r["energia_frenagem_MJ"])
    assert r["energia_frenagem_MJ"] > 0 and r["potencia_pico_kW"] > 100


def test_resfriamento_leva_ao_ambiente_e_regime_com_varias_voltas():
    r = F.termica(C, DF, DR, 0.6, voltas=12, T0_C=25.0)
    picos = [x["T_pico_diant_C"] for x in r["voltas"]]
    assert picos[0] < picos[-1] and picos[-1] > 100                              # esquenta ao longo das voltas
    assert abs(picos[-1] - picos[-2]) < abs(picos[1] - picos[0])                 # e tende a um regime
    # mais troca de calor (h0 alto) → regime mais frio que o de referência
    frio = F.termica(C, F.Disco(massa=1.4, cp=800.0, area=0.045, h0=500.0), DR, 0.6, voltas=12)
    assert frio["voltas"][-1]["T_pico_diant_C"] < picos[-1]
    assert r["traco_ultima_volta"]["T_diant_C"][0] > 25 and len(r["traco_ultima_volta"]["s_m"]) == len(r["traco_ultima_volta"]["T_tras_C"])


def test_mais_massa_termica_menos_pico_e_mais_ventilacao_menos_pico():
    base = F.termica(C, DF, DR, 0.6, voltas=3)["voltas"][-1]["T_pico_diant_C"]
    pesado = F.termica(C, F.Disco(massa=2.8, cp=800.0, area=0.045), DR, 0.6, voltas=3)["voltas"][-1]["T_pico_diant_C"]
    vent = F.termica(C, F.Disco(massa=1.4, cp=800.0, area=0.045, h0=60.0, h1=4.0), DR, 0.6, voltas=3)["voltas"][-1]["T_pico_diant_C"]
    assert pesado < base and vent < base


def test_limite_do_usuario_gera_aviso_e_tempo_acima():
    d = F.Disco(massa=1.4, cp=800.0, area=0.045, lim_T_C=150.0)
    r = F.termica(C, d, DR, 0.6, voltas=3)
    assert any("limite SEU" in x for x in r["avisos"]) and max(x["s_acima_limite_diant"] for x in r["voltas"]) > 0
    r2 = F.termica(C, F.Disco(massa=1.4, cp=800.0, area=0.045, lim_T_C=5000.0), DR, 0.6, voltas=1)
    assert not any("limite SEU" in x for x in r2["avisos"]) and all(x["s_acima_limite_diant"] == 0 for x in r2["voltas"])


def test_erros_e_texto():
    for kw in (dict(freio_diant=1.0), dict(voltas=0), dict(voltas=500)):
        with pytest.raises(ValueError): F.termica(C, DF, DR, **{"freio_diant": 0.6, "voltas": 1, **kw})
    for bad in (F.Disco(0, 800, 0.04), F.Disco(1, 800, 0.04, emissividade=2), F.Disco(1, 800, 0.04, f_disco=0)):
        with pytest.raises(ValueError): F.termica(C, bad, DR)
    t = F.texto(F.termica(C, DF, DR, 0.6, voltas=2))
    assert "Freios" in t and "Não valida contra dados" in t


def test_cli_e_exportacao(tmp_path):
    import io, json
    import nexus_cli
    out = tmp_path / "f.json"
    buf = io.StringIO()
    rc = nexus_cli.executar(["--json", "freio-termico", "--disco-diant", "massa=1.4", "cp=800", "area=0.045", "--disco-tras", "massa=1.1", "cp=800", "area=0.04",
                             "--voltas", "2", "--saida", str(out)], out=buf)
    assert rc == 0
    d = json.loads(buf.getvalue())
    assert d["classe"] == "SIMULACAO_NUMERICA" and len(d["voltas"]) == 2 and out.exists()
    assert nexus_cli.executar(["freio-termico", "--disco-diant", "massa=1.4", "--disco-tras", "massa=1", "cp=800", "area=0.04"], out=io.StringIO()) == 1
