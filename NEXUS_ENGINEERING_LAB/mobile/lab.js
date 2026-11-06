/* NEXUS Lab (celular) — portagem em JS das calculadoras ANALÍTICAS do desktop (modules/aero.py, structural.py, truss_fem.py, fatigue.py).
   Validado contra o Python em tests (mobile/validate_lab.py). Não é CFD nem FEA 3D; coeficientes e propriedades são digitados pelo usuário. */
(function(root){
'use strict';
const G=9.80665,R_AIR=287.0528,GAMMA=1.4,PI=Math.PI;
const hyp=Math.hypot,sq=x=>x*x;
function solveLin(A,b){ // Gauss com pivotamento parcial; devolve null se singular
 const n=b.length,M=A.map((r,i)=>r.slice().concat([b[i]]));let scale=0;for(let i=0;i<n;i++)scale=Math.max(scale,Math.abs(M[i][i]));
 for(let c=0;c<n;c++){let p=c;for(let r=c+1;r<n;r++)if(Math.abs(M[r][c])>Math.abs(M[p][c]))p=r;
  if(Math.abs(M[p][c])<=1e-10*Math.max(scale,1e-300))return null;[M[c],M[p]]=[M[p],M[c]];
  for(let r=c+1;r<n;r++){const f=M[r][c]/M[c][c];if(f!==0)for(let k=c;k<=n;k++)M[r][k]-=f*M[c][k];}}
 const x=new Array(n);for(let i=n-1;i>=0;i--){let s=M[i][n];for(let k=i+1;k<n;k++)s-=M[i][k]*x[k];x[i]=s/M[i][i];}return x;}
// ---------- FEA 3D Tet4 (viga engastada em caixa) — espelho de modules/fea3d.py
function feaCant(Lx,Ly,Lz,nx,ny,nz,E,nu,Fz){
 if(nx*ny*nz>("feaCant"==='feaCant10'?64:200))throw new Error('Malha grande demais para o celular ('+nx*ny*nz+' células). Reduza as divisões.'); // engaste em x=0, força total Fz (N) na face x=Lx, distribuída por carga consistente
 if(!(Lx>0&&Ly>0&&Lz>0&&E>0&&nu>-1&&nu<0.5&&nx>=1&&ny>=1&&nz>=1))throw new Error('Parâmetros inválidos');
 const N=(nx+1)*(ny+1)*(nz+1);if(N*3>1200)throw new Error('Malha grande demais para o celular ('+N+' nós, máx. 400).');
 const ix=(i,j,k)=>(i*(ny+1)+j)*(nz+1)+k,nodes=[];for(let i=0;i<=nx;i++)for(let j=0;j<=ny;j++)for(let k=0;k<=nz;k++)nodes.push([Lx*i/nx,Ly*j/ny,Lz*k/nz]);
 const HT=[[0,1,3,7],[0,1,5,7],[0,4,5,7],[0,4,6,7],[0,2,6,7],[0,2,3,7]],tets=[];
 for(let i=0;i<nx;i++)for(let j=0;j<ny;j++)for(let k=0;k<nz;k++){const c=[];for(let d=0;d<2;d++)for(let b=0;b<2;b++)for(let a=0;a<2;a++)c.push(ix(i+a,j+b,k+d));
  for(const t of HT){let q=[c[t[0]],c[t[1]],c[t[2]],c[t[3]]];const P=q.map(n=>nodes[n]);const u=[0,1,2].map(m=>P[1][m]-P[0][m]),v=[0,1,2].map(m=>P[2][m]-P[0][m]),w=[0,1,2].map(m=>P[3][m]-P[0][m]);
   const vol=(u[1]*v[2]-u[2]*v[1])*w[0]+(u[2]*v[0]-u[0]*v[2])*w[1]+(u[0]*v[1]-u[1]*v[0])*w[2];if(vol<0)q=[q[0],q[2],q[1],q[3]];tets.push(q);}}
 const lam=E*nu/((1+nu)*(1-2*nu)),mu=E/(2*(1+nu)),D=[[lam+2*mu,lam,lam,0,0,0],[lam,lam+2*mu,lam,0,0,0],[lam,lam,lam+2*mu,0,0,0],[0,0,0,mu,0,0],[0,0,0,0,mu,0],[0,0,0,0,0,mu]];
 const n3=3*N,K=Array.from({length:n3},()=>new Float64Array(n3));
 for(const t of tets){const P=t.map(n=>nodes[n]);const M=P.map(p=>[1,p[0],p[1],p[2]]);
  const C=[0,1,2,3].map(()=>[0,0,0,0]);for(let c=0;c<4;c++){const e=[0,0,0,0];e[c]=1;const x=solveLin(M,e);for(let r=0;r<4;r++)C[r][c]=x[r];}
  // C = M^-1 (linhas: coeficientes); gradiente da função de forma a = C[1..3][a]
  const det=(()=>{const u=[0,1,2].map(m=>P[1][m]-P[0][m]),v=[0,1,2].map(m=>P[2][m]-P[0][m]),w=[0,1,2].map(m=>P[3][m]-P[0][m]);return Math.abs((u[1]*v[2]-u[2]*v[1])*w[0]+(u[2]*v[0]-u[0]*v[2])*w[1]+(u[0]*v[1]-u[1]*v[0])*w[2])/6;})();
  const B=Array.from({length:6},()=>new Array(12).fill(0));
  for(let a=0;a<4;a++){const bx=C[1][a],by=C[2][a],bz=C[3][a];B[0][3*a]=bx;B[1][3*a+1]=by;B[2][3*a+2]=bz;B[3][3*a]=by;B[3][3*a+1]=bx;B[4][3*a+1]=bz;B[4][3*a+2]=by;B[5][3*a]=bz;B[5][3*a+2]=bx;}
  const DB=D.map(r=>B[0].map((_,c)=>{let s=0;for(let k=0;k<6;k++)s+=r[k]*B[k][c];return s;}));
  for(let p=0;p<12;p++)for(let q=0;q<12;q++){let s=0;for(let k=0;k<6;k++)s+=B[k][p]*DB[k][q];K[3*t[(p/3)|0]+p%3][3*t[(q/3)|0]+q%3]+=s*det;}}
 // carga consistente na face x=Lx
 const F=new Float64Array(n3),tipSet=new Set();nodes.forEach((p,i)=>{if(Math.abs(p[0]-Lx)<1e-9)tipSet.add(i);});
 let tot=0;const w=new Map(),seen=new Map();
 for(const t of tets)for(const f of [[0,1,2],[0,1,3],[0,2,3],[1,2,3]]){const key=f.map(a=>t[a]).sort((a,b)=>a-b).join(',');seen.set(key,(seen.get(key)||0)+1);}
 for(const [key,c] of seen){if(c!==1)continue;const q=key.split(',').map(Number);if(!q.every(n=>tipSet.has(n)))continue;const p=q.map(n=>nodes[n]);
  const u=[0,1,2].map(m=>p[1][m]-p[0][m]),v=[0,1,2].map(m=>p[2][m]-p[0][m]);const cx=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]];const A=0.5*Math.hypot(...cx);tot+=A;q.forEach(n=>w.set(n,(w.get(n)||0)+A/3));}
 for(const [n,a] of w)F[3*n+2]+=Fz*a/tot;
 const free=[];for(let i=0;i<N;i++)if(nodes[i][0]>1e-9)for(let c=0;c<3;c++)free.push(3*i+c);
 const A=free.map(r=>Array.from(free,c=>K[r][c])),x=solveLin(A,free.map(r=>F[r]));if(!x)throw new Error('Sistema singular');
 const U=new Float64Array(n3);free.forEach((d,i)=>U[d]=x[i]);let s=0,cnt=0;for(const n of tipSet){s+=U[3*n+2];cnt++;}
 return{tipDeflection:s/cnt,nodes:N,elements:tets.length,dofs:free.length};}
