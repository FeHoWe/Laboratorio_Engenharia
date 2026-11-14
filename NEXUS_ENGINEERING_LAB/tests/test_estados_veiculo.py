import math
import pytest
from modules import estados_veiculo as EV, vehicle_dynamics as VD, vehicle_lateral as VL


def test_longitudinal_posicao_integra_velocidade():
    v = VD.Veiculo(massa=300, cd=0.8, area=1.0, crr=0.015, forca_motriz=2000, potencia=60e3, mu=1.3)
    s = EV.longitudinal(v, 4.0, 0.01, frear_em=2.5, forca_freio=3000)
    L = s["linhas"]
    assert s["classe"] == "SIMULACAO_NUMERICA" and L[0][4] == 0 and max(l[4] for l in L) > 5
    x = sum(0.5 * (L[i][4] + L[i + 1][4]) * (L[i + 1][0] - L[i][0]) for i in range(len(L) - 1))
    assert x == pytest.approx(L[-1][1], rel=1e-6) and min(l[5] for l in L) < 0     # houve desaceleração após frear_em
    assert EV.para_csv(s).splitlines()[0] == ",".join(EV.CAMPOS)


def test_curva_trajetoria_e_quadros():
    s = EV.curva(VL.exemplo_ilustrativo(), 20.0, math.radians(2.0), 3.0)
    L = s["linhas"]
    assert L[-1][2] != 0 and L[-1][3] != 0 and abs(L[-1][8]) > 0                    # curvou: y, ψ e r diferentes de zero
    assert L[-1][2] * L[-1][3] > 0                                                   # sentido da curva coerente (y e ψ mesmo sinal)
    q = EV.quadros(s, 30)
    assert 2 <= len(q) <= 30 and q[0]["t_s"] == 0 and q[-1]["t_s"] == pytest.approx(L[-1][0])
    with pytest.raises(EV.EstadosError): EV.quadros(s, 1)
