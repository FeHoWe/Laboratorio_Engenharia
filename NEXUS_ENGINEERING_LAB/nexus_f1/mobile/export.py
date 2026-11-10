"""Visualizador mobile SOMENTE LEITURA: gera um HTML autocontido (sem servidor) com os resultados simulados.

Abre em qualquer celular: pista animada, telemetria, resumo, segmentos e som do motor sintetizado (WebAudio)
a partir do RPM/acelerador da telemetria. Não executa simulação — apenas exibe resultados calculados no desktop.
"""
from __future__ import annotations

import json

import numpy as np

from ..core.laptime import LapResult, format_time

_TPL = r"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>NEXUS F1 · Visualizador</title>
<style>
:root{--bg:#06101a;--p:#0b1b29;--p2:#0f2538;--c:#19d3f5;--cd:#0f7f95;--a:#ffb02e;--r:#ff4d4d;--g:#2ee6a6;--t:#cfeaf5;--m:#6f93a6}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--t);font:14px system-ui,Segoe UI,sans-serif;padding:env(safe-area-inset-top) 0 env(safe-area-inset-bottom)}
header{padding:12px 14px;border-bottom:1px solid var(--cd);background:linear-gradient(180deg,#0a2234,var(--bg))}
h1{margin:0;font-size:15px;letter-spacing:3px;color:var(--c)}.sub{color:var(--m);font-size:11px}
.big{font:700 34px Consolas,monospace;color:var(--c);margin:4px 0}
select{background:#081824;color:var(--t);border:1px solid var(--cd);border-radius:6px;padding:6px;width:100%;margin-top:6px}
nav{display:flex;overflow-x:auto;background:var(--p2)}nav button{flex:1;min-width:84px;background:none;border:0;color:var(--m);padding:11px 6px;font-weight:600;border-bottom:2px solid transparent}
nav button.on{color:var(--c);border-color:var(--c)}
section{display:none;padding:10px}section.on{display:block}
canvas{width:100%;background:var(--p);border:1px solid #12394d;border-radius:8px;display:block}
.row{display:flex;gap:8px;align-items:center;margin:8px 0}button.b{background:#0c4a60;color:#fff;border:1px solid var(--c);border-radius:6px;padding:9px 14px;font-weight:700}
input[type=range]{flex:1}table{width:100%;border-collapse:collapse;font-size:12px}td,th{padding:6px 5px;border-bottom:1px solid #12394d;text-align:left}th{color:var(--c)}
.tag{display:inline-block;padding:2px 7px;border-radius:10px;font-size:11px;border:1px solid}.ok{color:var(--g);border-color:var(--g)}.no{color:var(--a);border-color:var(--a)}
.note{color:var(--m);font-size:11px;margin-top:10px;line-height:1.4}
.hud{display:flex;justify-content:space-between;font:700 22px Consolas,monospace;margin-top:6px}.hud small{font:11px system-ui;color:var(--m);display:block}
</style></head><body>
<header><h1>NEXUS F1 · SIMULAÇÃO</h1><div class="sub">Visualizador somente leitura · resultados calculados no desktop</div>
<div class="big" id="lap">—</div><div id="tag"></div><select id="sel"></select></header>
<nav id="nav"><button data-t="pista" class="on">Pista</button><button data-t="tele">Telemetria</button><button data-t="res">Resumo</button><button data-t="seg">Segmentos</button></nav>
<section id="pista" class="on"><canvas id="cv" width="700" height="520"></canvas>
<div class="hud"><div><span id="hv">0</span><small>km/h</small></div><div><span id="hg">1</span><small>marcha</small></div><div><span id="hr">0</span><small>rpm</small></div><div><span id="ht">0:00.000</span><small>tempo</small></div></div>
<div class="row"><button class="b" id="play">▶ Play</button><button class="b" id="snd" style="background:#123a52">🔇 Som</button><input type="range" id="sl" min="0" max="1000" value="0"></div>
<div class="row"><span class="sub">velocidade</span><select id="spd" style="width:auto"><option>0.25</option><option>0.5</option><option selected>1</option><option>2</option><option>4</option></select></div></section>
<section id="tele"><canvas id="cp" width="700" height="760"></canvas></section>
<section id="res"><table id="tb"></table><div class="note" id="viol"></div></section>
<section id="seg"><table id="ts"></table></section>
<div style="padding:0 12px 18px" class="note" id="src"></div>
<script>
const DATA=__DATA__;
let cur=0,t=0,playing=false,last=0,snd=false;
const $=i=>document.getElementById(i);
const fmt=s=>{const m=Math.floor(s/60);return m+":"+(s-60*m).toFixed(3).padStart(6,"0")};
const sel=$("sel");DATA.forEach((d,i)=>{const o=document.createElement("option");o.value=i;o.textContent=d.name+" — "+fmt(d.lap);sel.appendChild(o)});
document.querySelectorAll("nav button").forEach(b=>b.onclick=()=>{document.querySelectorAll("nav button").forEach(x=>x.classList.remove("on"));b.classList.add("on");document.querySelectorAll("section").forEach(s=>s.classList.remove("on"));$(b.dataset.t).classList.add("on");draw()});
sel.onchange=()=>{cur=+sel.value;t=0;load()};
function spdColor(u){u=Math.max(0,Math.min(1,u));let a,b,k;if(u<.5){a=[40,90,255];b=[25,211,245];k=u/.5}else{a=[25,211,245];b=[255,176,46];k=(u-.5)/.5}return"rgb("+a.map((x,i)=>Math.round(x+(b[i]-x)*k)).join(",")+")"}
function load(){const d=DATA[cur];$("lap").textContent=fmt(d.lap);
$("tag").innerHTML='<span class="tag '+(d.compliant?'ok':'no')+'">'+(d.compliant?'REGULAMENTAR':'NÃO REGULAMENTAR')+'</span> <span class="sub">'+d.track+' · '+d.compound+' · temporada '+d.season+'</span>';
let h="";for(const [k,v] of d.summary)h+="<tr><td>"+k+"</td><td>"+v+"</td></tr>";$("tb").innerHTML="<tr><th>Métrica</th><th>Valor</th></tr>"+h;
$("viol").innerHTML=d.violations.length?("<b>Desvios do regulamento</b><br>"+d.violations.join("<br>")):"";
let s="<tr><th>Segmento</th><th>m</th><th>s</th><th>Vmín</th><th>Vmáx</th></tr>";for(const g of d.segs)s+="<tr><td>"+g[0]+"</td><td>"+g[1]+"</td><td>"+g[2]+"</td><td>"+g[3]+"</td><td>"+g[4]+"</td></tr>";$("ts").innerHTML=s;
$("src").textContent=d.source;
const xs=d.x,ys=d.y;d.bx=[Math.min(...xs),Math.max(...xs)];d.by=[Math.min(...ys),Math.max(...ys)];draw()}
function xf(d,cv,x,y){const W=cv.width,H=cv.height,m=40;const sc=Math.min((W-2*m)/(d.bx[1]-d.bx[0]),(H-2*m)/(d.by[1]-d.by[0]));
return[m+(W-2*m-(d.bx[1]-d.bx[0])*sc)/2+(x-d.bx[0])*sc,H-m-(H-2*m-(d.by[1]-d.by[0])*sc)/2-(y-d.by[0])*sc]}
function idx(d,tt){let lo=0,hi=d.t.length-1;while(lo<hi){const m=(lo+hi)>>1;if(d.t[m]<tt)lo=m+1;else hi=m}return Math.max(0,Math.min(d.t.length-1,lo-1))}
function drawTrack(){const d=DATA[cur],cv=$("cv"),c=cv.getContext("2d");c.clearRect(0,0,cv.width,cv.height);
const n=d.x.length,vmin=Math.min(...d.v),vmax=Math.max(...d.v);
c.lineCap="round";c.lineJoin="round";c.strokeStyle="#0d2a3b";c.lineWidth=20;c.beginPath();for(let i=0;i<=n;i++){const p=xf(d,cv,d.x[i%n],d.y[i%n]);i?c.lineTo(...p):c.moveTo(...p)}c.stroke();
c.lineWidth=7;for(let i=0;i<n;i++){const a=xf(d,cv,d.x[i],d.y[i]),b=xf(d,cv,d.x[(i+1)%n],d.y[(i+1)%n]);c.strokeStyle=spdColor((d.v[i]-vmin)/(vmax-vmin+1e-9));c.beginPath();c.moveTo(...a);c.lineTo(...b);c.stroke()}
const k=idx(d,t),k2=(k+1)%n,fr=k<n-1?(t-d.t[k])/Math.max(d.t[k+1]-d.t[k],1e-9):0;
const p=xf(d,cv,d.x[k]+(d.x[k2]-d.x[k])*fr,d.y[k]+(d.y[k2]-d.y[k])*fr);c.fillStyle="#ff4d4d";c.strokeStyle="#fff";c.lineWidth=3;c.beginPath();c.arc(p[0],p[1],11,0,7);c.fill();c.stroke();
$("hv").textContent=Math.round(d.v[k]);$("hg").textContent=d.g[k];$("hr").textContent=Math.round(d.rpm[k]);$("ht").textContent=fmt(t);return k}
function drawPlots(){const d=DATA[cur],cv=$("cp"),c=cv.getContext("2d");c.clearRect(0,0,cv.width,cv.height);
const P=[["Velocidade (km/h)",[[d.v,"#19d3f5"]]],["Acelerador / Freio",[[d.thr,"#2ee6a6"],[d.brk,"#ff4d4d"]]],["RPM",[[d.rpm,"#ffb02e"]]],["Aceleração (g)",[[d.ax,"#2ee6a6"],[d.ay,"#b388ff"]]],["Pneus (°C)",[[d.tf,"#19d3f5"],[d.tr,"#ffb02e"]]]];
const h=cv.height/P.length,L=d.len;c.font="22px system-ui";
P.forEach((p,i)=>{const top=i*h+30,hh=h-44,l0=64,w=cv.width-l0-10;c.fillStyle="#19d3f5";c.fillText(p[0],l0,top-8);c.strokeStyle="#12394d";c.lineWidth=1;c.strokeRect(l0,top,w,hh);
let lo=1e9,hi=-1e9;p[1].forEach(([a])=>{lo=Math.min(lo,Math.min(...a));hi=Math.max(hi,Math.max(...a))});if(i==1){lo=0;hi=1}if(hi-lo<1e-9)hi=lo+1;
c.fillStyle="#6f93a6";c.font="16px system-ui";c.fillText(hi.toPrecision(3),4,top+14);c.fillText(lo.toPrecision(3),4,top+hh);c.font="22px system-ui";
p[1].forEach(([a,col])=>{c.strokeStyle=col;c.lineWidth=2;c.beginPath();a.forEach((v,j)=>{const x=l0+w*d.s[j]/L,y=top+hh-hh*(v-lo)/(hi-lo);j?c.lineTo(x,y):c.moveTo(x,y)});c.stroke()});
const k=idx(d,t),cx=l0+w*d.s[k]/L;c.strokeStyle="#fff";c.beginPath();c.moveTo(cx,top);c.lineTo(cx,top+hh);c.stroke()})}
function draw(){const k=drawTrack();if($("tele").classList.contains("on"))drawPlots();return k}
// áudio: harmônicos seguindo o RPM (WebAudio)
let ac,osc=[],gn,master;
function startSnd(){ac=ac||new (window.AudioContext||window.webkitAudioContext)();master=ac.createGain();master.gain.value=.35;master.connect(ac.destination);
const amps=[1,.62,.66,.4,.34,.24,.17,.13];osc=amps.map((a,i)=>{const o=ac.createOscillator();o.type="sine";const g=ac.createGain();g.gain.value=a*.18;o.connect(g);g.connect(master);o.start();return{o,g,a}})}
function stopSnd(){osc.forEach(x=>{try{x.o.stop()}catch(e){}});osc=[]}
function updSnd(k){if(!snd||!osc.length)return;const d=DATA[cur],f0=d.rpm[k]/60*d.cyl/2,load=0.25+0.75*d.thr[k];
osc.forEach((x,i)=>{x.o.frequency.setTargetAtTime(Math.min(f0*(i+1),9000),ac.currentTime,.03);x.g.gain.setTargetAtTime(x.a*.18*load*Math.pow(.9,i*(1-d.thr[k])),ac.currentTime,.05)})}
$("snd").onclick=()=>{snd=!snd;$("snd").textContent=snd?"🔊 Som":"🔇 Som";if(snd&&playing)startSnd();else stopSnd()};
$("play").onclick=()=>{playing=!playing;$("play").textContent=playing?"⏸ Pausar":"▶ Play";last=performance.now();if(playing&&snd)startSnd();if(!playing)stopSnd();if(playing&&t>=DATA[cur].lap-.05)t=0};
$("sl").oninput=e=>{t=e.target.value/1000*DATA[cur].lap;draw()};
function loop(now){if(playing){t+=(now-last)/1000*parseFloat($("spd").value);if(t>=DATA[cur].lap){t=DATA[cur].lap;playing=false;$("play").textContent="▶ Play";stopSnd()}
$("sl").value=t/DATA[cur].lap*1000}last=now;const k=draw();if(playing)updSnd(k);requestAnimationFrame(loop)}
load();requestAnimationFrame(loop);
</script></body></html>"""


def _pack(res: LapResult, name: str, step: int = 2) -> dict:
    t = res.tel
    sl = slice(None, None, step)
    r1 = lambda a, nd=1: np.round(np.asarray(a, float)[sl], nd).tolist()
    s = res.summary
    summary = [
        ["Tempo de volta", format_time(res.lap_time)],
        ["Setores", " / ".join(format_time(x) for x in res.sectors)],
        ["Velocidade máx.", f"{s['v_max_kmh']:.1f} km/h"], ["Velocidade média", f"{s['v_avg_kmh']:.1f} km/h"],
        ["Velocidade mín.", f"{s['v_min_kmh']:.1f} km/h"], ["Acel. lateral máx.", f"{s['a_lat_max_g']:.2f} g"],
        ["Desacel. máx.", f"{s['a_brake_max_g']:.2f} g"], ["Frenagem total", f"{s['braking_distance_total_m']:.0f} m / {s['n_braking_zones']} zonas"],
        ["Tempo curvas / retas", f"{s['time_corners_s']:.2f} / {s['time_straights_s']:.2f} s"],
        ["Combustível", f"{s['fuel_used_kg']:.2f} kg"], ["Temp. pneus", f"{s['tyre_temp_mean_c']:.0f} °C"],
        ["Desgaste/volta", f"{s['tyre_wear_per_lap'] * 100:.2f} %"], ["Massa", f"{s['mass_kg']:.0f} kg"],
        ["Aero", f"{res.car.aero_preset} (CdA {res.car.cda:.2f} / ClA {res.car.cla:.2f})"],
    ]
    return dict(
        name=name, lap=res.lap_time, compliant=res.compliant, track=res.track.name, compound=res.compound, season=res.car.season,
        cyl=6, len=res.track.length_m, source=res.track.data_source + ". Valores são estimativas do modelo; consulte o desktop para detalhes.",
        summary=summary, violations=[v.message for v in res.violations],
        segs=[[g["name"], f"{g['length']:.0f}", f"{g['time']:.2f}", f"{g['v_min']:.0f}", f"{g['v_max']:.0f}"] for g in res.segments],
        x=r1(t["x"]), y=r1(t["y"]), s=r1(t["s"]), t=r1(t["t"], 3), v=r1(t["v_kmh"]), g=[int(x) for x in np.asarray(t["gear"])[sl]],
        rpm=r1(t["rpm"], 0), thr=r1(t["throttle"], 2), brk=r1(t["brake"], 2), ax=r1(t["ax_g"], 2), ay=r1(t["ay_g"], 2),
        tf=r1(t["Tf"], 0), tr=r1(t["Tr"], 0),
    )


def build_mobile_html(results: list[LapResult], names: list[str] | None = None) -> str:
    names = names or [f"{r.track.name.split('(')[0].strip()} · {r.car.name}" for r in results]
    data = [_pack(r, n) for r, n in zip(results, names)]
    return _TPL.replace("__DATA__", json.dumps(data, separators=(",", ":"), ensure_ascii=False))