// ---------- FEA 3D Tet10 (quadrático, sem travamento) — espelho de modules/fea_tet10.py
function feaCant10(Lx,Ly,Lz,nx,ny,nz,E,nu,Fz){
 if(nx*ny*nz>("feaCant10"==='feaCant10'?64:200))throw new Error('Malha grande demais para o celular ('+nx*ny*nz+' células). Reduza as divisões.');
 if(!(Lx>0&&Ly>0&&Lz>0&&E>0&&nu>-1&&nu<0.5&&nx>=1&&ny>=1&&nz>=1))throw new Error('Parâmetros inválidos');
 const ix=(i,j,k)=>(i*(ny+1)+j)*(nz+1)+k,nodes=[];for(let i=0;i<=nx;i++)for(let j=0;j<=ny;j++)for(let k=0;k<=nz;k++)nodes.push([Lx*i/nx,Ly*j/ny,Lz*k/nz]);
 const HT=[[0,1,3,7],[0,1,5,7],[0,4,5,7],[0,4,6,7],[0,2,6,7],[0,2,3,7]],ED=[[0,1],[1,2],[2,0],[0,3],[1,3],[2,3]],tets=[],mid=new Map();
 for(let i=0;i<nx;i++)for(let j=0;j<ny;j++)for(let k=0;k<nz;k++){const c=[];for(let d=0;d<2;d++)for(let b=0;b<2;b++)for(let a=0;a<2;a++)c.push(ix(i+a,j+b,k+d));
  for(const t of HT){let q=[c[t[0]],c[t[1]],c[t[2]],c[t[3]]];const P=q.map(n=>nodes[n]);const u=[0,1,2].map(m=>P[1][m]-P[0][m]),v=[0,1,2].map(m=>P[2][m]-P[0][m]),w=[0,1,2].map(m=>P[3][m]-P[0][m]);
   if((u[1]*v[2]-u[2]*v[1])*w[0]+(u[2]*v[0]-u[0]*v[2])*w[1]+(u[0]*v[1]-u[1]*v[0])*w[2]<0)q=[q[0],q[2],q[1],q[3]];
   for(const [a,b] of ED){const key=Math.min(q[a],q[b])+'_'+Math.max(q[a],q[b]);if(!mid.has(key)){mid.set(key,nodes.length);nodes.push(nodes[q[a]].map((x,m)=>(x+nodes[q[b]][m])/2));}q.push(mid.get(key));}
   tets.push(q);}}
 const N=nodes.length;if(N>450)throw new Error('Malha grande demais para o celular ('+N+' nós, máx. 450). Reduza as divisões.');
 const lam=E*nu/((1+nu)*(1-2*nu)),mu=E/(2*(1+nu)),D=[[lam+2*mu,lam,lam,0,0,0],[lam,lam+2*mu,lam,0,0,0],[lam,lam,lam+2*mu,0,0,0],[0,0,0,mu,0,0],[0,0,0,0,mu,0],[0,0,0,0,0,mu]];
 const A_=0.5854101966249685,B_=0.1381966011250105,GP=[[B_,B_,B_],[A_,B_,B_],[B_,A_,B_],[B_,B_,A_]];
 function dN(xi){const L=[1-xi[0]-xi[1]-xi[2],xi[0],xi[1],xi[2]],dL=Array.from({length:10},()=>[0,0,0,0]);for(let i=0;i<4;i++)dL[i][i]=4*L[i]-1;
  ED.forEach(([a,b],k)=>{dL[4+k][a]=4*L[b];dL[4+k][b]=4*L[a];});return dL.map(r=>[r[1]-r[0],r[2]-r[0],r[3]-r[0]]);}
 const inv3=m=>{const[a,b,c,d,e,f,g,h,i]=[m[0][0],m[0][1],m[0][2],m[1][0],m[1][1],m[1][2],m[2][0],m[2][1],m[2][2]];const det=a*(e*i-f*h)-b*(d*i-f*g)+c*(d*h-e*g);
  return{det,m:[[(e*i-f*h)/det,(c*h-b*i)/det,(b*f-c*e)/det],[(f*g-d*i)/det,(a*i-c*g)/det,(c*d-a*f)/det],[(d*h-e*g)/det,(b*g-a*h)/det,(a*e-b*d)/det]]};};
 const n3=3*N,K=Array.from({length:n3},()=>new Float64Array(n3));
 for(const t of tets){const P=t.map(n=>nodes[n]);
  for(const xi of GP){const d=dN(xi);const J=[[0,0,0],[0,0,0],[0,0,0]];for(let a=0;a<10;a++)for(let j=0;j<3;j++)for(let k=0;k<3;k++)J[j][k]+=d[a][j]*P[a][k];
   const {det,m:Ji}=inv3(J);if(det<=0)throw new Error('Elemento invertido');
   const B=Array.from({length:6},()=>new Array(30).fill(0));
   for(let a=0;a<10;a++){const g=[0,1,2].map(r=>Ji[r][0]*d[a][0]+Ji[r][1]*d[a][1]+Ji[r][2]*d[a][2]);const[bx,by,bz]=g;
    B[0][3*a]=bx;B[1][3*a+1]=by;B[2][3*a+2]=bz;B[3][3*a]=by;B[3][3*a+1]=bx;B[4][3*a+1]=bz;B[4][3*a+2]=by;B[5][3*a]=bz;B[5][3*a+2]=bx;}
   const w=det/24;const DB=D.map(r=>B[0].map((_,c)=>{let s=0;for(let k=0;k<6;k++)s+=r[k]*B[k][c];return s;}));
   for(let p=0;p<30;p++)for(let q=0;q<30;q++){let s=0;for(let k=0;k<6;k++)s+=B[k][p]*DB[k][q];K[3*t[(p/3)|0]+p%3][3*t[(q/3)|0]+q%3]+=s*w;}}}
 const F=new Float64Array(n3),tip=new Set();nodes.forEach((p,i)=>{if(Math.abs(p[0]-Lx)<1e-9)tip.add(i);});
 const FC=[[0,1,2,4,5,6],[0,1,3,4,8,7],[0,2,3,6,9,7],[1,2,3,5,9,8]],seen=new Map();let tot=0;
 for(const t of tets)for(const f of FC){const key=[t[f[0]],t[f[1]],t[f[2]]].sort((a,b)=>a-b).join(',');if(!seen.has(key))seen.set(key,[]);seen.get(key).push(f.map(a=>t[a]));}
 const wt=new Map();
 for(const [,lst] of seen){if(lst.length!==1||!lst[0].every(n=>tip.has(n)))continue;const n6=lst[0],p=n6.slice(0,3).map(n=>nodes[n]);
  const u=[0,1,2].map(m=>p[1][m]-p[0][m]),v=[0,1,2].map(m=>p[2][m]-p[0][m]);const A=0.5*Math.hypot(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]);tot+=A;
  n6.slice(3).forEach(n=>wt.set(n,(wt.get(n)||0)+A/3));}
 for(const [n,a] of wt)F[3*n+2]+=Fz*a/tot;
 const used=new Set();tets.forEach(t=>t.forEach(n=>used.add(n)));const free=[];for(const i of used)if(nodes[i][0]>1e-9)for(let c=0;c<3;c++)free.push(3*i+c);
 const x=solveLin(free.map(r=>free.map(c=>K[r][c])),free.map(r=>F[r]));if(!x)throw new Error('Sistema singular');
 const U=new Float64Array(n3);free.forEach((d,i)=>U[d]=x[i]);let s=0,cnt=0;for(const n of tip){if(used.has(n)){s+=U[3*n+2];cnt++;}}
 return{tipDeflection:s/cnt,nodes:used.size,elements:tets.length,dofs:free.length};}
// ---------- aero
function isa(h,dT=0){if(h<-500||h>20000)throw new Error('Altitude fora de 0–20 km da ISA.');
 const T0=288.15,p0=101325,L=-0.0065;let T,p;
 if(h<=11000){T=T0+L*h;p=p0*Math.pow(T/T0,-G/(L*R_AIR));}
 else{const T11=T0+L*11000,p11=p0*Math.pow(T11/T0,-G/(L*R_AIR));T=T11;p=p11*Math.exp(-G*(h-11000)/(R_AIR*T11));}
 const Ta=T+dT,rho=p/(R_AIR*Ta),mu=1.458e-6*Math.pow(Ta,1.5)/(Ta+110.4);return{T:Ta,p,rho,mu,a:Math.sqrt(GAMMA*R_AIR*Ta)};}
