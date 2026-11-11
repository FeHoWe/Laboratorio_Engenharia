"""Incerteza de discretização por Richardson/GCI (Roache; Celik et al. 2008) para 3 malhas.

Honestidade: só calcula quando a sequência é MONOTÔNICA (convergência monotônica) e as diferenças não são nulas; do contrário devolve
`aplicavel=False` com o motivo — NÃO força uma ordem aparente nem uma incerteza.
"""
from __future__ import annotations

import math


def gci3(h: tuple, f: tuple, fs: float = 1.25) -> dict:
    """h = (h1, h2, h3) tamanhos CARACTERÍSTICOS (fino→grosso, h1<h2<h3); f = (f1, f2, f3) o mesmo ordenamento. Retorna ordem aparente p,
    valor extrapolado e GCI do fino (fração)."""
    h1, h2, h3 = h
    f1, f2, f3 = f
    if not (0 < h1 < h2 < h3):
        raise ValueError("h deve ser crescente (fino→grosso) e positivo")
    e21, e32 = f2 - f1, f3 - f2
    r21, r32 = h2 / h1, h3 / h2
    if e21 == 0 or e32 == 0:
        return {"aplicavel": False, "motivo": "diferenças nulas entre malhas (nada a extrapolar)"}
    if e32 / e21 <= 0:
        return {"aplicavel": False, "motivo": "convergência NÃO monotônica (oscilatória): GCI/Richardson não se aplicam", "e21": e21, "e32": e32}
    p = 2.0
    for _ in range(200):                                              # ponto fixo (Celik et al. 2008, eq. 3.2–3.4), razão r pode diferir
        q = math.log((r21 ** p - 1) / (r32 ** p - 1))
        pn = abs(math.log(abs(e32 / e21)) + q) / math.log(r21)
        if abs(pn - p) < 1e-10:
            p = pn
            break
        p = pn
    f_ext = (r21 ** p * f1 - f2) / (r21 ** p - 1)
    ea = abs((f1 - f2) / f1)
    gci = fs * ea / (r21 ** p - 1)
    return {"aplicavel": True, "ordem_aparente": p, "valor_extrapolado": f_ext, "gci_fino": gci, "erro_relativo_aprox": ea,
            "razao_refino": [r21, r32], "obs": "ordem aparente fora de ~[0,5; 3] indica sequência pouco confiável" if not 0.5 <= p <= 3 else ""}
