"""CalculiX avançado (V3.5): plasticidade bilinear, multimaterial por regiões e contato entre corpos.

Estende a entrada de `calculix_io.write_inp` SEM alterá-la. Tudo é executado com o `ccx` real; sem `ccx` o resultado é NAO_EXECUTADO.
Materiais NUNCA são atribuídos automaticamente: o usuário informa E, nu e (opcional) a curva elastoplástica de cada região.
Plasticidade: pequenas deformações (ou NLGEOM se pedido), encruamento isotrópico bilinear — sigma_y, módulo tangente Et.
Contato: nó-superfície (escravo = nós, mestre = faces de elemento), penalidade linear K, atrito de Coulomb opcional.
Limites: sem plasticidade cíclica/cinemática, sem dano, sem contato autônomo (auto-contato); malha Tet4/Tet10 (faces por nós de canto).
"""
from __future__ import annotations
import re, subprocess
from pathlib import Path
import numpy as np
from . import solver_registry as sr
from .result_trace import TracedResult

FACES = ((0, 1, 2), (0, 3, 1), (1, 3, 2), (2, 3, 0))      # S1..S4 do C3D4/C3D10 (nós de canto, 0-indexado)


def curva_bilinear(E, sigma_y, Et, eps_max=0.05):
    """Tabela (tensão, deformação plástica) para *PLASTIC. Et = módulo tangente pós-escoamento (< E)."""
    if not (0 < Et < E) or sigma_y <= 0:
        raise ValueError("exige 0 < Et < E e sigma_y > 0")
    Ep = E * Et / (E - Et)                                  # módulo plástico (dσ/dεp)
    return [(sigma_y, 0.0), (sigma_y + Ep * eps_max, eps_max)]


def tensao_bilinear(eps, E, sigma_y, Et):
    """Resposta analítica uniaxial (referência para teste): tensão para deformação total eps (>=0)."""
    ey = sigma_y / E
    return E * eps if eps <= ey else sigma_y + Et * (eps - ey)


def nos_plano(mesh, eixo, valor, tol=1e-6, regioes=None, reg=None):
    ids = np.where(np.abs(mesh.nodes[:, eixo] - valor) <= tol)[0]
    if regioes is not None:
        ok = set(np.unique(mesh.tets[np.asarray(regioes) == reg]).tolist())
        ids = np.array([i for i in ids if i in ok])
    return [int(i) for i in ids]


def faces_em_nos(mesh, nos, regioes=None, reg=None):
    """[(elemento, nº da face 1..4)] cujas 3 arestas de canto estão todas em `nos`."""
    S = set(int(n) for n in nos); out = []
    for e, t in enumerate(mesh.tets):
        if regioes is not None and regioes[e] != reg: continue
        for k, f in enumerate(FACES):
            if all(int(t[i]) in S for i in f): out.append((e, k + 1))
    return out