const dynQ=(rho,v)=>0.5*rho*v*v, force=(ca,rho,v)=>dynQ(rho,v)*ca, reynolds=(rho,v,L,mu)=>rho*v*L/mu;
const cfTurb=re=>{if(re<=0)throw new Error('Re deve ser positivo.');return 0.455/Math.pow(Math.log10(re),2.58);};
class Vehicle{constructor(o){Object.assign(this,{crr:0.012,rho:1.225},o);}
 drag(v){return force(this.cda,this.rho,v);} downforce(v){return force(this.cla,this.rho,v);}
 normal(v){return this.mass*G+this.downforce(v);} rolling(v){return v>0?this.crr*this.normal(v):0;}
 preq(v){return(this.drag(v)+this.rolling(v))*v;}
 top(){let lo=1,hi=200;if(this.preq(hi)<this.power)return hi;for(let i=0;i<80;i++){const m=0.5*(lo+hi);if(this.preq(m)<this.power)lo=m;else hi=m;}return 0.5*(lo+hi);}
 corner(R){if(R<=0)throw new Error('Raio deve ser positivo.');const den=this.mass/R-this.mu_tyre*0.5*this.rho*this.cla;return den<=0?Infinity:Math.sqrt(this.mu_tyre*this.mass*G/den);}
 brake(v){return(this.mu_tyre*this.normal(v)+this.drag(v))/this.mass;}
 accel(v){return(this.power/Math.max(v,1)-this.drag(v)-this.rolling(v))/this.mass;}}
function naca4AlphaL0(m,p){if(m<=0)return 0;const N=4001,th=[],f=[];
 for(let i=0;i<N;i++){const t=PI*i/(N-1),x=0.5*(1-Math.cos(t));const dz=x<p?2*m/(p*p)*(p-x):2*m/sq(1-p)*(p-x);th.push(t);f.push(dz*(Math.cos(t)-1));}
 let s=0;for(let i=0;i<N-1;i++)s+=0.5*(f[i]+f[i+1])*(th[i+1]-th[i]);return -s/PI;}
function liftingLine(span,chordFn,alphaDeg,alphaL0Deg=0,twistFn=null,a0=2*PI,N=40,hGround=null){
 const th=[],s=[],c=[];for(let i=1;i<=N;i++){const t=i*PI/(2*N);th.push(t);s.push(Math.cos(t));c.push(chordFn(Math.cos(t)));}
 const alpha=s.map(v=>(alphaDeg+(twistFn?twistFn(v):0)-alphaL0Deg)*PI/180),mu=c.map(v=>v*a0/(4*span));
 const M=[];for(let i=0;i<N;i++){M.push([]);for(let j=0;j<N;j++){const n=2*j+1;M[i].push(Math.sin(n*th[i])*(n*mu[i]+Math.sin(th[i])));}}
 const rhs=mu.map((m,i)=>m*alpha[i]*Math.sin(th[i])),A=solveLin(M,rhs);if(!A)throw new Error('Sistema da linha sustentadora singular.');
 let area=0;const K=2000;for(let i=0;i<K;i++){const y0=-1+2*i/K,y1=-1+2*(i+1)/K;area+=0.5*(chordFn(y0)+chordFn(y1))*(y1-y0)*span/2;}
 const ar=span*span/area,cl=A[0]*PI*ar;let delta=0;for(let j=1;j<N;j++)delta+=(2*j+1)*sq(A[j]/A[0]);
 let cdi=cl*cl/(PI*ar)*(1+delta),e=1/(1+delta);
 if(hGround!=null){const k=sq(16*hGround/span);cdi*=k/(1+k);e/=k/(1+k);}
 return{cl,cdi,e,ar,area,span};}
function wingForces(r,rho,v,cd0=0){const q=dynQ(rho,v),lift=q*r.area*r.cl,drag=q*r.area*(cd0+r.cdi);return{q,lift,drag,induced:q*r.area*r.cdi,ld:drag?lift/drag:Infinity};}
// ---------- estrutural (mm, N, MPa)
const secRect=(b,h)=>({area:b*h,inertia:b*h**3/12,c:h/2});
const secCircle=d=>({area:PI*d*d/4,inertia:PI*d**4/64,c:d/2});
function secTubeRound(d,t){const di=d-2*t;if(di<=0)throw new Error('Espessura maior que o raio.');return{area:PI*(d*d-di*di)/4,inertia:PI*(d**4-di**4)/64,c:d/2};}
function secTubeRect(b,h,t){const bi=b-2*t,hi=h-2*t;if(bi<=0||hi<=0)throw new Error('Espessura grande demais.');return{area:b*h-bi*hi,inertia:(b*h**3-bi*hi**3)/12,c:h/2};}
function secI(b,h,tf,tw){const hw=h-2*tf;if(hw<=0||tw>=b)throw new Error('Dimensões inválidas do perfil I.');return{area:2*b*tf+hw*tw,inertia:(b*h**3-(b-tw)*hw**3)/12,c:h/2};}
function beam(cs,P,L,E,sec,sy){if(L<=0||E<=0||sec.inertia<=0)throw new Error('Comprimento, E e inércia devem ser positivos.');
 const EI=E*sec.inertia;let d,M;
 if(cs==='cant_end'){d=P*L**3/(3*EI);M=P*L;}else if(cs==='cant_udl'){d=P*L**4/(8*EI);M=P*L*L/2;}
 else if(cs==='ss_mid'){d=P*L**3/(48*EI);M=P*L/4;}else if(cs==='ss_udl'){d=5*P*L**4/(384*EI);M=P*L*L/8;}
 else if(cs==='fp_mid'){d=0.009317*P*L**3/EI;M=3*P*L/16;}else throw new Error('caso desconhecido');
 const sigma=M*sec.c/sec.inertia,o={deflection:Math.abs(d),moment:Math.abs(M),sigma:Math.abs(sigma),stiffness:d?Math.abs(P/d):Infinity};
 if(sy)o.safety_factor=sigma?sy/Math.abs(sigma):Infinity;return o;}
function column(E,sec,L,K,sy){const r=Math.sqrt(sec.inertia/sec.area),lam=K*L/r,lamC=Math.sqrt(2*PI*PI*E/sy),pe=PI*PI*E*sec.inertia/sq(K*L);
 let pcr,regime;if(lam>=lamC){pcr=pe;regime='Euler (coluna esbelta)';}else{pcr=sec.area*sy*(1-sy*lam*lam/(4*PI*PI*E));regime='Johnson (coluna intermediária)';}
 return{slenderness:lam,slenderness_crit:lamC,p_euler:pe,p_crit:pcr,regime,r};}
const BOLT_AT={3:[0.5,5.03],4:[0.7,8.78],5:[0.8,14.2],6:[1.0,20.1],8:[1.25,36.6],10:[1.5,58.0],12:[1.75,84.3],14:[2.0,115.0],16:[2.0,157.0],20:[2.5,245.0],24:[3.0,353.0]};
function boltJoint(d,T,knut,proof,ext=0,ratio=4){const At=BOLT_AT[d][1],fi=T*1000/(knut*d),C=1/(1+ratio),fb=fi+C*ext,fc=fi-(1-C)*ext;
 return{At,preload:fi,preload_stress:fi/At,proof_load:proof*At,preload_ratio:fi/(proof*At),C,bolt_load:fb,bolt_stress:fb/At,clamp_load:fc,separation_load:C<1?fi/(1-C):Infinity,n_proof:fb?proof*At/fb:Infinity};}
