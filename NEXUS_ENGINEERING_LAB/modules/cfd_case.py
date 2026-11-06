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
                        rho: float = 1.225, nu: float = 1.5e-5, caixa=(-2, 6, -2, 2, 0, 3), iteracoes: int = 1000) -> Path:
    """Escreve system/ constant/ 0/ prontos. O STL deve ser copiado para constant/triSurface/ (em m)."""
    if v_inf <= 0 or area_ref <= 0 or comprimento_ref <= 0: raise ValueError("entradas inválidas")
    p = Path(pasta)
    for d in ("system", "constant/triSurface", "0"): (p / d).mkdir(parents=True, exist_ok=True)
    H = 'FoamFile { version 2.0; format ascii; class %s; object %s; }\n'
    x0, x1, y0, y1, z0, z1 = caixa
    (p/"system/blockMeshDict").write_text(H % ("dictionary", "blockMeshDict") + f"""convertToMeters 1;
vertices ( ({x0} {y0} {z0}) ({x1} {y0} {z0}) ({x1} {y1} {z0}) ({x0} {y1} {z0}) ({x0} {y0} {z1}) ({x1} {y0} {z1}) ({x1} {y1} {z1}) ({x0} {y1} {z1}) );
blocks ( hex (0 1 2 3 4 5 6 7) (80 32 24) simpleGrading (1 1 1) );
boundary ( inlet {{type patch; faces ((0 4 7 3));}} outlet {{type patch; faces ((1 2 6 5));}}
 ground {{type wall; faces ((0 3 2 1));}} top {{type symmetryPlane; faces ((4 5 6 7));}}
 sides {{type symmetryPlane; faces ((0 1 5 4) (3 7 6 2));}} );
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
 features (); refinementSurfaces {{ body {{ level (2 3); patchInfo {{ type wall; }} }} }} refinementRegions {{}} locationInMesh ({x0+0.5} 0.0 {z1-0.5}); allowFreeStandingZoneFaces true; }}
snapControls {{ nSmoothPatch 3; tolerance 2.0; nSolveIter 30; nRelaxIter 5; nFeatureSnapIter 10; }}
addLayersControls {{ layers {{}} relativeSizes true; expansionRatio 1.2; finalLayerThickness 0.3; minThickness 0.1; nGrow 0; featureAngle 60; nRelaxIter 3; nSmoothSurfaceNormals 1; nSmoothNormals 3; nSmoothThickness 10; maxFaceThicknessRatio 0.5; maxThicknessToMedialRatio 0.3; minMedialAxisAngle 90; nBufferCellsNoExtrude 0; nLayerIter 50; }}
meshQualityControls {{ maxNonOrtho 65; maxBoundarySkewness 20; maxInternalSkewness 4; maxConcave 80; minVol 1e-13; minTetQuality 1e-15; minArea -1; minTwist 0.02; minDeterminant 0.001; minFaceWeight 0.05; minVolRatio 0.01; minTriangleTwist -1; nSmoothScale 4; errorReduction 0.75; }}
mergeTolerance 1e-6;
""")
    (p/"constant/transportProperties").write_text(H % ("dictionary", "transportProperties") + f"transportModel Newtonian; nu [0 2 -1 0 0 0 0] {nu};\n")
    (p/"constant/momentumTransport").write_text(H % ("dictionary", "momentumTransport") + "simulationType RAS; RAS { model kOmegaSST; turbulence on; printCoeffs on; }\n")
    I = 0.01; k = 1.5 * (v_inf * I) ** 2; om = k ** 0.5 / (0.09 ** 0.25 * comprimento_ref * 0.1)
    def field(cls, name, dims, internal, bc):
        (p/f"0/{name}").write_text(H % (cls, name) + f"dimensions {dims}; internalField {internal};\nboundaryField {{ {bc} }}\n")
    field("volVectorField", "U", "[0 1 -1 0 0 0 0]", f"uniform ({v_inf} 0 0)",
          f"inlet {{type fixedValue; value uniform ({v_inf} 0 0);}} outlet {{type zeroGradient;}} ground {{type noSlip;}} body {{type noSlip;}} top {{type symmetryPlane;}} sides {{type symmetryPlane;}}")
    field("volScalarField", "p", "[0 2 -2 0 0 0 0]", "uniform 0",
          "inlet {type zeroGradient;} outlet {type fixedValue; value uniform 0;} ground {type zeroGradient;} body {type zeroGradient;} top {type symmetryPlane;} sides {type symmetryPlane;}")
    field("volScalarField", "k", "[0 2 -2 0 0 0 0]", f"uniform {k:.6g}",
          f"inlet {{type fixedValue; value uniform {k:.6g};}} outlet {{type zeroGradient;}} ground {{type kqRWallFunction; value uniform {k:.6g};}} body {{type kqRWallFunction; value uniform {k:.6g};}} top {{type symmetryPlane;}} sides {{type symmetryPlane;}}")
    field("volScalarField", "omega", "[0 0 -1 0 0 0 0]", f"uniform {om:.6g}",
          f"inlet {{type fixedValue; value uniform {om:.6g};}} outlet {{type zeroGradient;}} ground {{type omegaWallFunction; value uniform {om:.6g};}} body {{type omegaWallFunction; value uniform {om:.6g};}} top {{type symmetryPlane;}} sides {{type symmetryPlane;}}")
    field("volScalarField", "nut", "[0 2 -1 0 0 0 0]", "uniform 0",
          "inlet {type calculated; value uniform 0;} outlet {type calculated; value uniform 0;} ground {type nutkWallFunction; value uniform 0;} body {type nutkWallFunction; value uniform 0;} top {type symmetryPlane;} sides {type symmetryPlane;}")
    (p/"Allrun").write_text("#!/bin/sh\nblockMesh && surfaceFeatureExtract 2>/dev/null; snappyHexMesh -overwrite && simpleFoam > log.simpleFoam 2>&1\n")
    return p

def executar_openfoam(pasta, timeout=3600) -> TracedResult:
    """Executa o caso se OpenFOAM instalado; senão NAO_EXECUTADO (sem números)."""
    st = sr.detect("OpenFOAM")
    if not st.instalado:
        return TracedResult("CFD OpenFOAM", "NAO_EXECUTADO", "simpleFoam k-ω SST",
                            limitacoes=[f"OpenFOAM NÃO INSTALADO. {st.instrucao}"])
    r = subprocess.run(["sh", "Allrun"], cwd=pasta, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        return TracedResult("CFD OpenFOAM", "NAO_EXECUTADO", "simpleFoam k-ω SST", limitacoes=["falha na execução: " + r.stderr[-300:]])
    return TracedResult("CFD OpenFOAM", "SIMULACAO_NUMERICA", "simpleFoam RANS k-ω SST", {"log": str(Path(pasta)/"log.simpleFoam")},
                        premissas=["regime permanente incompressível"], limitacoes=["sem estudo de malha → não validado"],
                        solver="OpenFOAM", solver_versao=st.versao or "?")
