"""Aerodinâmica em 3 níveis + gerador de caso OpenFOAM (simpleFoam, k-ω SST).

Nível 1 (ANALITICO): F = ½ρv²·CdA com coeficientes informados (modules.aero).
Nível 2 (ANALITICO): estimativa de arrasto de atrito por placa plana + arrasto de forma
    por Cd informado; nenhum coeficiente é inventado.
Nível 3 (SIMULACAO_NUMERICA): gera o caso OpenFOAM (blockMesh + STL via snappyHexMesh)
    e só EXECUTA se o OpenFOAM estiver instalado; senão devolve NAO_EXECUTADO.
Resultados do nível 3 NÃO são VALIDADOS sem referência informada.
"""
from __future__ import annotations
import math, shutil, subprocess
from pathlib import Path
from . import aero, solver_registry as sr
from .result_trace import TracedResult

def nivel1(cda: float, rho: float, v: float) -> TracedResult:
    if cda <= 0 or rho <= 0 or v < 0: raise ValueError("entradas inválidas")
    return TracedResult("Aero nível 1", "ANALITICO", "F = ½ρv²(CdA)",
        {"forca_N": aero.force(cda, rho, v), "q_Pa": aero.dynamic_pressure(rho, v)},
        {"CdA": cda, "rho": rho, "v": v}, ["coeficiente CdA informado pelo usuário"],
        ["não resolve o escoamento", "sem interferência entre componentes"])

def nivel2(cd_forma: float, area_frontal: float, area_molhada: float, comprimento: float, rho: float, v: float, mu: float = 1.81e-5) -> TracedResult:
    if min(area_frontal, area_molhada, comprimento, rho, v) <= 0: raise ValueError("entradas inválidas")
    re = aero.reynolds(rho, v, comprimento, mu); cf = aero.cf_flat_plate_turbulent(re)
    q = aero.dynamic_pressure(rho, v)
    df = q * cf * area_molhada; dp = q * cd_forma * area_frontal
    return TracedResult("Aero nível 2", "ANALITICO", "Atrito de placa plana turbulenta + arrasto de forma (Cd informado)",
        {"Re": re, "Cf": cf, "arrasto_atrito_N": df, "arrasto_forma_N": dp, "arrasto_total_N": df + dp},
        {"cd_forma": cd_forma, "A_frontal": area_frontal, "A_molhada": area_molhada, "L": comprimento, "rho": rho, "v": v, "mu": mu},
        ["Cf de placa plana turbulenta", "soma linear atrito + forma (sem interação)"],
        ["Cf de placa plana pode errar muito em corpos 3D", "Cd de forma depende do usuário"])

