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


# ---------------------------------------------------------------- V3.8: contato entre DUAS PEÇAS importadas / da biblioteca
def _bbox(shape):
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    b = Bnd_Box(); BRepBndLib.Add_s(shape, b)
    lo, hi = b.CornerMin(), b.CornerMax()
    return np.array([lo.X(), lo.Y(), lo.Z()]), np.array([hi.X(), hi.Y(), hi.Z()])


def _mover(shape, d):
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.gp import gp_Trsf, gp_Vec
    t = gp_Trsf(); t.SetTranslation(gp_Vec(*[float(x) for x in d]))
    return BRepBuilderAPI_Transform(shape, t, True).Shape()


def contato_duas_pecas(inferior, superior, E1, nu1, E2, nu2, forca, tamanho, K=1e7, mu=None, centrar_xy=True, ajuste=0.01) -> dict:
    """Duas PEÇAS (shapes OCP — de arquivo STEP ou da biblioteca) empilhadas ao longo de +z: `superior` é transladada até apoiar em `inferior`
    (z_min(sup) = z_max(inf); opcionalmente centrada em xy). Base da inferior travada em z (+ 3 vínculos de corpo rígido), força `forca` [N] para
    BAIXO distribuída nos nós do topo da superior, contato de penalidade nó-a-superfície detectado automaticamente (`contato_automatico`).
    Materiais E/ν de cada peça SÃO DO USUÁRIO. Unidades: mm, N, MPa. Sem ccx ou sem interface: NAO_EXECUTADO/ValueError (nunca inventa números).
    Verificação possível em geometria arbitrária: equilíbrio ΣRz = F; a rigidez do conjunto é comparada à de duas barras em série SÓ como ordem de grandeza
    (aviso: faces de contato não planas ou áreas diferentes invalidam essa comparação)."""
    if min(E1, E2, forca, tamanho, K) <= 0 or not (0 <= nu1 < 0.5 and 0 <= nu2 < 0.5):
        raise ValueError("E, força, tamanho, K positivos e 0 ≤ ν < 0,5")
    if (r := _sem_ccx()): return r
    from . import fea_gmsh as G
    if not G.available():
        return {"classe": "NAO_EXECUTADO", "aviso": "Gmsh indisponível: sem malha, nenhum número é produzido"}
    a0, a1 = _bbox(inferior); b0, b1 = _bbox(superior)
    d = np.array([0.0, 0.0, a1[2] - b0[2]])
    if centrar_xy:
        d[:2] = ((a0 + a1) / 2 - (b0 + b1) / 2)[:2]
    superior = _mover(superior, d)
    m1, i1 = G.mesh_from_shape(inferior, tamanho, order=1); m2, i2 = G.mesh_from_shape(superior, tamanho, order=1)
    if len(m1.tets) + len(m2.tets) > 60000:
        raise ValueError("malha grande demais para o contato de penalidade (> 60 000 tetraedros): aumente o tamanho")

    class M: pass
    m = M(); m.nodes = np.vstack([m1.nodes, m2.nodes]); m.tets = np.vstack([m1.tets, m2.tets + len(m1.nodes)])
    reg = np.r_[np.zeros(len(m1.tets), int), np.ones(len(m2.tets), int)]
    tol = max(1e-4, 1e-3 * tamanho)
    base = N.nos_plano(m, 2, float(m1.nodes[:, 2].min()), tol=tol, regioes=reg, reg=0)
    topo = N.nos_plano(m, 2, float(m2.nodes[:, 2].max()), tol=tol, regioes=reg, reg=1)
    if len(base) < 3 or len(topo) < 3:
        raise ValueError("faces de apoio (base da inferior / topo da superior) devem ser planas e horizontais (≥ 3 nós)")
    fixed = {n: (2,) for n in base}
    def trava_plano(nos, comps_extra):
        n0 = nos[0]; xy = m.nodes[nos][:, :2]
        n1 = nos[int(np.argmax(np.linalg.norm(xy - m.nodes[n0, :2], axis=1)))]
        if n1 == n0 or np.linalg.norm(m.nodes[n1, :2] - m.nodes[n0, :2]) < 1e-9:
            raise ValueError("face de apoio degenerada (sem extensão em xy)")
        return n0, n1
    n0, n1 = trava_plano(base, None); fixed[n0] = (0, 1, 2)
    dx, dy = abs(m.nodes[n1, 0] - m.nodes[n0, 0]), abs(m.nodes[n1, 1] - m.nodes[n0, 1])
    fixed[n1] = tuple(sorted(set(fixed.get(n1, ())) | ({1} if dx >= dy else {0})))
    t0, t1 = trava_plano(topo, None); fixed[t0] = tuple(sorted(set(fixed.get(t0, ())) | {0, 1}))
    dx, dy = abs(m.nodes[t1, 0] - m.nodes[t0, 0]), abs(m.nodes[t1, 1] - m.nodes[t0, 1])
    fixed[t1] = tuple(sorted(set(fixed.get(t1, ())) | ({1} if dx >= dy else {0})))
    ct = N.contato_automatico(m, reg, 0, 1, folga=0.75 * tamanho, K=K, mu=mu, ajuste=ajuste)
    wd = Path(tempfile.mkdtemp())
    N.write_inp_nl(m, [{"E": E1, "nu": nu1}, {"E": E2, "nu": nu2}], reg, fixed, {n: (0, 0, -forca / len(topo)) for n in topo}, wd / "c.inp",
                   nlgeom=True, contato=[ct], rf_nos=base)
    r, U, RF, _ = N.run_nl(wd / "c.inp")
    if r.classe != "SIMULACAO_NUMERICA":
        return {"classe": r.classe, "aviso": r.limitacoes[0]}
    soma = abs(sum(f[2] for f in RF.values()))
    uz = abs(float(np.mean([U[n + 1][2] for n in topo])))
    return {"classe": "SIMULACAO_NUMERICA", "u_topo_mm": uz, "reacao_base_N": soma, "forca_N": forca, "erro_equilibrio_pct": 100 * (soma / forca - 1),
            "rigidez_N_por_mm": forca / uz if uz > 0 else float("nan"), "nos_escravo": ct.get("n_escravo", len(ct["escravo"])), "faces_mestre": ct.get("n_mestre", len(ct["mestre"])),
            "tetraedros": int(len(m.tets)), "solver": r.solver, "versao": r.solver_versao,
            "nota": "malha Tet4 grossa; resultado de verificação do modelo, NÃO validação de peça real; K de penalidade deve ser variado até o resultado estabilizar"}


def peca_de_especificacao(spec: dict):
    """Cria o shape OCP de uma especificação da interface: {'tipo':'caixa','dx','dy','dz'} | {'tipo':'cilindro','r','h'} | {'tipo':'step','path'} (mm)."""
    t = spec.get("tipo")
    if t == "caixa":
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
        if min(spec["dx"], spec["dy"], spec["dz"]) <= 0: raise ValueError("dimensões da caixa devem ser positivas")
        return BRepPrimAPI_MakeBox(spec["dx"], spec["dy"], spec["dz"]).Shape()
    if t == "cilindro":
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
        if min(spec["r"], spec["h"]) <= 0: raise ValueError("raio e altura do cilindro devem ser positivos")
        return BRepPrimAPI_MakeCylinder(spec["r"], spec["h"]).Shape()
    if t == "step":
        from .cad_history import load_step, CadHistoryError
        try:
            return load_step(spec["path"])
        except CadHistoryError as e:
            raise ValueError(str(e))
    raise ValueError(f"tipo de peça desconhecido: {t!r}")
