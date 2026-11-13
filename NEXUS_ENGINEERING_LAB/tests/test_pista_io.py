"""V17 — leitura de pistas."""
import pytest
from modules import lapsim, pista_io as P


def test_formatos_cabecalho_comentarios_e_separadores():
    t = "# minha pista\ncomprimento_m,raio_m\n900,0\n80;60\n350\t0\n110, 35\n"
    assert P.ler_pista(t) == [(900.0, 0.0), (80.0, 60.0), (350.0, 0.0), (110.0, 35.0)]
    assert P.ler_pista("100;12,5\n200;0") == [(100.0, 12.5), (200.0, 0.0)]            # vírgula decimal com ;


def test_arquivo_ida_e_volta_e_roda_no_lapsim(tmp_path):
    f = tmp_path / "p.csv"
    f.write_text(P.para_csv(lapsim.PISTA_EXEMPLO), encoding="utf-8")
    p = P.ler_pista(f)
    assert p == [(float(a), float(b)) for a, b in lapsim.PISTA_EXEMPLO]
    c = lapsim.Carro(800, 500e3, 1.0, 3.0, 1.6)
    assert lapsim.volta(c, p, 3.0).valores["tempo_s"] == pytest.approx(lapsim.volta(c, None, 3.0).valores["tempo_s"])
    r = P.resumo(p)
    assert r["segmentos"] == 12 and r["comprimento_m"] == pytest.approx(3500) and r["raio_min_m"] == 25 and 0 < r["pct_reta"] < 100


@pytest.mark.parametrize("t,msg", [("", "nenhum"), ("# só comentário", "nenhum"), ("100", "use"), ("1,2,3", "use"), ("100,abc", "não numéricos"), ("0,10", "comprimento"), ("-5,0", "comprimento"),
                                   ("100,-3", "raio"), ("nan,3", "não numéricos|não finito"), ("inf,3", "não finito")])
def test_erros(t, msg):
    with pytest.raises(P.PistaError, match=msg):
        P.ler_pista(t)


def test_limite_de_segmentos():
    with pytest.raises(P.PistaError, match="segmentos"):
        P.ler_pista("\n".join("10,0" for _ in range(P.MAX_SEGMENTOS + 1)))