def gerar_caso_openfoam(pasta, stl_nome: str, v_inf: float, comprimento_ref: float, area_ref: float,
                        rho: float = 1.225, nu: float = 1.5e-5, caixa=(-2, 6, -2, 2, 0, 3), iteracoes: int = 1000, celulas=(80, 32, 24)) -> Path:
    """Escreve system/ constant/ 0/ prontos. O STL deve ser copiado para constant/triSurface/ (em m)."""
    if v_inf <= 0 or area_ref <= 0 or comprimento_ref <= 0: raise ValueError("entradas inválidas")
    p = Path(pasta)
    for d in ("system", "constant/triSurface", "0"): (p / d).mkdir(parents=True, exist_ok=True)
    H = 'FoamFile { version 2.0; format ascii; class %s; object %s; }\n'
    x0, x1, y0, y1, z0, z1 = caixa
    (p/"system/blockMeshDict").write_text(H % ("dictionary", "blockMeshDict") + f"""convertToMeters 1;
vertices ( ({x0} {y0} {z0}) ({x1} {y0} {z0}) ({x1} {y1} {z0}) ({x0} {y1} {z0}) ({x0} {y0} {z1}) ({x1} {y0} {z1}) ({x1} {y1} {z1}) ({x0} {y1} {z1}) );
blocks ( hex (0 1 2 3 4 5 6 7) ({celulas[0]} {celulas[1]} {celulas[2]}) simpleGrading (1 1 1) );
boundary ( inlet {{type patch; faces ((0 4 7 3));}} outlet {{type patch; faces ((1 2 6 5));}}
 ground {{type wall; faces ((0 3 2 1));}} top {{type symmetryPlane; faces ((4 5 6 7));}}
 sideL {{type symmetryPlane; faces ((0 1 5 4));}} sideR {{type symmetryPlane; faces ((3 7 6 2));}} );
""")
    (p/"system/controlDict").write_text(H % ("dictionary", "controlDict") + f"""application simpleFoam; startFrom startTime; startTime 0; stopAt endTime;
endTime {iteracoes}; deltaT 1; writeControl timeStep; writeInterval {iteracoes};
functions {{ forces {{ type forces; libs (forces); writeControl timeStep; writeInterval 10; patches (body);
 rho rhoInf; rhoInf {rho}; CofR (0 0 0); }}
 forceCoeffs {{ type forceCoeffs; libs (forceCoeffs); writeControl timeStep; writeInterval 10; patches (body);
 rho rhoInf; rhoInf {rho}; liftDir (0 0 1); dragDir (1 0 0); CofR (0 0 0); pitchAxis (0 1 0);
 magUInf {v_inf}; lRef {comprimento_ref}; Aref {area_ref}; }} }}
""")
    (p/"system/fvSchemes").write_text(H % ("dictionary", "fvSchemes") + """ddtSchemes {default steadyState;} gradSchemes {default Gauss linear;}
divSchemes {default none; div(phi,U) bounded Gauss linearUpwind grad(U); div(phi,k) bounded Gauss upwind; div(phi,omega) bounded Gauss upwind; div((nuEff*dev2(T(grad(U))))) Gauss linear;}
laplacianSchemes {default Gauss linear corrected;} interpolationSchemes {default linear;} snGradSchemes {default corrected;} wallDist {method meshWave;}
""")
    (p/"system/fvSolution").write_text(H % ("dictionary", "fvSolution") + """solvers { p {solver GAMG; smoother GaussSeidel; tolerance 1e-7; relTol 0.01;} "(U|k|omega)" {solver smoothSolver; smoother symGaussSeidel; tolerance 1e-8; relTol 0.1;} }
SIMPLE { nNonOrthogonalCorrectors 0; consistent yes; residualControl { p 1e-4; U 1e-5; "(k|omega)" 1e-5; } }
relaxationFactors { equations { U 0.9; ".*" 0.9; } }
""")
    (p/"system/snappyHexMeshDict").write_text(H % ("dictionary", "snappyHexMeshDict") + f"""castellatedMesh true; snap true; addLayers false;
geometry {{ {stl_nome} {{ type triSurfaceMesh; name body; }} }}
castellatedMeshControls {{ maxLocalCells 2000000; maxGlobalCells 4000000; minRefinementCells 10; nCellsBetweenLevels 3; resolveFeatureAngle 30;
 features (); refinementSurfaces {{ body {{ level (2 3); patchInfo {{ type wall; }} }} }} refinementRegions {{}} locationInMesh ({x0+0.05*(x1-x0)} 0.0 {z1-0.05*(z1-z0)}); allowFreeStandingZoneFaces true; }}
snapControls {{ nSmoothPatch 3; tolerance 2.0; nSolveIter 30; nRelaxIter 5; nFeatureSnapIter 10; }}
addLayersControls {{ layers {{}} relativeSizes true; expansionRatio 1.2; finalLayerThickness 0.3; minThickness 0.1; nGrow 0; featureAngle 60; nRelaxIter 3; nSmoothSurfaceNormals 1; nSmoothNormals 3; nSmoothThickness 10; maxFaceThicknessRatio 0.5; maxThicknessToMedialRatio 0.3; minMedialAxisAngle 90; nBufferCellsNoExtrude 0; nLayerIter 50; }}
meshQualityControls {{ maxNonOrtho 65; maxBoundarySkewness 20; maxInternalSkewness 4; maxConcave 80; minVol 1e-13; minTetQuality 1e-15; minArea -1; minTwist 0.02; minDeterminant 0.001; minFaceWeight 0.05; minVolRatio 0.01; minTriangleTwist -1; nSmoothScale 4; errorReduction 0.75; }}
mergeTolerance 1e-6;
""")
    (p/"constant/transportProperties").write_text(H % ("dictionary", "transportProperties") + f"transportModel Newtonian; nu [0 2 -1 0 0 0 0] {nu};\n")
    # v2012+/Foundation leem momentumTransport (chave `model`); ESI v1912 e anteriores leem turbulenceProperties (chave `RASModel`)
    for nome, chave in (("momentumTransport", "model"), ("turbulenceProperties", "RASModel")):
        (p/f"constant/{nome}").write_text(H % ("dictionary", nome) + f"simulationType RAS; RAS {{ {chave} kOmegaSST; turbulence on; printCoeffs on; }}\n")
    I = 0.01; k = 1.5 * (v_inf * I) ** 2; om = k ** 0.5 / (0.09 ** 0.25 * comprimento_ref * 0.1)
    def field(cls, name, dims, internal, bc):
        (p/f"0/{name}").write_text(H % (cls, name) + f"dimensions {dims}; internalField {internal};\nboundaryField {{ {bc} }}\n")
    field("volVectorField", "U", "[0 1 -1 0 0 0 0]", f"uniform ({v_inf} 0 0)",
          f"inlet {{type fixedValue; value uniform ({v_inf} 0 0);}} outlet {{type zeroGradient;}} ground {{type noSlip;}} body {{type noSlip;}} top {{type symmetryPlane;}} sideL {{type symmetryPlane;}} sideR {{type symmetryPlane;}}")
    field("volScalarField", "p", "[0 2 -2 0 0 0 0]", "uniform 0",
          "inlet {type zeroGradient;} outlet {type fixedValue; value uniform 0;} ground {type zeroGradient;} body {type zeroGradient;} top {type symmetryPlane;} sideL {type symmetryPlane;} sideR {type symmetryPlane;}")
    field("volScalarField", "k", "[0 2 -2 0 0 0 0]", f"uniform {k:.6g}",
          f"inlet {{type fixedValue; value uniform {k:.6g};}} outlet {{type zeroGradient;}} ground {{type kqRWallFunction; value uniform {k:.6g};}} body {{type kqRWallFunction; value uniform {k:.6g};}} top {{type symmetryPlane;}} sideL {{type symmetryPlane;}} sideR {{type symmetryPlane;}}")
    field("volScalarField", "omega", "[0 0 -1 0 0 0 0]", f"uniform {om:.6g}",
          f"inlet {{type fixedValue; value uniform {om:.6g};}} outlet {{type zeroGradient;}} ground {{type omegaWallFunction; value uniform {om:.6g};}} body {{type omegaWallFunction; value uniform {om:.6g};}} top {{type symmetryPlane;}} sideL {{type symmetryPlane;}} sideR {{type symmetryPlane;}}")
    field("volScalarField", "nut", "[0 2 -1 0 0 0 0]", "uniform 0",
          "inlet {type calculated; value uniform 0;} outlet {type calculated; value uniform 0;} ground {type nutkWallFunction; value uniform 0;} body {type nutkWallFunction; value uniform 0;} top {type symmetryPlane;} sideL {type symmetryPlane;} sideR {type symmetryPlane;}")
    (p/"Allrun").write_text("#!/bin/sh\nblockMesh && surfaceFeatureExtract 2>/dev/null; snappyHexMesh -overwrite && simpleFoam > log.simpleFoam 2>&1\n")
    return p