function shaftTorsion(T,d,L,Gm,di=0){const J=PI*(d**4-di**4)/32,tau=T*(d/2)/J,th=T*L/(Gm*J);return{tau,theta_rad:th,theta_deg:th*180/PI,stiffness:th?T/th:Infinity,J};}
function thinVessel(p,d,t){const r=d/2;return{hoop:p*r/t,axial:p*r/(2*t),thin_ok:t<d/20};}
const springMassFn=(k,m)=>Math.sqrt(k*1000/m)/(2*PI);
function cantileverFn(E,sec,L,rho,mode=1){const bl={1:1.8751,2:4.6941,3:7.8548}[mode],EI=E*1e6*sec.inertia*1e-12,ml=rho*sec.area*1e-6,l=L*1e-3;return bl*bl/(2*PI)*Math.sqrt(EI/(ml*l**4));}
// ---------- treliça (rigidez direta)
function parseTruss(text){const t={nodes:{},bars:{},loads:{}};
 text.split('\n').forEach((raw,i)=>{const line=raw.split('#')[0].trim();if(!line)return;const p=line.split(/\s+/),k=p[0].toUpperCase(),ln=i+1;
  try{if(k==='NODE'){const fx=(p.slice(5).find(q=>q.toLowerCase().startsWith('fix='))||'fix=').slice(4).toLowerCase();
    const xyz=[p[2],p[3],p[4]].map(Number);if(p.length<5||xyz.some(Number.isNaN))throw 0;t.nodes[p[1]]={xyz,fixed:['x','y','z'].map(c=>fx.includes(c))};}
   else if(k==='BAR'){const I=(p.slice(6).find(q=>q.toUpperCase().startsWith('I='))||'I=0').slice(2);const A=+p[4],E=+p[5];
    if(!t.nodes[p[2]]||!t.nodes[p[3]])throw new Error('nó inexistente ('+p[2]+', '+p[3]+')');if(p[2]===p[3])throw new Error('nós iguais');
    if(!(A>0)||!(E>0))throw new Error('A e E devem ser positivos');t.bars[p[1]]={n1:p[2],n2:p[3],area:A,E,inertia:+I};}
   else if(k==='LOAD'){if(!t.nodes[p[1]])throw new Error('nó inexistente: '+p[1]);const v=t.loads[p[1]]||[0,0,0];t.loads[p[1]]=[v[0]+ +p[2],v[1]+ +p[3],v[2]+ +p[4]];}
   else throw new Error("instrução desconhecida '"+p[0]+"'");}
  catch(e){throw new Error('Linha '+ln+': '+(e&&e.message?e.message:"formato inválido → '"+line+"'"));}});return t;}
function solveTruss(t){const ids=Object.keys(t.nodes),idx={};ids.forEach((n,i)=>idx[n]=i);const n=3*ids.length,bars=Object.entries(t.bars);if(!bars.length)throw new Error('Sem barras.');
 const K=Array.from({length:n},()=>new Array(n).fill(0)),geom={};
 for(const[id,b]of bars){const p1=t.nodes[b.n1].xyz,p2=t.nodes[b.n2].xyz,d=[0,1,2].map(i=>p2[i]-p1[i]),L=hyp(...d);if(L<1e-9)throw new Error('Barra '+id+': comprimento nulo.');
  const c=d.map(v=>v/L),s=[0,1,2].map(i=>3*idx[b.n1]+i).concat([0,1,2].map(i=>3*idx[b.n2]+i));
  for(let a=0;a<3;a++)for(let q=0;q<3;q++){const k=b.E*b.area/L*c[a]*c[q];K[s[a]][s[q]]+=k;K[s[3+a]][s[3+q]]+=k;K[s[a]][s[3+q]]-=k;K[s[3+a]][s[q]]-=k;}
  geom[id]=[L,c,s];}
 const F=new Array(n).fill(0);for(const[nid,v]of Object.entries(t.loads))for(let i=0;i<3;i++)F[3*idx[nid]+i]+=v[i];
 const fixed=ids.flatMap(nid=>t.nodes[nid].fixed),free=[];fixed.forEach((f,i)=>{if(!f)free.push(i);});
 if(!free.length)throw new Error('Todos os graus de liberdade estão restritos.');
 const x=solveLin(free.map(i=>free.map(j=>K[i][j])),free.map(i=>F[i]));
 if(!x)throw new Error('Estrutura hipostática (mecanismo) ou com graus de liberdade soltos: faltam barras/apoios. Em treliça plana restrinja o eixo fora do plano nos nós.');
 const u=new Array(n).fill(0);free.forEach((i,k)=>u[i]=x[k]);
 const R=K.map((row,i)=>row.reduce((a,v,j)=>a+v*u[j],0)-F[i]);free.forEach(i=>R[i]=0);
 const force={},stress={},length={},buck={};
 for(const[id,b]of bars){const[L,c,s]=geom[id];let dl=0;for(let i=0;i<3;i++)dl+=c[i]*(u[s[3+i]]-u[s[i]]);const N=b.E*b.area/L*dl;force[id]=N;stress[id]=N/b.area;length[id]=L;
  if(N<-1e-6&&b.inertia>0){const pcr=PI*PI*b.E*b.inertia/(L*L);buck[id]=[pcr,pcr/-N];}}
 const scale=Math.max(F.reduce((a,v)=>a+Math.abs(v),0),1);let eq=0;for(let d=0;d<3;d++){let s=0;for(let i=d;i<n;i+=3)s+=F[i]+R[i];eq=Math.max(eq,Math.abs(s));}
 const disp={},react={};ids.forEach(nid=>{disp[nid]=[0,1,2].map(i=>u[3*idx[nid]+i]);if(t.nodes[nid].fixed.some(Boolean))react[nid]=[0,1,2].map(i=>R[3*idx[nid]+i]);});
 return{displacement:disp,reactions:react,force,stress,length,equilibrium_error:eq/scale,buckling:buck};}
function warrenExample(panels=6,panel=2000,height=2000,area=8000,E=200000,inertia=6e6,load=50000){
 const out=['# Treliça Warren plana (plano x-z; y restrito). mm, N, MPa. Valores de A, E, I e cargas são EXEMPLOS: troque pelos seus.'];
 for(let i=0;i<=panels;i++)out.push(`NODE B${i} ${i*panel} 0 0 fix=y${i===0?'xz':(i===panels?'z':'')}`);
 for(let i=0;i<=panels;i++)out.push(`NODE T${i} ${i*panel} 0 ${height} fix=y`);
 let n=0;const bar=(a,b)=>{n++;out.push(`BAR m${n} ${a} ${b} ${area} ${E} I=${inertia}`);};
 for(let i=0;i<panels;i++){bar(`B${i}`,`B${i+1}`);bar(`T${i}`,`T${i+1}`);if(i%2===0)bar(`B${i}`,`T${i+1}`);else bar(`T${i}`,`B${i+1}`);}
 for(let i=0;i<=panels;i++)bar(`B${i}`,`T${i}`);for(let i=1;i<panels;i++)out.push(`LOAD B${i} 0 0 ${-load}`);return out.join('\n');}
// ---------- fadiga (Shigley)
const SURF={'Retificado':[1.58,-0.085],'Usinado ou laminado a frio':[4.51,-0.265],'Laminado a quente':[57.7,-0.718],'Forjado (bruto)':[272,-0.995]};
const REL={50:1,90:0.897,95:0.868,99:0.814,99.9:0.753,99.99:0.702,99.999:0.659,99.9999:0.62};
const KC={'Flexão':1,'Axial':0.85,'Torção':0.59,'Combinado':1};
function sizeFactor(d,axial){if(axial||d<=0)return 1;if(d<2.79)return 1;if(d<=51)return 1.24*Math.pow(d,-0.107);return 1.51*Math.pow(d,-0.157);}
function relFactor(p){const ks=Object.keys(REL).map(Number).sort((a,b)=>a-b);if(REL[p]!==undefined)return REL[p];
 if(p<ks[0]||p>ks[ks.length-1])throw new Error('Confiabilidade fora de 50 … 99,9999 %');
 for(let i=0;i<ks.length-1;i++){const lo=ks[i],hi=ks[i+1];if(p>=lo&&p<=hi)return REL[lo]+(REL[hi]-REL[lo])*(p-lo)/(hi-lo);}}
function fatFraction(su){return su<=490?0.9:(su>=1380?0.77:0.9+(0.77-0.9)*(su-490)/(1380-490));}
function endurance(mat,mar){if(mat.su<=0||mat.sy<=0)throw new Error('Su e Sy devem ser positivos.');if(mat.sy>mat.su)throw new Error('Sy não pode ser maior que Su.');
 if(mat.nk<=1e3)throw new Error('Nk deve ser maior que 10³.');let sep,est=false;
 if(mat.se_prime>0)sep=mat.se_prime;else if(mat.estimate_se){sep=mat.su<=1400?0.5*mat.su:700;est=true;}else throw new Error("Informe o limite de fadiga Se' ou marque a estimativa 0,5·Su (só aço).");
 const [a,b]=SURF[mar.surface],ka=mar.override_ka||a*Math.pow(mat.su,b),kb=sizeFactor(mar.d_eq,mar.load_type==='Axial'),kc=KC[mar.load_type],kd=mar.temp_factor,ke=relFactor(mar.reliability_pct),kf=mar.misc_factor;
 const w=[];if(est)w.push("Se' ESTIMADO (0,5·Su, regra empírica para aço) — prefira dado de ensaio.");if(mar.d_eq>254)w.push('Diâmetro acima de 254 mm: kb extrapolado.');
 return{se:ka*kb*kc*kd*ke*kf*sep,se_prime:sep,estimated:est,ka,kb,kc,kd,ke,kf,warnings:w};}
