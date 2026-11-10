"""Valida mobile/lab.js contra os módulos Python (aero, structural, truss_fem, fatigue). Uso: python mobile/validate_lab.py (sai 1 se divergir)."""
import json, math, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from modules import aero, structural as st, truss_fem as tf, fatigue as fa, frame_fem as fm

def units_check():
    from modules import units
    T = json.loads(units.export_table())
    pairs = [(d, a, b) for d, us in units.TABLE.items() for a in us for b in us]
    py = [units.convert(37.5, a, b) for d, a, b in pairs]
    js = json.loads(subprocess.check_output(['node', '-e', 'const L=require(process.argv[1]);const T=JSON.parse(process.argv[2]);const P=JSON.parse(process.argv[3]);console.log(JSON.stringify(P.map(p=>L.unitsConvert(T,37.5,p[1],p[2]))));', str(ROOT / 'mobile' / 'lab.js'), json.dumps(T), json.dumps(pairs)], text=True))
    return max(abs(x - y) / max(abs(x), 1e-12) for x, y in zip(py, js)), len(pairs)


def veh_check():
    from modules.vehicle_dynamics import Veiculo, simular
    V = Veiculo(massa=800, cd=0.9, area=1.5, crr=0.015, forca_motriz=9000, potencia=300000, mu=1.6)
    py = simular(V, 20, 0.01)[-1]
    js = json.loads(subprocess.check_output(['node', '-e', 'const L=require(process.argv[1]);const h=L.vehDyn({m:800,cd:0.9,area:1.5,crr:0.015,F:9000,P:300000,mu:1.6,rho:1.225},20,0.01,0);console.log(JSON.stringify(h[h.length-1]));', str(ROOT / 'mobile' / 'lab.js')], text=True))
    return max(abs(a - b) / max(abs(a), 1e-9) for a, b in zip(py, js))


def lat_check():
    """Paridade JS × Python do modelo lateral (regime, limite, skidpad, cargas, pneu)."""
    from modules import vehicle_lateral as vl
    casos = [dict(m=1200, iz=1800, a=1.15, b=1.35, h=0.5, tf=1.5, tr=1.5, c_f=45000, c_r=45000, mu_f=1.2, mu_r=1.2, cla=0.0),
             dict(m=800, iz=1100, a=1.6, b=1.9, h=0.3, tf=1.6, tr=1.5, c_f=90000, c_r=70000, mu_f=1.7, mu_r=1.5, cla=3.5, frac_dt_aero=0.45,
                  k_roll_f=80000, k_roll_r=50000, h_rc_f=0.04, h_rc_r=0.09)]
    pontos = [(20.0, 120.0), (35.0, 80.0), (60.0, 150.0), (90.0, 40.0)]
    worst = 0.0
    for kw in casos:
        v = vl.VeiculoLateral(**kw)
        jv = dict(m=v.m, iz=v.iz, a=v.a, b=v.b, h=v.h, tf=v.tf, tr=v.tr, cF=v.c_f, cR=v.c_r, muF=v.mu_f, muR=v.mu_r, krF=v.k_roll_f, krR=v.k_roll_r,
                  hRcF=v.h_rc_f, hRcR=v.h_rc_r, cla=v.cla, fracAero=v.frac_dt_aero)
        for vel, R in pontos:
            reg, lim, sp = vl.regime_curva(v, vel, R), vl.ay_limite(v, vel), vl.skidpad(v, R)
            js = json.loads(subprocess.check_output(['node', '-e', 'const L=require(process.argv[1]);const v=JSON.parse(process.argv[2]);const a=+process.argv[3],R=+process.argv[4];console.log(JSON.stringify({r:L.regimeCurva(v,a,R),l:L.ayLimite(v,a),s:L.skidpad(v,R)}));',
                                             str(ROOT / 'mobile' / 'lab.js'), json.dumps(jv), str(vel), str(R)]))
            pairs = [(reg["ay_ms2"], js["r"]["ay"]), (lim["ay_ms2"], js["l"]["ay"]), (sp["v_ms"], js["s"]["v"]), (reg["cargas"]["dzf"], js["r"]["cargas"]["dzf"]), (reg["cargas"]["dzr"], js["r"]["cargas"]["dzr"])]
            assert reg["saturado"] == js["r"]["saturado"] and lim["limite"] == js["l"]["limite"], (kw, vel, R)
            if not reg["saturado"]:
                pairs += [(reg["delta"], js["r"]["delta"]), (reg["beta"], js["r"]["beta"]), (reg["k_subesterco"], js["r"]["kSub"])]
            worst = max(worst, max(abs(a - b) / max(abs(a), 1e-9) for a, b in pairs))
    return worst


