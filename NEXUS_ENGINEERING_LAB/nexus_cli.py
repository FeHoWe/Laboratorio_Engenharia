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
  validar   [--carro k=v ...] --telemetria arq.csv [--tol rmse_kmh=3 tempo_pct_abs=1 ...] [--normalizar] [--setores 5]   compara com telemetria REAL sua
  calibrar  [--carro k=v ...] --telemetria arq.csv --param mu=1.2:1.9 cla=2:5 [--treino 0.7]   ajusta parâmetros EFETIVOS à telemetria
  projeto-carro arq.nexus --eixos y_diant_mm y_tras_mm [--extra Piloto=75@0,80,20 ...] [--volta] [--carro k=v ...]   massa/CG do projeto (só peças COM material) → carro
  volta-bicicleta [--carro k=v ...] [--tracao traseira|integral] [--freio-diant 0.6]   modelo de bicicleta (a, b, h, mu_f, mu_r, bal_aero, k_carga…)
  freio-termico --disco-diant massa=1.4 cp=800 area=0.045 --disco-tras massa=1.1 cp=800 area=0.04 [--voltas 5]   energia de frenagem e temperatura de disco (propriedades SUAS)
  dossie criar espec.json --saida x.dossie.json | dossie verificar x.dossie.json   dossiê reprodutível (entradas+semente+versões+hash; re-executa e confere)
  dinamica-lateral --massa 800 --a 1.6 --b 1.7 --iz 900 --cf 120000 --cr 140000 [--u 20 40 60] [--delta 0.02] [--t 3]   bicicleta linear 2 GDL (Cf, Cr SEUS) ; ou --projeto arq.nexus --eixos y_d y_t
  formato-telemetria                        imprime um CSV de exemplo do formato (gerado pelo simulador; NÃO é telemetria real)
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

