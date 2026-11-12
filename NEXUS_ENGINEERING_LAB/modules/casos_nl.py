"""Casos prontos de FEA não linear (V3.6) sobre `calculix_nl`: barra elastoplástica, barras em série (multimaterial) e blocos em contato.
Cada caso roda o CalculiX REAL e devolve a solução analítica ao lado (verificação). Materiais são SEMPRE informados pelo usuário.
Sem `ccx`: NAO_EXECUTADO (sem números). Malhas pequenas e estruturadas de caixa: servem para verificar o MODELO, não para peças reais."""
from __future__ import annotations

import tempfile
from pathlib import Path
import numpy as np
from . import calculix_nl as N, fea3d as F, solver_registry as sr


def _trava(m, eixo, valor_topo=None):
    base = N.nos_plano(m, eixo, 0.0); topo = N.nos_plano(m, eixo, float(m.nodes[:, eixo].max()))
    fixed = {n: (eixo,) for n in base}; o = [a for a in range(3) if a != eixo]
    n0 = base[0]; fixed[n0] = (0, 1, 2)
    n1 = max((n for n in base if n != n0), key=lambda n: m.nodes[n, o[0]]); fixed[n1] = tuple(sorted({o[1]} | set(fixed.get(n1, ()))))
    return base, topo, fixed


def _sem_ccx():
    return {"classe": "NAO_EXECUTADO", "aviso": "CalculiX não instalado: nenhum número é produzido"} if not sr.detect("CalculiX").instalado else None


def barra_plastica(E, nu, sigma_y, Et, comprimento, lado, deformacao, wd=None) -> dict:
    if min(E, sigma_y, comprimento, lado, deformacao) <= 0 or not (0 < Et < E):
        raise ValueError("E, σy, dimensões e deformação positivos; 0 < Et < E")
    if (r := _sem_ccx()): return r
    m = F.box_mesh(comprimento, lado, lado, 5, 2, 2); wd = Path(wd or tempfile.mkdtemp())
    base, topo, fixed = _trava(m, 0)
    mats = [{"E": E, "nu": nu, "plastico": N.curva_bilinear(E, sigma_y, Et)}]
    N.write_inp_nl(m, mats, np.zeros(len(m.tets), int), fixed, {}, wd / "c.inp", disp={n: {0: deformacao * comprimento} for n in topo}, rf_nos=base)
    r, U, RF, pe = N.run_nl(wd / "c.inp")
    if r.classe != "SIMULACAO_NUMERICA": return {"classe": r.classe, "aviso": r.limitacoes[0]}
    Fx = abs(sum(f[0] for f in RF.values())); ref = N.tensao_bilinear(deformacao, E, sigma_y, Et) * lado * lado
    return {"classe": "SIMULACAO_NUMERICA", "forca_ccx_N": Fx, "forca_analitica_N": ref, "erro_pct": 100 * (Fx / ref - 1), "peeq_max": pe,
            "plastificou": pe > 1e-6, "solver": r.solver, "versao": r.solver_versao}


def serie_materiais(E1, E2, nu, comprimento, lado, forca) -> dict:
    if min(E1, E2, comprimento, lado, forca) <= 0: raise ValueError("valores devem ser positivos")
    if (r := _sem_ccx()): return r
    m = F.box_mesh(lado, lado, comprimento, 2, 2, 8); wd = Path(tempfile.mkdtemp())
    reg = (m.nodes[m.tets].mean(axis=1)[:, 2] > comprimento / 2).astype(int)
    base, topo, fixed = _trava(m, 2)
    N.write_inp_nl(m, [{"E": E1, "nu": nu}, {"E": E2, "nu": nu}], reg, fixed, {n: (0, 0, -forca / len(topo)) for n in topo}, wd / "c.inp")
    r, U, RF, _ = N.run_nl(wd / "c.inp")
    if r.classe != "SIMULACAO_NUMERICA": return {"classe": r.classe, "aviso": r.limitacoes[0]}
    uz = abs(float(np.mean([U[n + 1][2] for n in topo])))
    ref = forca * (comprimento / 2 / E1 + comprimento / 2 / E2) / lado ** 2        # válido para ν≈0 (barra uniaxial)
    return {"classe": "SIMULACAO_NUMERICA", "u_ccx_mm": uz, "u_analitico_mm": ref, "erro_pct": 100 * (uz / ref - 1),
            "nota": "referência analítica uniaxial é exata só para ν=0; com ν>0 o erro inclui efeito de Poisson/vínculos"}


def blocos_contato(E, nu, comprimento_bloco, lado, forca, K=1e7) -> dict:
    if min(E, comprimento_bloco, lado, forca, K) <= 0: raise ValueError("valores devem ser positivos")
    if (r := _sem_ccx()): return r
    b1 = F.box_mesh(lado, lado, comprimento_bloco, 2, 2, 5); b2 = F.box_mesh(lado, lado, comprimento_bloco, 2, 2, 5)

    class M: pass
    m = M(); m.nodes = np.vstack([b1.nodes, b2.nodes + [0, 0, comprimento_bloco]]); m.tets = np.vstack([b1.tets, b2.tets + len(b1.nodes)])
    reg = np.r_[np.zeros(len(b1.tets), int), np.ones(len(b2.tets), int)]
    base, topo, fixed = _trava(m, 2)
    t0 = topo[0]; fixed[t0] = (0, 1); fixed[max((n for n in topo if n != t0), key=lambda n: m.nodes[n, 0])] = (1,)
    z = comprimento_bloco
    esc = N.nos_plano(m, 2, z, regioes=reg, reg=1); mest = N.faces_em_nos(m, N.nos_plano(m, 2, z, regioes=reg, reg=0), regioes=reg, reg=0)
    wd = Path(tempfile.mkdtemp())
    N.write_inp_nl(m, [{"E": E, "nu": nu}] * 2, reg, fixed, {n: (0, 0, -forca / len(topo)) for n in topo}, wd / "c.inp", nlgeom=True,
                   contato=[{"escravo": esc, "mestre": mest, "K": K, "ajuste": 0.01}])
    r, U, RF, _ = N.run_nl(wd / "c.inp")
    if r.classe != "SIMULACAO_NUMERICA": return {"classe": r.classe, "aviso": r.limitacoes[0]}
    uz = abs(float(np.mean([U[n + 1][2] for n in topo]))); ref = forca * 2 * comprimento_bloco / (E * lado ** 2)
    return {"classe": "SIMULACAO_NUMERICA", "u_ccx_mm": uz, "u_analitico_mm": ref, "erro_pct": 100 * (uz / ref - 1), "pressao_nominal_MPa": forca / lado ** 2,
            "nota": "ν=0 recomendado para comparar; K de penalidade deve ser aumentado até o resultado parar de mudar"}
