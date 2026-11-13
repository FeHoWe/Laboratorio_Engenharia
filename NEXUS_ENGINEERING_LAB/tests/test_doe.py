"""V11–V14 — fatorial, Monte Carlo, Pareto, stint."""
import json
import shutil
import subprocess
import pytest
from dataclasses import replace
from modules import lapsim, doe as D

BASE = lapsim.Carro(800, 500e3, 1.0, 3.0, 1.6, p_ers=300e3, e_ers=4e6)
T = lambda c: lapsim.volta(c, None, 3.0).valores["tempo_s"]  # noqa: E731


@pytest.mark.skipif(not shutil.which("node"), reason="node ausente")
def test_prng_igual_ao_do_celular():
    js = json.loads(subprocess.check_output(["node", "-e", "function m(a){return function(){a|=0;a=a+0x6D2B79F5|0;let t=Math.imul(a^a>>>15,1|a);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296;}}const r=m(42),s=m(2**31+7),q=m(0);console.log(JSON.stringify([...Array(6)].map(()=>r()).concat([...Array(4)].map(()=>s()),[...Array(3)].map(()=>q()))));"], text=True))
    r, s, q = D.mulberry32(42), D.mulberry32(2 ** 31 + 7), D.mulberry32(0)
    py = [r() for _ in range(6)] + [s() for _ in range(4)] + [q() for _ in range(3)]
    assert py == js and all(0 <= x < 1 for x in py)


def test_fatorial_um_fator_igual_diferenca_direta():
    r = D.fatorial(BASE, ["massa"], 10)
    direto = T(replace(BASE, massa=880.0)) - T(replace(BASE, massa=720.0))
    assert r["principais"][0]["efeito_s"] == pytest.approx(direto) and r["execucoes"] == 2


def test_fatorial_dois_fatores_formulas_e_ordem():
    r = D.fatorial(BASE, ["massa", "mu"], 5)
    t = {(a, b): T(replace(BASE, massa=800 * (1 + .05 * a), mu=1.6 * (1 + .05 * b))) for a in (-1, 1) for b in (-1, 1)}
    em = ((t[1, -1] + t[1, 1]) - (t[-1, -1] + t[-1, 1])) / 2
    inter = ((t[1, 1] + t[-1, -1]) - (t[1, -1] + t[-1, 1])) / 2
    d = {tuple(x["fatores"]): x["efeito_s"] for x in r["ordenados"]}
    assert d[("massa",)] == pytest.approx(em) and d[("massa", "mu")] == pytest.approx(inter)
    assert d[("massa",)] > 0 > d[("mu",)]
    assert [abs(x["efeito_s"]) for x in r["ordenados"]] == sorted((abs(x["efeito_s"]) for x in r["ordenados"]), reverse=True)
    assert r["execucoes"] == 4 and r["tempo_min_s"] <= r["tempo_medio_s"] <= r["tempo_max_s"]


def test_fatorial_erros():
    for args in (([], 5), (["a"] * 2, 5), (["x"], 5), (["massa"], 0), (["massa"], 60), (list(("massa", "p_ice", "cda", "cla", "mu", "crr", "p_ers")), 5)):
        with pytest.raises(ValueError): D.fatorial(BASE, *args)
    with pytest.raises(ValueError, match="vale 0"): D.fatorial(replace(BASE, p_ers=0.0), ["p_ers"], 5)


def test_monte_carlo_repetivel_e_coerente():
    inc = {"mu": ("normal", 2), "massa": ("uniforme", 1)}
    a = D.monte_carlo(BASE, inc, 120, 7)
    b = D.monte_carlo(BASE, inc, 120, 7)
    c = D.monte_carlo(BASE, inc, 120, 8)
    assert a == b and a["media_s"] != c["media_s"]
    assert a["min_s"] <= a["p05_s"] <= a["p50_s"] <= a["p95_s"] <= a["max_s"] and a["desvio_s"] > 0
    assert a["media_s"] == pytest.approx(a["tempo_base_s"], abs=0.2)
    cor = {x["campo"]: x["correlacao"] for x in a["correlacoes"]}
    assert cor["mu"] < -0.8 and cor["massa"] > 0 and abs(cor["mu"]) >= abs(cor["massa"]) and a["correlacoes"][0]["campo"] == "mu"


def test_monte_carlo_uniforme_respeita_limites_e_sem_incerteza_nao_ha_dispersao():
    r = D.monte_carlo(BASE, {"massa": ("uniforme", 3)}, 80, 3)
    assert T(replace(BASE, massa=800 * 1.03)) >= r["min_s"] >= T(replace(BASE, massa=800 * 0.97)) - 1e-9 and r["max_s"] <= T(replace(BASE, massa=800 * 1.03)) + 1e-9