EXEMPLO_B = dict(massa=800.0, a=1.6, b=1.7, h=0.30, p_ice=500e3, cda=1.0, cla=3.0, mu_f=1.6, mu_r=1.6, bal_aero=0.45, p_ers=300e3, e_ers=4e6)   # ILUSTRATIVO
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
    for nome in ("volta", "comparar", "tornado", "otimizar", "fatorial", "montecarlo", "pareto", "stint", "validar", "calibrar"):
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
        if nome == "validar":
            s.add_argument("--telemetria", required=True, metavar="arq.csv")
            s.add_argument("--tol", nargs="*", metavar="criterio=limite")
            s.add_argument("--normalizar", action="store_true")
            s.add_argument("--setores", type=int, default=5)
        if nome == "calibrar":
            s.add_argument("--telemetria", required=True, metavar="arq.csv")
            s.add_argument("--param", nargs="+", required=True, metavar="campo=lo:hi")
            s.add_argument("--treino", type=float, default=1.0)
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
    sub.add_parser("formato-telemetria")
    ds_ = sub.add_parser("dossie")
    ds_.add_argument("acao", choices=["criar", "verificar"])
    ds_.add_argument("arquivo", help="criar: especificação JSON {tipo, parametros, nota}; verificar: arquivo .dossie.json")
    ds_.add_argument("--saida", metavar="arq.dossie.json")
    ft = sub.add_parser("freio-termico")
    ft.add_argument("--carro", nargs="*", metavar="k=v")
    ft.add_argument("--disco-diant", nargs="+", metavar="k=v", required=True, help="massa=kg cp=J/kgK area=m2 [h0= h1= emissividade= f_disco= lim_T_C=]")
    ft.add_argument("--disco-tras", nargs="+", metavar="k=v", required=True)
    ft.add_argument("--freio-diant", type=float, default=0.6)
    ft.add_argument("--voltas", type=int, default=5)
    ft.add_argument("--t0", type=float, default=25.0)
    ft.add_argument("--t-amb", type=float, default=25.0)
    ft.add_argument("--pista", metavar="arquivo.csv")
    ft.add_argument("--ds", type=float, default=3.0)
    ft.add_argument("--saida", metavar="arquivo.{csv,json,pdf}")
    dl = sub.add_parser("dinamica-lateral")
    for k_ in ("massa", "a", "b", "iz", "cf", "cr"):
        dl.add_argument("--" + k_, type=float)
    dl.add_argument("--u", nargs="+", type=float, default=[30.0])
    dl.add_argument("--delta", type=float, default=0.02)
    dl.add_argument("--t", type=float, default=3.0)
    dl.add_argument("--projeto", metavar="arq.nexus")
    dl.add_argument("--eixos", nargs=2, type=float, metavar=("Y_DIANT", "Y_TRAS"))
    dl.add_argument("--saida", metavar="arquivo.{csv,json,pdf}")
    vb = sub.add_parser("volta-bicicleta")
    vb.add_argument("--carro", nargs="*", metavar="k=v")
    vb.add_argument("--tracao", default="traseira", choices=["traseira", "integral"])
    vb.add_argument("--freio-diant", type=float, default=None)
    vb.add_argument("--pista", metavar="arquivo.csv")
    vb.add_argument("--ds", type=float, default=3.0)
    pc = sub.add_parser("projeto-carro")
    pc.add_argument("arquivo")
    pc.add_argument("--eixos", nargs=2, type=float, required=True, metavar=("Y_DIANT", "Y_TRAS"))
    pc.add_argument("--extra", nargs="*", metavar="nome=kg@x,y,z")
    pc.add_argument("--volta", action="store_true", help="roda a volta com a massa do projeto (demais parâmetros de --carro)")
    pc.add_argument("--carro", nargs="*", metavar="k=v")
    pc.add_argument("--ds", type=float, default=3.0)
    pc.add_argument("--bicicleta", action="store_true", help="roda o modelo de bicicleta com massa, a, b e h DO PROJETO (demais parâmetros de --carro)")
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
        elif a.cmd == "validar":
            from modules import validacao_dados as VD
            r = VD.validar(_carro(a.carro), VD.ler_telemetria(Path(a.telemetria)), _pista(a), a.ds, _kv(a.tol, "--tol") or None, a.normalizar, a.setores)
            _exportar(a, "validacao", r)
            emit(VD.texto(r), {k: x for k, x in r.items() if k != "comparacao"})
        elif a.cmd == "calibrar":
            from modules import calibracao as KB, validacao_dados as VD
            r = KB.calibrar(_carro(a.carro), _faixas(a.param), VD.ler_telemetria(Path(a.telemetria)), _pista(a), a.ds, a.treino)
            _exportar(a, "calibracao", r)
            emit(KB.texto(r), r)
        elif a.cmd == "projeto-carro":
            from core.cad_engine import CadEngine
            from core.project_manager import ProjectManager
            from modules import carro_do_projeto as CP, lapsim
            extras = []
            for it in a.extra or []:
                try:
                    nome, r_ = it.split("=", 1)
                    m_, pos = r_.split("@", 1)
                    extras.append((nome.strip(), float(m_), tuple(float(x) for x in pos.split(","))))
                except ValueError:
                    raise ValueError(f"--extra: use nome=kg@x,y,z (recebido '{it}')")
            lev = CP.levantar(ProjectManager(CadEngine()).open(a.arquivo), a.eixos[0], a.eixos[1], extras)
            txt = CP.texto(lev)
            if a.volta:
                c = CP.carro_do_projeto(_carro(a.carro), lev)
                v = lapsim.volta(c, None, a.ds).valores
                lev["volta"] = {k: x for k, x in v.items() if not isinstance(x, list)}
                txt += f"\nVolta com a massa do projeto ({c.massa:.1f} kg; demais parâmetros SEUS/exemplo): {v['tempo_s']:.3f} s"
            if a.bicicleta:
                from modules import lapsim_bicicleta as LB
                d = dict(EXEMPLO_B)
                d.update(_kv(a.carro, "--carro"))
                d.update(massa=lev["massa_kg"], a=lev["a_m"], b=lev["b_m"], h=lev["altura_cg_m"])
                rb = LB.volta(LB.CarroB(**d), None, a.ds)
                lev["volta_bicicleta"] = {k: x for k, x in rb.valores.items() if not isinstance(x, list)}
                txt += "\n" + LB.texto(rb)
            emit(txt, lev)
        elif a.cmd == "volta-bicicleta":
            from modules import lapsim_bicicleta as LB
            d = dict(EXEMPLO_B)
            d.update(_kv(a.carro, "--carro"))
            try:
                c = LB.CarroB(tracao=a.tracao, freio_diant=a.freio_diant, **d)
            except TypeError as exc:
                raise ValueError(f"--carro: parâmetro desconhecido ({exc})")
            r = LB.volta(c, _pista(a), a.ds)
            emit(LB.texto(r), {"classe": r.classe, "valores": {k: x for k, x in r.valores.items() if not isinstance(x, list)}, "limitacoes": r.limitacoes})
        elif a.cmd == "dinamica-lateral":
            from modules import dinamica_lateral as DL
            vals = {k_: getattr(a, k_) for k_ in ("massa", "a", "b", "iz", "cf", "cr")}
            if a.projeto:
                from core.cad_engine import CadEngine
                from core.project_manager import ProjectManager
                from modules import carro_do_projeto as CP
                if not a.eixos:
                    raise ValueError("--projeto exige --eixos y_diant y_tras")
                lev = CP.levantar(ProjectManager(CadEngine()).open(a.projeto), a.eixos[0], a.eixos[1])
                for k_, v_ in (("massa", lev["massa_kg"]), ("a", lev["a_m"]), ("b", lev["b_m"]), ("iz", lev["inercia_z_kgm2"])):
                    vals[k_] = vals[k_] if vals[k_] is not None else v_
            faltam = [k_ for k_, v_ in vals.items() if v_ is None]
            if faltam:
                raise ValueError("informe " + ", ".join("--" + k_ for k_ in faltam) + " (Cf e Cr são rigidezes de curva por EIXO, em N/rad: o NEXUS não as estima)")
            p_ = DL.ParamsLat(**vals)
            var = DL.varredura_velocidade(p_, a.u)
            deg = DL.degrau(p_, a.u[0], a.delta, a.t)
            est = {"classe": "ANALITICO", "solver": "modelo linear 2 GDL (exponencial de matriz)", "parametros": vals, "varredura": var, "degrau": {k_: x for k_, x in deg.items() if not isinstance(x, list)},
                   "limitacoes": var[0]["limitacoes"]}
            _exportar(a, "dinamica_lateral", est)
            emit("\n".join(DL.texto(g) for g in var[1:]) + ("\n" if len(var) > 1 else "") + DL.texto(deg), est)
        elif a.cmd == "freio-termico":
            from modules import freio_termico as FT
            def _disco(itens):
                d = _kv(itens, "--disco")
                try:
                    return FT.Disco(**d)
                except TypeError as exc:
                    raise ValueError(f"disco: parâmetro desconhecido ou faltando ({exc})")
            r = FT.termica(_carro(a.carro), _disco(a.disco_diant), _disco(a.disco_tras), a.freio_diant, _pista(a), a.ds, a.voltas, a.t0, a.t_amb)
            _exportar(a, "freio_termico", r)
            emit(FT.texto(r), {k_: x for k_, x in r.items() if k_ != "traco_ultima_volta"})
        elif a.cmd == "dossie":
            from modules import dossie as DS
            if a.acao == "criar":
                try:
                    esp = json.loads(open(a.arquivo, encoding="utf-8").read())
                    d_ = DS.criar(esp["tipo"], esp["parametros"], esp.get("nota", ""))
                except (OSError, ValueError, KeyError) as exc:
                    raise ValueError(f"especificação inválida: {exc}")
                if a.saida:
                    DS.salvar(d_, a.saida)
                emit(DS.texto(d_), {k_: x for k_, x in d_.items() if k_ != "resultado"})
            else:
                d_ = DS.carregar(a.arquivo)
                v_ = DS.verificar(d_)
                emit(DS.texto(d_, v_), v_)
                if not (v_["integro"] and v_["reproduziu"]):
                    return 1
        elif a.cmd == "formato-telemetria":
            from modules import validacao_dados as VD
            print(VD.para_csv_exemplo(_carro(None)), file=out, end="")
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
