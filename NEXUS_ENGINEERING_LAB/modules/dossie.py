"""V90 — Dossiê reprodutível: registra ENTRADAS + semente + versões + hash do resultado e permite RE-EXECUTAR e conferir.

Um dossiê é um arquivo JSON (`.dossie.json`) com: tipo do estudo, parâmetros exatos, semente, versão do NEXUS, versões de Python/NumPy/SciPy, o resultado e o SHA-256 do resultado
(números arredondados a 9 algarismos significativos para o hash não depender de ruído de último bit). `verificar` re-executa com as MESMAS entradas e diz se o hash bate.
O dossiê prova REPRODUTIBILIDADE (mesmas entradas → mesma saída nesta versão/ambiente); NÃO prova que o modelo representa o carro real. Não altera o formato `.nexus`.
Tipos suportados: volta, tornado, otimizacao, montecarlo, fatorial, stint, freio_termico.
"""
from __future__ import annotations

import hashlib
import json
import platform
import re
from pathlib import Path

FORMATO = 1
TIPOS = ("volta", "tornado", "otimizacao", "montecarlo", "fatorial", "stint", "freio_termico")


class DossieError(ValueError):
    pass


def _versao_app() -> str:
    try:
        txt = (Path(__file__).resolve().parent.parent / "interface" / "main_window.py").read_text(encoding="utf-8")
        return re.search(r'APP_VERSION = "([\d.]+)"', txt).group(1)
    except Exception:
        return "desconhecida"


def _norm(x):
    if isinstance(x, float):
        return float(f"{x:.9g}")
    if isinstance(x, dict):
        return {str(k): _norm(v) for k, v in sorted(x.items(), key=lambda kv: str(kv[0]))}
    if isinstance(x, (list, tuple)):
        return [_norm(v) for v in x]
    return x


def hash_resultado(res) -> str:
    return hashlib.sha256(json.dumps(_norm(res), sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _carro(par):
    from . import lapsim
    d = dict(par.get("carro") or {})
    try:
        return lapsim.Carro(**d)
    except TypeError as exc:
        raise DossieError(f"carro: parâmetro desconhecido ou faltando ({exc})")


def _pista(par):
    return par.get("pista")  # lista de segmentos como o lapsim espera (ou None = sintética)


def executar(tipo: str, par: dict) -> dict:
    """Roda o estudo `tipo` com os parâmetros `par` e devolve o resultado (sem listas pesadas de trajetória)."""
    if tipo not in TIPOS:
        raise DossieError(f"tipo desconhecido: {tipo} (use {', '.join(TIPOS)})")
    from . import doe, freio_termico, lapsim, otimizacao
    ds = float(par.get("ds", 3.0))
    c = _carro(par)
    pista = _pista(par)
    if tipo == "volta":
        r = lapsim.volta(c, pista, ds)
        return {"classe": r.classe, "valores": {k: v for k, v in r.valores.items() if not isinstance(v, list)}}
    if tipo == "tornado":
        return otimizacao.tornado(c, par.get("campos"), float(par.get("pct", 5.0)), pista, ds)
    if tipo == "otimizacao":
        return otimizacao.otimizar(c, {k: tuple(v) for k, v in par["faixas"].items()}, pista, ds, par.get("k_cda_por_cla"), int(par.get("iter", 40)), int(par.get("semente", 0)))
    if tipo == "montecarlo":
        return doe.monte_carlo(c, {k: tuple(v) for k, v in par["incertezas"].items()}, int(par.get("n", 300)), int(par.get("semente", 1)), pista, ds)
    if tipo == "fatorial":
        return doe.fatorial(c, par["campos"], float(par.get("pct", 5.0)), pista, ds)
    if tipo == "stint":
        return doe.stint(c, int(par["voltas"]), par["taxas"], pista, ds)
    d = lambda k: freio_termico.Disco(**par[k])  # noqa: E731
    r = freio_termico.termica(c, d("disco_diant"), d("disco_tras"), float(par.get("freio_diant", 0.6)), pista, ds, int(par.get("voltas", 5)), float(par.get("t0", 25.0)), float(par.get("t_amb", 25.0)))
    r.pop("traco_ultima_volta", None)
    return r


def criar(tipo: str, par: dict, nota: str = "") -> dict:
    import numpy
    import scipy
    res = executar(tipo, par)
    return {"formato_dossie": FORMATO, "tipo": tipo, "parametros": par, "resultado": res, "sha256_resultado": hash_resultado(res), "nota": nota,
            "ambiente": {"nexus": _versao_app(), "python": platform.python_version(), "numpy": numpy.__version__, "scipy": scipy.__version__},
            "avisos": ["Prova reprodutibilidade (mesmas entradas → mesma saída), não validade do modelo.",
                       "Hash depende da versão do NEXUS e das bibliotecas numéricas; versões diferentes podem divergir sem que isso seja erro."]}


def salvar(d: dict, caminho) -> Path:
    p = Path(caminho)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    return p


def carregar(caminho) -> dict:
    try:
        d = json.loads(Path(caminho).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise DossieError(f"não foi possível ler o dossiê: {exc}")
    if not isinstance(d, dict) or d.get("formato_dossie") != FORMATO or not {"tipo", "parametros", "sha256_resultado"} <= set(d):
        raise DossieError("arquivo não é um dossiê NEXUS (formato_dossie 1)")
    return d


def verificar(d: dict) -> dict:
    """Re-executa e compara. `integro`: hash guardado == hash do resultado guardado (arquivo não foi adulterado); `reproduziu`: nova execução == hash guardado."""
    integro = hash_resultado(d.get("resultado")) == d["sha256_resultado"]
    novo = hash_resultado(executar(d["tipo"], d["parametros"]))
    amb = criar_ambiente()
    mesma = {k: amb[k] == (d.get("ambiente") or {}).get(k) for k in amb}
    return {"integro": integro, "reproduziu": novo == d["sha256_resultado"], "hash_guardado": d["sha256_resultado"], "hash_novo": novo, "ambiente_igual": mesma,
            "observacao": ("Reproduziu exatamente." if novo == d["sha256_resultado"] else "NÃO reproduziu" + (" — o ambiente/versões diferem, o que pode explicar a diferença." if not all(mesma.values()) else " no MESMO ambiente: investigue."))}


def criar_ambiente() -> dict:
    import numpy
    import scipy
    return {"nexus": _versao_app(), "python": platform.python_version(), "numpy": numpy.__version__, "scipy": scipy.__version__}


def texto(d: dict, v: dict | None = None) -> str:
    L = [f"Dossiê {d['tipo']} — SHA-256 {d['sha256_resultado'][:16]}… · NEXUS {d['ambiente']['nexus']} · Python {d['ambiente']['python']} · NumPy {d['ambiente']['numpy']} · SciPy {d['ambiente']['scipy']}"]
    if d.get("nota"):
        L.append("nota: " + d["nota"])
    if v:
        L.append(f"integridade do arquivo: {'ok' if v['integro'] else 'ADULTERADO/CORROMPIDO'} · reprodução: {'ok' if v['reproduziu'] else 'FALHOU'} — {v['observacao']}")
    return "\n".join(L + ["⚠ " + x for x in d["avisos"]])