def _ler_coeficientes(pasta: Path):
    """Última linha de postProcessing/forceCoeffs/*/coefficient.dat → (iteração, Cd, Cl) ou None (nada é inventado)."""
    arqs = sorted(Path(pasta).glob("postProcessing/forceCoeffs/*/coefficient*.dat"))
    if not arqs:
        return None
    cab, ult = None, None
    for ln in arqs[-1].read_text().splitlines():
        if ln.startswith("#"):
            if "Cd" in ln and "Cl" in ln:
                cab = ln.lstrip("# ").split()
            continue
        if ln.strip():
            ult = ln.split()
    if not ult or not cab:
        return None
    d = dict(zip(cab, ult))
    return int(float(d.get("Time", ult[0]))), float(d["Cd"]), float(d["Cl"])


def ler_log_simplefoam(texto: str) -> dict:
    """Convergência a partir do log do simpleFoam: nº de iterações, resíduos finais iniciais, flag 'convergiu', NaN/erro fatal."""
    import re
    n = len(re.findall(r"^Time = ", texto, flags=re.M))
    res = {}
    for campo in ("Ux", "Uy", "Uz", "p", "k", "omega"):
        m = re.findall(rf"Solving for {campo}, Initial residual = ([0-9.eE+-]+)", texto)
        if m:
            res[campo] = float(m[-1])
    return {"iteracoes": n, "residuos_iniciais_finais": res, "convergiu": "SIMPLE solution converged" in texto,
            "erro_fatal": ("FOAM FATAL" in texto) or bool(re.search(r"(Initial residual|Final residual) = nan|\bsigFpe\b", texto, flags=re.I))}


