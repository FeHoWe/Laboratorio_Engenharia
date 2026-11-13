"""V103 Fase D — comparação A/B de veículos."""
import pytest
from modules import veiculo_comparacao as VC, lapsim, lapsim_bicicleta as LB, dinamica_lateral as DL

CARRO = dict(massa=800.0, p_ice=500e3, cda=1.0, cla=3.0, mu=1.6, p_ers=300e3, e_ers=4e6)
BIC = dict(massa=800.0, a=1.6, b=1.7, h=0.3, p_ice=500e3, cda=1.0, cla=3.0, mu_f=1.6, mu_r=1.6)
LAT = dict(massa=800.0, a=1.6, b=1.7, iz=900.0, cf=120e3, cr=140e3)
FRE = {"disco_diant": dict(massa=1.4, cp=800.0, area=0.045), "disco_tras": dict(massa=1.1, cp=800.0, area=0.04), "voltas": 2}
A = {"carro": CARRO, "bicicleta": BIC, "lateral": LAT, "U_ms": 40, "freios": FRE}


def test_valores_batem_com_modulos_diretos_e_sinais():
    B = {**A, "carro": {**CARRO, "massa": 760.0}, "bicicleta": {**BIC, "massa": 760.0}, "lateral": {**LAT, "massa": 760.0}}
    r = VC.comparar(A, B)
    d = {x["metrica"]: x for x in r["linhas"]}
    assert d["tempo_volta_lapsim_s"]["A"] == pytest.approx(lapsim.volta(lapsim.Carro(**CARRO), None, 3.0).valores["tempo_s"])
    assert d["tempo_volta_bicicleta_s"]["B"] == pytest.approx(LB.volta(LB.CarroB(**B["bicicleta"]), None, 3.0).valores["tempo_s"])
    assert d["tempo_volta_lapsim_s"]["delta_B_menos_A"] < 0                         # menos massa → mais rápido
    assert d["tempo_volta_lapsim_s"]["delta_B_menos_A"] == pytest.approx(d["tempo_volta_lapsim_s"]["B"] - d["tempo_volta_lapsim_s"]["A"])
    g = DL.varredura_velocidade(DL.ParamsLat(**LAT), [40.0])[0]
    assert d["gradiente_subesterco_graus_por_g"]["A"] == pytest.approx(g["gradiente_subesterco_graus_por_g"])
    assert d["comportamento"]["delta_B_menos_A"] is None and isinstance(d["comportamento"]["A"], str)
    assert d["energia_frenagem_MJ"]["modelo"] == "freios" and "SUAS" in d["energia_frenagem_MJ"]["hipoteses"]
    assert all(x["hipoteses"] for x in r["linhas"]) and r["classe"] == "SIMULACAO_NUMERICA"


def test_bloco_que_so_uma_tem_vira_nota_nao_numero():
    B = {"carro": CARRO}
    r = VC.comparar(A, B)
    assert [x["metrica"] for x in r["linhas"]] == ["tempo_volta_lapsim_s"]
    assert any("tempo_volta_bicicleta_s" in n and "não comparável" in n for n in r["notas"]) and any("gradiente" in n for n in r["notas"])


def test_identicas_dao_delta_zero_e_texto():
    r = VC.comparar(A, A)
    assert all(x["delta_B_menos_A"] in (0, 0.0, None) for x in r["linhas"])
    t = VC.texto(r)
    assert "Comparação A/B" in t and "NÃO devem ser somados" in t and "hipotéticos" in t


def test_erros():
    with pytest.raises(ValueError, match="configuração B"): VC.comparar(A, {})
    with pytest.raises(ValueError, match="configuração A"): VC.comparar({"U_ms": 3}, A)
    with pytest.raises(TypeError): VC.comparar({"carro": {"zzz": 1}}, A)


def test_cli_e_exportacao(tmp_path):
    import io, json
    import nexus_cli
    pa, pb = tmp_path / "a.json", tmp_path / "b.json"
    pa.write_text(json.dumps({"carro": CARRO})); pb.write_text(json.dumps({"carro": {**CARRO, "massa": 780.0}}))
    saida = tmp_path / "c.pdf"; buf = io.StringIO()
    assert nexus_cli.executar(["--json", "comparar-veiculos", str(pa), str(pb), "--saida", str(saida)], out=buf) == 0
    d = json.loads(buf.getvalue()); assert d["linhas"][0]["delta_B_menos_A"] < 0 and saida.read_bytes()[:5] == b"%PDF-"
    assert nexus_cli.executar(["comparar-veiculos", str(pa), str(tmp_path / "nao.json")], out=io.StringIO()) == 1
    pb.write_text(json.dumps({"carro": {"zzz": 1}}))
    assert nexus_cli.executar(["comparar-veiculos", str(pa), str(pb)], out=io.StringIO()) == 1