def lap_check():
    from modules import lapsim, f1_mass
    c = lapsim.Carro(800, 500e3, 1.0, 3.0, 1.6, p_ers=300e3, e_ers=4e6)
    py = lapsim.volta(c).valores
    js = json.loads(subprocess.check_output(['node', '-e', 'const L=require(process.argv[1]);const r=L.lapSim({m:800,pIce:500e3,cda:1,cla:3,mu:1.6,pErs:300e3,eErs:4e6});const it=[["a",100,[0,0,100]],["b",300,[10,1000,300]],["c",50,[-40,400,55]]];const b=L.f1Balance(it,0,1000);console.log(JSON.stringify([r.tempo,r.vMedia,r.vMax,r.vMin,r.eMJ,b.massa,b.cg[0],b.cg[1],b.cg[2],b.pFront,b.I[0][0],b.I[1][1],b.I[2][2],b.I[0][2]]));', str(ROOT / 'mobile' / 'lab.js')], text=True))
    b = f1_mass.balance([("a", 100, (0, 0, 100)), ("b", 300, (10, 1000, 300)), ("c", 50, (-40, 400, 55))], 0, 1000)
    pyv = [py["tempo_s"], py["v_media_kmh"], py["v_max_kmh"], py["v_min_kmh"], py["energia_ers_usada_MJ"], b["massa_kg"], *b["cg_mm"], b["pct_dianteiro"],
           b["inercia_kgm2"][0][0], b["inercia_kgm2"][1][1], b["inercia_kgm2"][2][2], b["inercia_kgm2"][0][2]]
    from modules import telemetria
    tp = telemetria.telemetria(c, None, 2.0, 8, 15000, 340, 3).valores
    tj = json.loads(subprocess.check_output(['node', '-e', 'const L=require(process.argv[1]);const T=L.telemetry({m:800,pIce:500e3,cda:1,cla:3,mu:1.6,pErs:300e3,eErs:4e6},null,2,8,15000,340,3);console.log(JSON.stringify([T.tempo,...T.setores,T.gLatMax,T.gFreioMax,T.gAcelMax,T.rpmMax,T.pctPleno,T.pctFreio,Math.max(...T.ch.ers)]));', str(ROOT / 'mobile' / 'lab.js')], text=True))
    tv = [tp["tempo_s"], *tp["setores_s"], tp["g_lat_max"], tp["g_frenagem_max"], tp["g_acel_max"], tp["rpm_max_visto"], tp["tempo_acelerador_pleno_pct"], tp["tempo_freio_pct"], max(tp["canais"]["ers_MJ"])]
    return max(max(abs(a - c2) / max(abs(a), 1e-9) for a, c2 in zip(pyv, js)), max(abs(a - c2) / max(abs(a), 1e-9) for a, c2 in zip(tv, tj)))


def fea_check():
    import numpy as np
    from modules import fea3d as F
    m = F.box_mesh(100, 10, 10, 10, 2, 2)
    fixed = {i: (0, 1, 2) for i, p in enumerate(m.nodes) if p[0] < 1e-9}
    tip = [i for i, p in enumerate(m.nodes) if abs(p[0] - 100) < 1e-9]
    u, vm, R, vol = F.solve(m, 210000, 0.3, fixed, F.surface_load(m, tip, (0, 0, -100)))
    py = float(np.mean(u[tip, 2]))
    js = json.loads(subprocess.check_output(['node', '-e', 'const L=require(process.argv[1]);console.log(JSON.stringify(L.feaCant(100,10,10,10,2,2,210000,0.3,-100)));', str(ROOT / 'mobile' / 'lab.js')], text=True))
    return abs(py - js["tipDeflection"]) / abs(py), len(m.tets) == js["elements"]