# ---------------------------------------------------------------- pós-processamento próprio (força de pressão)
def _blocos_lista(texto: str):
    """Interpreta o conteúdo de uma lista OpenFOAM ASCII `N ( ... )` → lista de linhas internas."""
    i = texto.index("(", texto.index("\n", texto.find("FoamFile")) if "FoamFile" in texto else 0)
    # pula até a primeira linha que contém só N (contagem) seguida de '('
    import re
    m = re.search(r"^\s*(\d+)\s*\n?\s*\(", texto, flags=re.M)
    n = int(m.group(1))
    corpo = texto[m.end():]
    return n, corpo


def _ler_patch_boundary(pasta: Path, patch: str):
    import re
    t = (Path(pasta) / "constant/polyMesh/boundary").read_text()
    m = re.search(rf"\b{re.escape(patch)}\s*\{{(.*?)\}}", t, flags=re.S)
    if not m:
        raise KeyError(f"patch '{patch}' não existe na malha")
    nf = int(re.search(r"nFaces\s+(\d+)", m.group(1)).group(1))
    sf = int(re.search(r"startFace\s+(\d+)", m.group(1)).group(1))
    return sf, nf


def forcas_pressao(pasta, patch: str = "body", rho: float = 1.225, v_inf: float = 1.0, a_ref: float = 1.0,
                   drag_dir=(1, 0, 0), lift_dir=(0, 0, 1), tempo: str | None = None, detalhe: bool = False) -> dict:
    """Força de PRESSÃO sobre `patch` por integração própria: F = ρ·Σ p_cin·S_f (S_f aponta para dentro do corpo).

    NÃO inclui atrito viscoso (tensão de cisalhamento) — logo `cd_pressao` ≤ Cd total para corpos com atrito relevante.
    Existe porque certos builds de OpenFOAM abortam ao carregar função-objeto `forces`. Lê malha/campos ASCII.
    """
    import re
    import numpy as np
    pasta = Path(pasta)
    sf, nf = _ler_patch_boundary(pasta, patch)
    pm = pasta / "constant/polyMesh"
    n_pts, corpo = _blocos_lista((pm / "points").read_text())
    pts = np.array([[float(x) for x in ln.split()] for ln in re.findall(r"^\(([^)]*)\)", corpo, flags=re.M)][:n_pts], float)
    n_f, corpo = _blocos_lista((pm / "faces").read_text())
    faces = [[int(x) for x in m.split()] for m in re.findall(r"^\d+\(([^)]*)\)", corpo, flags=re.M)]
    if len(pts) != n_pts or len(faces) != n_f:
        raise ValueError("malha ilegível (formato não é ASCII?)")
    if tempo is None:
        tempos = sorted((float(d.name), d.name) for d in pasta.iterdir() if d.is_dir() and re.fullmatch(r"[0-9.]+", d.name) and float(d.name) > 0)
        if not tempos:
            raise FileNotFoundError("nenhum passo de tempo escrito (o solver não gravou resultado)")
        tempo = tempos[-1][1]
    ptxt = (pasta / tempo / "p").read_text()
    m = re.search(rf"\b{re.escape(patch)}\s*\{{(.*?)\n\s*\}}", ptxt, flags=re.S)
    if not m:
        raise KeyError(f"campo p sem patch '{patch}'")
    bloco = m.group(1)
    mu = re.search(r"value\s+uniform\s+([-0-9.eE+]+)", bloco)
    if mu:
        pv = np.full(nf, float(mu.group(1)))
    elif "nonuniform" not in bloco:
        # zeroGradient não grava valor na parede: p_parede = p da célula dona da face (definição de zeroGradient)
        n_o, corpo_o = _blocos_lista((pm / "owner").read_text())
        owner = np.array(corpo_o.split(")")[0].split(), int)[:n_o]
        mi = re.search(r"internalField\s+(uniform\s+([-0-9.eE+]+)|nonuniform\s+List<scalar>\s*\n?\s*(\d+)\s*\(([^)]*)\))", ptxt, flags=re.S)
        if mi.group(2) is not None:
            pv = np.full(nf, float(mi.group(2)))
        else:
            interno = np.array(mi.group(4).split(), float)
            pv = interno[owner[sf:sf + nf]]
    else:
        k = bloco.index("nonuniform")
        mm = re.search(r"(\d+)\s*\(([^)]*)\)", bloco[k:], flags=re.S)
        pv = np.array(mm.group(2).split(), float)
        if len(pv) != nf:
            raise ValueError("campo p do patch com tamanho diferente do nº de faces")
    F = np.zeros(3)
    area = 0.0
    if detalhe:                                                      # geometria + p cinemático por face (para mapa de Cp no visualizador)
        usados = sorted({k for i in range(nf) for k in faces[sf + i]})
        remap = {k: j for j, k in enumerate(usados)}
        det = {"pontos": pts[usados], "faces": [[remap[k] for k in faces[sf + i]] for i in range(nf)], "p_cin": np.asarray(pv, float)}
    for i in range(nf):
        idx = faces[sf + i]
        P = pts[idx]
        Sf = 0.5 * sum(np.cross(P[k] - P[0], P[k + 1] - P[0]) for k in range(1, len(idx) - 1))
        F += pv[i] * Sf * rho
        area += np.linalg.norm(Sf)
    q = 0.5 * rho * v_inf ** 2
    dd, ld = np.array(drag_dir, float), np.array(lift_dir, float)
    out = {"tempo": tempo, "forca_N": F.tolist(), "area_patch_m2": float(area), "cd_pressao": float(F @ dd / (q * a_ref)),
           "cl_pressao": float(F @ ld / (q * a_ref)), "obs": "somente pressão; sem atrito viscoso"}
    if detalhe:
        out.update(det)
        out["cp"] = det["p_cin"] / (0.5 * v_inf ** 2)                # Cp = p_cin/(½V²), pressão de referência = 0 (saída)
    return out


