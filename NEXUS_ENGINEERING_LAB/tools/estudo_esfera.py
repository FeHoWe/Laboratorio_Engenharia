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
for tag,cel,it in (("grossa",(40,16,16),500),("media",(60,24,24),700),("fina",(80,32,32),900)):
    t=time.time()
    m=trimesh.creation.icosphere(subdivisions=4,radius=0.5)
    # esfera D=1 m, em m, STL já em metros
    p=f"{OUT}/esfera.stl"; m.export(p)
    r=cfd_job.run_case(stl_path=p,stl_unit="m",v_inf=20.0,iteracoes=it,celulas=list(cel),gap_m=4.0,a_ref=np.pi/4,nu=2e-4,
        out_dir=f"{OUT}/{tag}",timeout=3000)
    x=r["result"]; v=x["valores"]
    res.append({"malha":tag,"celulas":cel,"iter":it,"classe":x["classe"],"conv":v.get("convergiu"),"cd_p":v.get("cd_pressao"),"cd_f":v.get("cd_atrito_estimado"),
      "cd_tot":v.get("cd_total_estimado"),"cl":v.get("cl_total_estimado"),"bloq":r["info"]["bloqueio_pct"],"s":time.time()-t,"lim":x["limitacoes"][:2]})
    json.dump(res,open(f"{OUT}/res.json","w"),ensure_ascii=False,indent=1)
