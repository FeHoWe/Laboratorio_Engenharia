"""Integração CalculiX: executa `ccx` (se instalado) e LÊ resultados .dat; cruza com o NEXUS.

Entrada gerada por `write_inp` (C3D4 ou C3D10) com `*NODE PRINT, U` e `*EL PRINT, S` em arquivo .dat (ASCII).
STATUS DE TESTE: o analisador é testado com amostras sintéticas do formato documentado E, quando `ccx` existe, com execução real
(tests/test_calculix_real.py: CalculiX 2.21, malha Gmsh Tet10, viga tubular — deslocamento NEXUS-Tet10 × ccx concordam e ambos
ficam a poucos % de Timoshenko). Sem `ccx` instalado o resultado é NAO_EXECUTADO. Use `compare` para validar na sua máquina.
"""
from __future__ import annotations
import re, subprocess
from pathlib import Path
import numpy as np
from . import solver_registry as sr
from .result_trace import TracedResult

# Ordem Tet10 NEXUS (4:0-1 5:1-2 6:2-0 7:0-3 8:1-3 9:2-3) = ordem do C3D10 do CalculiX (5:1-2? ver nota)
# CalculiX C3D10: nós 5..10 = arestas 1-2, 2-3, 3-1, 1-4, 2-4, 3-4 (1-indexado) = 0-1,1-2,2-0,0-3,1-3,2-3 → idêntico ao NEXUS.


def write_inp(mesh, E, nu, fixed, loads, path, rho=None, frd=False):
    """`frd=True` também pede o arquivo .frd (campo nodal completo de U e S) para leitura por `parse_frd`."""
    ten = mesh.tets.shape[1] == 10
    L = ["*NODE"] + [f"{i+1}, {x:.9g}, {y:.9g}, {z:.9g}" for i, (x, y, z) in enumerate(mesh.nodes)]
    L += [f"*ELEMENT, TYPE={'C3D10' if ten else 'C3D4'}, ELSET=EALL"] + [f"{i+1}, " + ", ".join(str(a+1) for a in t) for i, t in enumerate(mesh.tets)]
    L += ["*MATERIAL, NAME=MAT", "*ELASTIC", f"{E:.9g}, {nu:.9g}"]
    if rho: L += ["*DENSITY", f"{rho:.9g}"]
    L += ["*SOLID SECTION, ELSET=EALL, MATERIAL=MAT", "*STEP", "*STATIC", "*BOUNDARY"]
    for nd, cs in fixed.items():
        for c in cs: L.append(f"{nd+1}, {c+1}, {c+1}")
    L.append("*CLOAD")
    for nd, f in loads.items():
        for c in range(3):
            if f[c]: L.append(f"{nd+1}, {c+1}, {f[c]:.9g}")
    L += ["*NODE PRINT, NSET=NALL", "U", "*EL PRINT, ELSET=EALL", "S"]
    if frd:
        L += ["*NODE FILE", "U", "*EL FILE", "S"]
    L += ["*END STEP"]
    # conjunto de todos os nós
    L.insert(L.index("*MATERIAL, NAME=MAT"), "*NSET, NSET=NALL, GENERATE\n1, %d, 1" % len(mesh.nodes))
    Path(path).write_text("\n".join(L) + "\n")


def parse_dat(text: str):
    """Retorna (U[n,3] por id de nó, S: {elem: lista de (sxx,syy,szz,sxy,sxz,syz) nos pontos de integração})."""
    U, S = {}, {}
    mode = None
    for line in text.splitlines():
        low = line.lower()
        if "displacements" in low and "vx" in low: mode = "U"; continue
        if "stresses" in low and "sxx" in low: mode = "S"; continue
        if not line.strip(): continue
        parts = line.split()
        try: nums = [float(x.replace("D", "E")) for x in parts]
        except ValueError:
            mode = None if not re.match(r"^\s*[-+0-9]", line) else mode; continue
        if mode == "U" and len(nums) == 4: U[int(nums[0])] = nums[1:4]
        elif mode == "S" and len(nums) == 8: S.setdefault(int(nums[0]), []).append(nums[2:8])
    return U, S


def parse_frd(text: str) -> dict:
    """Lê o .frd ASCII do CalculiX (formato de colunas fixas: id em 10 colunas, valores E12.5).

    Retorna {"U": {nó: [ux,uy,uz]}, "S": {nó: [sxx,syy,szz,sxy,syz,szx]}} do ÚLTIMO passo presente. Campos ausentes ficam vazios.
    """
    out, mode, ncomp = {"U": {}, "S": {}}, None, 0
    for ln in text.splitlines():
        if ln.startswith(" -4"):
            nome = ln[5:13].strip()
            mode = "U" if nome == "DISP" else ("S" if nome == "STRESS" else None)
            if mode:
                out[mode] = {}                      # novo passo sobrescreve (fica o último)
                ncomp = 3 if mode == "U" else 6
        elif ln.startswith(" -3"):
            mode = None
        elif ln.startswith(" -1") and mode:
            nd = int(ln[3:13])
            vals = [float(ln[13 + 12 * i: 25 + 12 * i]) for i in range(ncomp)]
            out[mode][nd] = vals
    return out


