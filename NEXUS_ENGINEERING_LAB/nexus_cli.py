"""V6.1 — NEXUS em linha de comando (sem interface gráfica): diagnóstico, volta, comparação A/B, sensibilidade, otimização e verificação de projeto.

Uso:  python nexus_cli.py <comando> [opções]      (--json imprime o resultado completo em JSON)
  doctor                                   estado do ambiente (Python, bibliotecas, motores)
  volta     [--carro k=v ...]              simulação de volta (lapsim)
  comparar  [--carro k=v ...] --b k=v ...  A/B: B muda só o que for informado
  tornado   [--carro k=v ...] [--pct 5]    sensibilidade ±pct por parâmetro
  otimizar  [--carro k=v ...] --faixa campo=lo:hi ... [--k-cda-por-cla K] [--iter N]
  fatorial  [--carro k=v ...] --campos massa mu ... [--pct 5]          fatorial 2^k: efeitos e interações
  montecarlo [--carro k=v ...] --inc mu=normal:2 massa=uniforme:1 [--n 300] [--semente 1]
  pareto    [--carro k=v ...] --grade e_ers=0,2e6,4e6 p_ers=1e5,3e5 [--objetivos tempo_s energia_ers_usada_MJ]
  stint     [--carro k=v ...] --voltas 10 --taxa massa=-1.5 mu=-0.002   (taxas por volta SUAS)
  Todos os comandos de volta aceitam --pista arquivo.csv (comprimento_m, raio_m; raio 0 = reta).
  verificar arquivo.nexus                  consistência do projeto (regras; nada estimado)
Parâmetros do carro (padrão = exemplo ILUSTRATIVO): massa, p_ice (W), cda, cla, mu, crr, p_ers (W), e_ers (J). Classes: SIMULACAO_NUMERICA / ANALITICO.
Código de saída: 0 ok · 1 erro de uso/entrada · 2 verificar: achado CRITICO.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

EXEMPLO = dict(massa=800.0, p_ice=500e3, cda=1.0, cla=3.0, mu=1.6, p_ers=300e3, e_ers=4e6)


def _kv(itens, nome):
    out = {}
    for s in itens or []:
        if "=" not in s:
            raise ValueError(f"{nome}: use campo=valor (recebido '{s}')")
        k, v = s.split("=", 1)
        try:
            out[k.strip()] = float(v.replace(",", "."))
        except ValueError:
            raise ValueError(f"{nome}: valor inválido em '{s}'")
    return out


def _carro(itens):
    from modules import lapsim
    d = dict(EXEMPLO)
    d.update(_kv(itens, "--carro"))
    try:
        return lapsim.Carro(**d)
    except TypeError as exc:
        raise ValueError(f"--carro: parâmetro desconhecido ({exc})")


def _faixas(itens):
    out = {}
    for s in itens or []:
        try:
            k, r = s.split("=", 1)
            lo, hi = r.split(":", 1)
            out[k.strip()] = (float(lo), float(hi))
        except ValueError:
            raise ValueError(f"--faixa: use campo=lo:hi (recebido '{s}')")
    return out


def _listas(itens, nome):
    out = {}
    for s_ in itens or []:
        try:
            k, v = s_.split("=", 1)
            out[k.strip()] = [float(x) for x in v.split(",") if x.strip()]
        except ValueError:
            raise ValueError(f"{nome}: use campo=v1,v2,… (recebido '{s_}')")
        if not out[k.strip()]:
            raise ValueError(f"{nome}: lista vazia em '{s_}'")
    return out


def _incertezas(itens):
    out = {}
    for s_ in itens or []:
        try:
            k, r = s_.split("=", 1)
            d, p = r.split(":", 1)
            out[k.strip()] = (d.strip(), float(p))
        except ValueError:
            raise ValueError(f"--inc: use campo=normal:pct ou campo=uniforme:pct (recebido '{s_}')")
    return out


def _pista(a):
    if getattr(a, "pista", None):
        from modules import pista_io
        return pista_io.ler_pista(Path(a.pista))
    return None


def _json_seguro(o):
    from dataclasses import asdict, is_dataclass
    if is_dataclass(o) and not isinstance(o, type):
        return asdict(o)
    return str(o)


def _exportar(a, tipo, estudo):
    if getattr(a, "saida", None):
        from modules import estudos_export
        estudos_export.exportar(tipo, estudo, a.saida)


def executar(argv=None, out=None) -> int:
    out = out or sys.stdout
    p = argparse.ArgumentParser(prog="nexus_cli", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--json", action="store_true", help="imprime o resultado completo em JSON")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor")
    for nome in ("volta", "comparar", "tornado", "otimizar", "fatorial", "montecarlo", "pareto", "stint"):
        s = sub.add_parser(nome)
        s.add_argument("--carro", nargs="*", metavar="k=v")
        s.add_argument("--ds", type=float, default=3.0)
        s.add_argument("--pista", metavar="arquivo.csv")
        if nome == "fatorial":
            s.add_argument("--campos", nargs="+", required=True)
            s.add_argument("--pct", type=float, default=5.0)
        if nome == "montecarlo":
            s.add_argument("--inc", nargs="+", metavar="campo=dist:pct", required=True)
            s.add_argument("--n", type=int, default=300)
            s.add_argument("--semente", type=int, default=1)
        if nome == "pareto":
            s.add_argument("--grade", nargs="+", metavar="campo=v1,v2", required=True)
            s.add_argument("--objetivos", nargs=2, default=["tempo_s", "energia_ers_usada_MJ"])
        if nome == "stint":
            s.add_argument("--voltas", type=int, required=True)
            s.add_argument("--taxa", nargs="+", metavar="campo=taxa", required=True)
        if nome != "volta":
            s.add_argument("--saida", metavar="arquivo.{csv,json,pdf}", help="exporta o estudo")
        if nome == "comparar":
            s.add_argument("--b", nargs="+", metavar="k=v", required=True)
        if nome == "tornado":
            s.add_argument("--pct", type=float, default=5.0)
        if nome == "otimizar":
            s.add_argument("--faixa", nargs="+", metavar="campo=lo:hi", required=True)
            s.add_argument("--k-cda-por-cla", type=float, default=None)
            s.add_argument("--iter", type=int, default=40)
    v = sub.add_parser("verificar")
    v.add_argument("arquivo")
    try:
        a = p.parse_args(argv)
    except SystemExit as e:
        return 1 if e.code else 0

    def emit(texto, dados):
        print(json.dumps(dados, ensure_ascii=False, indent=1, default=_json_seguro) if a.json else texto, file=out)

    try:
        if a.cmd == "doctor":
            from core import doctor
            cs = doctor.run_all()
            emit(doctor.report_text(cs), [{"nome": c.nome, "estado": c.estado, "versao": c.versao} for c in cs])
        elif a.cmd == "volta":
            from modules import lapsim
            r = lapsim.volta(_carro(a.carro), _pista(a), a.ds)
            vv = r.valores
            emit(f"Volta — {r.classe} ({r.solver} {r.solver_versao})\n  tempo {vv['tempo_s']:.3f} s · v média {vv['v_media_kmh']:.1f} km/h · máx {vv['v_max_kmh']:.1f} · mín {vv['v_min_kmh']:.1f}"
                 f" · energia elétrica {vv['energia_ers_usada_MJ']:.2f} MJ · {vv['comprimento_m']:.0f} m\n" + "\n".join("⚠ " + x for x in r.limitacoes),
                 {"classe": r.classe, "valores": {k: x for k, x in vv.items() if not isinstance(x, list)}, "limitacoes": r.limitacoes})
        elif a.cmd == "comparar":
            from modules import comparacao
            A = _carro(a.carro)
            B = replace(A, **_kv(a.b, "--b"))
            c = comparacao.comparar_voltas(A, B, _pista(a), a.ds)
            _exportar(a, "comparacao", c)
            emit(comparacao.texto(c), {k: x for k, x in c.items() if not k.startswith("resultado_") and k != "delta_tempo_ao_longo_da_pista"})
        elif a.cmd == "tornado":
            from modules import otimizacao
            t = otimizacao.tornado(_carro(a.carro), None, a.pct, _pista(a), a.ds)
            _exportar(a, "tornado", t)
            emit(otimizacao.texto_tornado(t), t)
        elif a.cmd == "otimizar":
            from modules import otimizacao
            o = otimizacao.otimizar(_carro(a.carro), _faixas(a.faixa), _pista(a), a.ds, a.k_cda_por_cla, a.iter)
            _exportar(a, "otimizacao", o)
            emit(otimizacao.texto_otimizacao(o), o)
        elif a.cmd == "fatorial":
            from modules import doe
            r = doe.fatorial(_carro(a.carro), a.campos, a.pct, _pista(a), a.ds)
            _exportar(a, "fatorial", r)
            emit(doe.texto_fatorial(r), r)
        elif a.cmd == "montecarlo":
            from modules import doe
            r = doe.monte_carlo(_carro(a.carro), _incertezas(a.inc), a.n, a.semente, _pista(a), a.ds)
            _exportar(a, "monte_carlo", r)
            emit(doe.texto_mc(r), r)
        elif a.cmd == "pareto":
            from modules import doe
            r = doe.pareto(_carro(a.carro), _listas(a.grade, "--grade"), tuple(a.objetivos), _pista(a), a.ds)
            _exportar(a, "pareto", r)
            emit(doe.texto_pareto(r), {k: x for k, x in r.items() if k != "pontos"})
        elif a.cmd == "stint":
            from modules import doe
            r = doe.stint(_carro(a.carro), a.voltas, _kv(a.taxa, "--taxa"), _pista(a), a.ds)
            _exportar(a, "stint", r)
            emit(doe.texto_stint(r), r)
        elif a.cmd == "verificar":
            from core.cad_engine import CadEngine
            from core.project_manager import ProjectManager
            from modules.intelligence import verificar_projeto
            proj = ProjectManager(CadEngine()).open(a.arquivo)
            par = verificar_projeto(proj)
            emit(par.texto(), {"titulo": par.titulo, "resumo": par.resumo, "pior": par.pior(),
                               "achados": [{"nivel": x.nivel, "texto": x.texto, "evidencia": x.evidencia} for x in par.achados]})
            return 2 if par.pior() == "CRITICO" else 0
    except Exception as exc:   # entrada inválida ou falha do solver: mensagem curta, sem traceback
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(executar())