def write_inp_nl(mesh, materiais, regioes, fixed, loads, path, disp=None, nlgeom=False, contato=None,
                 incremento=(0.1, 1.0, 1e-5, 1.0), rf_nos=None):
    """materiais: lista de {E, nu, rho?, plastico?: [(sigma, eps_p),...]}; regioes: índice de material por elemento.
    fixed {nó:(comps)}, loads {nó:(fx,fy,fz)}, disp {nó:{comp:valor}} (deslocamento prescrito).
    contato: lista de {escravo: [nós], mestre: [(elem, face)], K, mu?}. rf_nos: nós cujas reações serão impressas."""
    regioes = np.asarray(regioes, int)
    if len(regioes) != len(mesh.tets): raise ValueError("regioes deve ter um valor por elemento")
    if regioes.min() < 0 or regioes.max() >= len(materiais): raise ValueError("região sem material definido")
    ten = mesh.tets.shape[1] == 10
    L = ["*NODE"] + [f"{i+1}, {x:.9g}, {y:.9g}, {z:.9g}" for i, (x, y, z) in enumerate(mesh.nodes)]
    L += ["*NSET, NSET=NALL, GENERATE", f"1, {len(mesh.nodes)}, 1"]
    for r in range(len(materiais)):
        idx = np.where(regioes == r)[0]
        if len(idx) == 0: continue
        L += [f"*ELEMENT, TYPE={'C3D10' if ten else 'C3D4'}, ELSET=R{r}"] + [f"{e+1}, " + ", ".join(str(a+1) for a in mesh.tets[e]) for e in idx]
    for r, m in enumerate(materiais):
        if not (regioes == r).any(): continue
        L += [f"*MATERIAL, NAME=M{r}", "*ELASTIC", f"{m['E']:.9g}, {m['nu']:.9g}"]
        if m.get("rho"): L += ["*DENSITY", f"{m['rho']:.9g}"]
        if m.get("plastico"):
            L += ["*PLASTIC"] + [f"{s:.9g}, {p:.9g}" for s, p in m["plastico"]]
        L += [f"*SOLID SECTION, ELSET=R{r}, MATERIAL=M{r}"]
    for i, c in enumerate(contato or []):
        if c.get("escravo_faces"):                          # superfície-superfície (recomendado: robusto com K alto)
            L += [f"*SURFACE, NAME=SS{i}"] + [f"{e+1}, S{f}" for e, f in c["escravo_faces"]]
            tipo = "SURFACE TO SURFACE"
        else:
            L += [f"*NSET, NSET=CS{i}"] + _linhas([n + 1 for n in c["escravo"]])
            L += [f"*SURFACE, NAME=SS{i}, TYPE=NODE", f"CS{i}"]; tipo = "NODE TO SURFACE"
        L += [f"*SURFACE, NAME=SM{i}"] + [f"{e+1}, S{f}" for e, f in c["mestre"]]
        L += [f"*SURFACE INTERACTION, NAME=SI{i}", "*SURFACE BEHAVIOR, PRESSURE-OVERCLOSURE=LINEAR", f"{c['K']:.9g}"]
        if c.get("mu"): L += ["*FRICTION", f"{c['mu']:.9g}, {c.get('K_atrito', c['K']/10):.9g}"]
        L += [f"*CONTACT PAIR, INTERACTION=SI{i}, TYPE={tipo}" + (f", ADJUST={c['ajuste']:g}" if c.get("ajuste") else ""), f"SS{i}, SM{i}"]
    if rf_nos:
        L += ["*NSET, NSET=NRF"] + _linhas([n + 1 for n in rf_nos])
    L += ["*STEP, NLGEOM, INC=200" if nlgeom else "*STEP, INC=200", "*STATIC", ", ".join(f"{v:g}" for v in incremento), "*BOUNDARY"]
    for nd, cs in fixed.items():
        for c in cs: L.append(f"{nd+1}, {c+1}, {c+1}")
    for nd, d in (disp or {}).items():
        for c, v in d.items(): L.append(f"{nd+1}, {c+1}, {c+1}, {v:.9g}")
    if loads:
        L.append("*CLOAD")
        for nd, f in loads.items():
            for c in range(3):
                if f[c]: L.append(f"{nd+1}, {c+1}, {f[c]:.9g}")
    L += ["*NODE PRINT, NSET=NALL", "U"]
    if rf_nos: L += ["*NODE PRINT, NSET=NRF", "RF"]
    L += ["*EL PRINT, ELSET=R%d" % next(r for r in range(len(materiais)) if (regioes == r).any()), "S"] + (["PEEQ"] if any(m.get("plastico") for m in materiais) else [])
    L += ["*END STEP"]
    Path(path).write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")


def _linhas(ids, n=8):
    return [", ".join(str(i) for i in ids[k:k + n]) for k in range(0, len(ids), n)]


def _f(x):
    """float tolerante ao formato Fortran do ccx (1.5-259 = 1.5E-259, 1.0D+00)."""
    x = x.replace("D", "E")
    x = re.sub(r"^([-+]?[0-9.]+)([-+][0-9]{3})$", r"\1E\2", x)
    return float(x)


def parse_dat_nl(text: str):
    """Último passo impresso: (U {nó:(ux,uy,uz)}, RF {nó:(fx,fy,fz)}, PEEQ máx)."""
    U, RF, peeq, tempo = {}, {}, 0.0, 0.0
    modo = None
    for line in text.splitlines():
        low = line.lower()
        if "displacements" in low and "vx" in low:
            modo = "U"; U = {}; m_t = re.search(r"time\s+([-+0-9.eEdD]+)", line)
            tempo = float(m_t.group(1).replace("D", "E")) if m_t else tempo; continue
        if low.strip().startswith("forces") : modo = "RF"; RF = {}; continue
        if "equivalent plastic strain" in low or "peeq" in low: modo = "P"; continue
        if "stresses" in low: modo = "S"; continue
        parts = line.split()
        if not parts: continue
        try: nums = [_f(x) for x in parts]
        except ValueError: modo = None; continue
        if modo == "U" and len(nums) == 4: U[int(nums[0])] = tuple(nums[1:4])
        elif modo == "RF" and len(nums) == 4: RF[int(nums[0])] = tuple(nums[1:4])
        elif modo == "P" and len(nums) >= 3: peeq = max(peeq, nums[2])
    parse_dat_nl.tempo = tempo
    return U, RF, peeq


def incremento_total(inp_path):
    """Tempo total do passo (2º valor da linha de incrementos do *STATIC)."""
    L = Path(inp_path).read_text(encoding="utf-8").splitlines()
    for i, l in enumerate(L):
        if l.strip().upper().startswith("*STATIC"):
            try: return float(L[i + 1].split(",")[1])
            except (IndexError, ValueError): return 1.0
    return 1.0


