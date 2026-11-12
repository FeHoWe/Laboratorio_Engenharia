import numpy as np, pytest
from modules import tire_fit as tf, vehicle_lateral as vl


def _dados(c, mu, n=40, ruido=0.0, amax=14, seed=1):
    r = np.random.default_rng(seed); out = []
    for al in np.linspace(-amax, amax, n):
        fz = 3000 + 2000 * r.random()
        out.append((al, fz, vl.pneu_fy(np.radians(al), fz, c, mu) * (1 + ruido * r.standard_normal())))
    return out


def test_recupera_parametros_sem_ruido():
    r = tf.ajustar(_dados(65000, 1.4))
    assert r["c_alpha_N_rad"] == pytest.approx(65000, rel=1e-3) and r["mu"] == pytest.approx(1.4, rel=1e-3) and r["mu_identificavel"]


def test_com_ruido_e_sem_saturacao_avisa():
    r = tf.ajustar(_dados(65000, 1.4, ruido=0.02))
    assert abs(r["c_alpha_N_rad"] / 65000 - 1) < 0.1 and r["rmse_N"] > 0
    r2 = tf.ajustar(_dados(65000, 1.4, amax=1.0))
    assert r2["mu_identificavel"] is False and "NÃO é identificável" in r2["aviso"]


def test_validacoes_e_csv(tmp_path):
    with pytest.raises(ValueError): tf.ajustar([(1, 3000, 100)] * 3)
    with pytest.raises(ValueError): tf.ajustar([(1, 3000, 100)] * 8)
    p = tmp_path / "x.csv"; p.write_text("a,b\n1,2\n")
    with pytest.raises(ValueError): tf.ler_csv(p)
    p.write_text("alpha_graus,fz_N,fy_N\n1,abc,3\n")
    with pytest.raises(ValueError): tf.ler_csv(p)
    d = _dados(60000, 1.3); p.write_text("alpha_graus,fz_N,fy_N\n" + "\n".join(",".join(map(str, x)) for x in d))
    assert tf.ajustar(tf.ler_csv(p))["n"] == 40
