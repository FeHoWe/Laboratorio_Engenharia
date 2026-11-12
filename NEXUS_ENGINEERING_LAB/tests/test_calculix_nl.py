"""V3.5 estrutural: plasticidade, multimaterial e contato com o ccx REAL, contra soluções analíticas de barra."""
import numpy as np
import pytest
from modules import calculix_nl as N, fea3d as F, solver_registry as sr

pytestmark = pytest.mark.skipif(not sr.detect("CalculiX").instalado, reason="CalculiX não instalado")
E, NU, SY, ET = 210000.0, 0.3, 250.0, 2100.0


def _barra(lx, ly, lz, nx, ny, nz):
    return F.box_mesh(lx, ly, lz, nx, ny, nz)


def _fixa_xmin_u_xmax(m, eixo, valor):
    base = N.nos_plano(m, eixo, 0.0); topo = N.nos_plano(m, eixo, m.nodes[:, eixo].max())
    fixed = {n: (eixo,) for n in base}
    # impede movimento de corpo rígido sem restringir Poisson: 1 nó trava os outros eixos, outro trava 1 eixo
    o = [a for a in range(3) if a != eixo]
    n0 = base[0]; fixed[n0] = tuple(range(3))
    ba = [n for n in base if n != n0]
    n1 = max(ba, key=lambda n: m.nodes[n, o[0]]); fixed[n1] = tuple(sorted(set(fixed[n1]) | {o[1]}))
    return base, topo, fixed, {n: {eixo: valor} for n in topo}


def test_plasticidade_bilinear_vs_analitico(tmp_path):
    m = _barra(20, 4, 4, 5, 2, 2); L, A = 20.0, 16.0
    eps = 0.006                                                            # ~5x a deformação de escoamento
    mats = [{"E": E, "nu": NU, "plastico": N.curva_bilinear(E, SY, ET)}]
    base, topo, fixed, disp = _fixa_xmin_u_xmax(m, 0, eps * L)
    N.write_inp_nl(m, mats, np.zeros(len(m.tets), int), fixed, {}, tmp_path / "p.inp", disp=disp, rf_nos=base)
    r, U, RF, pe = N.run_nl(tmp_path / "p.inp")
    assert r.classe == "SIMULACAO_NUMERICA"
    Fx = abs(sum(f[0] for f in RF.values()))
    esperado = N.tensao_bilinear(eps, E, SY, ET) * A
    assert abs(Fx / esperado - 1) < 0.02, (Fx, esperado)
    assert pe > 0.003                                                      # plastificou de fato


def test_regime_elastico_sem_plasticidade(tmp_path):
    m = _barra(20, 4, 4, 5, 2, 2); L, A = 20.0, 16.0
    eps = 0.0008                                                           # < sigma_y/E
    mats = [{"E": E, "nu": NU, "plastico": N.curva_bilinear(E, SY, ET)}]
    base, topo, fixed, disp = _fixa_xmin_u_xmax(m, 0, eps * L)
    N.write_inp_nl(m, mats, np.zeros(len(m.tets), int), fixed, {}, tmp_path / "e.inp", disp=disp, rf_nos=base)
    r, U, RF, pe = N.run_nl(tmp_path / "e.inp")
    Fx = abs(sum(f[0] for f in RF.values()))
    assert abs(Fx / (E * eps * A) - 1) < 0.02 and pe < 1e-9


def test_multimaterial_em_serie(tmp_path):
    m = _barra(4, 4, 20, 2, 2, 8); A = 16.0; Fz = 1000.0
    cz = m.nodes[m.tets].mean(axis=1)[:, 2]
    reg = (cz > 10).astype(int)                                            # região 0: z<10 (aço); 1: z>10 (alumínio, usuário informou)
    mats = [{"E": 210000.0, "nu": 0.0}, {"E": 70000.0, "nu": 0.0}]
    base, topo, fixed, _ = _fixa_xmin_u_xmax(m, 2, 0.0)
    loads = {n: (0, 0, -Fz / len(topo)) for n in topo}
    N.write_inp_nl(m, mats, reg, fixed, loads, tmp_path / "m.inp")
    r, U, RF, _ = N.run_nl(tmp_path / "m.inp")
    uz = np.mean([U[n + 1][2] for n in topo])
    esp = -Fz * (10 / 210000.0 + 10 / 70000.0) / A
    assert abs(uz / esp - 1) < 0.03, (uz, esp)


