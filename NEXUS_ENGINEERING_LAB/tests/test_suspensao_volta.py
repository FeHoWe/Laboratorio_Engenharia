import dataclasses
import pytest
from modules import lapsim_bicicleta as LB, suspension as S, suspensao_volta as SV

C = LB.CarroB(massa=300, a=0.8, b=0.7, h=0.30, p_ice=60e3, cda=0.8, cla=1.0, mu_f=1.4, mu_r=1.4, k_carga=0.2)
SU = S.exemplo_ilustrativo()


def test_transferencia_balanco_e_soma():
    t = SV.transferencia(C, 0.05, 0.08, 1.2, 1.2, 1.0, 0.5)
    L = C.a + C.b
    rc_cg = 0.05 + (0.08 - 0.05) * C.a / L
    total = C.massa * 9.80665 * 1.0 * (C.h) / 1.2                                # ΔFz total = m·ay·h/t se bitolas iguais
    # geométrica por eixo + elástica = m·ay·h/t quando RC_no_CG consistente com média ponderada
    assert t["dFz_diant_N"] + t["dFz_tras_N"] == pytest.approx(total, rel=0.05) and t["RC_no_CG_m"] == pytest.approx(rc_cg)
    with pytest.raises(SV.SuspensaoVoltaError): SV.transferencia(C, 0.05, 0.05, 1.2, 1.2, 1.0, 1.5)


def test_analise_e_limites():
    r = SV.analisar(C, SU, SU, 1.2, 1.2, 1.2, 0.55, rolagem_graus_por_g=1.0)
    assert r["classe"] == "SIMULACAO_NUMERICA" and r["delta_tempo_s"] > 0 and r["mu_f_efetivo"] < C.mu_f and 0 < r["fator_aderencia_diant"] < 1
    assert r["camber"]["externa_graus"] != r["camber"]["interna_graus"] and "NÃO entra" in r["camber"]["obs"]
    r0 = SV.analisar(dataclasses.replace(C, k_carga=0.0), SU, SU, 1.2, 1.2, 1.2)
    assert r0["delta_tempo_s"] == pytest.approx(0.0, abs=1e-9) and "zero por construção" in " ".join(r0["avisos"])
    assert "Suspensão→Volta" in SV.texto(r)
    with pytest.raises(SV.SuspensaoVoltaError, match="descola"): SV.analisar(C, SU, SU, 0.3, 0.3, 3.0)