def fea10_check():
    import numpy as np
    from modules import fea3d as F, fea_tet10 as Q
    m = Q.to_quadratic(F.box_mesh(100, 10, 10, 6, 1, 1))
    fixed = {i: (0, 1, 2) for i, p in enumerate(m.nodes) if p[0] < 1e-9}
    tip = [i for i, p in enumerate(m.nodes) if abs(p[0] - 100) < 1e-9]
    u, vm, R, vol = Q.solve(m, 210000, 0.3, fixed, Q.surface_load10(m, tip, (0, 0, -100)))
    py = float(np.mean(u[tip, 2]))
    js = json.loads(subprocess.check_output(['node', '-e', 'const L=require(process.argv[1]);console.log(JSON.stringify(L.feaCant10(100,10,10,6,1,1,210000,0.3,-100)));', str(ROOT / 'mobile' / 'lab.js')], text=True))
    return abs(py - js["tipDeflection"]) / abs(py), len(m.tets) == js["elements"]


def py_cases():
    out = {}
    out["isa0"] = list(aero.isa(0).values()); out["isa5k"] = list(aero.isa(5000, 10).values()); out["isa15k"] = list(aero.isa(15000).values())
    v = aero.Vehicle(mass=800, cda=1.1, cla=3.2, power=700e3, mu_tyre=1.6, crr=0.015, rho=1.2)
    out["veh"] = [v.top_speed(), v.corner_speed(60), v.brake(80) if hasattr(v, "brake") else v.braking_decel(80), v.accel(70), v.power_required(60)]
    out["naca"] = aero.naca4_alpha_l0(0.04, 0.4)
    r = aero.lifting_line(1.6, lambda s: 0.3 - 0.1 * abs(s), 5, -2.0, lambda s: -1.0 * abs(s), h_ground=0.1)
    out["ll"] = [r.cl, r.cdi, r.e, r.ar, r.area]
    out["beam"] = [list(st.beam(c, 1000, 800, 210000, st.i_beam(60, 100, 8, 5), 300).values()) for c in ("cant_end", "cant_udl", "ss_mid", "ss_udl", "fp_mid")]
    out["col"] = list(st.column_buckling(210000, st.tube_round(40, 3), 1500, 0.7, 350).values())[:5]
    out["bolt"] = list(st.bolt_joint(10, 40, 0.2, 640, 8000, 4).values())
    out["shaft"] = list(st.shaft_torsion(2e5, 30, 400, 79000, 10).values())
    out["vessel"] = list(st.thin_vessel(2, 300, 5).values())
    out["fn"] = [st.spring_mass_fn(20, 2), st.cantilever_fn(70000, st.rect(20, 5), 300, 2700, 2)]
    text = tf.warren_example()
    res = tf.solve(tf.parse(text))
    out["truss"] = [res.equilibrium_error, [res.force[k] for k in sorted(res.force)], [res.displacement[k].tolist() for k in sorted(res.displacement)]]
    ft = fm.parse(fm.portal_example() + "\nNODE E 3000 2000 3000\nBEAM e1 C E 5380 8.356e7 6.04e6 2.0e5 210000 80000\nLOAD E 0 -3000 -5000 100000 0 0\n")
    fr = fm.solve(ft)
    out["frame"] = [fr.equilibrium_error, [fr.displacement[k].tolist() for k in sorted(fr.displacement)], [fr.end_forces[k].tolist() for k in sorted(fr.end_forces)],
                    [list(fm.moment_at(ft, fr, k, s)) for k in sorted(ft.beams) for s in (0.25, 0.5)]]
    mt = fm.parse(fm.portal_example() + "\nMASS C 500\nMASS B 200\n")
    out["modal"] = fm.modal(mt, 6).freq_hz
    bt = fm.parse(fm.portal_example() + "\nLOAD C -80000 0 0\n")
    bk = fm.buckling(bt, 3); out["buck"] = bk.factors
    mat = fa.FatigueMaterial("x", 600, 400, None, True)
    mar = fa.MarinInputs("Usinado ou laminado a frio", 25, "Combinado", 1.0, 99.0, 0.9)
    sec = fa.Section("Círculo cheio", d=25)
    load = fa.LoadRange((0, 0), (-200000, 300000), (0, 100000))
    conc = fa.Concentration(kt_bending=2.0, q_bending=0.8, kt_torsion=1.5, q_torsion=0.9)
    f = fa.analyze(mat, mar, sec, load, conc, "Goodman")
    out["fat"] = [f.se["se"], f.stress["sigma_a"], f.stress["sigma_m"], [f.factors[k] for k in sorted(f.factors)], f.sigma_ar, f.cycles if math.isfinite(f.cycles) else "inf"]
    blocks = [fa.Block("a", 250, 50, 1e5), fa.Block("b", 300, 80, 1e4)]
    m = fa.miner(blocks, mat, f.curve); out["miner"] = [m["damage"], [r_["N"] if math.isfinite(r_["N"]) else "inf" for r_ in m["rows"]]]
    sp = fa.SpringInputs(3.5, 25, 8, 10, 40, 10, 100, 79000, 7.85, 1800, 500)
    s = fa.spring_analysis(sp); out["spring"] = [s["k"], s["tau_a"], s["tau_m"], s["n_f"], s["fn_hz"], s["mass_kg"], s["solid_len"]]
    return out

