from modules import referencias as R


def test_selos_e_aviso_honesto():
    r = R.rodar()
    assert all(c["ok"] for c in r["casos"]) and r["selos"]["CFD"] == "NAO_EXECUTADO"
    assert "NÃO é validação contra ensaio" in r["aviso"]
    assert {"Estrutural (vigas)", "Veículo (pneu)", "Veículo (suspensão)", "CAD (sketch)", "Fadiga"} <= set(r["selos"])