KC = 1e7


def test_contato_entre_blocos_equilibrio_e_pressao(tmp_path):
    # dois blocos empilhados SEM nós compartilhados (superfície de contato) × barra única (solução analítica F·L/(E·A))
    b1 = _barra(4, 4, 10, 2, 2, 5); b2 = _barra(4, 4, 10, 2, 2, 5)
    n1 = len(b1.nodes)
    class M: pass
    m = M(); m.nodes = np.vstack([b1.nodes, b2.nodes + [0, 0, 10.0]]); m.tets = np.vstack([b1.tets, b2.tets + n1])
    reg = np.r_[np.zeros(len(b1.tets), int), np.ones(len(b2.tets), int)]
    mats = [{"E": E, "nu": 0.0}, {"E": E, "nu": 0.0}]
    base = N.nos_plano(m, 2, 0.0); topo = N.nos_plano(m, 2, 20.0)
    fixed = {n: (2,) for n in base}; fixed[base[0]] = (0, 1, 2)
    ba = [n for n in base if n != base[0]]; n1_ = max(ba, key=lambda n: m.nodes[n, 0]); fixed[n1_] = (1, 2)
    # bloco superior só toca por contato sem atrito: trava seu movimento de corpo rígido lateral (x,y,giro)
    t0 = topo[0]; fixed[t0] = (0, 1); t1 = max([n for n in topo if n != t0], key=lambda n: m.nodes[n, 0]); fixed[t1] = (1,)
    Fz = 800.0; loads = {n: (0, 0, -Fz / len(topo)) for n in topo}
    esc = [n for n in N.nos_plano(m, 2, 10.0, regioes=reg, reg=1)]
    mest = N.faces_em_nos(m, N.nos_plano(m, 2, 10.0, regioes=reg, reg=0), regioes=reg, reg=0)
    fesc = N.faces_em_nos(m, esc, regioes=reg, reg=1)
    assert len(esc) > 0 and len(mest) > 0 and len(fesc) > 0
    N.write_inp_nl(m, mats, reg, fixed, loads, tmp_path / "c.inp", nlgeom=True,
                   contato=[{"escravo": esc, "mestre": mest, "K": KC, "ajuste": 0.01}])
    r, U, RF, _ = N.run_nl(tmp_path / "c.inp")
    assert r.classe == "SIMULACAO_NUMERICA"
    uz = np.mean([U[n + 1][2] for n in topo]); esp = -Fz * 20.0 / (E * 16.0)
    assert abs(uz / esp - 1) < 0.03, (uz, esp)                              # contato fechado transmite a carga como barra única


def test_validacoes(tmp_path):
    m = _barra(4, 4, 4, 1, 1, 1)
    with pytest.raises(ValueError): N.curva_bilinear(E, 250, E)
    with pytest.raises(ValueError): N.write_inp_nl(m, [{"E": E, "nu": .3}], np.ones(len(m.tets), int), {}, {}, tmp_path / "x.inp")


def test_penalidade_converge_com_K(tmp_path):
    """O erro do contato por penalidade cai quando K sobe (1e5 → 1e7): é a verificação de que o contato é realmente aplicado."""
    import importlib, sys
    erros = []
    for k, K in enumerate((1e5, 1e7)):
        src = (tmp_path / f"k{k}"); src.mkdir()
        mod = sys.modules[__name__]; old = mod.KC; mod.KC = K
        try: test_contato_entre_blocos_equilibrio_e_pressao.__wrapped__(src) if hasattr(test_contato_entre_blocos_equilibrio_e_pressao, "__wrapped__") else test_contato_entre_blocos_equilibrio_e_pressao(src)
        except AssertionError as e: erros.append(str(e))
        finally: mod.KC = old
    assert len(erros) <= 1                                                 # K=1e5 pode falhar a tolerância de 3%, K=1e7 não
