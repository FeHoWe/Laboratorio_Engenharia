"""Simulação de volta do veículo para rodar em PROCESSO ISOLADO (core.jobs.submit_python): entrada e retorno 100 % JSON.
Erros de entrada voltam como {"_erro": msg}. Mesmo cálculo de `lapsim_veiculo.volta` (classe ANALITICO); nada é inventado."""
from __future__ import annotations

from modules.nl_job import _py


def volta(veiculo: dict, p_ice: float, cda: float, ds: float = 6.0) -> dict:
    from modules import lapsim_veiculo as LV, vehicle_lateral as VL
    try:
        v = VL.VeiculoLateral(**veiculo)
        print("NEXUS_PROGRESS 5", flush=True)
        r = LV.volta(v, p_ice, cda, ds=ds)
    except (ValueError, TypeError, KeyError) as exc:
        return {"_erro": str(exc)}
    print("NEXUS_PROGRESS 100", flush=True)
    return _py({"valores": r.valores, "limitacoes": list(r.limitacoes), "premissas": list(r.premissas), "classe": r.classe})