def run_nl(inp_path, timeout=1800):
    """Executa o ccx. Retorna (TracedResult, U, RF, peeq_max). Sem ccx: NAO_EXECUTADO."""
    st = sr.detect("CalculiX")
    if not st.instalado:
        return TracedResult("CalculiX", "NAO_EXECUTADO", "ccx *STATIC não linear", limitacoes=[f"CalculiX NÃO INSTALADO. {st.instrucao}"]), {}, {}, 0.0
    p = Path(inp_path); job = p.with_suffix("")
    r = subprocess.run([st.caminho, job.name], cwd=p.parent, capture_output=True, text=True, timeout=timeout)
    dat = job.with_suffix(".dat")
    if r.returncode != 0 or not dat.exists():
        return TracedResult("CalculiX", "NAO_EXECUTADO", "ccx *STATIC não linear", limitacoes=["falha: " + (r.stderr or r.stdout)[-400:]]), {}, {}, 0.0
    U, RF, pe = parse_dat_nl(dat.read_text(encoding="utf-8"))
    if parse_dat_nl.tempo < 0.9999 * incremento_total(p):
        return TracedResult("CalculiX", "NAO_EXECUTADO", "ccx *STATIC não linear", limitacoes=[
            f"NÃO CONVERGIU: o passo parou em t={parse_dat_nl.tempo:g} (de {incremento_total(p):g}); resultado parcial descartado"]), {}, {}, 0.0
    um = max((float(np.linalg.norm(v)) for v in U.values()), default=0.0)
    vals = {"u_max_mm": um, "peeq_max": pe, "nos": len(U)}
    return (TracedResult("CalculiX", "SIMULACAO_NUMERICA", "ccx *STATIC não linear", vals, solver="CalculiX",
                         solver_versao=st.versao or "?", limitacoes=["sem estudo de malha → não validado"]), U, RF, pe)


def _faces_contorno(mesh, regioes, reg):
    """Faces (elem, nº 1..4) de contorno da região `reg` (aparecem uma só vez entre os elementos da região)."""
    cont = {}
    for e, t in enumerate(mesh.tets):
        if regioes[e] != reg: continue
        for k, f in enumerate(FACES):
            chave = tuple(sorted(int(t[i]) for i in f))
            cont.setdefault(chave, []).append((e, k + 1))
    return [v[0] for v in cont.values() if len(v) == 1]


def contato_automatico(mesh, regioes, reg_mestre: int, reg_escravo: int, folga: float, K: float, mu: float | None = None, ajuste: float | None = None) -> dict:
    """Detecta o contato entre duas regiões de uma malha QUALQUER (V3.7): escravo = nós de contorno da região escravo a ≤ `folga` de alguma face de
    contorno da região mestre; mestre = faces de contorno da mestre a ≤ `folga` de algum nó escravo. Distâncias por centroide/nó (aproximação):
    use `folga` ≥ ~metade da aresta local. Devolve o dicionário aceito por `write_inp_nl(contato=[...])` mais `n_escravo`, `n_mestre`.
    Levanta ValueError se nenhuma interface for encontrada (não inventa contato)."""
    from scipy.spatial import cKDTree
    regioes = np.asarray(regioes, int)
    fm, fe = _faces_contorno(mesh, regioes, reg_mestre), _faces_contorno(mesh, regioes, reg_escravo)
    if not fm or not fe: raise ValueError("região sem faces de contorno")
    def geo(e, f):
        P = mesh.nodes[[mesh.tets[e][i] for i in FACES[f - 1]]]; c = P.mean(axis=0)
        n = np.cross(P[1] - P[0], P[2] - P[0]); n = n / max(np.linalg.norm(n), 1e-300)
        if n @ (c - mesh.nodes[mesh.tets[e][:4]].mean(axis=0)) < 0: n = -n                 # normal para fora do elemento
        return c, n
    gm = [geo(e, f) for e, f in fm]; ge = [geo(e, f) for e, f in fe]
    cm, nm = np.array([g[0] for g in gm]), np.array([g[1] for g in gm]); ce, ne = np.array([g[0] for g in ge]), np.array([g[1] for g in ge])
    # faces de contato = vizinhas (≤ folga) com normais ANTIPARALELAS (descarta paredes laterais próximas à quina)
    dme, ime = cKDTree(ce).query(cm); dem, iem = cKDTree(cm).query(ce)
    ok_m = [i for i in range(len(fm)) if dme[i] <= folga and nm[i] @ ne[ime[i]] < -0.7]
    ok_e = [i for i in range(len(fe)) if dem[i] <= folga and ne[i] @ nm[iem[i]] < -0.7]
    if not ok_m or not ok_e: raise ValueError(f"nenhuma interface a ≤ {folga:g} entre as regiões {reg_mestre} e {reg_escravo}")
    mest = [fm[i] for i in ok_m]
    esc = sorted({int(mesh.tets[fe[i][0]][k]) for i in ok_e for k in FACES[fe[i][1] - 1]})
    out = {"escravo": esc, "mestre": mest, "K": K, "n_escravo": len(esc), "n_mestre": len(mest)}
    if mu: out["mu"] = mu
    if ajuste: out["ajuste"] = ajuste
    return out