def vm_nodal(S: dict) -> dict:
    """von Mises por nó a partir de {nó: [sxx,syy,szz,sxy,syz,szx]}."""
    r = {}
    for nd, (sxx, syy, szz, sxy, syz, szx) in S.items():
        r[nd] = float(np.sqrt(0.5 * ((sxx - syy) ** 2 + (syy - szz) ** 2 + (szz - sxx) ** 2) + 3 * (sxy ** 2 + syz ** 2 + szx ** 2)))
    return r


def export_vtk_frd(path, mesh, frd: dict, title="CalculiX") -> None:
    """VTK legado (ParaView) com malha + deslocamento + von Mises NODAL do CalculiX (ids 1..n = índice+1)."""
    n = len(mesh.nodes)
    ten = mesh.tets.shape[1] == 10
    U = np.array([frd["U"].get(i + 1, [0, 0, 0]) for i in range(n)])
    vm = vm_nodal(frd["S"]) if frd["S"] else {}
    L = ["# vtk DataFile Version 3.0", title, "ASCII", "DATASET UNSTRUCTURED_GRID", f"POINTS {n} double"]
    L += [f"{x:.9g} {y:.9g} {z:.9g}" for x, y, z in mesh.nodes]
    m = len(mesh.tets); k = 10 if ten else 4
    L += [f"CELLS {m} {(k + 1) * m}"] + [f"{k} " + " ".join(str(int(a)) for a in t) for t in mesh.tets]
    # ordem dos nós do Tet10 do VTK (24) coincide com a do CalculiX/NEXUS nos nós de aresta 4..9, exceto 8↔9 já tratado na malha
    L += [f"CELL_TYPES {m}"] + [("24" if ten else "10")] * m
    L += [f"POINT_DATA {n}", "VECTORS deslocamento_mm double"] + [f"{a:.9g} {b:.9g} {c:.9g}" for a, b, c in U]
    if vm:
        L += ["SCALARS von_mises_MPa double 1", "LOOKUP_TABLE default"] + [f"{vm.get(i + 1, 0.0):.9g}" for i in range(n)]
    Path(path).write_text("\n".join(L) + "\n")


def vm_from_S(S) -> dict:
    out = {}
    for e, pts in S.items():
        v = []
        for sxx, syy, szz, sxy, sxz, syz in pts:
            v.append(np.sqrt(0.5*((sxx-syy)**2 + (syy-szz)**2 + (szz-sxx)**2) + 3*(sxy**2 + sxz**2 + syz**2)))
        out[e] = float(np.mean(v))
    return out


def run(inp_path, timeout=3600) -> TracedResult:
    st = sr.detect("CalculiX")
    if not st.instalado:
        return TracedResult("CalculiX", "NAO_EXECUTADO", "ccx *STATIC", limitacoes=[f"CalculiX NÃO INSTALADO. {st.instrucao}"])
    p = Path(inp_path); job = p.with_suffix("")
    r = subprocess.run([st.caminho, job.name], cwd=p.parent, capture_output=True, text=True, timeout=timeout)
    dat = job.with_suffix(".dat")
    if r.returncode != 0 or not dat.exists():
        return TracedResult("CalculiX", "NAO_EXECUTADO", "ccx *STATIC", limitacoes=["falha: " + (r.stderr or r.stdout)[-300:]])
    U, S = parse_dat(dat.read_text())
    vm = vm_from_S(S)
    um = max((np.linalg.norm(v) for v in U.values()), default=0.0)
    vals = {"u_max_mm": float(um), "vm_max_MPa": max(vm.values(), default=0.0), "nos": len(U)}
    frd = job.with_suffix(".frd")
    if frd.exists():
        fr = parse_frd(frd.read_text())
        if fr["S"]:
            vals["vm_nodal_max_MPa"] = max(vm_nodal(fr["S"]).values())
            vals["vm_nodal_origem"] = ".frd (extrapolação nodal do CalculiX)"
    return TracedResult("CalculiX", "SIMULACAO_NUMERICA", "ccx *STATIC linear", vals,
                        solver="CalculiX", solver_versao=st.versao or "?", limitacoes=["sem estudo de malha → não validado"])


def compare(nexus_u_max: float, ccx: TracedResult, tol_pct: float = 3.0) -> dict:
    """Cruza deslocamento máximo NEXUS × CalculiX (mesma malha/BC). Sem resultado do ccx não afirma nada."""
    if ccx.classe != "SIMULACAO_NUMERICA":
        return {"status": "NAO_COMPARADO", "motivo": "CalculiX não executado"}
    d = abs(nexus_u_max - ccx.valores["u_max_mm"]) / ccx.valores["u_max_mm"] * 100
    return {"status": "CONCORDA" if d <= tol_pct else "DIVERGE", "diferenca_pct": d}
