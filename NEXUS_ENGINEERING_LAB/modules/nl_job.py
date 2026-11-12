"""Casos não lineares (CalculiX) para rodar em PROCESSO ISOLADO (core.jobs.submit_python): entrada e retorno 100 % JSON.

`run(caso, params)` despacha para `casos_nl`. Erros de entrada (ValueError/KeyError) voltam como {"_erro": msg} — o diálogo mostra "ERRO: …" sem
derrubar nada. Sem CalculiX o resultado traz classe NAO_EXECUTADO (nenhum número é inventado).
"""
from __future__ import annotations


def _py(x):
    """Converte numpy → tipos nativos para o JSON do job."""
    try:
        import numpy as np
    except Exception:  # noqa: BLE001
        return x
    if isinstance(x, dict):
        return {str(k): _py(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_py(v) for v in x]
    if isinstance(x, np.generic):
        return x.item()
    if isinstance(x, np.ndarray):
        return x.tolist()
    return x


def run(caso: str, params: dict) -> dict:
    print("NEXUS_PROGRESS 5", flush=True)
    from modules import casos_nl as CN
    try:
        if caso == "plastico":
            r = CN.barra_plastica(**params)
        elif caso == "serie":
            r = CN.serie_materiais(**params)
        elif caso == "contato":
            r = CN.blocos_contato(**params)
        elif caso == "contato2":
            p = dict(params)
            inf, sup = CN.peca_de_especificacao(p.pop("inferior")), CN.peca_de_especificacao(p.pop("superior"))
            r = CN.contato_duas_pecas(inf, sup, **p)
        else:
            raise ValueError(f"caso desconhecido: {caso!r}")
    except (ValueError, KeyError) as e:
        return {"_erro": str(e)}
    print("NEXUS_PROGRESS 100", flush=True)
    return _py(r)