JS = r"""
const L=require(process.argv[1]);const o={};
o.isa0=Object.values(L.isa(0));o.isa5k=Object.values(L.isa(5000,10));o.isa15k=Object.values(L.isa(15000));
const v=new L.Vehicle({mass:800,cda:1.1,cla:3.2,power:700e3,mu_tyre:1.6,crr:0.015,rho:1.2});
o.veh=[v.top(),v.corner(60),v.brake(80),v.accel(70),v.preq(60)];o.naca=L.naca4AlphaL0(0.04,0.4);
const r=L.liftingLine(1.6,s=>0.3-0.1*Math.abs(s),5,-2.0,s=>-1.0*Math.abs(s),2*Math.PI,40,0.1);
o.ll=[r.cl,r.cdi,r.e,r.ar,r.area];
const sec=L.secI(60,100,8,5);o.beam=['cant_end','cant_udl','ss_mid','ss_udl','fp_mid'].map(c=>Object.values(L.beam(c,1000,800,210000,sec,300)));
o.col=Object.values(L.column(210000,L.secTubeRound(40,3),1500,0.7,350)).slice(0,5);
o.bolt=Object.values(L.boltJoint(10,40,0.2,640,8000,4));o.shaft=Object.values(L.shaftTorsion(2e5,30,400,79000,10));
o.vessel=Object.values(L.thinVessel(2,300,5));o.fn=[L.springMassFn(20,2),L.cantileverFn(70000,L.secRect(20,5),300,2700,2)];
const t=L.solveTruss(L.parseTruss(L.warrenExample()));const ks=Object.keys(t.force).sort();
o.truss=[t.equilibrium_error,ks.map(k=>t.force[k]),Object.keys(t.displacement).sort().map(k=>t.displacement[k])];
const fx=L.parseFrame(L.frameExample()+"\nNODE E 3000 2000 3000\nBEAM e1 C E 5380 8.356e7 6.04e6 2.0e5 210000 80000\nLOAD E 0 -3000 -5000 100000 0 0\n"),fres=L.solveFrame(fx);
o.frame=[fres.equilibrium_error,Object.keys(fres.displacement).sort().map(k=>fres.displacement[k]),Object.keys(fres.end_forces).sort().map(k=>fres.end_forces[k]),Object.keys(fx.beams).sort().flatMap(k=>[0.25,0.5].map(s=>L.frameMoment(fx,fres,k,s)))];
const mfr=L.parseFrame(L.frameExample()+"\nMASS C 500\nMASS B 200\n");o.modal=L.modalFrame(mfr,6).freq_hz;
const bfr=L.parseFrame(L.frameExample()+"\nLOAD C -80000 0 0\n");o.buck=L.bucklingFrame(bfr,3).factors;
const mat={su:600,sy:400,se_prime:null,estimate_se:true,has_knee:true,nk:1e6,f:null};
const f=L.fatigueAnalyze(mat,{surface:'Usinado ou laminado a frio',d_eq:25,load_type:'Combinado',temp_factor:1,reliability_pct:99,misc_factor:0.9,override_ka:null},
 {kind:'Círculo cheio',d:25},{axial:[0,0],bending:[-200000,300000],torsion:[0,100000]},{kt_axial:1,q_axial:1,kt_bending:2,q_bending:0.8,kt_torsion:1.5,q_torsion:0.9},'Goodman');
o.fat=[f.se.se,f.stress.sigma_a,f.stress.sigma_m,Object.keys(f.factors).sort().map(k=>f.factors[k]),f.sigma_ar,isFinite(f.cycles)?f.cycles:'inf'];
const m=L.miner([{label:'a',sigma_a:250,sigma_m:50,cycles:1e5},{label:'b',sigma_a:300,sigma_m:80,cycles:1e4}],mat,f.curve);
o.miner=[m.damage,m.rows.map(r=>isFinite(r.N)?r.N:'inf')];
const s=L.springAnalysis({wire_d:3.5,coil_d:25,active_coils:8,total_coils:10,installed_len:40,lift:10,preload_force:100,g_mpa:79000,density_g_cm3:7.85,su:1800,sse:500,ssu:null});
o.spring=[s.k,s.tau_a,s.tau_m,s.n_f,s.fn_hz,s.mass_kg,s.solid_len];
console.log(JSON.stringify(o,(k,x)=>x===Infinity?'inf':x));
"""