def _ler_malha(pasta: Path):
    """points, faces, owner, neighbour (ASCII) → (pts, faces, owner, neigh)."""
    import re
    import numpy as np
    pm = Path(pasta) / "constant/polyMesh"
    n_pts, corpo = _blocos_lista((pm / "points").read_text())
    pts = np.array([[float(x) for x in ln.split()] for ln in re.findall(r"^\(([^)]*)\)", corpo, flags=re.M)][:n_pts], float)
    n_f, corpo = _blocos_lista((pm / "faces").read_text())
    faces = [[int(x) for x in m.split()] for m in re.findall(r"^\d+\(([^)]*)\)", corpo, flags=re.M)]
    n_o, co = _blocos_lista((pm / "owner").read_text())
    owner = np.array(co.split(")")[0].split(), int)[:n_o]
    n_n, cn = _blocos_lista((pm / "neighbour").read_text())
    neigh = np.array(cn.split(")")[0].split(), int)[:n_n]
    return pts, faces, owner, neigh


def _lista_campo(txt: str, vetor: bool):
    """Primeira lista `nonuniform List<...> N (...)` do texto → array (N,) ou (N,3)."""
    import re
    import numpy as np
    m = re.search(r"nonuniform\s+List<(?:scalar|vector)>\s*\n?\s*(\d+)\s*\n?\s*\(", txt)
    if not m:
        return None
    n = int(m.group(1))
    corpo = txt[m.end():]
    if vetor:
        v = np.array([[float(x) for x in ln.split()] for ln in re.findall(r"^\(([^)]*)\)", corpo, flags=re.M)][:n], float)
    else:
        v = np.array(corpo.split(")")[0].split(), float)[:n]
    return v if len(v) == n else None


