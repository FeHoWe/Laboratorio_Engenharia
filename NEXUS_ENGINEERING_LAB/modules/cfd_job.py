"""CFD (OpenFOAM simpleFoam) para rodar em PROCESSO ISOLADO (core.jobs.submit_python): argumentos e retorno 100 % JSON.

Entrada: peça da biblioteca (`part_key`+`part_params`, mm) OU um STL já em metros (`stl_path`, `stl_unit` 'm'|'mm').
O corpo é posicionado com a face x-mín em x=0, centrado em y, com folga `gap_m` do solo; o domínio escala com o comprimento L.
A área de referência é a da CAIXA ENVOLVENTE frontal (y×z) quando não informada — é só referência de normalização, NÃO a área frontal real.
Sem OpenFOAM: retorna NAO_EXECUTADO (sem números). Nada é validado sem referência informada.
"""
from __future__ import annotations

import tempfile
import threading
import time
from pathlib import Path


def _p(x: float) -> None:
    print(f"NEXUS_PROGRESS {x}", flush=True)


def _mesh_from_part(part_key: str, part_params: dict):
    from core.cad_engine import CadEngine
    from samples.library import PARTS
    shape = PARTS[part_key].make(**part_params)
    m = CadEngine().tessellate(shape)
    return m.vertices * 0.001, m.faces                               # peças da biblioteca estão em mm


def area_frontal_projetada(vertices, faces, n: int = 600) -> float:
    """Área PROJETADA no plano y-z (vista de frente, escoamento em +x) por rasterização exata de triângulos (n×n pixels sobre a caixa).

    Erro ≈ perímetro×pixel/2 (para n=600 e esfera: <0,5 %). É a área frontal REAL da malha — melhor referência de Cd que a caixa envolvente.
    """
    import numpy as np
    v = np.asarray(vertices, float)[:, 1:3]
    f = np.asarray(faces)
    lo, hi = v.min(0), v.max(0)
    span = np.maximum(hi - lo, 1e-12)
    scale = (n - 1) / span.max()
    shape = np.ceil(span * scale).astype(int) + 2
    img = np.zeros(shape, bool)
    p = (v - lo) * scale
    for t in f:
        a, b, c = p[t[0]], p[t[1]], p[t[2]]
        x0, x1 = int(np.floor(min(a[0], b[0], c[0]))), int(np.ceil(max(a[0], b[0], c[0])))
        y0, y1 = int(np.floor(min(a[1], b[1], c[1]))), int(np.ceil(max(a[1], b[1], c[1])))
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(den) < 1e-12:
            continue
        X, Y = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5, indexing="ij")
        l1 = ((b[1] - c[1]) * (X - c[0]) + (c[0] - b[0]) * (Y - c[1])) / den
        l2 = ((c[1] - a[1]) * (X - c[0]) + (a[0] - c[0]) * (Y - c[1])) / den
        m = (l1 >= 0) & (l2 >= 0) & (l1 + l2 <= 1)
        img[x0:x1 + 1, y0:y1 + 1] |= m
    return float(img.sum() / scale ** 2)


def preparar_caso(pasta, vertices, faces, v_inf: float, iteracoes: int, celulas, gap_m: float, a_ref: float | None, rho: float, nu: float,
                  dominio=(2.0, 6.0, 2.0, 3.0), ar_livre: bool = False, camadas: int = 0) -> dict:
    """Escreve o caso OpenFOAM + STL. `dominio` = (a montante, a jusante, meia-largura, altura) em múltiplos de L."""
    import numpy as np
    import trimesh
    from modules import cfd_case
    v = np.asarray(vertices, float).copy()
    lo, hi = v.min(0), v.max(0)
    ext = hi - lo
    L = float(ext.max())
    if L <= 0:
        raise ValueError("geometria vazia")
    up, down, half, top = dominio
    if ar_livre:                                                    # corpo centrado num domínio simétrico em y e z (sem solo)
        H = 2 * half * L
        gap_m = H / 2 - ext[2] / 2
    v -= np.array([lo[0], (lo[1] + hi[1]) / 2, lo[2]])
    v[:, 2] += gap_m
    a_caixa = float(ext[1] * ext[2])
    a_proj = area_frontal_projetada(v, faces)
    a_ref_usada = a_ref if a_ref else a_proj
    caixa = (-up * L, down * L, -half * L, half * L, 0.0, H if ar_livre else max(top * L, gap_m + ext[2] + L))
    bloqueio = a_caixa / ((caixa[3] - caixa[2]) * (caixa[5] - caixa[4]))
    p = cfd_case.gerar_caso_openfoam(pasta, "corpo.stl", v_inf, float(ext[0]), a_ref_usada, rho=rho, nu=nu, caixa=caixa,
                                     iteracoes=iteracoes, celulas=tuple(celulas), ar_livre=ar_livre, camadas=camadas)
    trimesh.Trimesh(vertices=v, faces=np.asarray(faces), process=False).export(p / "constant/triSurface/corpo.stl")
    return {"pasta": str(p), "L_m": L, "origem_m": [float(lo[0]), float((lo[1] + hi[1]) / 2), float(lo[2])], "gap_m": float(gap_m), "a_ref_m2": a_ref_usada, "a_ref_origem": "informada" if a_ref else "área frontal PROJETADA da malha (rasterizada) — não a da caixa", "a_caixa_m2": a_caixa, "a_proj_m2": a_proj,
            "ar_livre": ar_livre,
            "bloqueio_pct": 100 * bloqueio, "caixa_m": list(caixa), "extensao_m": ext.tolist()}


