"""V120 — Suspensão → Volta: leva a GEOMETRIA da suspensão (modules.suspension.DuploA) até o tempo de volta do modelo de bicicleta, em cadeia explícita e SIMPLIFICADA:

  geometria → altura do centro de rolagem (RC) por eixo → transferência lateral de carga (parte geométrica + elástica) em um ay de referência (SEU)
  → perda de aderência do eixo pela sensibilidade de carga do pneu (k_carga, SEU): μ_ef = μ0·(1 − k·(ΔFz/Fz_ref)²) (exato p/ μ linear na carga)
  → μ_f, μ_r efetivos → lapsim_bicicleta.volta  (comparado com a mesma volta sem transferência lateral).

Simplificações DECLARADAS: linearização num único ay de referência (a transferência real varia curva a curva); RC tomado em heave 0 (RC migra); distribuição de rigidez
de rolagem informada por você (fração dianteira); sem camber de pneu na aderência (camber é só REPORTADO, sem dado de pneu); massa não suspensa ≈ massa total;
com k_carga = 0 o efeito no tempo é ZERO por construção (pneu sem sensibilidade de carga). Classe: SIMULACAO_NUMERICA de um modelo reduzido, NÃO validado.
"""
from __future__ import annotations

import math

from . import lapsim_bicicleta as LB, suspension as S
from .lapsim import G

CLASSE = "SIMULACAO_NUMERICA"


class SuspensaoVoltaError(ValueError):
    pass


def transferencia(carro: LB.CarroB, rc_f: float, rc_r: float, bitola_f: float, bitola_r: float, ay_g: float, frac_rigidez_diant: float = 0.5) -> dict:
    """ΔFz por eixo (N) em ay_g (g): geométrica = m_eixo·ay·RC/bitola; elástica = m·ay·(h − RC_linha)·rigidez_eixo/bitola. Eixos têm massa estática por eixo."""
    if not 0 < frac_rigidez_diant < 1 or min(bitola_f, bitola_r) <= 0 or ay_g < 0:
        raise SuspensaoVoltaError("frac_rigidez_diant em (0,1), bitolas > 0, ay ≥ 0")
    L = carro.L
    mf, mr = carro.massa * carro.b / L, carro.massa * carro.a / L
    ay = ay_g * G
    # linha de rolagem (eixo de rolagem) → altura sob o CG por interpolação linear entre os RC dos eixos
    rc_cg = rc_f + (rc_r - rc_f) * (carro.a / L)
    braco = carro.h - rc_cg
    elast = carro.massa * ay * braco
    d_f = mf * ay * rc_f / bitola_f + elast * frac_rigidez_diant / bitola_f
    d_r = mr * ay * rc_r / bitola_r + elast * (1 - frac_rigidez_diant) / bitola_r
    return {"dFz_diant_N": d_f, "dFz_tras_N": d_r, "RC_no_CG_m": rc_cg, "braco_rolagem_m": braco, "Fz_ref_diant_N": mf * G / 2.0, "Fz_ref_tras_N": mr * G / 2.0}


def perda_aderencia(dFz: float, fz_roda: float, k: float) -> float:
    """Fração da capacidade lateral do eixo que sobra: 1 − k·(ΔFz/Fz_roda)². Se a roda interna descolar (ΔFz ≥ Fz_roda) levanta erro (modelo deixa de valer)."""
    if dFz >= fz_roda:
        raise SuspensaoVoltaError("roda interna descola neste ay (ΔFz ≥ Fz estática da roda): o modelo linear não vale")
    return 1.0 - k * (dFz / fz_roda) ** 2


def analisar(carro: LB.CarroB, susp_f: S.DuploA, susp_r: S.DuploA, bitola_f: float, bitola_r: float, ay_ref_g: float, frac_rigidez_diant: float = 0.5,
             rolagem_graus_por_g: float | None = None, pista=None, ds: float = 3.0) -> dict:
    rf, rr = S.resolver(susp_f, 0.0), S.resolver(susp_r, 0.0)
    if rf["RC_altura_m"] is None or rr["RC_altura_m"] is None:
        raise SuspensaoVoltaError("centro de rolagem indefinido (braços paralelos): informe uma geometria com IC finito")
    t = transferencia(carro, rf["RC_altura_m"], rr["RC_altura_m"], bitola_f, bitola_r, ay_ref_g, frac_rigidez_diant)
    kf = perda_aderencia(t["dFz_diant_N"], t["Fz_ref_diant_N"], carro.k_carga)
    kr = perda_aderencia(t["dFz_tras_N"], t["Fz_ref_tras_N"], carro.k_carga)
    import dataclasses
    c2 = dataclasses.replace(carro, mu_f=carro.mu_f * kf, mu_r=carro.mu_r * kr)
    base = LB.volta(carro, pista, ds).valores["tempo_s"]
    com = LB.volta(c2, pista, ds).valores["tempo_s"]
    camber = None
    if rolagem_graus_por_g is not None:
        heave = math.radians(rolagem_graus_por_g * ay_ref_g) * bitola_f / 2.0
        try:
            camber = {"externa_graus": S.resolver(susp_f, heave)["camber_graus"], "interna_graus": S.resolver(susp_f, -heave)["camber_graus"], "heave_roda_m": heave,
                      "obs": "camber dianteiro REPORTADO (heave ≈ φ·bitola/2); NÃO entra na aderência (sem dado de pneu)"}
        except ValueError as e:
            camber = {"erro": str(e)}
    return {"classe": CLASSE, "RC_diant_m": rf["RC_altura_m"], "RC_tras_m": rr["RC_altura_m"], **t, "fator_aderencia_diant": kf, "fator_aderencia_tras": kr,
            "mu_f_efetivo": c2.mu_f, "mu_r_efetivo": c2.mu_r, "tempo_sem_transferencia_s": base, "tempo_com_transferencia_s": com, "delta_tempo_s": com - base, "camber": camber,
            "avisos": ["Linearização em um único ay de referência; RC em heave 0.", "Sem camber na aderência; sem rigidezes reais (distribuição de rolagem informada por você).",
                       "k_carga = 0 → delta de tempo zero por construção." if carro.k_carga == 0 else "Efeito depende do k_carga SEU (sensibilidade de carga do pneu)."]}


def texto(r: dict) -> str:
    return (f"Suspensão→Volta — {r['classe']}\nRC dianteiro {r['RC_diant_m'] * 1000:.1f} mm · RC traseiro {r['RC_tras_m'] * 1000:.1f} mm · RC no CG {r['RC_no_CG_m'] * 1000:.1f} mm\n"
            f"ΔFz diant {r['dFz_diant_N']:.0f} N · tras {r['dFz_tras_N']:.0f} N · aderência diant {r['fator_aderencia_diant']:.4f} · tras {r['fator_aderencia_tras']:.4f}\n"
            f"Volta: {r['tempo_sem_transferencia_s']:.3f} s → {r['tempo_com_transferencia_s']:.3f} s (Δ {r['delta_tempo_s']:+.3f} s)\n" + "\n".join("⚠ " + a for a in r["avisos"]))
