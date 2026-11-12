"""Integração CFD → Veículo (V3.6): leva Cd/ClA de um resultado de CFD para o modelo longitudinal, com a PROVENIÊNCIA e os alertas junto.

Recusa resultado NAO_EXECUTADO. Usa o Cd TOTAL estimado (pressão + atrito estimado) se existir; senão só pressão, e avisa que subestima.
O Cd é adimensional: para um carro em escala real passe `area_real` (a área de referência do CFD vale só para a escala simulada).
Nada é "validado" por passar por aqui: a classe e os limites do CFD seguem junto no campo `alertas`.
"""
from __future__ import annotations

from dataclasses import replace
from .vehicle_dynamics import Veiculo


def cd_do_cfd(out: dict) -> dict:
    """`out` = dicionário devolvido por `cfd_job.run_case` (chaves result, info, pressao, opcionalmente viscoso)."""
    res = out.get("result") or {}
    if res.get("classe") in (None, "NAO_EXECUTADO"):
        raise ValueError("CFD NAO_EXECUTADO: não há coeficientes para usar")
    alertas = list(res.get("limitacoes") or [])
    p = out.get("pressao") or {}; v = out.get("viscoso") or (res.get("valores") or {})
    if "cd_total_estimado" in v:
        cd, base = float(v["cd_total_estimado"]), "Cd total ESTIMADO (pressão + atrito de 1ª ordem)"
        cl = float(v.get("cl_total_estimado", p.get("cl_pressao", 0.0)))
    elif "cd_pressao" in p:
        cd, base, cl = float(p["cd_pressao"]), "Cd só de PRESSÃO (sem atrito: subestima)", float(p.get("cl_pressao", 0.0))
        alertas.append("sem atrito viscoso: Cd subestimado")
    else:
        raise ValueError("resultado sem Cd/Cl utilizável")
    info = out.get("info") or {}
    if info.get("bloqueio_pct", 0) > 5: alertas.append(f"bloqueio do domínio {info['bloqueio_pct']:.1f} % (>5 %)")
    return {"cd": cd, "cl": cl, "a_ref_m2": info.get("a_ref_m2"), "base": base, "classe_cfd": res.get("classe"), "alertas": alertas}


def veiculo_com_cfd(base: Veiculo, out: dict, area_real: float | None = None) -> tuple[Veiculo, dict]:
    c = cd_do_cfd(out)
    area = area_real if area_real else c["a_ref_m2"]
    if not area or area <= 0:
        raise ValueError("informe a área frontal real do veículo (o CFD não trouxe área de referência)")
    prov = dict(c, area_usada_m2=area, area_origem="informada pelo usuário" if area_real else "área de referência do CFD (escala simulada)")
    return replace(base, cd=c["cd"], area=float(area)), prov


def de_resultado_projeto(r: dict) -> dict:
    """Converte um resultado de CFD salvo no projeto (dict do TracedResult + vínculo) na forma aceita por `cd_do_cfd`."""
    if "CFD" not in str(r.get("nome", "")) and "OpenFOAM" not in str(r.get("solver", "")) and "cd_total_estimado" not in (r.get("valores") or {}) and "cd" not in (r.get("valores") or {}):
        raise ValueError("o resultado não parece ser de CFD")
    ent = r.get("entradas") or {}
    v = r.get("valores") or {}
    out = {"result": {"classe": r.get("classe"), "limitacoes": r.get("limitacoes") or [], "valores": v}, "info": {"a_ref_m2": ent.get("a_ref_m2"), "bloqueio_pct": ent.get("bloqueio_pct", 0)},
           "pressao": {}}
    if "cd_total_estimado" not in v and "cd_pressao" not in v and v.get("cd") is not None:
        out["pressao"] = {"cd_pressao": v["cd"], "cl_pressao": v.get("cl", 0.0)}
    return out