def flat(x):
    if isinstance(x, (list, tuple)):
        for i in x: yield from flat(i)
    elif isinstance(x, str): yield x
    else: yield float(x)

def main():
    py = py_cases()
    py = json.loads(json.dumps(py, default=lambda o: "inf" if o == float("inf") else float(o)).replace("Infinity", '"inf"'))
    js = json.loads(subprocess.check_output(["node", "-e", JS, str(ROOT / "mobile" / "lab.js")], text=True))
    worst, bad = 0.0, []
    for k in py:
        a, b = list(flat(py[k])), list(flat(js[k]))
        if len(a) != len(b): bad.append((k, "tamanho")); continue
        for x, y in zip(a, b):
            if isinstance(x, str) or isinstance(y, str):
                if x != y: bad.append((k, x, y))
                continue
            mag = max(abs(q) for q in a if not isinstance(q, str)) or 1.0
            rel = abs(x - y) / mag                      # erro relativo à maior grandeza do grupo (ignora ruído em zeros numéricos)
            worst = max(worst, rel)
            if rel > 1e-8: bad.append((k, x, y))
    print("maior erro (relativo à maior grandeza de cada grupo) JS×Python:", f"{worst:.2e}", "| divergências:", bad[:10])
    ue, un = units_check()
    print(f"unidades: {un} conversões JS×Python, erro relativo máx {ue:.2e}")
    ve = veh_check()
    print(f"veículo RK4: erro relativo máx JS×Python {ve:.2e}")
    ae = lat_check()
    print(f"dinâmica lateral (bicicleta, escova, transferência de carga): erro relativo máx JS×Python {ae:.2e}")
    le = lap_check()
    print(f"F1 volta + massa/CG/inércia: erro relativo máx JS×Python {le:.2e}")
    fe, same = fea_check()
    print(f"FEA Tet4 (viga): erro relativo JS×Python {fe:.2e}, mesmo nº de elementos: {same}")
    f10, same10 = fea10_check()
    print(f"FEA Tet10 (viga): erro relativo JS×Python {f10:.2e}, mesmo nº de elementos: {same10}")
    sys.exit(1 if bad or ue > 1e-12 or ve > 1e-9 or ae > 1e-9 or le > 1e-9 or fe > 1e-8 or not same or f10 > 1e-8 or not same10 else 0)

if __name__ == "__main__":
    main()
