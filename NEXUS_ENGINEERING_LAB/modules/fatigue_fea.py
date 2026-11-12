"""Fadiga a partir do resultado do FEA (V3.6): usa a tensão de von Mises máxima do ESTUDO (ponto crítico) como σ_max do ciclo.

Entrada: `vm_max` (MPa, do TracedResult/FEA), razão de carga R = σ_min/σ_max, material (Su, Sy, Se' digitados), Se corrigido (MPa, de `fatigue.endurance_limit`
ou digitado). Von Mises é escalar e sem sinal: o ciclo é tratado como σ_max=vm_max, σ_min=R·vm_max (carga proporcional, um só ponto crítico).
LIMITES: (1) tensão em quina viva/ponto de aplicação de carga é singular e depende da malha — só use valor de região convergida e sem singularidade;
(2) von Mises sem sinal não distingue tração de compressão (R<0 vira σm menor); (3) não inclui Kf: se o FEA já resolve o entalhe, NÃO multiplique de novo.
Classe ANALITICO (critério sobre um resultado numérico). Se o resultado do FEA não for SIMULACAO_NUMERICA/VALIDADO, recusa.
"""
from __future__ import annotations

from . import fatigue as fa
from .result_trace import TracedResult


def avaliar(res: TracedResult, razao_R: float, mat: fa.FatigueMaterial, se_corrigido: float, regra: str = "Goodman") -> dict:
    if res.classe not in ("SIMULACAO_NUMERICA", "VALIDADO"):
        raise ValueError(f"resultado do FEA é {res.classe}: não há tensão para avaliar fadiga")
    vm = (res.valores or {}).get("vm_nodal_max_MPa", (res.valores or {}).get("vm_max_MPa"))
    if vm is None or vm <= 0:
        raise ValueError("resultado sem tensão de von Mises positiva")
    if not (-1.0 <= razao_R < 1.0):
        raise ValueError("razão R deve estar em [-1, 1)")
    mat.validate()
    smax, smin = vm, razao_R * vm
    sa, sm = (smax - smin) / 2.0, (smax + smin) / 2.0
    sf = fa.safety_factors(sa, max(sm, 0.0), se_corrigido, mat.su, mat.sy)
    sar = fa.equivalent_reversed(sa, max(sm, 0.0), mat.su, "Goodman" if regra not in ("Goodman", "Gerber", "SWT") else regra)
    N = fa.build_sn(mat, se_corrigido).life(sar)
    return {"sigma_max_MPa": smax, "sigma_a_MPa": sa, "sigma_m_MPa": sm, "coef_seguranca": sf, "sigma_ar_equiv_MPa": sar, "ciclos": N,
            "vida_infinita": N == float("inf"), "origem_tensao": "vm_nodal_max_MPa" if "vm_nodal_max_MPa" in (res.valores or {}) else "vm_max_MPa",
            "classe": "ANALITICO",
            "avisos": ["tensão de ponto crítico do FEA: confira singularidade/malha antes de confiar", "von Mises não distingue tração/compressão"]}