def forcas_viscosas(pasta, patch: str = "body", rho: float = 1.225, nu: float = 1.5e-5, v_inf: float = 1.0, a_ref: float = 1.0,
                    drag_dir=(1, 0, 0), lift_dir=(0, 0, 1), tempo: str | None = None) -> dict:
    """ESTIMATIVA do atrito viscoso: τ_w = ρ(ν+ν_t,parede)·U_t/y por face (lei da parede), integrada sobre `patch`.

    U_t = velocidade da célula dona menos sua componente normal; y = distância do centro da célula à face (centro da célula por média
    dos centros de suas faces — aproximação). ν_t,parede vem do `nut` gravado pelo nutkWallFunction. NÃO é a função-objeto
    `wallShearStress` (quebrada neste build): é uma estimativa de 1ª ordem, adequada a ordem de grandeza e tendência, não a valores finos.
    """
    import re
    import numpy as np
    pasta = Path(pasta)
    sf, nf = _ler_patch_boundary(pasta, patch)
    pts, faces, owner, neigh = _ler_malha(pasta)
    if tempo is None:
        tempos = sorted((float(d.name), d.name) for d in pasta.iterdir() if d.is_dir() and re.fullmatch(r"[0-9.]+", d.name) and float(d.name) > 0)
        if not tempos:
            raise FileNotFoundError("nenhum passo de tempo escrito")
        tempo = tempos[-1][1]
    U = _lista_campo((pasta / tempo / "U").read_text(), True)
    if U is None:
        raise ValueError("U com internalField uniforme/ilegível")
    nut_txt = (pasta / tempo / "nut").read_text()
    m = re.search(rf"\b{re.escape(patch)}\s*\{{(.*?)\n\s*\}}", nut_txt, flags=re.S)
    nutw = _lista_campo(m.group(1), False) if m else None
    if nutw is None or len(nutw) != nf:
        raise ValueError("nut do patch ausente (sem função de parede) — atrito não estimado")
    ncell = len(U)
    # centros de face e de célula
    fc, fa = [], []
    for idx in faces:
        P = pts[idx]; c0 = P.mean(0); S = np.zeros(3); wsum = 0.0; cc = np.zeros(3)
        for k in range(len(idx)):
            a, b = P[k], P[(k + 1) % len(idx)]
            ar = 0.5 * np.cross(a - c0, b - c0); w = np.linalg.norm(ar)
            S += ar; wsum += w; cc += w * (c0 + a + b) / 3
        fc.append(cc / wsum if wsum > 0 else c0); fa.append(S)
    fc = np.array(fc); fa = np.array(fa)
    cen = np.zeros((ncell, 3)); cnt = np.zeros(ncell)
    for i, o in enumerate(owner):
        cen[o] += fc[i]; cnt[o] += 1
    for i, n in enumerate(neigh):
        cen[n] += fc[i]; cnt[n] += 1
    cen /= np.maximum(cnt, 1)[:, None]
    F = np.zeros(3); area = 0.0; ymin, ymax = 1e9, 0.0
    for i in range(nf):
        f = sf + i; Sf = fa[f]; A = np.linalg.norm(Sf)
        n = Sf / A; c = owner[f]
        y = abs((cen[c] - fc[f]) @ n)
        Ut = U[c] - (U[c] @ n) * n
        F += rho * (nu + nutw[i]) * Ut / max(y, 1e-12) * A
        area += A; ymin, ymax = min(ymin, y), max(ymax, y)
    q = 0.5 * rho * v_inf ** 2
    dd, ld = np.array(drag_dir, float), np.array(lift_dir, float)
    return {"tempo": tempo, "forca_N": F.tolist(), "area_patch_m2": float(area), "cd_atrito": float(F @ dd / (q * a_ref)), "cl_atrito": float(F @ ld / (q * a_ref)),
            "y_primeira_celula_m": [float(ymin), float(ymax)],
            "obs": "ESTIMATIVA de 1ª ordem (lei da parede, centro de célula aproximado); não é a função-objeto wallShearStress"}