function secProps(s){if(s.kind==='Círculo cheio'){const d=s.d;return{A:PI*d*d/4,I:PI*d**4/64,c:d/2,J:PI*d**4/32,r:d/2};}
 if(s.kind==='Tubo'){const o=s.d,i=s.di;if(!(i>=0&&i<o))throw new Error('Tubo: 0 ≤ di < d externo.');return{A:PI*(o*o-i*i)/4,I:PI*(o**4-i**4)/64,c:o/2,J:PI*(o**4-i**4)/32,r:o/2};}
 return{A:s.b*s.h,I:s.b*s.h**3/12,c:s.h/2,J:0,r:0};}
const kfOf=(kt,q,ov)=>{if(ov!=null&&ov!=='')return +ov;if(q<0||q>1)throw new Error('q deve estar entre 0 e 1.');if(kt<1)throw new Error('Kt deve ser ≥ 1.');return 1+q*(kt-1);};
function nominal(sec,load,kf,combined){const p=secProps(sec),ma=r=>[(r[1]+r[0])/2,Math.abs(r[1]-r[0])/2],parts={};
 const need=(v,n)=>{if(!v)throw new Error("Propriedade de seção '"+n+"' é zero: defina a geometria da seção para esse esforço.");return v;};
 [['axial',load.axial,x=>x/need(p.A,'A')],['bending',load.bending,x=>x*p.c/need(p.I,'I')],['torsion',load.torsion,x=>x*p.r/need(p.J,'J')]].forEach(([k,r,f])=>{const[m,a]=ma(r);parts[k]=(m===0&&a===0)?[0,0]:[f(m),f(a)];});
 const div=combined?0.85:1,sa0=kf.bending*parts.bending[1]+kf.axial*parts.axial[1]/div,sa1=kf.torsion*parts.torsion[1],sm0=kf.bending*parts.bending[0]+kf.axial*parts.axial[0],sm1=kf.torsion*parts.torsion[0];
 const sa=Math.sqrt(sa0*sa0+3*sa1*sa1),sm=Math.sqrt(sm0*sm0+3*sm1*sm1);return{sigma_a:sa,sigma_m:sm,sigma_max:sa+sm,nominal:parts,props:p};}
function safetyFactors(sa,sm,se,su,sy){if(sa<0||sm<0)throw new Error('σa e σm equivalentes devem ser ≥ 0.');if(sa===0&&sm===0)return{Goodman:Infinity,Soderberg:Infinity,'ASME-elíptico':Infinity,Gerber:Infinity,'Escoamento (Langer)':Infinity};
 const o={Goodman:1/(sa/se+sm/su),Soderberg:1/(sa/se+sm/sy),'ASME-elíptico':1/Math.sqrt(sq(sa/se)+sq(sm/sy))};
 o.Gerber=sm===0?se/sa:(sa===0?su/sm:0.5*sq(su/sm)*(sa/se)*(-1+Math.sqrt(1+sq(2*sm*se/(su*sa)))));o['Escoamento (Langer)']=sy/(sa+sm);return o;}
function eqReversed(sa,sm,su,rule='Goodman'){if(rule==='Goodman')return sm>=su?Infinity:sa/(1-sm/su);if(rule==='Gerber')return sm>=su?Infinity:sa/(1-sq(sm/su));if(rule==='SWT')return Math.sqrt((sa+sm)*sa);throw new Error('Regra desconhecida');}
function buildSN(mat,se){const f=mat.f||fatFraction(mat.su),sf=f*mat.su;if(se>=sf)throw new Error('Se corrigido ≥ f·Su: a curva S-N degenera (confira Se\', fatores de Marin e f).');
 const b=-Math.log10(sf/se)/(Math.log10(mat.nk)-3),a=sf/Math.pow(1e3,b);
 return{a,b,se,sf1e3:sf,nk:mat.nk,has_knee:mat.has_knee,stress_at(n){return a*Math.pow(n,b);},life(s){if(s<=0)return Infinity;if(!isFinite(s))return 0;if(this.has_knee&&s<=se)return Infinity;return Math.pow(s/a,1/b);}};}
function fatigueAnalyze(mat,mar,sec,load,conc,rule='Goodman'){const se=endurance(mat,mar),kf={axial:kfOf(conc.kt_axial,conc.q_axial,conc.kf_axial),bending:kfOf(conc.kt_bending,conc.q_bending,conc.kf_bending),torsion:kfOf(conc.kt_torsion,conc.q_torsion,conc.kf_torsion)};
 const st=nominal(sec,load,kf,mar.load_type==='Combinado'),fac=safetyFactors(st.sigma_a,st.sigma_m,se.se,mat.su,mat.sy),curve=buildSN(mat,se.se),sar=eqReversed(st.sigma_a,st.sigma_m,mat.su,rule),cyc=curve.life(sar);
 const w=se.warnings.slice();w.push('Kf também aplicado à tensão média (conservador).');
 const low=isFinite(sar)&&sar>curve.sf1e3;if(low)w.push('σ equivalente acima de f·Su: fadiga de baixo ciclo (< 10³) — fora da validade do método de tensões nominais.');
 if(st.sigma_max>mat.sy)w.push('σmax acima de Sy: escoamento local no 1º ciclo — o método elástico não vale (use deformação-vida).');
 if(!mat.has_knee)w.push('Material sem limite de fadiga: sempre há vida finita (a curva é extrapolada além de Nk).');
 return{se,stress:st,factors:fac,sigma_ar:sar,curve,cycles:cyc,infinite:!isFinite(cyc),low_cycle:low,warnings:w};}
function miner(blocks,mat,curve,rule='Goodman'){let damage=0;const rows=blocks.map(b=>{const sar=eqReversed(b.sigma_a,b.sigma_m,mat.su,rule),n=curve.life(sar),d=!isFinite(n)?0:(n===0?Infinity:b.cycles/n);damage+=d;return{label:b.label,N:n,damage:d,sigma_ar:sar};});
 const reps=damage===0?Infinity:1/damage,tot=blocks.reduce((a,b)=>a+b.cycles,0);return{rows,damage,repetitions:reps,cycles_to_failure:reps*tot};}
function springAnalysis(s){for(const k of['wire_d','coil_d','active_coils','total_coils','g_mpa','su','sse','density_g_cm3'])if(!(s[k]>0))throw new Error("Mola: '"+k+"' deve ser positivo.");
 const c=s.coil_d/s.wire_d,k=s.g_mpa*s.wire_d**4/(8*s.coil_d**3*s.active_coils),fmin=s.preload_force,fmax=fmin+k*s.lift,ks=1+0.5/c,kb=(4*c+2)/(4*c-3),cst=8*s.coil_d/(PI*s.wire_d**3);
 const fa=(fmax-fmin)/2,fm=(fmax+fmin)/2,ta=kb*cst*fa,tm=ks*cst*fm,ssu=s.ssu||0.67*s.su,nf=(ta||tm)?1/(ta/s.sse+tm/ssu):Infinity;
 const solid=s.total_coils*s.wire_d,minLen=s.installed_len-s.lift,clash=minLen-solid,mass=s.density_g_cm3*1e-3*(PI*s.wire_d**2/4)*(PI*s.coil_d*s.total_coils)*1e-3;
 const rho=s.density_g_cm3*1e-6,fn=(s.wire_d/(2*PI*s.coil_d**2*s.active_coils))*Math.sqrt(s.g_mpa*1e6/(2*rho*1e9))*1e3;
 const w=[];if(c<4||c>12)w.push('Índice de mola C = '+c.toFixed(1)+' fora de 4 … 12: fórmulas menos confiáveis.');if(clash<=0)w.push('Mola chega à altura sólida!');
 return{C:c,k,f_min:fmin,f_max:fmax,tau_a:ta,tau_m:tm,n_f:nf,ssu,solid_len:solid,min_len:minLen,clearance_to_solid:clash,mass_kg:mass,fn_hz:fn,max_rpm_13x:fn/13*2*60,warnings:w};}

