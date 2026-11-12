/* NEXUS Lab (celular) — interface dos módulos: seletor de projeto, abas, calculadoras, massa, interferência. Depende de lab.js e do visualizador 3D. */
(function(){
'use strict';
const L=window.LAB,$=s=>document.querySelector(s),N=()=>window.__nexus;
const nf=(x,d=4)=>{if(x===Infinity)return '∞';if(x===-Infinity)return '−∞';if(x==null||Number.isNaN(x))return '—';const a=Math.abs(x);
 if(a!==0&&(a>=1e7||a<1e-3))return x.toExponential(3).replace('.',',');return x.toLocaleString('pt-BR',{maximumSignificantDigits:d});};
const esc=s=>String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const store={get(k,d){try{const v=localStorage.getItem('nexus.'+k);return v==null?d:JSON.parse(v);}catch(e){return d;}},set(k,v){try{localStorage.setItem('nexus.'+k,JSON.stringify(v));}catch(e){}}};
const TABS=[['3d','3D'],['aero','Aero'],['estr','Estrutural'],['trel','Treliça'],['port','Pórtico'],['fad','Fadiga'],['fea','FEA 3D'],['veic','Veículo'],['f1','F1'],['f1sim','F1 Sim'],['f1an','F1 Análise'],['prod','Produtos'],['massa','Massa'],['unid','Unidades'],['interf','Interferência'],['sobre','Sobre']];
let cur='3d',project=null,MATS=null;const built={};
// ---- construtor de cartões
function card(title,note,fields,fn,opts={}){
 const c=document.createElement('section');c.className='card';const vals={};
 c.innerHTML=`<h2>${title}</h2>${note?`<p class="n">${note}</p>`:''}<div class="f"></div><div class="btns" style="margin-top:6px"><button class="p mini">Calcular</button><button class="mini cp">Copiar</button></div><div class="res" aria-live="polite" style="display:none"></div>`;
 const box=c.querySelector('.f'),out=c.querySelector('.res');
 fields.forEach(f=>{if(f.h){box.insertAdjacentHTML('beforeend',`<p class="n" style="margin:8px 0 4px"><b>${f.h}</b></p>`);return;}
  const id='f'+Math.random().toString(36).slice(2,8),saved=store.get('f.'+title+'.'+f.k,undefined);const v=saved!==undefined?saved:f.v;
  const row=document.createElement('div');row.className='fld';row.dataset.k=f.k;
  const lab=`<label for="${id}">${f.l}${f.u?` <span class="tag">${f.u}</span>`:''}</label>`;
  if(f.sel)row.innerHTML=lab+`<select id="${id}">${f.sel.map(o=>`<option value="${esc(o[0])}"${String(o[0])===String(v)?' selected':''}>${esc(o[1])}</option>`).join('')}</select>`;
  else if(f.chk)row.innerHTML=lab+`<input id="${id}" type="checkbox" ${v?'checked':''} style="width:24px;min-height:24px">`;
  else row.innerHTML=lab+`<input id="${id}" inputmode="decimal" type="text" value="${v===null||v===undefined?'':v}" placeholder="${f.ph||''}">`;
  if(f.w)row.dataset.w=JSON.stringify(f.w);box.appendChild(row);});
 function applyW(){box.querySelectorAll('.fld[data-w]').forEach(r=>{const[dk,list]=JSON.parse(r.dataset.w),src=box.querySelector('.fld[data-k="'+dk+'"] select,.fld[data-k="'+dk+'"] input');r.style.display=list.includes(src.value)?'':'none';});}
 box.addEventListener('change',applyW);applyW();
 function read(){const o={};box.querySelectorAll('.fld').forEach(r=>{const i=r.querySelector('input,select'),k=r.dataset.k;
  if(i.type==='checkbox')o[k]=i.checked;else if(i.tagName==='SELECT')o[k]=i.value;else{const t=i.value.trim().replace(',','.');o[k]=t===''?null:Number(t);if(t!==''&&Number.isNaN(o[k]))throw new Error('Valor inválido em "'+k+'": '+i.value);}
  store.set('f.'+title+'.'+k,i.type==='checkbox'?i.checked:i.value);});return o;}
 function run(){out.style.display='block';try{const html=fn(read(),out);out.innerHTML=html;out.dataset.err='';}catch(e){out.innerHTML='<span class="warn">⚠ '+esc(e.message)+'</span>';out.dataset.err='1';}}
 c.querySelector('.p').onclick=run;box.addEventListener('change',()=>{if(out.style.display==='block')run();});
 c.querySelector('.cp').onclick=async()=>{if(out.style.display!=='block')run();const ins=[...box.querySelectorAll('.fld')].filter(r=>r.style.display!=='none').map(r=>{const i=r.querySelector('input,select'),l=r.querySelector('label').innerText.trim().replace(/\s+/g,' ');return '  '+l+' = '+(i.type==='checkbox'?(i.checked?'sim':'não'):(i.tagName==='SELECT'?i.selectedOptions[0].text:i.value));});
  const ta0=box.querySelector('textarea');const t='NEXUS Lab '+(window.__ver||'')+' — '+title+' — '+new Date().toLocaleString('pt-BR')+'\n\nENTRADAS\n'+(ta0?ta0.value+'\n':'')+ins.join('\n')+'\n\nRESULTADO\n'+(out.innerText||'');try{await (async()=>{const cp=c.querySelector('.cp');try{await navigator.clipboard.writeText(t);cp.textContent='Copiado ✓';}catch(e){try{const ta=document.createElement('textarea');ta.value=t;ta.style.position='fixed';ta.style.opacity='0';document.body.append(ta);ta.select();const ok=document.execCommand('copy');ta.remove();cp.textContent=ok?'Copiado ✓':'Copie manualmente';}catch(e2){cp.textContent='Copie manualmente';}}})();setTimeout(()=>c.querySelector('.cp').textContent='Copiar',1500);}catch(e){const r=document.createRange();r.selectNodeContents(out);const s=getSelection();s.removeAllRanges();s.addRange(r);}};
 c.run=run;return c;}
const line=(k,v,u='')=>`${k.padEnd(30)} <b>${v}</b> ${u}\n`;
const caveat=t=>`\n<span class="warn">${t}</span>`;
// ---- gráficos SVG genéricos
function plotSVG(o){const W=340,H=o.h||190,ml=44,mr=8,mt=10,mb=26,xs=o.series.flatMap(s=>s.x),ys=o.series.flatMap(s=>s.y).filter(Number.isFinite);
 let x0=Math.min(...xs),x1=Math.max(...xs),y0=Math.min(...ys,o.zero?0:Infinity),y1=Math.max(...ys,o.zero?0:-Infinity);if(x1===x0)x1=x0+1;if(y1===y0){y1=y0+1;}const pad=(y1-y0)*.06;y0-=pad;y1+=pad;
 const X=x=>ml+(x-x0)/(x1-x0)*(W-ml-mr),Y=y=>H-mb-(y-y0)/(y1-y0)*(H-mb-mt),cols=['#27d3ff','#ffb22e','#7dffb0','#ff4d6d'];let g='';
 for(let i=0;i<=4;i++){const yv=y0+(y1-y0)*i/4;g+=`<line x1="${ml}" y1="${Y(yv)}" x2="${W-mr}" y2="${Y(yv)}" stroke="#14384b"/><text x="${ml-4}" y="${Y(yv)+3}" fill="#6f95a8" font-size="9" text-anchor="end">${nf(yv,3)}</text>`;
  const xv=x0+(x1-x0)*i/4;g+=`<text x="${X(xv)}" y="${H-12}" fill="#6f95a8" font-size="9" text-anchor="middle">${nf(xv,3)}</text>`;}
 if(y0<0&&y1>0)g+=`<line x1="${ml}" y1="${Y(0)}" x2="${W-mr}" y2="${Y(0)}" stroke="#2a6a85"/>`;
 const lines=o.series.map((s,i)=>{const d=s.x.map((x,j)=>Number.isFinite(s.y[j])?(j&&Number.isFinite(s.y[j-1])?'L':'M')+X(x).toFixed(1)+' '+Y(s.y[j]).toFixed(1):'').join('');return `<path d="${d}" fill="none" stroke="${s.c||cols[i%4]}" stroke-width="2"${s.dash?' stroke-dasharray="5 3"':''}/>`;}).join('');
 const marks=(o.marks||[]).map(m=>`<line x1="${X(m.x)}" y1="${mt}" x2="${X(m.x)}" y2="${H-mb}" stroke="#ff4d6d" stroke-dasharray="3 3"/><text x="${Math.min(X(m.x)+3,W-60)}" y="${mt+9}" fill="#ff4d6d" font-size="9">${esc(m.t)}</text>`).join('');
 const leg=o.series.map((s,i)=>`<span style="color:${s.c||cols[i%4]}">━ ${esc(s.n)}</span>`).join(' &nbsp; ');
 return `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="${esc(o.title||'gráfico')}"><rect width="${W}" height="${H}" fill="#06121c"/>${g}${lines}${marks}<text x="${W/2}" y="${H-1}" fill="#8fb4c8" font-size="9" text-anchor="middle">${esc(o.xl||'')}</text><text x="2" y="9" fill="#8fb4c8" font-size="9">${esc(o.yl||'')}</text></svg><div class="tag" style="margin-bottom:6px">${esc(o.title||'')} · ${leg}</div>`;}
function beamDiagram(cs,P,Lc){const n=60,x=[],V=[],M=[];for(let i=0;i<=n;i++){const t=i/n,xx=t*Lc;x.push(xx);let v,m;
  if(cs==='cant_end'){v=P;m=-P*(Lc-xx);}else if(cs==='cant_udl'){v=P*(Lc-xx);m=-P*(Lc-xx)**2/2;}
  else if(cs==='ss_mid'){v=xx<Lc/2?P/2:-P/2;m=xx<Lc/2?P*xx/2:P*(Lc-xx)/2;}else if(cs==='ss_udl'){v=P*(Lc/2-xx);m=P*xx*(Lc-xx)/2;}
  else{v=xx<Lc/2?11*P/16:-5*P/16;m=xx<Lc/2?-3*P*Lc/16+11*P*xx/16:5*P*(Lc-xx)/16;}V.push(v);M.push(m);}
 const dv=cs==='cant_udl'||cs==='ss_udl'?'N':'N';return plotSVG({title:'Cortante V(x) [N]',series:[{n:'V',x,y:V}],xl:'x [mm]',yl:'V [N]',zero:1})+plotSVG({title:'Momento fletor M(x) [N·mm] (sagging +)',series:[{n:'M',x,y:M,c:'#ffb22e'}],xl:'x [mm]',yl:'M [N·mm]',zero:1});}
// ---- AERO
function tabAero(p){
 p.append(card('Atmosfera padrão ISA','Densidade, pressão, viscosidade (Sutherland) e velocidade do som de 0 a 20 km.',[{k:'h',l:'Altitude',u:'m',v:0},{k:'dT',l:'Desvio de temperatura',u:'K',v:0}],
  a=>{const r=L.isa(a.h,a.dT);return line('Temperatura',nf(r.T-273.15),'°C')+line('Pressão',nf(r.p/100),'hPa')+line('Densidade ρ',nf(r.rho),'kg/m³')+line('Viscosidade μ',nf(r.mu),'Pa·s')+line('Velocidade do som',nf(r.a),'m/s');}));
 p.append(card('Arrasto, sustentação e potência','F = ½ρV²·(C·A). CdA e ClA são DIGITADOS por você (o app não deduz coeficientes da geometria). ClA positivo = downforce.',
  [{k:'v',l:'Velocidade',u:'km/h',v:300},{k:'h',l:'Altitude',u:'m',v:0},{k:'cda',l:'CdA',u:'m²',v:1.1},{k:'cla',l:'ClA (downforce)',u:'m²',v:3.2}],
  a=>{const r=L.isa(a.h),v=a.v/3.6,fd=L.force(a.cda,r.rho,v),fl=L.force(a.cla,r.rho,v);
   return line('Pressão dinâmica q',nf(L.dynQ(r.rho,v)),'Pa')+line('Arrasto',nf(fd),'N')+line('Downforce',nf(fl),'N')+line('Potência contra arrasto',nf(fd*v/1000),'kW')+line('Razão ClA/CdA',nf(a.cla/a.cda))+caveat('Potência aerodinâmica ≠ potência do motor (faltam rendimento, rolamento etc.).');}));
 p.append(card('Número de Reynolds','Re = ρ·V·L/μ. Escolha o comprimento característico apropriado (corda, comprimento do carro…).',[{k:'v',l:'Velocidade',u:'km/h',v:300},{k:'L',l:'Comprimento característico',u:'m',v:0.4},{k:'h',l:'Altitude',u:'m',v:0}],
  a=>{const r=L.isa(a.h),re=L.reynolds(r.rho,a.v/3.6,a.L,r.mu);return line('Reynolds',nf(re))+line('Mach',nf(a.v/3.6/r.a))+line('Cf placa plana turbulenta',re>5e5&&re<1e9?nf(L.cfTurb(re)):'fora de 5e5–1e9')+caveat('Estimativa de placa plana: não representa a camada-limite de corpos reais.');}));
 p.append(card('Desempenho do veículo','Modelo de ponto-massa: atrito constante, sem transferência de carga nem limite de tração. Tudo digitado por você.',
  [{k:'m',l:'Massa',u:'kg',v:800},{k:'cda',l:'CdA',u:'m²',v:1.1},{k:'cla',l:'ClA (downforce)',u:'m²',v:3.2},{k:'pw',l:'Potência na roda',u:'kW',v:700},{k:'mu',l:'μ pneu–solo',v:1.6},{k:'crr',l:'Resistência de rolamento',v:0.015},{k:'rho',l:'Densidade do ar',u:'kg/m³',v:1.2},{k:'R',l:'Raio da curva',u:'m',v:60},{k:'vb',l:'Velocidade de frenagem',u:'km/h',v:250}],
  a=>{const v=new L.Vehicle({mass:a.m,cda:a.cda,cla:a.cla,power:a.pw*1000,mu_tyre:a.mu,crr:a.crr,rho:a.rho});const vc=v.corner(a.R),vt=v.top();
   let rows='  km/h   arrasto[N]  downforce[N]  P_req[kW]\n';for(const k of[100,150,200,250,300,350]){const s=k/3.6;rows+=`  ${String(k).padStart(4)}  ${nf(v.drag(s)).padStart(10)}  ${nf(v.downforce(s)).padStart(12)}  ${nf(v.preq(s)/1000).padStart(9)}\n`;}
   const xs=[],pr=[],pa=[],dr=[],dn=[];for(let k=20;k<=Math.max(400,vt*3.6*1.1);k+=10){const s=k/3.6;xs.push(k);pr.push(v.preq(s)/1000);pa.push(a.pw);dr.push(v.drag(s)/1000);dn.push(v.downforce(s)/1000);}
   const ch=plotSVG({title:'Potência requerida × disponível',series:[{n:'P requerida',x:xs,y:pr},{n:'P disponível',x:xs,y:pa,c:'#7dffb0',dash:1}],xl:'km/h',yl:'kW',marks:[{x:vt*3.6,t:'vmáx '+nf(vt*3.6,4)}],zero:1})+plotSVG({title:'Arrasto e downforce',series:[{n:'arrasto',x:xs,y:dr},{n:'downforce',x:xs,y:dn,c:'#ffb22e'}],xl:'km/h',yl:'kN',zero:1});
   return line('Velocidade máx. (P=Preq)',nf(vt*3.6),'km/h')+line('Vel. máx. na curva',isFinite(vc)?nf(vc*3.6):'∞ (downforce sustenta)','km/h')+line('Desaceleração a '+a.vb+' km/h',nf(v.brake(a.vb/3.6)/9.80665),'g')+line('Aceleração a 200 km/h',nf(v.accel(200/3.6)/9.80665),'g')+'\n'+rows+ch+caveat('Sem limite de tração/rotação; vmax pode ser superestimada.');}));
 p.append(card('Asa finita (linha sustentadora de Prandtl)','Asa reta simétrica, corda linear raiz→ponta. Perfil: α_L0 digitado ou NACA 4 dígitos (camber m, posição p). Efeito solo = aproximação de aeronave (McCormick), NÃO vale para F1 com assoalho.',
  [{k:'b',l:'Envergadura',u:'m',v:1.6},{k:'cr',l:'Corda na raiz',u:'m',v:0.3},{k:'ct',l:'Corda na ponta',u:'m',v:0.2},{k:'al',l:'Incidência na raiz',u:'°',v:5},{k:'tw',l:'Torção na ponta (washout −)',u:'°',v:-1},{h:'Perfil'},{k:'m',l:'NACA camber m (0 = simétrico)',v:0.04},{k:'pp',l:'NACA posição p',v:0.4},{k:'a0',l:'α_L0 manual (vazio = NACA)',u:'°',v:null},{k:'cd0',l:'Cd0 do perfil (digitado)',v:0.01},{k:'hg',l:'Altura ao solo (vazio = sem solo)',u:'m',v:null},{k:'v',l:'Velocidade',u:'km/h',v:200},{k:'alt',l:'Altitude',u:'m',v:0}],
  a=>{const aL0=a.a0!=null?a.a0:L.naca4AlphaL0(a.m||0,a.pp||0.4)*180/Math.PI;const r=L.liftingLine(a.b,s=>a.cr+(a.ct-a.cr)*Math.abs(s),a.al,aL0,s=>(a.tw||0)*Math.abs(s),2*Math.PI,40,a.hg);
   const at=L.isa(a.alt),f=L.wingForces(r,at.rho,a.v/3.6,a.cd0||0);
   const al=[],cl=[],cdt=[];for(let q=-4;q<=14.01;q+=1){const w=L.liftingLine(a.b,s=>a.cr+(a.ct-a.cr)*Math.abs(s),q,aL0,s=>(a.tw||0)*Math.abs(s),2*Math.PI,40,a.hg);al.push(q);cl.push(w.cl);cdt.push((a.cd0||0)+w.cdi);}
   const ch=plotSVG({title:'CL × incidência (teoria linear)',series:[{n:'CL',x:al,y:cl}],xl:'α raiz [°]',yl:'CL',zero:1,marks:[{x:a.al,t:'α='+a.al}]})+plotSVG({title:'Polar: CL × CD',series:[{n:'CL(CD)',x:cdt,y:cl,c:'#ffb22e'}],xl:'CD (Cd0 + CDi)',yl:'CL',zero:1});
   return line('α_L0',nf(aL0),'°')+line('Alongamento AR',nf(r.ar))+line('Área',nf(r.area),'m²')+line('CL',nf(r.cl))+line('CDi',nf(r.cdi))+line('Eficiência de Oswald e',nf(r.e))+line('Sustentação',nf(f.lift),'N')+line('Arrasto total',nf(f.drag),'N')+line('L/D',nf(f.ld))+ch+caveat('Teoria linear de pequenos ângulos, sem estol, sem enflechamento, sem compressibilidade.');}));}
// ---- ESTRUTURAL
const SEC=[['rect','Retângulo (b × h)',['b','h']],['circ','Círculo (d)',['d']],['tubo','Tubo redondo (d, t)',['d','t']],['tuber','Tubo retangular (b, h, t)',['b','h','t']],['i','Perfil I (b, h, tf, tw)',['b','h','tf','tw']]];
function mkSec(a){switch(a.st){case'rect':return L.secRect(a.b,a.h);case'circ':return L.secCircle(a.d);case'tubo':return L.secTubeRound(a.d,a.t);case'tuber':return L.secTubeRect(a.b,a.h,a.t);default:return L.secI(a.b,a.h,a.tf,a.tw);}}
const secF=()=>[{k:'st',l:'Seção',sel:SEC.map(s=>[s[0],s[1]]),v:'rect'},{k:'b',l:'b (largura)',u:'mm',v:30,w:['st',['rect','tuber','i']]},{k:'h',l:'h (altura)',u:'mm',v:50,w:['st',['rect','tuber','i']]},{k:'d',l:'d (diâmetro)',u:'mm',v:40,w:['st',['circ','tubo']]},{k:'t',l:'t (parede)',u:'mm',v:3,w:['st',['tubo','tuber']]},{k:'tf',l:'tf (mesa)',u:'mm',v:8,w:['st',['i']]},{k:'tw',l:'tw (alma)',u:'mm',v:5,w:['st',['i']]}];
function tabEstr(p){
 const note='mm, N, MPa. E, Sy, G e cargas são DIGITADOS; resistência dos materiais clássica, não é elementos finitos.';
 p.append(card('Viga (Euler–Bernoulli)',note,[{k:'cs',l:'Caso',sel:[['cant_end','Balanço — carga na ponta'],['cant_udl','Balanço — distribuída'],['ss_mid','Biapoiada — carga no meio'],['ss_udl','Biapoiada — distribuída'],['fp_mid','Engastada-apoiada — meio']],v:'cant_end'},{k:'P',l:'Carga (N ou N/mm)',v:1000},{k:'Lc',l:'Comprimento',u:'mm',v:800},{k:'E',l:'E',u:'MPa',v:210000},{k:'sy',l:'Sy (opcional)',u:'MPa',v:300},...secF()],
  a=>{const s=mkSec(a),r=L.beam(a.cs,a.P,a.Lc,a.E,s,a.sy);return line('Área',nf(s.area),'mm²')+line('Inércia I',nf(s.inertia),'mm⁴')+line('Flecha máxima',nf(r.deflection),'mm')+line('Momento máximo',nf(r.moment/1e6),'kN·m')+line('Tensão de flexão máx.',nf(r.sigma),'MPa')+line('Rigidez',nf(r.stiffness),'N/mm')+(r.safety_factor!=null?line('Coef. de segurança (escoamento)',nf(r.safety_factor)):'')+beamDiagram(a.cs,a.P,a.Lc)+'<span class="tag">Diagramas pelas reações estáticas clássicas (sinal: sagging positivo; balanço tem M negativo no engaste).</span>';}));
 p.append(card('Flambagem de coluna (Euler/Johnson)',note,[{k:'K',l:'Condição de extremidades',sel:[[1,'Articulada–articulada (K=1)'],[2,'Engastada–livre (K=2)'],[0.7,'Engastada–articulada (K=0,7)'],[0.5,'Engastada–engastada (K=0,5)']],v:1},{k:'Lc',l:'Comprimento',u:'mm',v:1500},{k:'E',l:'E',u:'MPa',v:210000},{k:'sy',l:'Sy',u:'MPa',v:350},{k:'P',l:'Carga aplicada (opc.)',u:'N',v:null},...secF()],
  a=>{const s=mkSec(a),r=L.column(a.E,s,a.Lc,+a.K,a.sy);return line('Raio de giração',nf(r.r),'mm')+line('Esbeltez λ',nf(r.slenderness))+line('λ crítica',nf(r.slenderness_crit))+line('Regime',r.regime)+line('P Euler',nf(r.p_euler/1000),'kN')+line('Carga crítica',nf(r.p_crit/1000),'kN')+(a.P?line('Coef. de segurança',nf(r.p_crit/a.P)):'');}));
 p.append(card('Parafuso pré-tensionado (Shigley)','Pré-carga Fi = T/(K·d). O fator K (≈0,2 seco) varia muito: digite o seu.',[{k:'d',l:'Métrico M',sel:Object.keys(L.BOLT_AT).map(k=>[k,'M'+k]),v:10},{k:'T',l:'Torque',u:'N·m',v:40},{k:'K',l:'Fator de torque K',v:0.2},{k:'sp',l:'Carga de prova Sp',u:'MPa',v:640},{k:'Pe',l:'Carga externa de tração',u:'N',v:8000},{k:'r',l:'Rigidez km/kb',v:4}],
  a=>{const r=L.boltJoint(+a.d,a.T,a.K,a.sp,a.Pe||0,a.r);return line('Área de tensão At',nf(r.At),'mm²')+line('Pré-carga Fi',nf(r.preload/1000),'kN')+line('Fi / carga de prova',nf(r.preload_ratio))+line('Carga no parafuso',nf(r.bolt_load/1000),'kN')+line('Tensão no parafuso',nf(r.bolt_stress),'MPa')+line('Carga de aperto restante',nf(r.clamp_load/1000),'kN')+line('Carga de separação',nf(r.separation_load/1000),'kN')+line('n vs. carga de prova',nf(r.n_proof))+(r.clamp_load<0?caveat('Junta separa!'):'');}));
 p.append(card('Torção de eixo',note,[{k:'T',l:'Torque',u:'N·m',v:200},{k:'d',l:'Diâmetro externo',u:'mm',v:30},{k:'di',l:'Diâmetro interno',u:'mm',v:0},{k:'Lc',l:'Comprimento',u:'mm',v:400},{k:'G',l:'G',u:'MPa',v:79000}],
  a=>{const r=L.shaftTorsion(a.T*1000,a.d,a.Lc,a.G,a.di||0);return line('Tensão de cisalhamento',nf(r.tau),'MPa')+line('Torção',nf(r.theta_deg),'°')+line('Rigidez torcional',nf(r.stiffness/1000),'N·m/rad')+line('J',nf(r.J),'mm⁴');}));
 p.append(card('Vaso de pressão de parede fina',note,[{k:'p',l:'Pressão',u:'MPa',v:2},{k:'d',l:'Diâmetro interno',u:'mm',v:300},{k:'t',l:'Espessura',u:'mm',v:5}],a=>{const r=L.thinVessel(a.p,a.d,a.t);return line('Tensão circunferencial',nf(r.hoop),'MPa')+line('Tensão axial',nf(r.axial),'MPa')+(r.thin_ok?'':caveat('t ≥ d/20: parede NÃO é fina, fórmula imprecisa.'));}));
 p.append(card('Vibração',note,[{k:'k',l:'Rigidez (massa-mola)',u:'N/mm',v:20},{k:'m',l:'Massa',u:'kg',v:2},{h:'Viga em balanço'},{k:'E',l:'E',u:'MPa',v:70000},{k:'rho',l:'Densidade',u:'kg/m³',v:2700},{k:'Lc',l:'Comprimento',u:'mm',v:300},{k:'mode',l:'Modo',sel:[[1,'1'],[2,'2'],[3,'3']],v:1},...secF()],
  a=>line('Massa-mola f',nf(L.springMassFn(a.k,a.m)),'Hz')+line('Balanço, modo '+a.mode,nf(L.cantileverFn(a.E,mkSec(a),a.Lc,a.rho,+a.mode)),'Hz')));}
// ---- TRELIÇA
function trussSVG(t,r,scale){const ids=Object.keys(t.nodes),P=ids.map(i=>t.nodes[i].xyz);const sp=[0,1,2].map(a=>Math.max(...P.map(p=>p[a]))-Math.min(...P.map(p=>p[a])));
 const ax=[0,1,2].sort((a,b)=>sp[b]-sp[a]).slice(0,2).sort(),[u,v]=ax;const W=340,H=240,m=20;const xs=P.map(p=>p[u]),ys=P.map(p=>p[v]);
 const dm=Math.max(...ids.map(i=>Math.hypot(...r.displacement[i]))),ext=Math.max(sp[u],sp[v],1),ex=dm>0?scale*0.08*ext/dm:0;
 const pt=(id,def)=>{const p=t.nodes[id].xyz,d=r.displacement[id];return[p[u]+(def?ex*d[u]:0),p[v]+(def?ex*d[v]:0)];};
 const all=ids.flatMap(i=>[pt(i,0),pt(i,1)]),x0=Math.min(...all.map(p=>p[0])),x1=Math.max(...all.map(p=>p[0])),y0=Math.min(...all.map(p=>p[1])),y1=Math.max(...all.map(p=>p[1]));
 const k=Math.min((W-2*m)/Math.max(x1-x0,1),(H-2*m)/Math.max(y1-y0,1)),X=x=>m+(x-x0)*k,Y=y=>H-m-(y-y0)*k;const fm=Math.max(...Object.values(r.force).map(Math.abs),1);let s='';
 for(const[id,b]of Object.entries(t.bars)){const a=pt(b.n1,0),c=pt(b.n2,0);s+=`<line x1="${X(a[0])}" y1="${Y(a[1])}" x2="${X(c[0])}" y2="${Y(c[1])}" stroke="#2a4a5c" stroke-width="1" stroke-dasharray="3 3"/>`;}
 for(const[id,b]of Object.entries(t.bars)){const a=pt(b.n1,1),c=pt(b.n2,1),N=r.force[id],col=N>1e-6?'#27d3ff':(N<-1e-6?'#ffb22e':'#6f95a8');s+=`<line x1="${X(a[0])}" y1="${Y(a[1])}" x2="${X(c[0])}" y2="${Y(c[1])}" stroke="${col}" stroke-width="${1+4*Math.abs(N)/fm}"/>`;}
 for(const id of ids){const a=pt(id,1);s+=`<circle cx="${X(a[0])}" cy="${Y(a[1])}" r="${t.nodes[id].fixed.some(Boolean)?4:2.5}" fill="${t.nodes[id].fixed.some(Boolean)?'#7dffb0':'#cfeaf6'}"/>`;}
 return `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Treliça deformada"><rect width="${W}" height="${H}" fill="#06121c"/>${s}</svg><div class="tag">plano ${'xyz'[u]}–${'xyz'[v]} · ciano tração · laranja compressão · tracejado = indeformada · deformação ×${nf(ex,3)} (exagerada)</div>`;}
function tabTrel(p){
 const c=card('Treliça espacial de barras articuladas','Método da rigidez direta. Formato: NODE id x y z [fix=xyz] · BAR id n1 n2 A E [I=..] · LOAD nó fx fy fz (mm, N, MPa). Linear, sem peso próprio, cargas só nos nós.',
  [{k:'sy',l:'Sy p/ triagem (opc.)',u:'MPa',v:250},{k:'sc',l:'Exagero da deformada',sel:[[1,'×1'],[3,'×3'],[10,'×10']],v:1}],
  (a,out)=>{const t=L.parseTruss(ta.value),r=L.solveTruss(t);store.set('truss',ta.value);let s=line('Nós / barras',Object.keys(t.nodes).length+' / '+Object.keys(t.bars).length)+line('Erro de equilíbrio global',r.equilibrium_error.toExponential(2))+'\n  barra   L[mm]   N[kN]   σ[MPa]  situação\n';
   const worst=Object.keys(r.force).sort((x,y)=>Math.abs(r.force[y])-Math.abs(r.force[x]));
   for(const id of Object.keys(t.bars)){const N=r.force[id],st=N>1e-6?'tração':(N<-1e-6?'compr.':'nula');let ex='';if(a.sy&&Math.abs(r.stress[id])>1e-6)ex+=' n_esc='+nf(a.sy/Math.abs(r.stress[id]),3);if(r.buckling[id])ex+=' n_Euler='+nf(r.buckling[id][1],3);
    s+=`  ${id.padEnd(6)} ${nf(r.length[id],5).padStart(7)} ${nf(N/1000,4).padStart(8)} ${nf(r.stress[id],4).padStart(8)}  ${st}${ex}\n`;}
   const md=Math.max(...Object.entries(r.displacement).map(([i,d])=>[Math.hypot(...d),i]).map(x=>x[0]));
   s+=`\n  esforço máx.: <b>${worst[0]}</b> = ${nf(r.force[worst[0]]/1000)} kN · deslocamento máx. ${nf(md)} mm\n`;
   const rx=Object.entries(r.reactions);s+='\n  reações (kN):\n'+rx.map(([i,v])=>`   ${i}: ${v.map(x=>nf(x/1000,4)).join('  ')}`).join('\n');
   return s+'\n'+trussSVG(t,r,+a.sc)+caveat('Modelo linear de pequenos deslocamentos; flambagem global e plasticidade não incluídas.');});
 const ta=document.createElement('textarea');ta.spellcheck=false;ta.value=store.get('truss',L.warrenExample());ta.style.minHeight='220px';c.querySelector('.f').prepend(ta);
 const b=document.createElement('button');b.className='mini';b.textContent='Carregar exemplo Warren';b.onclick=()=>{ta.value=L.warrenExample();c.run();};c.querySelector('.btns').appendChild(b);p.append(c);}
// ---- PÓRTICO
function frameSVG(fr,res,scaleD,scaleM){const ids=Object.keys(fr.nodes),P=ids.map(i=>fr.nodes[i].xyz);const sp=[0,1,2].map(a=>Math.max(...P.map(p=>p[a]))-Math.min(...P.map(p=>p[a])));
 const[u,v]=[0,1,2].sort((a,b)=>sp[b]-sp[a]).slice(0,2).sort(),W=340,H=260,m=22,ext=Math.max(sp[u],sp[v],1);
 const dmax=Math.max(...ids.map(i=>Math.hypot(...res.displacement[i].slice(0,3))),1e-12),ds=scaleD*0.08*ext/dmax;
 const mmax=Math.max(1e-9,...Object.keys(fr.beams).flatMap(id=>[0,.1,.2,.3,.4,.5,.6,.7,.8,.9,1].map(s=>{const q=L.frameMoment(fr,res,id,s);return Math.hypot(q[0],q[1]);}))),ms=scaleM*0.12*ext/mmax;
 const lines=[],polys=[],pts=[];const dot=(a,b)=>a[0]*b[0]+a[1]*b[1]+a[2]*b[2],cr=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
 for(const[id,b]of Object.entries(fr.beams)){const q=res.info[id],t=q.R[0],p1=fr.nodes[b.n1].xyz,d1=res.displacement[b.n1],d2=res.displacement[b.n2];
  const a1=dot(d1,t),a2=dot(d2,t),t1=d1.slice(0,3).map((x,i)=>x-a1*t[i]),t2=d2.slice(0,3).map((x,i)=>x-a2*t[i]),sl1=cr(d1.slice(3),t),sl2=cr(d2.slice(3),t);
  const und=[],def=[],mom=[];
  for(let k=0;k<=20;k++){const s=k/20,h1=1-3*s*s+2*s**3,h2=s-2*s*s+s**3,h3=3*s*s-2*s**3,h4=-s*s+s**3,ax=a1*(1-s)+a2*s;
   const base=[0,1,2].map(i=>p1[i]+s*q.L*t[i]);und.push([base[u],base[v]]);
   const dd=[0,1,2].map(i=>ax*t[i]+h1*t1[i]+h2*q.L*sl1[i]+h3*t2[i]+h4*q.L*sl2[i]);def.push([base[u]+ds*dd[u],base[v]+ds*dd[v]]);
   const[My,Mz]=L.frameMoment(fr,res,id,s),off=[0,1,2].map(i=>-My*q.R[2][i]+Mz*q.R[1][i]);mom.push([base[u]+ds*dd[u]+ms*off[u],base[v]+ds*dd[v]+ms*off[v]]);}
  lines.push({und,def,mom});pts.push(...und,...def,...mom);}
 const x0=Math.min(...pts.map(p=>p[0])),x1=Math.max(...pts.map(p=>p[0])),y0=Math.min(...pts.map(p=>p[1])),y1=Math.max(...pts.map(p=>p[1])),k=Math.min((W-2*m)/Math.max(x1-x0,1),(H-2*m)/Math.max(y1-y0,1)),X=x=>m+(x-x0)*k,Y=y=>H-m-(y-y0)*k;
 const pl=a=>a.map(p=>X(p[0]).toFixed(1)+','+Y(p[1]).toFixed(1)).join(' ');let s='';
 lines.forEach(l=>{s+=`<polygon points="${pl(l.def.concat(l.mom.slice().reverse()))}" fill="rgba(255,178,46,.18)" stroke="none"/><polyline points="${pl(l.mom)}" fill="none" stroke="#ffb22e" stroke-width="1.2"/>`;});
 lines.forEach(l=>s+=`<polyline points="${pl(l.und)}" fill="none" stroke="#2a4a5c" stroke-dasharray="3 3"/>`);lines.forEach(l=>s+=`<polyline points="${pl(l.def)}" fill="none" stroke="#27d3ff" stroke-width="2.2"/>`);
 for(const id of ids){const p=fr.nodes[id].xyz,d=res.displacement[id],f=fr.nodes[id].fixed.some(Boolean);s+=`<circle cx="${X(p[u]+ds*d[u])}" cy="${Y(p[v]+ds*d[v])}" r="${f?4.5:3}" fill="${f?'#7dffb0':'#cfeaf6'}"/>`;}
 return `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Pórtico: deformada e diagrama de momentos"><rect width="${W}" height="${H}" fill="#06121c"/>${s}</svg><div class="tag">plano ${'xyz'[u]}–${'xyz'[v]} · ciano = deformada ×${nf(ds,3)} (exagerada) ${ms>0?` · laranja = diagrama de momento fletor, desenhado no lado TRACIONADO da viga (escala ×${nf(ms,3)} mm por N·mm)`:''} · tracejado = indeformada</div>`;}
function tabPort(p){
 const c=card('Pórtico espacial de vigas (MEF)','Euler–Bernoulli, 6 GDL/nó. NODE id x y z [fix=xyzXYZ] (minúsculas = translações, MAIÚSCULAS = rotações) · BEAM id n1 n2 A Iy Iz J E G [ref=x,y,z] [c=mm] · LOAD nó fx fy fz [mx my mz] · DLOAD viga wx wy wz · MASS nó kg · BEAM…rho=kg/m³ p/ modal (mm, N, MPa, N·mm). Iy/My = flexão no plano x–z; viga vertical usa X global como referência.',
  [{k:'sy',l:'Sy p/ triagem (opc.)',u:'MPa',v:250},{k:'sd',l:'Exagero da deformada',sel:[[1,'×1'],[3,'×3'],[10,'×10']],v:1},{k:'sm',l:'Escala do momento',sel:[[0.5,'×0,5'],[1,'×1'],[2,'×2']],v:1},{k:'view',l:'Desenho',sel:[['0','Estática + momentos'],['1','Modo 1'],['2','Modo 2'],['3','Modo 3'],['4','Modo 4'],['5','Flambagem 1'],['6','Flambagem 2']],v:'0'}],
  (a)=>{const fr=L.parseFrame(ta.value),res=L.solveFrame(fr);store.set('frame',ta.value);const st=[0,.1,.2,.3,.4,.5,.6,.7,.8,.9,1];
   let s=line('Nós / vigas',Object.keys(fr.nodes).length+' / '+Object.keys(fr.beams).length)+line('Erro de equilíbrio global',res.equilibrium_error.toExponential(2))+'\n  viga   L[mm]  N[kN]  |V|máx  T[kN·m]  |My|máx  |Mz|máx   σmáx[MPa]\n';let worst=[0,''];
   for(const[id,b]of Object.entries(fr.beams)){const q=res.info[id],f=res.end_forces[id];const my=Math.max(...st.map(x=>Math.abs(L.frameMoment(fr,res,id,x)[0]))),mz=Math.max(...st.map(x=>Math.abs(L.frameMoment(fr,res,id,x)[1])));
    const vm=Math.max(...st.map(x=>Math.hypot(...L.frameShear(fr,res,id,x)))),sg=b.c?Math.max(...st.map(x=>{const m=L.frameMoment(fr,res,id,x);return Math.abs(f[0])/b.A+Math.abs(m[0])*b.c/b.Iy+Math.abs(m[1])*b.c/b.Iz;})):null;
    if(sg!=null&&sg>worst[0])worst=[sg,id];s+=`  ${id.padEnd(6)} ${nf(q.L,5).padStart(6)} ${nf(f[0]/1000,4).padStart(7)} ${nf(vm/1000,4).padStart(7)} ${nf(Math.abs(f[3])/1e6,3).padStart(8)} ${nf(my/1e6,4).padStart(8)} ${nf(mz/1e6,4).padStart(8)}  ${sg!=null?nf(sg,4)+(a.sy?'  n='+nf(a.sy/sg,3):''):'—'}\n`;}
   s+='\n  deslocamentos (mm | mrad):\n'+Object.entries(res.displacement).map(([i,d])=>`   ${i.padEnd(4)} ${d.slice(0,3).map(x=>nf(x,4).padStart(9)).join('')}  |${d.slice(3).map(x=>nf(x*1e3,4).padStart(9)).join('')}`).join('\n');
   s+='\n\n  reações (kN | kN·m):\n'+Object.entries(res.reactions).map(([i,r])=>`   ${i.padEnd(4)} ${r.slice(0,3).map(x=>nf(x/1000,4).padStart(9)).join('')}  |${r.slice(3).map(x=>nf(x/1e6,4).padStart(9)).join('')}`).join('\n');
   if(worst[1])s+=`\n\n  σ normal máx.: <b>${nf(worst[0])} MPa</b> na viga ${worst[1]} (N/A + M·c/I nas duas flexões, soma conservadora)`;
   let modal=null;if(Object.values(fr.beams).every(b=>b.rho>0)){modal=L.modalFrame(fr,6);s+='\n\n  <b>Análise modal</b> (massa consistente + MASS; sem amortecimento)\n  massa total considerada: '+nf(modal.mass_total_kg)+' kg\n'+modal.freq_hz.map((f,i)=>`   modo ${i+1}: ${nf(f,6).padStart(9)} Hz   T=${nf(1/f,4)} s`).join('\n');}
   else s+='\n\n  (análise modal: informe rho=kg/m³ em TODAS as vigas; use MASS nó kg para massas concentradas)';
   let bk=null;try{bk=L.bucklingFrame(fr,3);}catch(e){bk=null;}
   if(bk&&bk.factors.length){s+='\n\n  <b>Flambagem linear</b> ((K+λKg)φ=0; λ multiplica o carregamento aplicado)\n'+bk.factors.map((l,i)=>`   modo ${i+1}: λcr = ${nf(l,6)}`).join('\n')+'\n   1ª carga crítica = '+nf(bk.factors[0],5)+' × carregamento aplicado (elástica, sem imperfeições; colunas curtas escoam antes)';}
   else s+='\n\n  (flambagem: o carregamento aplicado não comprime nenhuma viga)';
   let vw=+a.view;let drawRes=res,sm=+a.sm;if(vw>=5){const q=bk&&bk.shapes[vw-5];if(q){drawRes=Object.assign({},res,{displacement:q});sm=0;s+='\n\n  desenho: flambagem '+(vw-4)+' (λcr='+nf(bk.factors[vw-5],5)+'), forma normalizada';}vw=0;}if(vw>0&&modal&&modal.shapes[vw-1]){drawRes=Object.assign({},res,{displacement:modal.shapes[vw-1]});sm=0;s+='\n\n  desenho: modo '+vw+' ('+nf(modal.freq_hz[vw-1],5)+' Hz), forma normalizada';}
   return s+'\n'+frameSVG(fr,drawRes,+a.sd,sm)+caveat('Linear, pequenos deslocamentos, sem cisalhamento (Euler–Bernoulli), sem P-Δ/flambagem global, sem peso próprio automático.');});
 const ta=document.createElement('textarea');ta.spellcheck=false;ta.value=store.get('frame',L.frameExample());ta.style.minHeight='230px';c.querySelector('.f').prepend(ta);
 const b=document.createElement('button');b.className='mini';b.textContent='Carregar exemplo (pórtico)';b.onclick=()=>{ta.value=L.frameExample();c.run();};c.querySelector('.btns').appendChild(b);p.append(c);}
// ---- FADIGA
function snSVG(curve,pts){const W=340,H=200,m=34;const lx=n=>m+(Math.log10(n)-3)/5*(W-m-8),smax=curve.sf1e3*1.1,Y=s=>H-20-(s/smax)*(H-30);
 let d='';for(let i=0;i<60;i++){const n=Math.pow(10,3+5*i/59);let s=curve.stress_at(n);if(curve.has_knee&&n>=curve.nk)s=curve.se;d+=(i?'L':'M')+lx(n).toFixed(1)+' '+Y(s).toFixed(1);}
 let g='';[3,4,5,6,7,8].forEach(e=>g+=`<line x1="${lx(10**e)}" y1="10" x2="${lx(10**e)}" y2="${H-20}" stroke="#14384b"/><text x="${lx(10**e)}" y="${H-6}" fill="#6f95a8" font-size="9" text-anchor="middle">1e${e}</text>`);
 const mark=pts.map(q=>isFinite(q[1])&&q[1]>0?`<circle cx="${lx(Math.min(Math.max(q[0],1e3),1e8))}" cy="${Y(q[1])}" r="4" fill="#ff4d6d"/>`:'').join('');
 return `<svg viewBox="0 0 ${W} ${H}" width="100%"><rect width="${W}" height="${H}" fill="#06121c"/>${g}<path d="${d}" fill="none" stroke="#27d3ff" stroke-width="2"/>${mark}<text x="4" y="14" fill="#6f95a8" font-size="9">σ [MPa]</text><line x1="${m}" y1="${Y(curve.se)}" x2="${W-8}" y2="${Y(curve.se)}" stroke="#ffb22e" stroke-dasharray="4 3"/></svg><div class="tag">curva S-N (Basquin) · Se tracejado · ponto = σ equivalente do caso</div>`;}
function fatInputs(a){const mat={su:a.su,sy:a.sy,se_prime:a.sep,estimate_se:a.est,has_knee:a.knee,nk:a.nk,f:null};
 const mar={surface:a.surf,d_eq:a.deq||0,load_type:a.lt,temp_factor:a.kd||1,reliability_pct:a.rel,misc_factor:a.kf2||1,override_ka:null};
 const sec={kind:a.sk,d:a.sd,di:a.sdi||0,b:a.sb,h:a.sh};
 const load={axial:[a.amin||0,a.amax||0],bending:[a.bmin||0,a.bmax||0],torsion:[a.tmin||0,a.tmax||0]};
 const conc={kt_axial:a.kta||1,q_axial:a.qa??1,kt_bending:a.ktb||1,q_bending:a.qb??1,kt_torsion:a.ktt||1,q_torsion:a.qt??1};return{mat,mar,sec,load,conc};}
function tabFad(p){
 const F=[{h:'Material (digite os dados da folha/ensaio)'},{k:'su',l:'Su',u:'MPa',v:600},{k:'sy',l:'Sy',u:'MPa',v:400},{k:'sep',l:"Se' (vazio = estimar)",u:'MPa',v:null},{k:'est',l:"Estimar Se'=0,5·Su (aço)",chk:1,v:true},{k:'knee',l:'Tem limite de fadiga',chk:1,v:true},{k:'nk',l:'Nk (ciclos do joelho)',v:1e6},
  {h:'Fatores de Marin'},{k:'surf',l:'Superfície',sel:Object.keys(L.SURF).map(k=>[k,k]),v:'Usinado ou laminado a frio'},{k:'deq',l:'Diâmetro equivalente',u:'mm',v:25},{k:'lt',l:'Tipo de carga',sel:Object.keys(L.KC).map(k=>[k,k]),v:'Combinado'},{k:'kd',l:'kd temperatura',v:1},{k:'rel',l:'Confiabilidade',u:'%',v:99},{k:'kf2',l:'kf diversos',v:1},
  {h:'Seção'},{k:'sk',l:'Tipo',sel:[['Círculo cheio','Círculo cheio'],['Tubo','Tubo'],['Retângulo','Retângulo']],v:'Círculo cheio'},{k:'sd',l:'d (externo)',u:'mm',v:25,w:['sk',['Círculo cheio','Tubo']]},{k:'sdi',l:'di (tubo)',u:'mm',v:0,w:['sk',['Tubo']]},{k:'sb',l:'b (ret.)',u:'mm',v:20,w:['sk',['Retângulo']]},{k:'sh',l:'h (ret.)',u:'mm',v:30,w:['sk',['Retângulo']]},
  {h:'Faixa de carga no ciclo (mín / máx)'},{k:'amin',l:'Axial mín',u:'N',v:0},{k:'amax',l:'Axial máx',u:'N',v:0},{k:'bmin',l:'Momento fletor mín',u:'N·mm',v:-200000},{k:'bmax',l:'Momento fletor máx',u:'N·mm',v:300000},{k:'tmin',l:'Torque mín',u:'N·mm',v:0},{k:'tmax',l:'Torque máx',u:'N·mm',v:100000},
  {h:'Concentração de tensão'},{k:'ktb',l:'Kt flexão',v:2},{k:'qb',l:'q flexão',v:0.8},{k:'ktt',l:'Kt torção',v:1.5},{k:'qt',l:'q torção',v:0.9},{k:'kta',l:'Kt axial',v:1},{k:'qa',l:'q axial',v:1},
  {k:'rule',l:'Regra p/ vida',sel:[['Goodman','Goodman'],['Gerber','Gerber'],['SWT','SWT']],v:'Goodman'}];
 p.append(card('Fadiga por tensões nominais','Vida infinita/finita (Shigley, cap. 6): Marin, Goodman/Gerber/Soderberg/ASME, curva S-N. Resistências SEMPRE digitadas por você; não é FEA.',F,
  a=>{const{mat,mar,sec,load,conc}=fatInputs(a),r=L.fatigueAnalyze(mat,mar,sec,load,conc,a.rule);
   let s=line("Se' (corpo de prova)",nf(r.se.se_prime),'MPa')+line('ka kb kc kd ke kf',[r.se.ka,r.se.kb,r.se.kc,r.se.kd,r.se.ke,r.se.kf].map(x=>nf(x,3)).join(' '))+line('Se corrigido',nf(r.se.se),'MPa')+line('σa′ (von Mises)',nf(r.stress.sigma_a),'MPa')+line('σm′ (von Mises)',nf(r.stress.sigma_m),'MPa')+line('σmax',nf(r.stress.sigma_max),'MPa')+'\n';
   for(const[k,v]of Object.entries(r.factors))s+=line('n '+k,nf(v));s+=line('σ equivalente reverso',nf(r.sigma_ar),'MPa')+line('Vida',r.infinite?'<b class="ok">infinita</b>':nf(r.cycles,6)+' ciclos');
   return s+r.warnings.map(w=>caveat('• '+w)).join('')+snSVG(r.curve,[[Math.min(r.infinite?1e8:r.cycles,1e8),r.sigma_ar]]);}));
 p.append(card('Dano acumulado (Miner)','Usa o material e as regras do cartão acima. Uma linha por bloco: rótulo σa σm ciclos (σ equivalentes de von Mises, MPa).',[{k:'blk',l:'—',v:''}],
  (a,out)=>{const fa=fatInputs(readCard('Fadiga por tensões nominais'));
   const r0=L.fatigueAnalyze(fa.mat,fa.mar,fa.sec,fa.load,fa.conc,'Goodman'),bl=ta2.value.split('\n').map(x=>x.trim()).filter(Boolean).map(x=>{const q=x.split(/\s+/);if(q.length<4)throw new Error('Linha inválida: '+x);return{label:q[0],sigma_a:+q[1],sigma_m:+q[2],cycles:+q[3]};});
   store.set('miner',ta2.value);const m=L.miner(bl,fa.mat,r0.curve,readCard('Fadiga por tensões nominais').rule);
   let s='  bloco     σ_ar[MPa]      N[ciclos]   dano\n';m.rows.forEach(r=>s+=`  ${r.label.padEnd(8)} ${nf(r.sigma_ar,5).padStart(10)} ${(isFinite(r.N)?nf(r.N,5):'∞').padStart(14)} ${nf(r.damage,3).padStart(8)}\n`);
   return s+'\n'+line('Dano por repetição D',nf(m.damage))+line('Repetições até a falha',nf(m.repetitions))+line('Ciclos até a falha',nf(m.cycles_to_failure))+caveat('Regra linear de Miner: sem efeito de sequência; ciclos abaixo do limite de fadiga têm dano zero (pode ser não conservador).');}));
 const mc=p.lastChild,ta2=document.createElement('textarea');ta2.value=store.get('miner','curva 250 50 100000\nfreio 300 80 10000');mc.querySelector('.f').innerHTML='';mc.querySelector('.f').appendChild(ta2);
 p.append(card('Mola helicoidal (cisalhamento, Goodman)','Taxa, tensões de Wahl/Bergsträsser, coeficiente de fadiga, altura sólida e surto. G, Su, Sse digitados.',
  [{k:'wire_d',l:'Diâmetro do fio d',u:'mm',v:3.5},{k:'coil_d',l:'Diâmetro médio D',u:'mm',v:25},{k:'active_coils',l:'Espiras ativas Na',v:8},{k:'total_coils',l:'Espiras totais Nt',v:10},{k:'installed_len',l:'Comprimento instalado',u:'mm',v:40},{k:'lift',l:'Curso',u:'mm',v:10},{k:'preload_force',l:'Força de pré-carga',u:'N',v:100},{k:'g_mpa',l:'G',u:'MPa',v:79000},{k:'density_g_cm3',l:'Densidade',u:'g/cm³',v:7.85},{k:'su',l:'Su do fio',u:'MPa',v:1800},{k:'sse',l:'Sse (fadiga em cisalhamento)',u:'MPa',v:500},{k:'ssu',l:'Ssu (vazio = 0,67·Su)',u:'MPa',v:null}],
  a=>{const r=L.springAnalysis(a);return line('Índice C',nf(r.C))+line('Taxa k',nf(r.k),'N/mm')+line('Força mín / máx',nf(r.f_min)+' / '+nf(r.f_max),'N')+line('τa / τm',nf(r.tau_a)+' / '+nf(r.tau_m),'MPa')+line('n fadiga',nf(r.n_f))+line('Altura sólida',nf(r.solid_len),'mm')+line('Folga até sólido',nf(r.clearance_to_solid),'mm')+line('Massa',nf(r.mass_kg*1000),'g')+line('Frequência natural',nf(r.fn_hz),'Hz')+r.warnings.map(w=>caveat('• '+w)).join('');}));}
function readCard(title){const c=[...document.querySelectorAll('#panel .card')].find(x=>x.querySelector('h2').textContent===title),o={};c.querySelectorAll('.fld').forEach(r=>{const i=r.querySelector('input,select'),k=r.dataset.k;
 if(i.type==='checkbox')o[k]=i.checked;else if(i.tagName==='SELECT')o[k]=i.value;else{const t=i.value.trim().replace(',','.');o[k]=t===''?null:Number(t);}});return o;}
// ---- MASSA
function pickMat(cb){const m=$('#modal');m.classList.add('on');m.innerHTML=`<div class="row"><input type="search" id="mq" placeholder="Buscar material (ex.: alumínio, aço, titânio)…" style="flex:1"><button class="mini" id="mx">Fechar</button></div><div class="tag">Densidades do banco do NEXUS (valor típico; faixa quando houver). Escolha é SUA — nada é atribuído sozinho.</div><div id="mlist"></div>`;
 const list=$('#mlist'),q=$('#mq');function fill(){const t=q.value.toLowerCase();const rows=MATS.filter(x=>!t||(x[0]+' '+x[1]).toLowerCase().includes(t)).slice(0,120);
  list.innerHTML=rows.map((x,i)=>`<div class="mi" data-i="${MATS.indexOf(x)}"><b>${esc(x[0])}</b><br><span class="tag">${esc(x[1])} · ${nf(x[2],5)} kg/m³${x[3]!=null&&x[4]!=null?` (faixa ${nf(x[3],4)}–${nf(x[4],4)})`:''}</span></div>`).join('')||'<div class="mi">Nada encontrado.</div>';}
 q.oninput=fill;fill();list.onclick=e=>{const d=e.target.closest('.mi');if(!d||d.dataset.i==null)return;m.classList.remove('on');cb(MATS[+d.dataset.i]);};$('#mx').onclick=()=>m.classList.remove('on');q.focus();}
function tabMassa(p){
 const D=N().data();if(!D){p.innerHTML='<div class="card">Carregando…</div>';return;}
 const key='mat.'+project,asg=store.get(key,{});const groups=new Map();
 D.parts.forEach((q,i)=>{if(q.vol==null)return;const g=groups.get(q.name)||{name:q.name,n:0,vol:0,items:[]};g.n++;g.vol+=q.vol;g.items.push(i);groups.set(q.name,g);});
 const arr=[...groups.values()];let tot=0,withM=0,nWith=0,nAll=0;
 arr.forEach(g=>{nAll+=g.n;const a=asg[g.name];if(a){g.m=g.vol*1e-9*a[1]*1000;tot+=g.m;nWith+=g.n;}});
 const head=document.createElement('section');head.className='card';
 head.innerHTML=`<h2>Massa e BOM</h2><p class="n">Massa = Volume (do B-rep) × densidade do material <b>que você escolher</b>. Nada é atribuído automaticamente. Sem material = sem massa (PROPRIEDADE NÃO INFORMADA).</p>
 <div class="res" style="display:block">${line('Massa com material',nf(tot/1000,5),'kg')}${line('Peças com material',nWith+' / '+nAll)}${nWith<nAll?'<span class="warn">PARCIAL: faltam materiais em '+(nAll-nWith)+' peças — o total NÃO é a massa do conjunto.</span>':'<span class="ok">Todas as peças têm material (massa total do conjunto, sob suas escolhas).</span>'}</div>
 <div class="btns" style="margin-top:8px"><button class="mini" id="mb">Exportar BOM (texto)</button><button class="mini" id="mc">Limpar escolhas</button></div><textarea id="mt" style="display:none" readonly></textarea>`;
 p.append(head);
 const c=document.createElement('section');c.className='card';c.innerHTML=`<table class="tbl"><tr><th>Peça</th><th>Vol. cm³</th><th>Material</th><th>g</th></tr>${arr.map((g,gi)=>{const a=asg[g.name];return `<tr><td>${esc(g.name)}${g.n>1?' ×'+g.n:''}</td><td>${nf(g.vol/1000/g.n,4)}</td><td><button class="mini" data-g="${gi}" style="min-height:34px;padding:0 8px;font-size:11px">${a?esc(a[0].slice(0,26)):'escolher'}</button></td><td>${g.m!=null?nf(g.m,4):'—'}</td></tr>`;}).join('')}</table>`;p.append(c);
 c.onclick=e=>{const b=e.target.closest('button[data-g]');if(!b)return;const g=arr[+b.dataset.g];pickMat(m=>{asg[g.name]=[m[0],m[2]];store.set(key,asg);rebuild('massa');});};
 head.querySelector('#mc').onclick=()=>{store.set(key,{});rebuild('massa');};
 head.querySelector('#mb').onclick=()=>{const t=['# BOM — '+D.name,'','| Peça | Qtd | Vol. unit. (cm³) | Material | Densidade (kg/m³) | Massa (g) |','|---|---|---|---|---|---|'];
  arr.forEach(g=>{const a=asg[g.name];t.push(`| ${g.name} | ${g.n} | ${nf(g.vol/1000/g.n,5)} | ${a?a[0]:'PROPRIEDADE NÃO INFORMADA'} | ${a?a[1]:'—'} | ${g.m!=null?nf(g.m,5):'—'} |`);});
  t.push('',`Massa com material: ${nf(tot/1000,5)} kg · peças com material ${nWith}/${nAll}${nWith<nAll?' — PARCIAL':''}`);const ta=head.querySelector('#mt');ta.style.display='block';ta.value=t.join('\n');ta.select();try{navigator.clipboard.writeText(ta.value).catch(()=>{});}catch(e){}};}
// ---- INTERFERÊNCIA
function tabInterf(p){
 const D=N().data();if(!D){p.innerHTML='<div class="card">Carregando…</div>';return;}
 const c=document.createElement('section');c.className='card';let rows,mode;
 if(D.clashes){mode='exata';rows=D.clashes.map(x=>({a:x[0],b:x[1],v:x[2]}));}
 else{mode='nenhum';rows=[];}
 c.innerHTML=`<h2>Interferências (pose montada)</h2><p class="n">${mode==='exata'?'Volume da interseção booleana EXATA (OpenCascade), calculado no desktop. Toque na linha para ver as duas peças no 3D.':'Este projeto não tem cálculo exato embarcado.'}
 Verificação ESTÁTICA: encaixes propositais (rolamento, solda) aparecem como colisão — a decisão é sua.</p>
 <div class="row"><label for="fq">Filtro</label><input type="search" id="fq" placeholder="nome da peça" style="flex:1"></div><div class="res" style="display:block" id="cnt"></div><table class="tbl" id="ct"></table>`;
 p.append(c);const t=c.querySelector('#ct'),q=c.querySelector('#fq');
 function fill(){const f=q.value.toLowerCase();const r=rows.filter(x=>!f||(D.parts[x.a].name+' '+D.parts[x.b].name).toLowerCase().includes(f));
  c.querySelector('#cnt').innerHTML=rows.length?`${rows.length} pares com sobreposição ≥ 1 mm³ · mostrando ${Math.min(r.length,80)}`:'<span class="ok">Nenhuma interferência ≥ 1 mm³ nesta pose.</span>';
  t.innerHTML='<tr><th>Peça A</th><th>Peça B</th><th>mm³</th></tr>'+r.slice(0,80).map(x=>`<tr class="tap" data-a="${x.a}" data-b="${x.b}"><td>${esc(D.parts[x.a].name)}</td><td>${esc(D.parts[x.b].name)}</td><td>${nf(x.v,4)}</td></tr>`).join('');}
 q.oninput=fill;fill();t.onclick=e=>{const r=e.target.closest('tr.tap');if(!r)return;setTab('3d');setTimeout(()=>N().focusPair(+r.dataset.a,+r.dataset.b),60);};}
function tabSobre(p){const R=window.__registry||[];p.innerHTML=`<section class="card"><h2>NEXUS Engineering Lab — celular</h2><p class="n">Versão ${window.__ver||''}. Espelho de bancada do app desktop (Windows, Python/OpenCascade). Para testar quando o computador não está disponível.</p>
 <div class="res" style="display:block"><b>O que roda aqui</b>\n• 3D: ${R.length} projetos (seleção, explosão, corte, medição, animação onde há mecanismo: motor, F1 2026/2027, F1 clássicos, aeronaves e demais)\n• <b>Aba F1</b>: volta quase-estacionária, <b>telemetria sintética</b> (canais + CSV), massa/CG/inércia e conferência de regulamento — estudo com SEUS parâmetros, não substitui sistemas de equipe nem homologação\n• Aerodinâmica, estrutural, treliça, <b>pórtico 3D de vigas com análise modal</b>, fadiga/Miner/mola e conversão de unidades: calculadoras em JS <b>validadas contra o Python</b> (diferença relativa ≈ 1e-13)\n• Massa/BOM com material escolhido por você (banco de ${MATS?MATS.length:'…'} materiais)\n• Interferências exatas pré-calculadas no desktop\n\n<b>O que NÃO roda aqui</b>\n• Importar STEP/STL, criar ou editar peças (CAD paramétrico), booleanas\n• Biblioteca editável e Arsenal versionado (use o desktop; aqui há a vitrine das 18 peças)\n• FEA 3D: aba FEA 3D (viga maciça, Tet4 próprio); peças arbitrárias, CFD (OpenFOAM) e CalculiX só no desktop\n• Dinâmica veicular: aba Veículo (RK4 longitudinal 1D + curva em regime com bicicleta/escova/transferência de carga, analíticas); a animação do F1 continua cenário prescrito\n• CalculiX e OpenFOAM: só no desktop (aqui nada é executado); no desktop o NEXUS tem diagnóstico de ambiente, FEA em processo isolado (cancelável, com progresso), leitura do campo .frd do CalculiX, log central, backups e resultados amarrados à versão da geometria\n\n<b>Honestidade</b>\n• Nenhum material é atribuído sozinho; coeficientes e propriedades são digitados por você\n• Modelos predefinidos são de referência/didáticos, não CAD de fabricante\n• Resultados valem tanto quanto as entradas e hipóteses</div></section>`;}
// ---- UNIDADES
function tabFea(p){const c=document.createElement('section');c.className='card';
 const F=[['L','Comprimento (mm)',100],['b','Largura b (mm)',10],['h','Altura h (mm)',10],['nx','Divisões em x',8],['ny','Divisões em y',1],['nz','Divisões em z',1],['E','E (MPa) — informe',210000],['nu','ν — informe',0.3],['P','Força na ponta (N, + para baixo)',100]];
 c.innerHTML=`<h2>FEA 3D — viga engastada (Tet10 / Tet4)</h2><p class="n">Elasticidade linear com tetraedros <b>quadráticos (Tet10, sem travamento)</b> ou lineares (Tet4, trava em flexão), engaste em x=0, carga na ponta distribuída por carga consistente. <b>Classe: SIMULAÇÃO NUMÉRICA</b> (solver NEXUS-Tet10/Tet4, espelho dos módulos Python, diferença ≈1e-11). Tet4 trava em flexão e <b>subestima</b>; Tet10 fecha com a teoria de Timoshenko já em malha grossa. Compare abaixo. Material é seu: nada é atribuído.</p><div class="fld"><label>Elemento</label><select id="fel"><option value="10">Tet10 quadrático</option><option value="4">Tet4 linear</option></select></div>`+
 F.map(f=>`<div class="fld"><label>${f[1]}</label><input data-k="${f[0]}" inputmode="decimal" type="text" value="${store.get('fe.'+f[0],f[2])}"></div>`).join('')+'<button class="p" id="fgo">Calcular</button><div class="res" style="display:block" id="fr"></div>';p.append(c);
 const r=c.querySelector('#fr');c.querySelector('#fgo').onclick=()=>{r.innerHTML='Calculando…';setTimeout(()=>{try{const q={};c.querySelectorAll('input').forEach(i=>{q[i.dataset.k]=Number(i.value.replace(',','.'));store.set('fe.'+i.dataset.k,i.value);if(Number.isNaN(q[i.dataset.k]))throw new Error('Valor inválido em '+i.dataset.k);});
  const t0=performance.now(),res=(c.querySelector('#fel').value==='10'?L.feaCant10:L.feaCant)(q.L,q.b,q.h,q.nx,q.ny,q.nz,q.E,q.nu,-q.P),dt=performance.now()-t0;
  const I=q.b*q.h**3/12,eb=q.P*q.L**3/(3*q.E*I),G=q.E/(2*(1+q.nu)),tm=eb+q.P*q.L/(G*(5/6)*q.b*q.h),d=Math.abs(res.tipDeflection);
  r.innerHTML=line('Deslocamento da ponta (FEA)',nf(d,6),'mm')+'\n'+line('Euler-Bernoulli',nf(eb,6),'mm')+'\n'+line('Timoshenko',nf(tm,6),'mm')+'\n'+line('FEA / Timoshenko',nf(d/tm*100,4),'%')+'\n'+line('Malha',res.nodes+' nós · '+res.elements+' tet · '+res.dofs+' GDL','')+'\n<span class="n">Classe: SIMULAÇÃO NUMÉRICA · NEXUS-Tet'+c.querySelector('#fel').value+' · '+nf(dt,3)+' ms · linear, pequenas deformações, seção maciça retangular</span>';}catch(e){r.innerHTML='<span class="warn">⚠ '+esc(e.message)+'</span>';}},30);};}
function tabVeic(p){const c=document.createElement('section');c.className='card';
 const F=[['m','Massa (kg)',800],['cd','Cd',0.9],['area','Área frontal (m²)',1.5],['crr','Crr',0.015],['F','Força trativa máx (N)',9000],['P','Potência máx (W)',300000],['mu','μ pneu',1.6],['tf','Tempo (s)',20],['v0','v inicial (m/s)',0]];
 c.innerHTML=`<h2>Dinâmica longitudinal (integração RK4)</h2><p class="n">Modelo 1D de ponto material: arrasto ½ρCdAv², rolamento, limite de potência e de aderência. <b>Classe: ANALÍTICO</b> — não é multicorpo, sem slip de pneu, sem transferência de carga. Todos os parâmetros são seus; nada é inventado. Separado da animação prescrita do F1.</p>`+
 F.map(f=>`<div class="fld"><label>${f[1]}</label><input data-k="${f[0]}" inputmode="decimal" type="text" value="${store.get('vd.'+f[0],f[2])}"></div>`).join('')+'<div class="res" style="display:block" id="vr"></div>';p.append(c);
 const r=c.querySelector('#vr');function go(){try{const q={};c.querySelectorAll('input').forEach(i=>{q[i.dataset.k]=Number(i.value.replace(',','.'));store.set('vd.'+i.dataset.k,i.value);if(Number.isNaN(q[i.dataset.k]))throw new Error('Valor inválido em '+i.dataset.k);});
  const h=L.vehDyn({m:q.m,cd:q.cd,area:q.area,crr:q.crr,F:q.F,P:q.P,mu:q.mu,rho:1.225},q.tf,0.01,q.v0);const last=h[h.length-1];const vmax=Math.max(...h.map(a=>a[2]));
  const t100=(h.find(a=>a[2]>=100/3.6)||[null])[0];
  r.innerHTML=line('v final',nf(last[2]*3.6,5),'km/h')+'\n'+line('v máx',nf(vmax*3.6,5),'km/h')+'\n'+line('distância',nf(last[1],6),'m')+'\n'+line('0→100 km/h',t100==null?'não atingiu':nf(t100,4),t100==null?'':'s')+'\n<span class="n">Classe: ANALÍTICO · RK4 dt=0,01 s</span>';}catch(e){r.innerHTML='<span class="warn">⚠ '+esc(e.message)+'</span>';}}
 c.querySelectorAll('input').forEach(i=>i.oninput=go);go();}
function tabCurva(p){const c=document.createElement('section');c.className='card';
 const F=[['m','Massa (kg)',1200],['iz','Inércia de guinada Iz (kg·m²)',1800],['a','CG → eixo dianteiro (m)',1.15],['b','CG → eixo traseiro (m)',1.35],['h','Altura do CG (m)',0.5],['tf','Bitola dianteira (m)',1.5],['tr','Bitola traseira (m)',1.5],
  ['cF','Rigidez de curva por pneu diant. (N/rad)',45000],['cR','Rigidez de curva por pneu tras. (N/rad)',45000],['muF','μ de pico diant.',1.2],['muR','μ de pico tras.',1.2],['krF','Rigidez de rolagem diant. (N·m/rad)',60000],['krR','Rigidez de rolagem tras. (N·m/rad)',40000],
  ['hRcF','Centro de rolagem diant. (m)',0.05],['hRcR','Centro de rolagem tras. (m)',0.08],['cla','ClA downforce (m²)',0],['v','Velocidade (km/h)',80],['R','Raio da curva (m)',100]];
 c.innerHTML=`<h2>Curva em regime (bicicleta + transferência de carga)</h2><p class="n">Modelo de uma pista com pneu de escova (rigidez de curva e μ seus), transferência de carga lateral (centros de rolagem + rigidez de rolagem) e skidpad com downforce. <b>Classe: ANALÍTICO</b> — não é multicorpo; sem cambagem nem acoplamento com tração/freio. <b>Valores iniciais ILUSTRATIVOS</b> (carro leve genérico), não de um veículo real. Validado contra o Python do NEXUS (erro ≈ 1e-15).</p>`+
 F.map(f=>`<div class="fld"><label>${f[1]}</label><input data-k="${f[0]}" inputmode="decimal" type="text" value="${store.get('lat.'+f[0],f[2])}"></div>`).join('')+'<div class="res" style="display:block" id="cr"></div>';p.append(c);
 const r=c.querySelector('#cr');function go(){try{const q={};c.querySelectorAll('input').forEach(i=>{q[i.dataset.k]=Number(i.value.replace(',','.'));store.set('lat.'+i.dataset.k,i.value);if(Number.isNaN(q[i.dataset.k]))throw new Error('Valor inválido em '+i.dataset.k);});
  const V=Object.assign({},q);delete V.v;delete V.R;const ms=q.v/3.6,rg=L.regimeCurva(V,ms,q.R),lm=L.ayLimite(V,ms),sp=L.skidpad(V,q.R);
  let h=line('a lateral pedida',nf(rg.ayG,4),'g')+'\n'+line('a lateral limite',nf(lm.ayG,4),'g')+'\n<span class="n">Limite: '+lm.limite+'</span>\n'+line('transf. de carga frente',nf(rg.cargas.dzf,5),'N')+'\n'+line('transf. de carga traseira',nf(rg.cargas.dzr,5),'N')+'\n';
  if(rg.saturado)h+='<span class="warn">⚠ A aderência NÃO sustenta esta curva (satura: '+rg.eixoSaturado+'). Nenhum esterçamento é calculado.</span>\n';
  else h+=line('esterçamento (eixo)',nf(rg.delta*180/Math.PI,4),'°')+'\n'+line('deriva do CG β',nf(rg.beta*180/Math.PI,4),'°')+'\n'+line('gradiente de subesterço K',nf(rg.kSub*180/Math.PI*9.80665,4),'°/g')+'\n<span class="n">Comportamento: '+rg.comportamento+'</span>\n';
  h+=line('v máx no raio (skidpad)',nf(sp.vKmh,5),'km/h')+'\n'+line('tempo de uma volta no raio',nf(sp.tVolta,4),'s')+'\n<span class="n">Classe: ANALÍTICO · escova + Milliken · parâmetros ILUSTRATIVOS até você digitar os seus</span>';r.innerHTML=h;}catch(e){r.innerHTML='<span class="warn">⚠ '+e.message+'</span>';}}
 c.querySelectorAll('input').forEach(i=>i.oninput=go);go();}
function tabPneuSusp(p){const c=document.createElement('section');c.className='card';
 const T=[['fz','Fz (N)',4000],['cA','C_α (N/rad)',60000],['cK','C_κ (N)',80000],['mu','μ',1.5],['kap','κ (escorregamento longitudinal)',0.08],['al','α (graus)',4]];
 const S=['A','B','C','D','W','P'].map(n=>[n,L.SUSP_EX[n]]);
 c.innerHTML=`<h2>Pneu combinado (Fx–Fy) e suspensão duplo-A</h2><p class="n">Pneu de escova com escorregamento combinado: respeita o círculo de atrito μ·Fz. Suspensão em vista frontal 2D (y para fora, z para cima, metros): camber, Δbitola, centro de rolagem. <b>Classe: ANALÍTICO</b>; sem elastocinemática, caster/KPI. <b>Valores iniciais ILUSTRATIVOS</b>, não de um carro real. Validado contra o Python do NEXUS.</p>`+
 T.map(f=>`<div class="fld"><label>${f[1]}</label><input data-t="${f[0]}" inputmode="decimal" type="text" value="${store.get('ps.'+f[0],f[2])}"></div>`).join('')+'<div class="res" style="display:block" id="pt"></div><h3>Pontos da suspensão (y ; z)</h3>'+
 S.map(f=>`<div class="fld"><label>${f[0]}</label><input data-s="${f[0]}" type="text" value="${store.get('ps.'+f[0],f[1][0]+' ; '+f[1][1])}"></div>`).join('')+
 '<div class="fld"><label>heave mín / máx (m)</label><input id="hh" type="text" value="'+store.get('ps.hh','-0.03 ; 0.03')+'"></div><div class="res" style="display:block" id="ps"></div>';p.append(c);
 const rt=c.querySelector('#pt'),rs=c.querySelector('#ps'),num=s=>Number(String(s).replace(',','.'));
 function go(){try{const q={};c.querySelectorAll('input[data-t]').forEach(i=>{q[i.dataset.t]=num(i.value);store.set('ps.'+i.dataset.t,i.value);if(Number.isNaN(q[i.dataset.t]))throw new Error('Valor inválido em '+i.dataset.t);});
  if(!(q.mu>0)||!(q.cA>0)||!(q.cK>0))throw new Error('μ, C_α e C_κ devem ser positivos');const f=L.forcaCombinada(q.kap,q.al*Math.PI/180,q.fz,q.cA,q.cK,q.mu),lim=q.mu*q.fz,r=Math.hypot(f[0],f[1]);
  rt.innerHTML=line('Fx',nf(f[0],5),'N')+'\n'+line('Fy',nf(f[1],5),'N')+'\n'+line('uso do círculo de atrito',nf(100*r/Math.max(lim,1e-9),4),'%')+'\n<span class="n">Classe: ANALÍTICO · escova combinada</span>';}catch(e){rt.innerHTML='<span class="warn">⚠ '+e.message+'</span>';}
  try{const s={};c.querySelectorAll('input[data-s]').forEach(i=>{store.set('ps.'+i.dataset.s,i.value);const a=i.value.split(';').map(num);if(a.length!==2||a.some(Number.isNaN))throw new Error('Ponto '+i.dataset.s+': use "y ; z"');s[i.dataset.s]=a;});
  const hv=c.querySelector('#hh').value;store.set('ps.hh',hv);const h=hv.split(';').map(num);if(h.length!==2||h.some(Number.isNaN))throw new Error('heave: use "mín ; máx"');
  let t='<table class="tbl"><tr><th>heave mm</th><th>camber °</th><th>Δbitola mm</th><th>RC mm</th></tr>';for(let k=0;k<5;k++){const hh=h[0]+(h[1]-h[0])*k/4,o=L.suspResolver(s,hh);t+=`<tr><td>${nf(hh*1000,4)}</td><td>${nf(o.camber,4)}</td><td>${nf(o.dBitola*1000,4)}</td><td>${o.RC==null?'—':nf(o.RC*1000,4)}</td></tr>`;}
  rs.innerHTML=t+'</table><span class="n">Classe: ANALÍTICO · cinemática 2D (vista frontal)</span>';}catch(e){rs.innerHTML='<span class="warn">⚠ '+e.message+'</span>';}}
 c.querySelectorAll('input').forEach(i=>i.oninput=go);go();
 const g=document.createElement('section');g.className='card';g.innerHTML='<h2>Diagrama g-g (aderência sob tração/frenagem)</h2><p class="n">Usa os parâmetros da seção <b>Curva em regime</b> (aba Veículo) e a velocidade dela. ax&gt;0: tração no eixo traseiro; ax&lt;0: frenagem 50/50. Sem arrasto nem arfagem. <b>Classe: ANALÍTICO</b>; valores iniciais ILUSTRATIVOS.</p><div class="res" style="display:block" id="gg"></div>';p.append(g);
 const rg=g.querySelector('#gg');function gg(){try{const K=['m','iz','a','b','h','tf','tr','cF','cR','muF','muR','krF','krR','hRcF','hRcR','cla'],D={m:1200,iz:1800,a:1.15,b:1.35,h:0.5,tf:1.5,tr:1.5,cF:45000,cR:45000,muF:1.2,muR:1.2,krF:60000,krR:40000,hRcF:0.05,hRcR:0.08,cla:0},V={};
  K.forEach(k=>{V[k]=Number(String(store.get('lat.'+k,D[k])).replace(',','.'));});const vel=Number(String(store.get('lat.v',80)).replace(',','.'))/3.6;const L2=L.latDefaults?L.latDefaults(V):V;
  const pts=L.diagramaGG(Object.assign({cla:0,fracAero:0.5,rho:1.225},V),vel,13,0.5);rg.innerHTML='<table class="tbl"><tr><th>ax g</th><th>ay máx g</th></tr>'+pts.map(q=>`<tr><td>${nf(q[0],3)}</td><td>${q[1]==null?'inviável':nf(q[1],3)}</td></tr>`).join('')+'</table>';}catch(e){rg.innerHTML='<span class="warn">⚠ '+e.message+'</span>';}}
 gg();document.querySelectorAll('input[data-k]').forEach(i=>i.addEventListener('input',()=>setTimeout(gg,0)));}
function tabUnid(p){const T=UT;if(!T){p.innerHTML='<div class="card">Tabela de unidades indisponível.</div>';return;}
 const c=document.createElement('section');c.className='card';const dims=Object.keys(T);
 c.innerHTML=`<h2>Conversão de unidades</h2><p class="n">SI como base. Fatores exatos por definição (pol = 0,0254 m, lb = 0,45359237 kg, atm = 101325 Pa…). Temperatura com deslocamento (°C, °F). Validado contra o módulo Python do NEXUS.</p>
 <div class="fld"><label>Grandeza</label><select id="ud">${dims.map(d=>`<option>${d}</option>`).join('')}</select></div>
 <div class="fld"><label>Valor</label><input id="uv" inputmode="decimal" type="text" value="${store.get('u.v','1')}"></div>
 <div class="fld"><label>De</label><select id="ua"></select></div><div class="fld"><label>Para</label><select id="ub"></select></div><div class="res" style="display:block" id="ur"></div>`;p.append(c);
 const d=c.querySelector('#ud'),v=c.querySelector('#uv'),a=c.querySelector('#ua'),b=c.querySelector('#ub'),r=c.querySelector('#ur');d.value=store.get('u.d',dims[0]);
 function fillU(){const us=Object.keys(T[d.value]);a.innerHTML=b.innerHTML=us.map(u=>`<option>${u}</option>`).join('');a.value=us[0];b.value=us[1]||us[0];}
 function go(){try{const x=Number(v.value.replace(',','.'));if(Number.isNaN(x))throw new Error('Valor inválido');store.set('u.v',v.value);store.set('u.d',d.value);
  r.innerHTML=line(x+' '+a.value+' =',nf(L.unitsConvert(T,x,a.value,b.value),10),b.value)+'\n'+Object.keys(T[d.value]).map(u=>'  '+nf(L.unitsConvert(T,x,a.value,u),8).padStart(16)+'  '+u).join('\n');}catch(e){r.innerHTML='<span class="warn">⚠ '+esc(e.message)+'</span>';}}
 d.onchange=()=>{fillU();go();};[v,a,b].forEach(e=>e.oninput=go);fillU();go();}
// ---- navegação
let UT=null;
function tabF1(p){const c=document.createElement('section');c.className='card';
 const F=[['m','Massa com piloto (kg)',800],['pIce','Potência de combustão (kW)',500],['cda','Cd·A (m²)',1.0],['cla','Cl·A (m²)',3.0],['mu','μ de aderência',1.6],['crr','Crr',0.012],['pErs','Implantação elétrica (kW)',300],['eErs','Energia elétrica por volta (MJ)',4]];
 const trk=store.get('f1.track',LAB_TRACK_TXT());
 c.innerHTML=`<h2>Engenharia F1 — volta, massa/CG e regulamento</h2><p class="n">Ferramentas de <b>estudo</b> com SEUS parâmetros; valores iniciais são exemplos, a pista é <b>sintética</b>. Volta: ponto material quase-estacionário, μ constante, elipse de atrito, sem pneus reais/transferência de carga/combustível. <b>Classe: SIMULAÇÃO NUMÉRICA (NEXUS-LapSim 1.0)</b> — não substitui os sistemas de uma equipe nem a homologação da FIA.</p><p class="n"><b>Volta</b></p>`+
 F.map(f=>`<div class="fld"><label>${f[1]}</label><input data-k="${f[0]}" inputmode="decimal" type="text" value="${store.get('f1.'+f[0],f[2])}"></div>`).join('')+
 `<div class="fld"><label>Pista: comprimento_m, raio_m (0 = reta), um por linha</label><textarea id="ft" rows="6" style="width:100%">${esc(trk)}</textarea></div><div class="res" style="display:block" id="fr"></div>
 <p class="n" style="margin-top:12px"><b>Telemetria sintética</b> (derivada da volta acima; <b>não é telemetria real</b>; pedais ESTIMADOS, marcha/rotação ILUSTRATIVAS)</p><div class="fld"><label>marchas, rpm máx., velocidade na última marcha (km/h), setores</label><input id="ftel" type="text" value="${store.get('f1.tel','8, 15000, 340, 3')}"></div><div class="res" style="display:block" id="fto"></div><canvas id="fc" width="640" height="340" style="width:100%;background:#0b1620;border-radius:8px"></canvas><div class="fld"><button id="fcsv" type="button">Baixar CSV da telemetria</button></div>
 <p class="n" style="margin-top:12px"><b>Massa e CG</b> (itens: nome, massa kg, x, y, z mm; uma linha por item)</p><div class="fld"><textarea id="fm" rows="4" style="width:100%">${esc(store.get('f1.items','Chassi, 120, 0, 1200, 300\nMotor e caixa, 150, 0, 2500, 400\nPiloto, 80, 0, 1000, 330\nLastro, 30, 0, 600, 100'))}</textarea></div>
 <div class="fld"><label>y do eixo dianteiro / traseiro (mm)</label><input id="fy" type="text" value="${store.get('f1.y','0, 3400')}"></div><div class="res" style="display:block" id="fb"></div>
 <p class="n" style="margin-top:12px"><b>Regulamento</b> (medidas em mm; vazio = sem medida; limites lidos em fontes públicas, ver desktop)</p><div class="fld"><label>Temporada</label><select id="fs"><option>2027</option><option>2026</option></select></div>
 <div class="fld"><label>meia-largura, entre-eixos, prancha, massa (kg), limite de massa 2027</label><input id="fg" type="text" value="${store.get('f1.reg','940, 3400, 10, , ')}"></div><div class="res" style="display:block" id="fg2"></div>`;p.append(c);
 const num=t=>{t=t.trim().replace(',','.');return t===''?null:Number(t);};
 function go(){const fr=c.querySelector('#fr'),fb=c.querySelector('#fb'),fg=c.querySelector('#fg2');
  try{const q={};c.querySelectorAll('input[data-k]').forEach(i=>{q[i.dataset.k]=Number(i.value.replace(',','.'));store.set('f1.'+i.dataset.k,i.value);if(Number.isNaN(q[i.dataset.k]))throw new Error('Valor inválido em '+i.dataset.k);});
   const tx=c.querySelector('#ft').value;store.set('f1.track',tx);const pista=tx.split('\n').filter(l=>l.trim()).map(l=>l.replace(';',',').split(',').map(Number));
   const r=L.lapSim({m:q.m,pIce:q.pIce*1e3,cda:q.cda,cla:q.cla,mu:q.mu,crr:q.crr,pErs:q.pErs*1e3,eErs:q.eErs*1e6},pista,2);const mn=Math.floor(r.tempo/60),sc=r.tempo-60*mn;
   fr.innerHTML=line('tempo de volta',mn+':'+(sc<10?'0':'')+sc.toFixed(3),'')+'\n'+line('comprimento',nf(r.comp,5),'m')+'\n'+line('v média / máx / mín',nf(r.vMedia,4)+' / '+nf(r.vMax,4)+' / '+nf(r.vMin,4),'km/h')+'\n'+line('energia elétrica usada',nf(r.eMJ,3),'MJ');}catch(e){fr.innerHTML='<span class="warn">⚠ '+esc(e.message)+'</span>';}
  try{const tt=c.querySelector('#ftel').value.split(',').map(Number);store.set('f1.tel',c.querySelector('#ftel').value);const q2={};c.querySelectorAll('input[data-k]').forEach(i=>q2[i.dataset.k]=Number(i.value.replace(',','.')));
   const tx2=c.querySelector('#ft').value,pista2=tx2.split('\n').filter(l=>l.trim()).map(l=>l.replace(';',',').split(',').map(Number));
   const T=L.telemetry({m:q2.m,pIce:q2.pIce*1e3,cda:q2.cda,cla:q2.cla,mu:q2.mu,crr:q2.crr,pErs:q2.pErs*1e3,eErs:q2.eErs*1e6},pista2,2,tt[0],tt[1],tt[2],tt[3]);c._tel=T;
   c.querySelector('#fto').innerHTML=line('setores',T.setores.map(x=>nf(x,4)).join(' | '),'s')+'\n'+line('g lateral / frenagem / aceleração máx.',nf(T.gLatMax,3)+' / '+nf(T.gFreioMax,3)+' / '+nf(T.gAcelMax,3),'g')+'\n'+line('acelerador pleno / freio',nf(T.pctPleno,3)+' / '+nf(T.pctFreio,3),'% da distância')+'\n<span class="n">Classe: SIMULAÇÃO NUMÉRICA (NEXUS-Telemetria 1.0) — dados SINTÉTICOS.</span>';drawTel(c.querySelector('#fc'),T.ch);}catch(e){c.querySelector('#fto').innerHTML='<span class="warn">⚠ '+esc(e.message)+'</span>';}
  try{const it=c.querySelector('#fm').value.split('\n').filter(l=>l.trim()).map(l=>{const a=l.split(',');if(a.length!==5)throw new Error('use: nome, massa, x, y, z');return[a[0].trim(),Number(a[1]),[Number(a[2]),Number(a[3]),Number(a[4])]];});
   store.set('f1.items',c.querySelector('#fm').value);const y=c.querySelector('#fy').value.split(',').map(Number);store.set('f1.y',c.querySelector('#fy').value);const b=L.f1Balance(it,y[0],y[1]);
   fb.innerHTML=line('massa',nf(b.massa,5),'kg')+'\n'+line('CG x,y,z',b.cg.map(v=>nf(v,5)).join(' , '),'mm')+'\n'+line('distribuição diant./tras.',nf(b.pFront,4)+' / '+nf(b.pRear,4),'%')+'\n'+line('inércia Ixx Iyy Izz',nf(b.I[0][0],4)+' '+nf(b.I[1][1],4)+' '+nf(b.I[2][2],4),'kg·m²')+'\n<span class="n">Classe: ANALÍTICO (massas pontuais)</span>';}catch(e){fb.innerHTML='<span class="warn">⚠ '+esc(e.message)+'</span>';}
  try{const g=c.querySelector('#fg').value.split(',').map(num);store.set('f1.reg',c.querySelector('#fg').value);const res=L.f1Check(c.querySelector('#fs').value,{half_width_mm:g[0],wheelbase_mm:g[1],plank_mm:g[2],mass_kg:g[3]},g[4]);
   fg.innerHTML=res.map(r=>`<div>${esc(r.rule)} · ${esc(r.title)} ${r.op} ${r.limit==null?'—':r.limit}: <b class="${r.status==='NAO_CONFORME'?'warn':''}">${r.status}</b></div>`).join('')+'<span class="n">Não é homologação; regras sem medida ficam SEM_MEDIDA.</span>';}catch(e){fg.innerHTML='<span class="warn">⚠ '+esc(e.message)+'</span>';}}
 c.querySelector('#fcsv').onclick=()=>{if(!c._tel)return;const b=new Blob([L.telemetryCsv(c._tel)],{type:'text/csv'}),a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='telemetria_sintetica.csv';document.body.appendChild(a);a.click();a.remove();};
 c.querySelectorAll('input,textarea,select').forEach(i=>i.oninput=go);c.querySelector('#fs').onchange=go;go();}
function drawTel(cv,ch){const x=cv.getContext('2d'),W=cv.width,H=cv.height;x.fillStyle='#0b1620';x.fillRect(0,0,W,H);
 const lanes=[['Velocidade km/h',['v'],['#33e0ff']],['Acelerador % (verde) / Freio % (vermelho) — estimados',['acel','freio'],['#3ddc84','#ff5c5c']],['Marcha — ilustrativa',['marcha'],['#ffd24d']],['g longitudinal (laranja) / lateral (azul)',['gLong','gLat'],['#ff9f43','#6c8cff']]];
 const lh=H/lanes.length,s=ch.s,sm=s[s.length-1]||1;lanes.forEach((ln,li)=>{const y0=li*lh;let lo=Infinity,hi=-Infinity;ln[1].forEach(k=>{lo=Math.min(lo,...ch[k]);hi=Math.max(hi,...ch[k]);});if(hi-lo<1e-9)hi=lo+1;
  x.fillStyle='#9fb4c4';x.font='12px sans-serif';x.fillText(ln[0]+'  ['+lo.toFixed(1)+' … '+hi.toFixed(1)+']',6,y0+13);
  ln[1].forEach((k,ci)=>{x.strokeStyle=ln[2][ci];x.lineWidth=1.3;x.beginPath();ch[k].forEach((b,i)=>{const px=5+(W-10)*s[i]/sm,py=y0+18+(lh-24)*(1-(b-lo)/(hi-lo));i?x.lineTo(px,py):x.moveTo(px,py);});x.stroke();});
  x.strokeStyle='#22384a';x.beginPath();x.moveTo(0,y0+lh);x.lineTo(W,y0+lh);x.stroke();});}

function tabF1Sim(c){c.innerHTML='<p class="n">Simulador NEXUS F1 (somente leitura): 15 circuitos calculados no desktop com parâmetros ESTIMADOS — pista animada, telemetria sintética e som de motor sintetizado a partir do RPM. Toque em Som para ligar o áudio.</p><iframe src="f1sim.html" style="width:100%;height:78vh;border:1px solid #12394d;border-radius:8px;background:#06101a" title="NEXUS F1 Sim"></iframe>';}
async function tabF1An(c){c.innerHTML='<p class="n">Análise no estilo MoTeC i2 / OptimumLap, pré-calculada no desktop para o carro-base 2025 (ESTIMADO). Mostra tendências, não dados de equipe.</p><div class="fld"><label>Circuito</label><select id="anc"></select></div><div id="ano"></div><canvas id="anp" width="640" height="260" style="width:100%;background:#0b1620;border-radius:8px"></canvas><canvas id="anh" width="640" height="220" style="width:100%;background:#0b1620;border-radius:8px;margin-top:8px"></canvas>';
 let D;try{D=await (await fetch('analise_f1.json')).json();}catch(e){c.querySelector('#ano').innerHTML='<span class="warn">⚠ analise_f1.json indisponível</span>';return;}
 const sel=c.querySelector('#anc');Object.entries(D.circuitos).forEach(([k,v])=>{const o=document.createElement('option');o.value=k;o.textContent=v.nome;sel.appendChild(o);});
 const line=(cv,xs,ys,tx,col,bar)=>{const x=cv.getContext('2d'),W=cv.width,H=cv.height;x.fillStyle='#0b1620';x.fillRect(0,0,W,H);const x0=Math.min(...xs),x1=Math.max(...xs);let y0=Math.min(...ys),y1=Math.max(...ys);if(bar)y0=Math.min(0,y0);if(y1-y0<1e-9)y1=y0+1;
  const px=v=>40+(W-52)*(v-x0)/((x1-x0)||1),py=v=>22+(H-48)*(1-(v-y0)/(y1-y0));x.fillStyle='#9fb4c4';x.font='12px sans-serif';x.fillText(tx,8,14);x.fillText(y1.toPrecision(4),2,30);x.fillText(y0.toPrecision(4),2,H-24);x.fillText(x0.toPrecision(3)+' … '+x1.toPrecision(3),44,H-8);
  x.strokeStyle=col;x.fillStyle=col;x.lineWidth=2;if(bar){const bw=Math.max(3,(W-52)/xs.length*0.8);xs.forEach((v,i)=>x.fillRect(px(v)-bw/2,Math.min(py(ys[i]),py(0)),bw,Math.abs(py(ys[i])-py(0))+1));}else{x.beginPath();xs.forEach((v,i)=>i?x.lineTo(px(v),py(ys[i])):x.moveTo(px(v),py(ys[i])));x.stroke();}};
 const show=()=>{const d=D.circuitos[sel.value];const rows=d.sens.map(s=>'<tr><td>'+s.p+'</td><td>'+Number(s.v.toPrecision(4))+'</td><td style="color:'+(s.d>0?'#ff7b7b':'#3ddc84')+'">'+(s.d>=0?'+':'')+s.d.toFixed(4)+' s</td></tr>').join('');
  const gs=Object.entries(d.gears).map(([g,t])=>g+'ª '+t.toFixed(1)+' s').join(' · ');
  c.querySelector('#ano').innerHTML='<div class="res" style="display:block">volta-base <b>'+d.lap.toFixed(3)+' s</b> · melhor nível de asa <b>'+d.aero.best.toFixed(2)+'</b> (0 = baixo arrasto, 1 = alta carga) · acelerador pleno '+d.pedais.acelerador_pleno_pct.toFixed(0)+' % · freio '+d.pedais.freio_pct.toFixed(0)+' %<br>marchas: '+gs+'</div><table style="width:100%;font-size:13px;margin:8px 0"><tr><th align="left">Parâmetro</th><th align="left">Valor</th><th align="left">Δ volta por +1 %</th></tr>'+rows+'</table>';
  line(c.querySelector('#anp'),d.aero.lv,d.aero.t,'Tempo de volta (s) × nível de asa','#33e0ff',false);line(c.querySelector('#anh'),d.hist.x,d.hist.s,'Histograma de velocidade (s por faixa, km/h)','#ffb02e',true);};
 sel.onchange=show;show();}
function LAB_TRACK_TXT(){return L.LAP_TRACK.map(a=>a.join(', ')).join('\n');}
function tabProd(p){const P=window.__produtos||[],G=window.__glossario||{};const ic={PRONTO:'✅',PARCIAL:'🟡',PLANEJADO:'⬜'};
 const c=document.createElement('section');c.className='card';
 c.innerHTML=`<h2>Produtos NEXUS</h2><p class="n">Mapa honesto do que existe: ✅ pronto e testado · 🟡 parcial (com limites) · ⬜ planejado (não existe ainda).</p>`+P.map(x=>`<div class="res" style="display:block"><b>${esc(x.nome)}</b> ${ic[x.estado]||''}\n${esc(x.missao)}\n`+x.caps.map(k=>`${ic[k.estado]} ${esc(k.rotulo)}${k.nota?' — '+esc(k.nota):''}`).join('\n')+`\n<i>Limites: ${x.lacunas.map(esc).join(' · ')}</i></div>`).join('');
 p.append(c);
 const d=document.createElement('section');d.className='card';
 d.innerHTML=`<h2>NEXUS INTELLIGENCE — fator de segurança</h2><p class="n">Parecer por regras (não é IA generativa; não inventa números). Informe a tensão von Mises máxima e o escoamento do SEU material.</p>
 <div class="fld"><label>von Mises máx. (MPa)</label><input id="iv" inputmode="decimal" type="text" value="${store.get('i.v','150')}"></div>
 <div class="fld"><label>Escoamento do material (MPa) — informe</label><input id="is" inputmode="decimal" type="text" value="${store.get('i.s','250')}"></div>
 <button class="p" id="ig">Interpretar</button><div class="res" style="display:block" id="ir"></div>
 <div class="fld"><label>Glossário</label><select id="gt">${Object.keys(G).map(k=>`<option>${esc(k)}</option>`).join('')}</select></div><div class="res" style="display:block" id="gr"></div>`;p.append(d);
 const num=s=>parseFloat(String(s).replace(',','.'));
 d.querySelector('#ig').onclick=()=>{const vm=num(d.querySelector('#iv').value),sy=num(d.querySelector('#is').value);store.set&&store.set('i.v',d.querySelector('#iv').value);store.set&&store.set('i.s',d.querySelector('#is').value);
  try{const r=LAB.interpFS(vm,sy);const t={CRITICO:'Escoamento previsto no ponto de máxima tensão.',ATENCAO:'Margem baixa (depende de cargas reais, fadiga e concentração).',INFO:'Margem sobre o escoamento (estático, sem fadiga).'}[r.nivel];
   d.querySelector('#ir').innerHTML=`Fator de segurança <b>${nf(r.fs)}</b> → <b>${r.nivel}</b>\n${t}\nFonte: von Mises=${vm} MPa, escoamento=${sy} MPa (informados por você).`;}catch(e){d.querySelector('#ir').textContent='⚠ '+e.message;}};
 const g=d.querySelector('#gt');g.onchange=()=>{d.querySelector('#gr').textContent=g.value+': '+G[g.value];};g.onchange();}
const BUILD={prod:tabProd,f1sim:tabF1Sim,f1an:tabF1An,fea:tabFea,veic:p=>{tabVeic(p);tabCurva(p);tabPneuSusp(p);},f1:tabF1,unid:tabUnid,aero:tabAero,estr:tabEstr,trel:tabTrel,port:tabPort,fad:tabFad,massa:tabMassa,interf:tabInterf,sobre:tabSobre};
function rebuild(id){const p=$('#panel');p.innerHTML='';BUILD[id](p);}
function setTab(id){cur=id;document.querySelectorAll('.tab').forEach(b=>b.setAttribute('aria-selected',b.dataset.t===id));
 const p=$('#panel'),v=$('#view');if(id==='3d'){p.style.display='none';v.style.display='flex';setTimeout(()=>N().resizeNow(),30);return;}
 v.style.display='none';p.style.display='block';const need=(id==='massa'||id==='interf'||id==='sobre'||!built[id]);if(need){rebuild(id);if(id!=='massa'&&id!=='interf'&&id!=='sobre'&&id!=='unid')built[id]=p.innerHTML&&[...p.childNodes];}
 else{p.innerHTML='';built[id].forEach(n=>p.appendChild(n));}p.scrollTop=0;}
function makeTabs(){const nav=$('#tabs');TABS.forEach(([id,t])=>{const b=document.createElement('button');b.className='tab';b.dataset.t=id;b.role='tab';b.textContent=t;b.onclick=()=>setTab(id);nav.appendChild(b);});}
async function openProject(key){project=key;$('#tag').textContent='carregando…';
 try{const r=await fetch('data/'+key+'.json');const D=await r.json();N().load(D);$('#tag').textContent=D.note?'modelo de referência':'somente leitura';window.__note=D.note;}
 catch(e){$('#tag').textContent='falha ao carregar';}
 store.set('proj',key);if(cur!=='3d')setTab(cur);}
async function init(){makeTabs();
 try{MATS=await (await fetch('materials.json')).json();}catch(e){MATS=[];}
 try{UT=await (await fetch('units.json')).json();}catch(e){UT=null;}
 let reg=[];try{reg=await (await fetch('data/registry.json')).json();}catch(e){}
 window.__registry=reg;const sel=$('#proj');reg.forEach(r=>{const o=document.createElement('option');o.value=r.key;o.textContent=r.title+(r.mech?' ▶':'');sel.appendChild(o);});
 const first=store.get('proj','f1'),pick=reg.find(r=>r.key===first)?first:(reg[0]&&reg[0].key);sel.value=pick;sel.onchange=()=>openProject(sel.value);
 setTab('3d');if(pick)openProject(pick);}
window.__ver=document.documentElement.dataset.ver||'';
window.addEventListener('load',()=>{if(window.__nexus)init();});
})();
