"""V17 — Leitura/validação de pistas (CSV/texto): uma linha por segmento `comprimento_m, raio_m` (raio 0 = reta).

Aceita separador `,` `;` ou tabulação, cabeçalho opcional e linhas `#` de comentário. Valida só estrutura física (números finitos, comprimento > 0,
raio ≥ 0); NÃO diz se a pista é realista nem a identifica com um circuito. Pistas lidas aqui são DADOS SEUS; a pista de exemplo do NEXUS é sintética.
"""
from __future__ import annotations

import math
import re
from pathlib import Path

MAX_SEGMENTOS = 5000


class PistaError(ValueError):
    pass


def ler_pista(origem) -> list[tuple[float, float]]:
    """`origem`: texto com quebras de linha ou caminho de arquivo (str/Path existente)."""
    if isinstance(origem, Path) or (isinstance(origem, str) and "\n" not in origem and len(origem) < 4096 and Path(origem).is_file()):
        texto = Path(origem).read_text(encoding="utf-8-sig")
    else:
        texto = str(origem)
    pista = []
    for n, bruto in enumerate(texto.splitlines(), 1):
        ln = bruto.strip()
        if not ln or ln.startswith("#"):
            continue
        partes = [p.strip() for p in re.split(r"[;,\t]", ln.replace(",", ".") if ";" in ln or "\t" in ln else ln) if p.strip() != ""]
        if len(partes) != 2:
            raise PistaError(f"linha {n}: use 'comprimento_m, raio_m' (recebido '{bruto.strip()}')")
        try:
            c, r = float(partes[0].replace(",", ".")), float(partes[1].replace(",", "."))
        except ValueError:
            if not pista and n <= 3 and not any(ch.isdigit() for ch in ln):           # cabeçalho textual
                continue
            raise PistaError(f"linha {n}: valores não numéricos ('{bruto.strip()}')")
        if not (math.isfinite(c) and math.isfinite(r)):
            raise PistaError(f"linha {n}: valor não finito")
        if c <= 0:
            raise PistaError(f"linha {n}: comprimento deve ser > 0 (recebido {c:g})")
        if r < 0:
            raise PistaError(f"linha {n}: raio deve ser ≥ 0 (0 = reta; recebido {r:g})")
        pista.append((c, r))
        if len(pista) > MAX_SEGMENTOS:
            raise PistaError(f"mais de {MAX_SEGMENTOS} segmentos")
    if not pista:
        raise PistaError("nenhum segmento encontrado")
    return pista


def resumo(pista) -> dict:
    total = sum(c for c, _ in pista)
    curvas = [r for _, r in pista if r > 0]
    return {"segmentos": len(pista), "comprimento_m": total, "pct_reta": 100.0 * sum(c for c, r in pista if r == 0) / total,
            "raio_min_m": min(curvas) if curvas else None, "raio_max_m": max(curvas) if curvas else None}


def para_csv(pista) -> str:
    return "comprimento_m,raio_m\n" + "".join(f"{c:g},{r:g}\n" for c, r in pista)