// ---------- pórtico espacial de vigas (Euler–Bernoulli), portado de modules/frame_fem.py
function parseFrame(text){const f={nodes:{},beams:{},loads:{},dloads:{},masses:{}};
 text.split('\n').forEach((raw,i)=>{const line=raw.split('#')[0].trim();if(!line)return;const p=line.split(/\s+/),k=p[0].toUpperCase(),ln=i+1;
  try{if(k==='NODE'){const fx=(p.slice(5).find(q=>q.toLowerCase().startsWith('fix='))||'fix=').slice(4);const xyz=[p[2],p[3],p[4]].map(Number);if(p.length<5||xyz.some(Number.isNaN))throw 0;
    f.nodes[p[1]]={xyz,fixed:'xyzXYZ'.split('').map(c=>fx.includes(c))};}
   else if(k==='BEAM'){if(!f.nodes[p[2]]||!f.nodes[p[3]])throw new Error('nó inexistente ('+p[2]+', '+p[3]+')');if(p[2]===p[3])throw new Error('nós iguais');
    const v=p.slice(4,10).map(Number);if(v.length<6||v.some(x=>!(x>0)))throw new Error('A, Iy, Iz, J, E e G devem ser positivos');
    const rf=p.slice(10).find(q=>q.toLowerCase().startsWith('ref=')),cf=p.slice(10).find(q=>q.toLowerCase().startsWith('c=')),rh=p.slice(10).find(q=>q.toLowerCase().startsWith('rho='));
    f.beams[p[1]]={n1:p[2],n2:p[3],A:v[0],Iy:v[1],Iz:v[2],J:v[3],E:v[4],G:v[5],ref:rf?rf.slice(4).split(',').map(Number):null,c:cf?+cf.slice(2):null,rho:rh?+rh.slice(4):null};}
   else if(k==='MASS'){if(!f.nodes[p[1]])throw new Error('nó inexistente: '+p[1]);if(!(+p[2]>0))throw new Error('massa deve ser positiva');f.masses[p[1]]=(f.masses[p[1]]||0)+ +p[2];}
   else if(k==='LOAD'){if(!f.nodes[p[1]])throw new Error('nó inexistente: '+p[1]);const v=[0,0,0,0,0,0];p.slice(2,8).forEach((x,j)=>v[j]=+x);const o=f.loads[p[1]]||[0,0,0,0,0,0];f.loads[p[1]]=o.map((a,j)=>a+v[j]);}
   else if(k==='DLOAD'){if(!f.beams[p[1]])throw new Error('viga inexistente: '+p[1]);f.dloads[p[1]]=[+p[2],+p[3],+p[4]];}
   else throw new Error("instrução desconhecida '"+p[0]+"'");}
  catch(e){throw new Error('Linha '+ln+': '+(e&&e.message?e.message:"formato inválido → '"+line+"'"));}});return f;}
function frameAxes(p1,p2,ref){const d=[0,1,2].map(i=>p2[i]-p1[i]),L=Math.hypot(...d);if(L<1e-9)throw new Error('viga com comprimento nulo');const ex=d.map(v=>v/L);
 const v=ref||(Math.abs(ex[2])<0.999?[0,0,1]:[1,0,0]),dt=v[0]*ex[0]+v[1]*ex[1]+v[2]*ex[2];let ez=[0,1,2].map(i=>v[i]-dt*ex[i]);const n=Math.hypot(...ez);
 if(n<1e-9)throw new Error('vetor de referência paralelo ao eixo da viga');ez=ez.map(x=>x/n);const ey=[ez[1]*ex[2]-ez[2]*ex[1],ez[2]*ex[0]-ez[0]*ex[2],ez[0]*ex[1]-ez[1]*ex[0]];return{R:[ex,ey,ez],L};}
function frameKloc(b,L){const{E,G,A,Iy,Iz,J}=b,k=Array.from({length:12},()=>new Array(12).fill(0)),a=E*A/L,t=G*J/L;
 k[0][0]=k[6][6]=a;k[0][6]=k[6][0]=-a;k[3][3]=k[9][9]=t;k[3][9]=k[9][3]=-t;
 const c1=12*E*Iz/L**3,c2=6*E*Iz/L**2,c3=4*E*Iz/L,c4=2*E*Iz/L;
 [[1,1,c1],[7,7,c1],[1,7,-c1],[7,1,-c1],[1,5,c2],[5,1,c2],[1,11,c2],[11,1,c2],[7,5,-c2],[5,7,-c2],[7,11,-c2],[11,7,-c2],[5,5,c3],[11,11,c3],[5,11,c4],[11,5,c4]].forEach(([i,j,v])=>k[i][j]+=v);
 const d1=12*E*Iy/L**3,d2=6*E*Iy/L**2,d3=4*E*Iy/L,d4=2*E*Iy/L;
 [[2,2,d1],[8,8,d1],[2,8,-d1],[8,2,-d1],[2,4,-d2],[4,2,-d2],[2,10,-d2],[10,2,-d2],[8,4,d2],[4,8,d2],[8,10,d2],[10,8,d2],[4,4,d3],[10,10,d3],[4,10,d4],[10,4,d4]].forEach(([i,j,v])=>k[i][j]+=v);return k;}
function frameT(R){const T=Array.from({length:12},()=>new Array(12).fill(0));for(let b=0;b<4;b++)for(let i=0;i<3;i++)for(let j=0;j<3;j++)T[3*b+i][3*b+j]=R[i][j];return T;}
const mv=(M,v)=>M.map(r=>r.reduce((a,x,j)=>a+x*v[j],0)),tr=M=>M[0].map((_,j)=>M.map(r=>r[j]));
function fixedEndLocal(w,L){const[wx,wy,wz]=w,f=new Array(12).fill(0);f[0]=f[6]=wx*L/2;f[1]=f[7]=wy*L/2;f[5]=wy*L*L/12;f[11]=-wy*L*L/12;f[2]=f[8]=wz*L/2;f[4]=-wz*L*L/12;f[10]=wz*L*L/12;return f;}
function solveFrame(fr){const ids=Object.keys(fr.nodes),idx={};ids.forEach((n,i)=>idx[n]=i);const n=6*ids.length,bs=Object.entries(fr.beams);if(!bs.length)throw new Error('Sem vigas.');
 const K=Array.from({length:n},()=>new Array(n).fill(0)),F=new Array(n).fill(0),info={};
 for(const[id,b]of bs){const{R,L}=frameAxes(fr.nodes[b.n1].xyz,fr.nodes[b.n2].xyz,b.ref),T=frameT(R),kl=frameKloc(b,L),Tt=tr(T);
  const kg=Tt.map(r=>0).map((_,i)=>0);const KT=kl.map(r=>T[0].map((_,j)=>r.reduce((a,x,m)=>a+x*T[m][j],0)));const kgl=Tt.map(r=>T[0].map((_,j)=>r.reduce((a,x,m)=>a+x*KT[m][j],0)));
  const s=[];for(let i=0;i<6;i++)s.push(6*idx[b.n1]+i);for(let i=0;i<6;i++)s.push(6*idx[b.n2]+i);
  for(let i=0;i<12;i++)for(let j=0;j<12;j++)K[s[i]][s[j]]+=kgl[i][j];
  let fe=new Array(12).fill(0);if(fr.dloads[id]){const wl=mv(R,fr.dloads[id]);fe=fixedEndLocal(wl,L);const fg=mv(Tt,fe);for(let i=0;i<12;i++)F[s[i]]+=fg[i];}
  info[id]={R,L,T,s,fe,kl};}
 const P=F.slice();for(const[nid,v]of Object.entries(fr.loads))for(let i=0;i<6;i++)P[6*idx[nid]+i]+=v[i];
 const fixed=ids.flatMap(nid=>fr.nodes[nid].fixed),free=[];fixed.forEach((f,i)=>{if(!f)free.push(i);});if(!free.length)throw new Error('Todos os graus de liberdade estão restritos.');
 const x=solveLin(free.map(i=>free.map(j=>K[i][j])),free.map(i=>P[i]));
 if(!x)throw new Error('Estrutura hipostática (mecanismo) ou com graus de liberdade soltos: faltam apoios/vigas (em pórtico plano restrinja v, θx e θz).');
 const u=new Array(n).fill(0);free.forEach((i,k)=>u[i]=x[k]);const Rr=K.map((row,i)=>row.reduce((a,v,j)=>a+v*u[j],0)-P[i]);free.forEach(i=>Rr[i]=0);
 const ends={};for(const[id]of bs){const q=info[id],ul=mv(q.T,q.s.map(i=>u[i])),fl=mv(q.kl,ul);ends[id]=fl.map((v,i)=>v-q.fe[i]);}
 const scale=Math.max(P.reduce((a,v)=>a+Math.abs(v),0),1);let eq=0;for(let d=0;d<3;d++){let s=0;for(let i=d;i<n;i+=6)s+=P[i]+Rr[i];eq=Math.max(eq,Math.abs(s));}
 const disp={},react={};ids.forEach(nid=>{disp[nid]=[0,1,2,3,4,5].map(i=>u[6*idx[nid]+i]);if(fr.nodes[nid].fixed.some(Boolean))react[nid]=[0,1,2,3,4,5].map(i=>Rr[6*idx[nid]+i]);});
 return{displacement:disp,reactions:react,end_forces:ends,equilibrium_error:eq/scale,info};}
