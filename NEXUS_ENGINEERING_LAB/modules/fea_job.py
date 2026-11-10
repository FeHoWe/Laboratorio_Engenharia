"""Estudo FEA estático para rodar em PROCESSO ISOLADO (core.jobs.submit_python): argumentos e retorno 100 % JSON.

`run_static(params)` constrói a peça da biblioteca, malha, resolve (NEXUS-Tet) e, se pedido e se `ccx` existir, repete o caso no
CalculiX e lê o `.frd`. Imprime `NEXUS_PROGRESS` por etapa (a interface mostra a barra). Nada é inventado: sem ccx, o campo
`ccx` vem com a classe NAO_EXECUTADO.
"""
from __future__ import annotations

import tempfile
from pathlib import Path


def _p(x: float) -> None:
    print(f"NEXUS_PROGRESS {x}", flush=True)


def run_static(part_key: str, part_params: dict, h: float, E: float, nu: float, ff: str, lf: str, force: list, sy=None,
               mesher: str = "voxel", order: int = 2, out_dir: str = "", ccx: bool = False) -> dict:
    from modules import calculix_io as C, fea3d, fea_study, fea_tet10, solver_registry as sr
    from samples.library import PARTS
    _p(5)
    shape = PARTS[part_key].make(**part_params)
    _p(15)
    res, d = fea_study.run(shape, h, E, nu, ff, lf, tuple(force), sy, nome=f"FEA {part_key}", mesher=mesher, order=order)
    _p(60)
    out = {"result": res.to_dict(), "vtk": None, "ccx": None}
    od = Path(out_dir) if out_dir else Path(tempfile.mkdtemp(prefix="nexus_fea_"))
    od.mkdir(parents=True, exist_ok=True)
    try:
        vtk = od / "resultado_nexus.vtk"
        mesh = d["mesh"]
        if mesh.tets.shape[1] == 4:
            fea3d.export_vtk(str(vtk), mesh, d["u"].reshape(-1, 3), d["vm"])
            out["vtk"] = str(vtk)
    except Exception as e:                                           # exportação é opcional; o resultado numérico segue válido
        out["vtk_erro"] = str(e)
    if ccx:
        st = sr.detect("CalculiX")
        if not st.instalado:
            out["ccx"] = {"classe": "NAO_EXECUTADO", "motivo": f"CalculiX NÃO INSTALADO. {st.instrucao}"}
        else:
            mesh = d["mesh"]
            fx = {i: (0, 1, 2) for i in fea_study.face_nodes(mesh, ff)}
            ln = fea_study.face_nodes(mesh, lf)
            loads = (fea_tet10.surface_load10 if mesh.tets.shape[1] == 10 else fea3d.surface_load)(mesh, ln, tuple(force))
            C.write_inp(mesh, E, nu, fx, loads, od / "ccx.inp", frd=True)
            _p(75)
            r = C.run(od / "ccx.inp", timeout=1800)
            o = {"classe": r.classe, "valores": r.valores, "limitacoes": r.limitacoes}
            if r.classe == "SIMULACAO_NUMERICA":
                import numpy as np
                u = d["u"].reshape(-1, 3)
                o["comparacao"] = C.compare(float(np.linalg.norm(u, axis=1).max()), r, tol_pct=3.0)
                frd = od / "ccx.frd"
                if frd.exists():
                    fr = C.parse_frd(frd.read_text())
                    C.export_vtk_frd(od / "resultado_ccx.vtk", mesh, fr)
                    o["vtk"] = str(od / "resultado_ccx.vtk")
            out["ccx"] = o
    _p(100)
    return out