def _ler_rho(pasta) -> float:
    import re
    m = re.search(r"rhoInf\s+([-0-9.eE+]+)", (Path(pasta) / "system/controlDict.com_funcoes").read_text())
    return float(m.group(1))


def _ler_nu(pasta) -> float:
    import re
    t = (Path(pasta) / "constant/transportProperties").read_text()
    return float(re.search(r"\bnu\s+(?:\[[^\]]*\]\s+)?([-0-9.eE+]+)", t).group(1))


def _ler_vinf(pasta) -> float:
    import re
    return float(re.search(r"magUInf\s+([-0-9.eE+]+)", (Path(pasta) / "system/controlDict.com_funcoes").read_text()).group(1))


def _ler_aref(pasta) -> float:
    import re
    return float(re.search(r"Aref\s+([-0-9.eE+]+)", (Path(pasta) / "system/controlDict.com_funcoes").read_text()).group(1))


def executar_openfoam(pasta, timeout=3600, cd_ref: float | None = None, cd_tol_pct: float = 10.0, ref_texto: str = "") -> TracedResult:
    """Executa o caso se OpenFOAM instalado; senão NAO_EXECUTADO (sem números).

    Devolve Cd/Cl (forceCoeffs), iterações e convergência lidos dos arquivos reais. Só vira VALIDADO se `cd_ref` (e `ref_texto`)
    forem informados e o Cd concordar dentro de `cd_tol_pct`.
    """
    st = sr.detect("OpenFOAM")
    if not st.instalado:
        return TracedResult("CFD OpenFOAM", "NAO_EXECUTADO", "simpleFoam k-ω SST",
                            limitacoes=[f"OpenFOAM NÃO INSTALADO. {st.instrucao}"])
    try:
        r = subprocess.run(sr.openfoam_shell("sh Allrun"), cwd=pasta, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return TracedResult("CFD OpenFOAM", "NAO_EXECUTADO", "simpleFoam k-ω SST", limitacoes=[f"tempo limite de {timeout} s excedido"])
    logp = Path(pasta) / "log.simpleFoam"
    log = logp.read_text(errors="replace") if logp.exists() else ""
    sem_funcoes = False
    if "FOAM FATAL" in log and 'IOstream "sha1"' in log:
        # defeito conhecido de certos pacotes/compilações do OpenFOAM (v1912 Debian): QUALQUER função-objeto aborta ao iniciar.
        # O solver em si funciona: refaz sem `functions` (malha já existe) e declara que Cd/Cl NÃO estão disponíveis.
        cd = Path(pasta) / "system" / "controlDict"
        txt = cd.read_text()
        i = txt.find("functions")
        if i >= 0:
            cd.with_name("controlDict.com_funcoes").write_text(txt)
            cd.write_text(txt[:i])
            r = subprocess.run(sr.openfoam_shell("simpleFoam > log.simpleFoam 2>&1"), cwd=pasta, capture_output=True, text=True, timeout=timeout)
            log = logp.read_text(errors="replace") if logp.exists() else ""
            sem_funcoes = True
    if r.returncode != 0 or not log or "FOAM FATAL" in log:
        return TracedResult("CFD OpenFOAM", "NAO_EXECUTADO", "simpleFoam k-ω SST",
                            limitacoes=["falha na execução: " + ((r.stderr or r.stdout or log)[-400:])])
    conv = ler_log_simplefoam(log)
    coef = _ler_coeficientes(pasta)
    vals = {"log": str(logp), **conv}
    if coef:
        vals.update({"iteracao_coef": coef[0], "cd": coef[1], "cl": coef[2]})
    lim = ["referência de área/comprimento/velocidade são as informadas no caso", "sem estudo de malha → não validado"]
    if sem_funcoes:
        try:
            fp = forcas_pressao(pasta, "body", rho=_ler_rho(pasta), v_inf=_ler_vinf(pasta), a_ref=_ler_aref(pasta))
            vals.update({"cd_pressao": fp["cd_pressao"], "cl_pressao": fp["cl_pressao"], "forca_pressao_N": fp["forca_N"], "coef_origem": "integração própria de pressão"})
            try:
                fv = forcas_viscosas(pasta, "body", rho=_ler_rho(pasta), nu=_ler_nu(pasta), v_inf=_ler_vinf(pasta), a_ref=_ler_aref(pasta))
                vals.update({"cd_atrito_estimado": fv["cd_atrito"], "forca_atrito_N": fv["forca_N"], "cd_total_estimado": fp["cd_pressao"] + fv["cd_atrito"],
                             "cl_total_estimado": fp["cl_pressao"] + fv["cl_atrito"], "coef_origem": "pressão (integração própria) + atrito ESTIMADO por lei da parede",
                             "y_primeira_celula_m": fv["y_primeira_celula_m"]})
            except Exception as e:
                vals["atrito_erro"] = str(e)[:160]
        except Exception as e:                                          # sem passo de tempo gravado etc.: não inventa
            vals["coef_pressao_erro"] = str(e)[:160]
        lim.insert(0, "Cd/Cl totais NÃO DISPONÍVEIS: as funções-objeto (forces/forceCoeffs) falham neste build do OpenFOAM (erro 'sha1'); "
                      "Cd/Cl vêm de integração PRÓPRIA: pressão exata do campo + atrito viscoso ESTIMADO por lei da parede (1ª ordem). O total é estimado, não medido")
    if not conv["convergiu"]:
        lim.insert(0, "NÃO CONVERGIU dentro das iterações pedidas (resíduos acima das tolerâncias do residualControl) — valores são do último passo, não de regime")
    classe, vref = "SIMULACAO_NUMERICA", ""
    if cd_ref is not None and coef and conv["convergiu"]:
        dif = abs(coef[1] - cd_ref) / abs(cd_ref) * 100
        vals["cd_ref"], vals["cd_dif_pct"] = cd_ref, dif
        if dif <= cd_tol_pct and ref_texto:
            classe, vref = "VALIDADO", ref_texto
    return TracedResult("CFD OpenFOAM", classe, "simpleFoam RANS k-ω SST", vals,
                        premissas=["regime permanente incompressível", "domínio, condições de contorno e k-ω SST gerados por gerar_caso_openfoam"],
                        limitacoes=lim, solver="OpenFOAM", solver_versao=st.versao or "?", validacao_ref=vref)