function frameMoment(fr,res,id,s){const q=res.info[id],f=res.end_forces[id],w=fr.dloads[id]?mv(q.R,fr.dloads[id]):[0,0,0],x=s*q.L;return[f[4]+x*f[2]+w[2]*x*x/2,f[5]-x*f[1]-w[1]*x*x/2];}
function frameShear(fr,res,id,s){const q=res.info[id],f=res.end_forces[id],w=fr.dloads[id]?mv(q.R,fr.dloads[id]):[0,0,0],x=s*q.L;return[f[1]+w[1]*x,f[2]+w[2]*x];}
function frameMloc(b,L){if(!(b.rho>0))throw new Error('Viga '+b.id+': informe rho=kg/m³ para a análise modal.');const rho=b.rho*1e-12,m=Array.from({length:12},()=>new Array(12).fill(0)),c=rho*b.A*L/6;
 m[0][0]=m[6][6]=2*c;m[0][6]=m[6][0]=c;const ct=rho*(b.Iy+b.Iz)*L/6;m[3][3]=m[9][9]=2*ct;m[3][9]=m[9][3]=ct;const k=rho*b.A*L/420;
 const base=[[156,22*L,54,-13*L],[22*L,4*L*L,13*L,-3*L*L],[54,13*L,156,-22*L],[-13*L,-3*L*L,-22*L,4*L*L]];
 [[[1,5,7,11],1],[[2,4,8,10],-1]].forEach(([d,sg])=>{const S=[1,sg,1,sg];d.forEach((ia,a)=>d.forEach((iq,q)=>{m[ia][iq]+=S[a]*S[q]*base[a][q]*k;}));});return m;}
function jacobiEig(A0){const n=A0.length,A=A0.map(r=>r.slice()),V=Array.from({length:n},(_,i)=>{const r=new Array(n).fill(0);r[i]=1;return r;});
 for(let sw=0;sw<100;sw++){let off=0;for(let i=0;i<n;i++)for(let j=i+1;j<n;j++)off+=A[i][j]*A[i][j];if(off<1e-22*n)break;
  for(let p=0;p<n-1;p++)for(let q=p+1;q<n;q++){if(Math.abs(A[p][q])<1e-300)continue;const th=(A[q][q]-A[p][p])/(2*A[p][q]),t=Math.sign(th||1)/(Math.abs(th)+Math.sqrt(th*th+1)),c=1/Math.sqrt(t*t+1),s=t*c;
   for(let k=0;k<n;k++){const akp=A[k][p],akq=A[k][q];A[k][p]=c*akp-s*akq;A[k][q]=s*akp+c*akq;}
   for(let k=0;k<n;k++){const apk=A[p][k],aqk=A[q][k];A[p][k]=c*apk-s*aqk;A[q][k]=s*apk+c*aqk;}
   for(let k=0;k<n;k++){const vkp=V[k][p],vkq=V[k][q];V[k][p]=c*vkp-s*vkq;V[k][q]=s*vkp+c*vkq;}}}
 return{w:A.map((r,i)=>r[i]),V};}
function modalFrame(fr,nModes=6){const ids=Object.keys(fr.nodes),idx={};ids.forEach((n,i)=>idx[n]=i);const n=6*ids.length,K=Array.from({length:n},()=>new Array(n).fill(0)),M=Array.from({length:n},()=>new Array(n).fill(0));let total=0;
 for(const[id,b]of Object.entries(fr.beams)){const{R,L}=frameAxes(fr.nodes[b.n1].xyz,fr.nodes[b.n2].xyz,b.ref),T=frameT(R),Tt=tr(T),kl=frameKloc(b,L),ml=frameMloc(b,L);
  const g=m=>{const X=m.map(r=>T[0].map((_,j)=>r.reduce((a,x,q)=>a+x*T[q][j],0)));return Tt.map(r=>T[0].map((_,j)=>r.reduce((a,x,q)=>a+x*X[q][j],0)));};
  const kg=g(kl),mg=g(ml),s=[];for(let i=0;i<6;i++)s.push(6*idx[b.n1]+i);for(let i=0;i<6;i++)s.push(6*idx[b.n2]+i);
  for(let i=0;i<12;i++)for(let j=0;j<12;j++){K[s[i]][s[j]]+=kg[i][j];M[s[i]][s[j]]+=mg[i][j];}total+=b.rho*1e-9*b.A*L;}
 for(const[nid,m]of Object.entries(fr.masses))for(let d=0;d<3;d++)M[6*idx[nid]+d][6*idx[nid]+d]+=m*1e-3,total+=d===0?m:0;
 const fixed=ids.flatMap(nid=>fr.nodes[nid].fixed),free=[];fixed.forEach((f,i)=>{if(!f)free.push(i);});if(!free.length)throw new Error('Todos os graus de liberdade estão restritos.');
 const Kf=free.map(i=>free.map(j=>K[i][j])),Mf=free.map(i=>free.map(j=>M[i][j])),nf=free.length;
 if(!solveLin(Kf,new Array(nf).fill(1)))throw new Error('Estrutura hipostática (mecanismo): a análise modal exige apoios suficientes.');
 const Lc=Array.from({length:nf},()=>new Array(nf).fill(0));
 for(let i=0;i<nf;i++)for(let j=0;j<=i;j++){let s=Mf[i][j];for(let k=0;k<j;k++)s-=Lc[i][k]*Lc[j][k];if(i===j){if(s<=0)throw new Error('Matriz de massa não positiva: confira rho/MASS.');Lc[i][i]=Math.sqrt(s);}else Lc[i][j]=s/Lc[j][j];}
 const fwd=(B)=>{const Y=B.map(r=>r.slice());for(let c=0;c<Y[0].length;c++)for(let i=0;i<nf;i++){let s=Y[i][c];for(let k=0;k<i;k++)s-=Lc[i][k]*Y[k][c];Y[i][c]=s/Lc[i][i];}return Y;};
 const Y=fwd(Kf),Yt=Y[0].map((_,j)=>Y.map(r=>r[j])),Z=fwd(Yt),A=Z[0].map((_,j)=>Z.map(r=>r[j]));for(let i=0;i<nf;i++)for(let j=i+1;j<nf;j++){const a=0.5*(A[i][j]+A[j][i]);A[i][j]=A[j][i]=a;}
 const{w,V}=jacobiEig(A),ord=w.map((x,i)=>i).sort((a,b)=>w[a]-w[b]).slice(0,Math.min(nModes,nf)),freq=[],shapes=[];
 for(const m of ord){freq.push(Math.sqrt(Math.max(w[m],0))/(2*Math.PI));const v=V.map(r=>r[m]),x=new Array(nf);for(let i=nf-1;i>=0;i--){let s=v[i];for(let k=i+1;k<nf;k++)s-=Lc[k][i]*x[k];x[i]=s/Lc[i][i];}
  const full=new Array(n).fill(0);free.forEach((g,i)=>full[g]=x[i]);const mx=Math.max(...full.map(Math.abs))||1;const sh={};ids.forEach(nid=>sh[nid]=[0,1,2,3,4,5].map(i=>full[6*idx[nid]+i]/mx));shapes.push(sh);}
 return{freq_hz:freq,shapes,mass_total_kg:total};}