def test_monte_carlo_erros():
    for inc, n in (({}, 10), ({"x": ("normal", 1)}, 10), ({"mu": ("beta", 1)}, 10), ({"mu": ("normal", 0)}, 10), ({"mu": ("normal", 80)}, 10), ({"mu": ("normal", 1)}, 1)):
        with pytest.raises(ValueError): D.monte_carlo(BASE, inc, n)


def _dominado(p, q):
    return all(x <= y for x, y in zip(q, p)) and any(x < y for x, y in zip(q, p))


def test_pareto_frente_nao_dominada_e_tradeoff():
    r = D.pareto(BASE, {"e_ers": [0, 2e6, 4e6, 6e6], "p_ers": [100e3, 300e3]})
    assert r["avaliacoes"] == 8
    pts = [p["objetivos"] for p in r["pontos"]]
    for p in r["frente"]:
        assert not any(_dominado(p["objetivos"], q) for q in pts)
    for p in r["pontos"]:
        if p["dominado"]:
            assert any(_dominado(p["objetivos"], q) for q in pts)
    fr = [p["objetivos"] for p in r["frente"]]
    assert fr == sorted(fr) and len(fr) >= 2                                    # mais energia usada ↔ menos tempo
    assert all(fr[i][0] < fr[i + 1][0] and fr[i][1] > fr[i + 1][1] for i in range(len(fr) - 1))     # ordenada por tempo: mais lento ⇒ menos energia


def test_pareto_maximizar_velocidade_e_erros():
    r = D.pareto(BASE, {"cla": [2.0, 3.0, 4.0]}, ("tempo_s", "v_max_kmh"))
    assert r["frente"]
    for bad in (({}, ("tempo_s", "v_max_kmh")), ({"cla": [1]}, ("tempo_s",)), ({"cla": [1]}, ("tempo_s", "tempo_s")), ({"cla": [1]}, ("tempo_s", "xx")), ({"cla": []}, ("tempo_s", "v_max_kmh")), ({"x": [1]}, ("tempo_s", "v_max_kmh"))):
        with pytest.raises(ValueError): D.pareto(BASE, *bad)
    with pytest.raises(ValueError, match="máx. 2000"): D.pareto(BASE, {"mu": list(range(1, 60)), "massa": list(range(700, 760))})


def test_stint_taxas_do_usuario():
    r = D.stint(BASE, 5, {"massa": -10.0})
    t = [x["tempo_s"] for x in r["linhas"]]
    assert t == sorted(t, reverse=True) and r["melhor_volta"] == 5 and r["pior_volta"] == 1
    assert r["linhas"][0]["tempo_s"] == pytest.approx(T(BASE)) and r["total_s"] == pytest.approx(sum(t))
    assert r["linhas"][2]["parametros"]["massa"] == pytest.approx(780.0)
    g = D.stint(BASE, 4, {"mu": -0.02})
    assert g["pior_volta"] == 4
    for bad in ((0, {"massa": 1}), (3, {}), (3, {"x": 1}), (500, {"massa": 1})):
        with pytest.raises(ValueError): D.stint(BASE, *bad)


def test_textos():
    assert "Fatorial 2^2" in D.texto_fatorial(D.fatorial(BASE, ["massa", "mu"], 5))
    assert "Monte Carlo" in D.texto_mc(D.monte_carlo(BASE, {"mu": ("normal", 1)}, 10, 1))
    assert "Pareto" in D.texto_pareto(D.pareto(BASE, {"e_ers": [0, 4e6]}))
    assert "NÃO é modelo" in D.texto_stint(D.stint(BASE, 2, {"massa": -1}))


def test_especificacao_em_texto():
    tipo, r = D.executar_especificacao("fatorial", "massa, mu ; 5", BASE)
    assert tipo == "fatorial" and r["campos"] == ["massa", "mu"]
    tipo, r = D.executar_especificacao("monte_carlo", "mu=normal:2, massa=uniforme:1 ; n=20 ; semente=3", BASE)
    assert r["n"] == 20 and r["semente"] == 3 and r["incertezas"]["mu"] == ["normal", 2.0]
    # unidades da tela (MJ) viram J no solver
    tipo, r = D.executar_especificacao("pareto", "e_ers=0,2,4", BASE, escala={"e_ers": 1e6})
    assert sorted(p["parametros"]["e_ers"] for p in r["pontos"]) == [0.0, 2e6, 4e6]
    tipo, r = D.executar_especificacao("stint", "voltas=3 ; p_ice=-1", BASE, escala={"p_ice": 1e3})
    assert r["taxas_por_volta"] == {"p_ice": -1000.0} and r["voltas"] == 3
    for est, txt in (("fatorial", ""), ("monte_carlo", "mu"), ("monte_carlo", "mu=normal"), ("pareto", "e_ers"), ("stint", "massa=1"), ("stint", "voltas=x ; massa=1"), ("monte_carlo", "mu=normal:1 ; foo=2")):
        with pytest.raises(ValueError):
            D.executar_especificacao(est, txt, BASE)
