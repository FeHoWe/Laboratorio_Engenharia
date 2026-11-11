"""Verificação de ambiente para o Windows 11 (e WSL2/GPU) — rode NA SUA MÁQUINA:  python tools/verificar_windows.py

Executa o diagnóstico do NEXUS (Python, bibliotecas, OpenCASCADE, Gmsh, CalculiX, OpenFOAM/WSL2, GPU/OpenGL) e MAIS provas funcionais:
solve FEA pequeno, geração de caso CFD, backup do Arsenal, abertura offscreen do visualizador. Grava `verificacao_windows.txt` e `.json`
na pasta atual. Cada item é PASSOU / FALHOU / NÃO APLICÁVEL — nada é presumido. Envie o .txt de volta para eu corrigir o que falhar.
"""
from __future__ import annotations

import json
import os
import platform
import sys
import tempfile
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen" if os.name != "nt" else os.environ.get("QT_QPA_PLATFORM", "windows"))


def _t(nome, fn):
    t = time.time()
    try:
        r = fn()
        return {"teste": nome, "estado": "NAO_APLICAVEL" if r is None else "PASSOU", "detalhe": r or "", "s": round(time.time() - t, 2)}
    except Exception as e:
        return {"teste": nome, "estado": "FALHOU", "detalhe": f"{type(e).__name__}: {e}", "trace": traceback.format_exc()[-600:], "s": round(time.time() - t, 2)}


def t_fea():
    from modules import fea_study
    from samples.library import PARTS
    k = next(iter(PARTS))
    res, d = fea_study.run(PARTS[k].make(), 4.0, 200000, 0.3, "xmin", "xmax", (0, 0, -100), None, mesher="voxel", order=1)
    assert res.classe == "SIMULACAO_NUMERICA" and res.valores
    return f"{res.classe}, {len(d['mesh'].tets)} tetraedros"


def t_cfd_caso():
    from modules import cfd_case
    p = cfd_case.gerar_caso_openfoam(Path(tempfile.mkdtemp()) / "c", "c.stl", 20, 1.0, 1.0)
    assert (p / "system/blockMeshDict").exists()
    return "caso OpenFOAM gerado"


def t_openfoam():
    from modules import solver_registry as sr
    st = sr.detect("OpenFOAM")
    return None if not st.instalado else f"{st.versao} via {st.caminho}"


def t_calculix():
    from modules import solver_registry as sr
    st = sr.detect("CalculiX")
    return None if not st.instalado else f"{st.versao}"


def t_arsenal():
    from modules.arsenal import Arsenal
    d = Path(tempfile.mkdtemp()) / "a.db"
    a = Arsenal(d); a.add_component("t", a.categories()[0], {"part_key": "x"}); a.close()
    Arsenal(d).close()
    return f"{len(Arsenal.list_backups(d))} backup(s)"


def t_viewport():
    from PySide6.QtWidgets import QApplication
    from interface.viewport import Viewport
    import numpy as np
    app = QApplication.instance() or QApplication([])
    vp = Viewport()
    vp.show_field(np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]], float), np.array([[0, 1, 2, 3]]), np.arange(4.0), "point")
    return "mapa de campo criado"


def main() -> int:
    from core import doctor
    cab = [f"NEXUS — verificação de ambiente  {time.strftime('%Y-%m-%d %H:%M:%S')}", f"{platform.platform()} | Python {platform.python_version()}", ""]
    checks = doctor.run_all()
    rel = {"sistema": platform.platform(), "python": platform.python_version(), "diagnostico": [c.__dict__ for c in checks], "testes": []}
    cab.append("== Diagnóstico ==")
    cab += [f"[{c.estado:>22}] {c.nome} {c.versao} {c.detalhe}" + (f"  → {c.instalacao}" if (not c.ok and c.instalacao) else "") for c in checks]
    cab += ["", "== Provas funcionais =="]
    for nome, fn in (("FEA pequeno (NEXUS-Tet4)", t_fea), ("Gerar caso CFD", t_cfd_caso), ("OpenFOAM acessível", t_openfoam), ("CalculiX acessível", t_calculix),
                     ("Arsenal + backup", t_arsenal), ("Visualizador (mapa de campo)", t_viewport)):
        r = _t(nome, fn); rel["testes"].append(r)
        cab.append(f"[{r['estado']:>13}] {nome}: {r['detalhe']} ({r['s']} s)" + (f"\n{r.get('trace', '')}" if r["estado"] == "FALHOU" else ""))
    falhas = [r for r in rel["testes"] if r["estado"] == "FALHOU"] + [c for c in checks if not c.ok and c.obrigatorio]
    cab += ["", f"RESULTADO: {'COM FALHAS (' + str(len(falhas)) + ')' if falhas else 'sem falhas nos itens obrigatórios/funcionais'}"]
    Path("verificacao_windows.txt").write_text("\n".join(cab), encoding="utf-8")
    Path("verificacao_windows.json").write_text(json.dumps(rel, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print("\n".join(cab))
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
