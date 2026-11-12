"""Estudo de malha da esfera (D=1 m, Re=1e5 por similaridade: V=20 m/s, nu=2e-4 m²/s). Reproduz NEXUS_CFD_SPHERE_STUDY.md.
Uso (com OpenFOAM instalado): python tools/estudo_esfera.py [pasta_saida]   — leva ~4 min."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
OUT = sys.argv[1] if len(sys.argv) > 1 else "estudo_esfera"
Path(OUT).mkdir(parents=True, exist_ok=True)
import json,sys,time,numpy as np,trimesh
from modules import cfd_job
res=[]
for tag,cel,it in (("grossa",(48,24,24),1500),("media",(72,36,36),1500),("fina",(108,54,54),1500)):
    t=time.time()
    m=trimesh.creation.icosphere(subdivisions=4,radius=0.5)
    p=f"{OUT}/esfera.stl"; m.export(p)
    r=cfd_job.run_case(stl_path=p,stl_unit="m",v_inf=20.0,iteracoes=it,celulas=list(cel),ar_livre=True,nu=2e-4,
        out_dir=f"{OUT}/{tag}",timeout=6000)
    x=r["result"]; v=x["valores"]
    res.append({"malha":tag,"celulas":cel,"h_rel":1.0/cel[0],"iter":v.get("iteracoes"),"classe":x["classe"],"conv":v.get("convergiu"),"cd_p":v.get("cd_pressao"),"cd_f":v.get("cd_atrito_estimado"),
      "cd_tot":v.get("cd_total_estimado"),"cl":v.get("cl_total_estimado"),"bloq":r["info"]["bloqueio_pct"],"a_ref":r["info"]["a_ref_m2"],"s":time.time()-t})
    json.dump(res,open(f"{OUT}/res.json","w"),ensure_ascii=False,indent=1)
if len(res)==3 and all(r["cd_tot"] is not None for r in res):
    from modules.cfd_gci import gci3
    g=gci3(tuple(r["h_rel"] for r in reversed(res)),tuple(r["cd_tot"] for r in reversed(res)))
    json.dump(g,open(f"{OUT}/gci.json","w"),ensure_ascii=False,indent=1); print("GCI",g)
