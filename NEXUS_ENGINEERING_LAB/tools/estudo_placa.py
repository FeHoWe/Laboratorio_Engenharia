"""Placa plana paralela ao escoamento (L=1 m, W=0.5 m, t=0.01 m), Re_L=1.33e6 (V=20 m/s, ar): compara o ATRITO estimado do NEXUS com o
Cf turbulento de placa plana (Schlichting: Cf = 0.455/(log10 Re)^2.58, uma face, médio) → Cd_atrito(ref=L·W) = 2·Cf.
Uso: python tools/estudo_placa.py [pasta_saida]. É uma VERIFICAÇÃO do estimador de atrito por lei da parede, não validação do solver."""
import json, math, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import trimesh
from modules import cfd_job

OUT = sys.argv[1] if len(sys.argv) > 1 else "estudo_placa"
Path(OUT).mkdir(parents=True, exist_ok=True)
V, NU, L, W = 20.0, 1.5e-5, 1.0, 0.5
Re = V * L / NU
cf = 0.455 / math.log10(Re) ** 2.58
alvo = 2 * cf
box = trimesh.creation.box(extents=(L, W, 0.01)); p = f"{OUT}/placa.stl"; box.export(p)
res = []
for tag, cel, it in (("media", (80, 32, 32), 1500), ("fina", (120, 48, 48), 1500)):
    t = time.time()
    r = cfd_job.run_case(stl_path=p, stl_unit="m", v_inf=V, iteracoes=it, celulas=list(cel), ar_livre=True, a_ref=L * W, nu=NU, out_dir=f"{OUT}/{tag}", timeout=6000)
    v = r["result"]["valores"]
    res.append({"malha": tag, "celulas": cel, "convergiu": v.get("convergiu"), "cd_atrito_estimado": v.get("cd_atrito_estimado"), "alvo_2cf": alvo, "cf_schlichting": cf,
                "cd_pressao": v.get("cd_pressao"), "y_primeira_celula_m": v.get("y_primeira_celula_m"), "s": time.time() - t})
    json.dump(res, open(f"{OUT}/res.json", "w"), ensure_ascii=False, indent=1)
