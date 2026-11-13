"""V6.2 — ajuste de várias variáveis a vários alvos (mínimos quadrados)."""
import pytest
from modules.cad_history import CadHistory, CadHistoryError
from tests.test_cad_nomes_restricoes import box


def peça():
    h = CadHistory(box())                      # caixa base do teste (40×40×10)
    h.definir("L", 5)
    h.definir("W", 5)
    h.add("box_add", x0=40, y0=0, z0=0, x1="=40+L", y1="=W", z1=10)
    return h


def test_duas_variaveis_dois_alvos():
    h = peça()
    r = h.ajustar_multi({"L": (1, 60), "W": (1, 40)}, [("dx", 70), ("dy", 40)])
    # dx = 40+L = 70 → L = 30 ; dy = max(40, W) = 40 → W qualquer ≤ 40 (sub-determinado em W): só L é fixado
    assert h.vars["L"] == pytest.approx(30, abs=1e-4) and r["convergiu"] and max(r["residuos_relativos"]) <= 1e-5


def test_volume_e_dimensao_determinado():
    h = peça()
    v0 = h.volume()
    # volume = base + L*W*10 ; alvo: L=20 e volume com W=8
    alvo_v = v0 - 5 * 5 * 10 + 20 * 8 * 10
    r = h.ajustar_multi({"L": (1, 60), "W": (1, 40)}, [("dx", 60), ("volume", alvo_v)])
    assert h.vars["L"] == pytest.approx(20, abs=1e-3) and h.vars["W"] == pytest.approx(8, abs=1e-2)
    assert r["determinacao"] == "determinado" and h.volume() == pytest.approx(alvo_v, rel=1e-5)


def test_incompativel_recusa_e_nao_altera():
    h = peça()
    antes = dict(h.vars)
    with pytest.raises(CadHistoryError, match="não atingiu"):
        h.ajustar_multi({"L": (1, 10)}, [("dx", 200)])           # L ≤ 10 → dx ≤ 50
    assert h.vars == antes


def test_erros_de_entrada_e_restricoes_preservadas():
    h = peça()
    h.restringir("L < 100")
    with pytest.raises(CadHistoryError, match="não existe"): h.ajustar_multi({"X": (0, 1)}, [("dx", 1)])
    with pytest.raises(CadHistoryError, match="métrica"): h.ajustar_multi({"L": (0, 1)}, [("massa", 1)])
    with pytest.raises(CadHistoryError, match="faixa"): h.ajustar_multi({"L": (5, 1)}, [("dx", 1)])
    with pytest.raises(CadHistoryError, match="ao menos"): h.ajustar_multi({}, [("dx", 1)])
    with pytest.raises(CadHistoryError, match="violada"): h.ajustar_multi({"L": (1, 200)}, [("dx", 190)])    # solução L=150 viola L < 100
    assert h.vars["L"] == 5 and h.restricoes == ["L < 100"]