def para_coords_originais(pontos_m, origem_m, gap_m: float, unidade_m: float):
    """Desfaz o posicionamento do caso: volta à posição/escala ORIGINAIS da geometria (unidade_m = metros por unidade, ex. 0,001 p/ mm)."""
    import numpy as np
    p = np.asarray(pontos_m, float).copy()
    p[:, 2] -= gap_m
    return (p + np.asarray(origem_m, float)) / unidade_m


def run_case(part_key: str = "", part_params: dict | None = None, stl_path: str = "", stl_unit: str = "m", v_inf: float = 20.0,
             iteracoes: int = 300, celulas: list | tuple = (60, 24, 18), gap_m: float = 0.0, a_ref: float | None = None,
             rho: float = 1.225, nu: float = 1.5e-5, ar_livre: bool = False, camadas: int = 0, cd_ref: float | None = None, ref_texto: str = "", out_dir: str = "",
             timeout: int = 3600) -> dict:
    import numpy as np
    from modules import cfd_case, solver_registry as sr
    _p(2)
    st = sr.detect("OpenFOAM")
    if not st.instalado:
        r = cfd_case.executar_openfoam(out_dir or tempfile.gettempdir())   # devolve NAO_EXECUTADO com a instrução de instalação
        return {"result": r.to_dict(), "campo": None, "info": None}
    unidade_m = 0.001 if (part_key and not stl_path) or stl_unit == "mm" else 1.0
    if stl_path:
        import trimesh
        m = trimesh.load(stl_path, force="mesh")
        vert = np.asarray(m.vertices, float) * (0.001 if stl_unit == "mm" else 1.0)
        fac = np.asarray(m.faces)
    elif part_key:
        vert, fac = _mesh_from_part(part_key, part_params or {})
    else:
        raise ValueError("informe uma peça da biblioteca ou um STL")
    od = Path(out_dir) if out_dir else Path(tempfile.mkdtemp(prefix="nexus_cfd_"))
    info = preparar_caso(od / "caso", vert, fac, v_inf, iteracoes, celulas, gap_m, a_ref, rho, nu, ar_livre=ar_livre, camadas=camadas)
    pasta = Path(info["pasta"])
    _p(8)
    stop = threading.Event()

    def vigia():                                                    # progresso = iterações já escritas no log do simpleFoam
        lg = pasta / "log.simpleFoam"
        while not stop.wait(1.0):
            try:
                n = sum(1 for ln in lg.read_text(errors="replace").splitlines() if ln.startswith("Time = "))
                _p(10 + 85 * min(n / max(iteracoes, 1), 1.0))
            except OSError:
                pass                                                # malhando ainda: log não existe
    th = threading.Thread(target=vigia, daemon=True)
    th.start()
    try:
        res = cfd_case.executar_openfoam(pasta, timeout=timeout, cd_ref=cd_ref, ref_texto=ref_texto)
    finally:
        stop.set()
        th.join(timeout=2)
    res.entradas.update({"v_inf_m_s": v_inf, "rho": rho, "nu": nu, "celulas": list(celulas), "iteracoes_pedidas": iteracoes, **{k: info[k] for k in ("L_m", "a_ref_m2", "a_ref_origem", "bloqueio_pct")}})
    if info["bloqueio_pct"] > 5:
        res.limitacoes.insert(0, f"bloqueio do domínio {info['bloqueio_pct']:.1f} % (>5 %): paredes interferem no escoamento")
    out = {"result": res.to_dict(), "campo": None, "info": info}
    if res.classe != "NAO_EXECUTADO":
        try:
            fp = cfd_case.forcas_pressao(pasta, "body", rho=rho, v_inf=v_inf, a_ref=info["a_ref_m2"], detalhe=True)
            f = od / "campo_cp.npz"
            np.savez_compressed(f, pontos=fp["pontos"], faces_len=np.array([len(x) for x in fp["faces"]]),
                                faces_idx=np.concatenate([np.asarray(x) for x in fp["faces"]]), cp=fp["cp"],
                                pontos_orig=para_coords_originais(fp["pontos"], info["origem_m"], info["gap_m"], unidade_m),
                                unidade=np.array("mm" if unidade_m == 0.001 else "m"))
            out["campo"] = str(f)
            out["pressao"] = {"cd_pressao": fp["cd_pressao"], "cl_pressao": fp["cl_pressao"], "tempo": fp["tempo"], "obs": fp["obs"]}
        except Exception as e:
            out["campo_erro"] = str(e)[:200]
    _p(100)
    return out