function genEig(Af,Bf){const nf=Af.length,Lc=Array.from({length:nf},()=>new Array(nf).fill(0));
 for(let i=0;i<nf;i++)for(let j=0;j<=i;j++){let s=Bf[i][j];for(let k=0;k<j;k++)s-=Lc[i][k]*Lc[j][k];if(i===j){if(s<=0)throw new Error('Matriz não positiva definida.');Lc[i][i]=Math.sqrt(s);}else Lc[i][j]=s/Lc[j][j];}
 const fwd=B=>{const Y=B.map(r=>r.slice());for(let c=0;c<Y[0].length;c++)for(let i=0;i<nf;i++){let s=Y[i][c];for(let k=0;k<i;k++)s-=Lc[i][k]*Y[k][c];Y[i][c]=s/Lc[i][i];}return Y;};
 const Y=fwd(Af),Z=fwd(Y[0].map((_,j)=>Y.map(r=>r[j]))),A=Z[0].map((_,j)=>Z.map(r=>r[j]));for(let i=0;i<nf;i++)for(let j=i+1;j<nf;j++){const a=0.5*(A[i][j]+A[j][i]);A[i][j]=A[j][i]=a;}
 const{w,V}=jacobiEig(A);return w.map((x,m)=>{const v=V.map(r=>r[m]),ph=new Array(nf);for(let i=nf-1;i>=0;i--){let s=v[i];for(let k=i+1;k<nf;k++)s-=Lc[k][i]*ph[k];ph[i]=s/Lc[i][i];}return{w:x,phi:ph};}).sort((a,b)=>a.w-b.w);}
function frameKg(b,L,N){const k=Array.from({length:12},()=>new Array(12).fill(0)),c=N/(30*L);
 const base=[[36,3*L,-36,3*L],[3*L,4*L*L,-3*L,-L*L],[-36,-3*L,36,-3*L],[3*L,-L*L,-3*L,4*L*L]];
 [[[1,5,7,11],1],[[2,4,8,10],-1]].forEach(([d,sg])=>{const S=[1,sg,1,sg];d.forEach((ia,a)=>d.forEach((iq,q)=>{k[ia][iq]+=S[a]*S[q]*base[a][q]*c;}));});
 const t=N*(b.Iy+b.Iz)/(b.A*L);k[3][3]=k[9][9]=t;k[3][9]=k[9][3]=-t;return k;}
function bucklingFrame(fr,nModes=3){const res=solveFrame(fr),ids=Object.keys(fr.nodes),idx={};ids.forEach((n,i)=>idx[n]=i);const n=6*ids.length,K=Array.from({length:n},()=>new Array(n).fill(0)),Kg=Array.from({length:n},()=>new Array(n).fill(0)),axial={};
 for(const[id,b]of Object.entries(fr.beams)){const q=res.info[id],T=q.T,Tt=tr(T),N=-res.end_forces[id][0];axial[id]=N;
  const g=m=>{const X=m.map(r=>T[0].map((_,j)=>r.reduce((a,x,qq)=>a+x*T[qq][j],0)));return Tt.map(r=>T[0].map((_,j)=>r.reduce((a,x,qq)=>a+x*X[qq][j],0)));};
  const kg=g(q.kl),gg=g(frameKg(b,q.L,N)),s=[];for(let i=0;i<6;i++)s.push(6*idx[b.n1]+i);for(let i=0;i<6;i++)s.push(6*idx[b.n2]+i);
  for(let i=0;i<12;i++)for(let j=0;j<12;j++){K[s[i]][s[j]]+=kg[i][j];Kg[s[i]][s[j]]+=gg[i][j];}}
 const fixed=ids.flatMap(nid=>fr.nodes[nid].fixed),free=[];fixed.forEach((f,i)=>{if(!f)free.push(i);});
 const Kf=free.map(i=>free.map(j=>K[i][j])),Gf=free.map(i=>free.map(j=>-Kg[i][j])),eg=genEig(Gf,Kf),tol=1e-12*Math.max(1,...eg.map(e=>Math.abs(e.w)));
 const pos=eg.filter(e=>e.w>tol).map(e=>({lam:1/e.w,phi:e.phi})).sort((a,b)=>a.lam-b.lam).slice(0,nModes),shapes=pos.map(e=>{const full=new Array(n).fill(0);free.forEach((g,i)=>full[g]=e.phi[i]);const mx=Math.max(...full.map(Math.abs))||1;const sh={};ids.forEach(nid=>sh[nid]=[0,1,2,3,4,5].map(i=>full[6*idx[nid]+i]/mx));return sh;});
 return{factors:pos.map(e=>e.lam),shapes,reference_axial:axial};}
function frameExample(span=6000,height=3000,w=20){const sec='5380 8.356e7 6.04e6 2.0e5 210000 80000';return['# Pórtico plano x-z (y e rotações X,Z restritos nos nós livres de apoio). mm, N, MPa, N·mm. Valores genéricos: troque pelos seus.',
 'NODE A 0 0 0 fix=xyzXYZ',`NODE B 0 0 ${height} fix=yXZ`,`NODE C ${span} 0 ${height} fix=yXZ`,`NODE D ${span} 0 0 fix=xyzXYZ`,`BEAM c1 A B ${sec} c=150 rho=7850`,`BEAM v B C ${sec} c=150 rho=7850`,`BEAM c2 C D ${sec} c=150 rho=7850`,`DLOAD v 0 0 ${-w}`,'LOAD B 10000 0 0'].join('\n');}
function unitsConvert(T,v,a,b){let da=null,db=null;for(const[d,us]of Object.entries(T)){if(us[a])da=da||d;if(us[b])db=db||d;}
 if(!da)throw new Error("Unidade desconhecida: '"+a+"'");if(!db)throw new Error("Unidade desconhecida: '"+b+"'");if(da!==db)throw new Error('Dimensões incompatíveis: '+a+' ('+da+') → '+b+' ('+db+')');
 const[fs,os]=T[da][a],[fd,od]=T[da][b];return((v*fs+os)-od)/fd;}
function vehDyn(v,tf,dt,v0,brakeAt,brakeF){const G=9.80665;v0=v0||0;let t=0,x=0,vel=v0;const out=[[0,0,vel,0]];
 const acc=(vl,tt)=>{const drag=0.5*v.rho*v.cd*v.area*vl*vl,roll=v.crr*v.m*G*Math.cos(v.inc||0),gr=v.m*G*Math.sin(v.inc||0);
  const ft=(brakeAt!=null&&tt>=brakeAt)?-brakeF:Math.min(v.F,v.P/Math.max(vl,0.1),v.mu*(v.fr==null?1:v.fr)*v.m*G);return(ft-drag-roll-gr)/v.m;};
 if(!(v.m>0&&v.area>0&&v.P>0&&v.F>0&&dt>0&&tf>0))throw new Error('Parâmetros devem ser positivos');
 while(t<tf-1e-12){const k1=acc(vel,t),k2=acc(vel+0.5*dt*k1,t+0.5*dt),k3=acc(vel+0.5*dt*k2,t+0.5*dt),k4=acc(vel+dt*k3,t+dt);
  const a=(k1+2*k2+2*k3+k4)/6;const vn=Math.max(vel+a*dt,0);x+=0.5*(vel+vn)*dt;vel=vn;t+=dt;out.push([t,x,vel,a]);}return out;}
const LAB={feaCant10,feaCant,vehDyn,bucklingFrame,unitsConvert,modalFrame,parseFrame,solveFrame,frameMoment,frameShear,frameExample,solveLin,isa,dynQ,force,reynolds,cfTurb,Vehicle,naca4AlphaL0,liftingLine,wingForces,secRect,secCircle,secTubeRound,secTubeRect,secI,beam,column,BOLT_AT,boltJoint,shaftTorsion,thinVessel,springMassFn,cantileverFn,parseTruss,solveTruss,warrenExample,SURF,REL,KC,endurance,fatigueAnalyze,safetyFactors,eqReversed,buildSN,miner,springAnalysis,secProps};
root.LAB=LAB;if(typeof module!=='undefined')module.exports=LAB;
})(typeof window!=='undefined'?window:globalThis);
