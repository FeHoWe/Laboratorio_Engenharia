"""Pneu combinado (Fx–Fy) e suspensão duplo-A (V3.5). Valores iniciais são ILUSTRATIVOS — o usuário informa os dados do seu carro."""
from __future__ import annotations
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget, QFormLayout, QDoubleSpinBox, QPushButton,
                               QTextEdit, QTableWidget, QTableWidgetItem, QLabel, QComboBox)
from modules import tire_combined as TC, suspension as SU, vehicle_combined as VC, vehicle_lateral as VL, tire_fit as TF, suspension3d as S3


def _spin(v, lo, hi, dec=3, step=0.1):
    s = QDoubleSpinBox(); s.setDecimals(dec); s.setRange(lo, hi); s.setSingleStep(step); s.setValue(v); return s


class VehicleGeoDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent); self.setWindowTitle("NEXUS VEHICLE — Pneu combinado e suspensão"); self.resize(720, 560)
        L = QVBoxLayout(self); tabs = QTabWidget(); L.addWidget(tabs)
        # --- pneu
        w = QWidget(); f = QFormLayout(w)
        self.fz = _spin(4000, 1, 1e6, 0, 100); self.ca = _spin(60000, 1, 1e7, 0, 1000); self.ck = _spin(80000, 1, 1e7, 0, 1000)
        self.mu = _spin(1.5, 0.05, 4, 2, 0.05); self.kap = _spin(0.08, -0.999, 5, 3, 0.01); self.alf = _spin(4.0, -45, 45, 2, 0.5)
        for t, x in (("Fz [N]", self.fz), ("C_α [N/rad]", self.ca), ("C_κ [N]", self.ck), ("μ", self.mu), ("κ (escorregamento longitudinal)", self.kap), ("α [graus]", self.alf)):
            f.addRow(t, x)
        b = QPushButton("Calcular força combinada"); b.clicked.connect(self.calc_tire); f.addRow(b)
        self.out_t = QTextEdit(); self.out_t.setReadOnly(True); f.addRow(self.out_t); tabs.addTab(w, "Pneu combinado")
        # --- suspensão
        w2 = QWidget(); v = QVBoxLayout(w2)
        v.addWidget(QLabel("Pontos (y, z) em metros — y para fora do carro, z para cima. Exemplo ILUSTRATIVO, não é de um carro real."))
        ex = SU.exemplo_ilustrativo(); self.tab = QTableWidget(6, 2); self.tab.setHorizontalHeaderLabels(["y [m]", "z [m]"])
        self.tab.setVerticalHeaderLabels(list("ABCDWP"))
        for i, n in enumerate("ABCDWP"):
            p = getattr(ex, n)
            for j in range(2): self.tab.setItem(i, j, QTableWidgetItem(f"{p[j]:.4f}"))
        v.addWidget(self.tab)
        h = QHBoxLayout(); self.h0 = _spin(-0.03, -0.2, 0, 3, 0.005); self.h1 = _spin(0.03, 0, 0.2, 3, 0.005)
        h.addWidget(QLabel("heave mín [m]")); h.addWidget(self.h0); h.addWidget(QLabel("máx [m]")); h.addWidget(self.h1)
        b2 = QPushButton("Resolver cinemática"); b2.clicked.connect(self.calc_susp); h.addWidget(b2); v.addLayout(h)
        self.out_s = QTextEdit(); self.out_s.setReadOnly(True); v.addWidget(self.out_s); tabs.addTab(w2, "Suspensão duplo-A")
        # --- suspensão 3D (V3.8)
        w6 = QWidget(); v6 = QVBoxLayout(w6)
        v6.addWidget(QLabel("Hardpoints (x à frente, y para fora, z acima) em metros. Exemplo ILUSTRATIVO — informe os pontos do SEU carro."))
        self.NOMES3 = ["LF", "LR", "B", "UF", "UR", "D", "T", "Tj", "W", "P"]
        ex3 = S3.exemplo_ilustrativo(); self.tab3 = QTableWidget(len(self.NOMES3), 3); self.tab3.setHorizontalHeaderLabels(["x [m]", "y [m]", "z [m]"])
        self.tab3.setVerticalHeaderLabels(["LF pivô inf. diant.", "LR pivô inf. tras.", "B rótula inf.", "UF pivô sup. diant.", "UR pivô sup. tras.", "D rótula sup.",
                                           "T barra dir. (interna)", "Tj barra dir. (manga)", "W centro da roda", "P contato"])
        for i, n in enumerate(self.NOMES3):
            for j in range(3): self.tab3.setItem(i, j, QTableWidgetItem(f"{getattr(ex3, n)[j]:.4f}"))
        v6.addWidget(self.tab3)
        h6 = QHBoxLayout(); self.s3h = _spin(0.03, 0.001, 0.2, 3, 0.005); self.s3r = _spin(0.015, 0.0, 0.1, 3, 0.005)
        self.s3fy = _spin(0.0, -1e5, 1e5, 0, 500); self.s3fx = _spin(0.0, -1e5, 1e5, 0, 500)
        self.s3k = [_spin(0.0, -5, 5, 3, 0.01) for _ in range(3)]
        for t, w in (("±heave [m]", self.s3h), ("curso cremalheira [m]", self.s3r), ("Fy [N]", self.s3fy), ("Fx [N]", self.s3fx),
                     ("toe/Fy [°/kN]", self.s3k[0]), ("toe/Fx [°/kN]", self.s3k[1]), ("camber/Fy [°/kN]", self.s3k[2])):
            h6.addWidget(QLabel(t)); h6.addWidget(w)
        v6.addLayout(h6)
        b6 = QPushButton("Resolver cinemática 3D (camber, toe, caster, KPI, trail, scrub, bump steer)"); b6.clicked.connect(self.calc_susp3d); v6.addWidget(b6)
        self.out_s3 = QTextEdit(); self.out_s3.setReadOnly(True); v6.addWidget(self.out_s3); tabs.addTab(w6, "Suspensão 3D")
        # --- g-g
        w3 = QWidget(); f3 = QFormLayout(w3); ex = VL.exemplo_ilustrativo()
        self.gg = {k: _spin(getattr(ex, k), 0, 1e6, 3, 0.1) for k in ("m", "a", "b", "h", "tf", "tr", "c_f", "c_r", "mu_f", "mu_r")}
        self.gg["vel"] = _spin(30.0, 1, 120, 1, 1)
        self.gg["sens_mu_f"] = _spin(0.0, 0, 0.8, 3, 0.05); self.gg["sens_mu_r"] = _spin(0.0, 0, 0.8, 3, 0.05)
        for k, t in (("m", "massa [kg]"), ("a", "CG→eixo diant. [m]"), ("b", "CG→eixo tras. [m]"), ("h", "altura do CG [m]"), ("tf", "bitola diant. [m]"), ("tr", "bitola tras. [m]"),
                     ("c_f", "C_α por pneu diant. [N/rad]"), ("c_r", "C_α por pneu tras. [N/rad]"), ("mu_f", "μ diant."), ("mu_r", "μ tras."), ("sens_mu_f", "sens. do μ à carga diant. (0 = μ constante)"), ("sens_mu_r", "sens. do μ à carga tras. (0 = μ constante)"), ("vel", "velocidade [m/s]")):
            f3.addRow(t, self.gg[k])
        b3 = QPushButton("Calcular diagrama g-g (ay máximo sob tração/frenagem)"); b3.clicked.connect(self.calc_gg); f3.addRow(b3)
        self.gg["pot"] = _spin(250000.0, 1, 5e6, 0, 10000); self.gg["cda"] = _spin(0.7, 0, 10, 3, 0.05)
        f3.addRow("potência [W] (volta)", self.gg["pot"]); f3.addRow("CdA [m²] (volta)", self.gg["cda"])
        b3b = QPushButton("Volta no circuito de EXEMPLO (sintético) com este veículo"); b3b.clicked.connect(self.calc_volta); f3.addRow(b3b)
        self.out_g = QTextEdit(); self.out_g.setReadOnly(True); f3.addRow(self.out_g); tabs.addTab(w3, "Aderência g-g")
        # --- CFD → Veículo
        w5 = QWidget(); f5 = QFormLayout(w5)
        f5.addRow(QLabel("Usa o Cd do ÚLTIMO resultado de CFD de um projeto no modelo longitudinal. Cd é adimensional: informe a ÁREA FRONTAL REAL do veículo."))
        self.pj = QComboBox()
        try:
            from interface.solvers_dialog import PROJECTS_DIR
            from modules.workspace import ProjectStore
            self._store = ProjectStore(PROJECTS_DIR); self.pj.addItems(self._store.list())
        except Exception:  # noqa: BLE001
            self._store = None
        f5.addRow("Projeto", self.pj)
        self.lg = {k: _spin(v, 0.0, 1e7, 3, 10) for k, v in dict(massa=1000, area=2.0, crr=0.012, fm=6000, pot=100000, mu=1.0).items()}
        for k, t in (("massa", "massa [kg]"), ("area", "área frontal REAL [m²]"), ("crr", "Crr"), ("fm", "força motriz [N]"), ("pot", "potência [W]"), ("mu", "μ")): f5.addRow(t, self.lg[k])
        b5 = QPushButton("Aplicar Cd do CFD e simular 40 s"); b5.clicked.connect(self.calc_cfd_veic); f5.addRow(b5)
        self.out_c = QTextEdit(); self.out_c.setReadOnly(True); f5.addRow(self.out_c); tabs.addTab(w5, "CFD → Veículo")
        # --- ajuste CSV
        w4 = QWidget(); f4 = QVBoxLayout(w4)
        f4.addWidget(QLabel("CSV com colunas alpha_graus, fz_N, fy_N (MEDIDAS). Ajusta C_α e μ do pneu de escova; μ só é identificável se houver pontos perto da saturação."))
        b4 = QPushButton("Abrir CSV e ajustar…"); b4.clicked.connect(self.ajustar_csv); f4.addWidget(b4)
        self.out_f = QTextEdit(); self.out_f.setReadOnly(True); f4.addWidget(self.out_f); tabs.addTab(w4, "Ajuste de pneu (CSV)")

    def calc_tire(self):
        import math
        try:
            fx, fy = TC.forca_combinada(self.kap.value(), math.radians(self.alf.value()), self.fz.value(), self.ca.value(), self.ck.value(), self.mu.value())
        except ValueError as e:
            self.out_t.setPlainText(f"ERRO: {e}"); return
        lim = self.mu.value() * self.fz.value(); r = (fx * fx + fy * fy) ** 0.5
        self.out_t.setPlainText(f"Fx = {fx:.1f} N\nFy = {fy:.1f} N\n|F| = {r:.1f} N  (limite μ·Fz = {lim:.1f} N; uso do círculo de atrito: {100*r/lim:.1f} %)\n\n"
                                "Modelo de escova com escorregamento combinado; classe ANALÍTICO. Parâmetros do pneu são do usuário (não há ajuste a dados reais).")

    def calc_susp(self):
        try:
            pts = {n: (float(self.tab.item(i, 0).text()), float(self.tab.item(i, 1).text())) for i, n in enumerate("ABCDWP")}
            s = SU.DuploA(**pts); c = SU.curva_heave(s, self.h0.value(), self.h1.value(), 7)
        except (ValueError, AttributeError) as e:
            self.out_s.setPlainText(f"ERRO: {e}"); return
        L = ["heave[mm]  camber[°]  Δbitola[mm]  RC[mm]  FVSA[mm]"]
        for r in c:
            rc = "—" if r["RC_altura_m"] is None else f"{r['RC_altura_m']*1000:.1f}"; fv = "—" if r["FVSA_m"] is None else f"{r['FVSA_m']*1000:.0f}"
            L.append(f"{r['heave_m']*1000:8.1f}  {r['camber_graus']:9.3f}  {r['delta_bitola_m']*1000:10.2f}  {rc:>6}  {fv:>7}")
        L.append("\nCinemática 2D (vista frontal), sem buchas/elastocinemática, sem caster/KPI. Classe ANALÍTICO.")
        self.out_s.setPlainText("\n".join(L))

    def calc_susp3d(self):
        try:
            pts = {n: tuple(float(self.tab3.item(i, j).text()) for j in range(3)) for i, n in enumerate(self.NOMES3)}
            s = S3.DuploA3D(**pts); h = self.s3h.value()
            res = S3.analisar(s, h); der = S3.derivadas(s)
            k = S3.CoefElasto(*[w.value() for w in self.s3k])
            curva = [S3.com_elastocinematica(s, h * f, 0.0, self.s3fy.value(), self.s3fx.value(), k) for f in (-1, -0.5, 0, 0.5, 1)]
            rk = S3.resolver_3d(s, 0.0, self.s3r.value())
        except (ValueError, AttributeError) as e:
            self.out_s3.setPlainText(f"ERRO: {e}"); return
        v = res.valores
        L = [f"Projeto: caster {v['caster_graus']:.2f}°  KPI {v['kpi_graus']:.2f}°  trail {v['trail_mecanico_m']*1000:.1f} mm  scrub {v['scrub_m']*1000:.1f} mm",
             f"Camber gain {der['camber_gain_graus_por_m']/1000:.4f} °/mm   Bump steer {der['bump_steer_graus_por_m']/1000:.4f} °/mm (toe-in)   Razão de esterçamento {der['razao_esterco_graus_por_mm']:.4f} °/mm de cremalheira",
             "", "heave[mm]  camber[°]  toe-in[°]  Δbitola[mm]  Δentre-eixos[mm]"]
        for r in curva:
            L.append(f"{r['heave_m']*1000:8.1f}  {r['camber_graus']:9.3f}  {r['toe_in_graus']:9.3f}  {r['delta_bitola_m']*1000:10.2f}  {r['delta_entre_eixos_m']*1000:12.2f}")
        L.append(f"\nCurso da cremalheira {self.s3r.value()*1000:.1f} mm → esterço (Δtoe-in) {rk['toe_in_graus']:.2f}°, camber {rk['camber_graus']:.2f}°, caster {rk['caster_graus']:.2f}°")
        L.append("Elastocinemática: LINEAR e SIMPLIFICADA — só os coeficientes que você digitou × forças (padrão 0); sem buchas. Classe ANALÍTICO (barras rígidas, rótulas ideais).")
        self.out_s3.setPlainText("\n".join(L))

    def calc_gg(self, vel=None):
        try:
            g = {k: w.value() for k, w in self.gg.items()}; vel = g.pop("vel"); g.pop("pot"); g.pop("cda")
            v = VL.VeiculoLateral(iz=1800.0, k_roll_f=60000.0, k_roll_r=40000.0, **g)
            pts = VC.diagrama_gg(v, vel, 13)
        except ValueError as e:
            self.out_g.setPlainText(f"ERRO: {e}"); return
        L = ["ax[g]   ay_max[g]   (ax>0 tração no eixo traseiro; ax<0 frenagem 50/50)"]
        L += [f"{ax:6.2f}   {('inviável' if ay is None or ay == 0 else f'{ay:.3f}'):>8}" for ax, ay in pts]
        L.append("\nSem arrasto, arfagem nem diferencial; círculo de atrito em saturação. Classe ANALÍTICO; parâmetros são do usuário (iniciais ILUSTRATIVOS).")
        self.out_g.setPlainText("\n".join(L))

    def ajustar_csv(self, caminho=None):
        if not caminho:
            from PySide6.QtWidgets import QFileDialog
            caminho, _ = QFileDialog.getOpenFileName(self, "CSV de pneu", "", "CSV (*.csv)")
            if not caminho: return
        try:
            r = TF.ajustar(TF.ler_csv(caminho))
        except (ValueError, OSError) as e:
            self.out_f.setPlainText(f"ERRO: {e}"); return
        self.out_f.setPlainText(f"C_α = {r['c_alpha_N_rad']:.0f} N/rad\nμ = {r['mu']:.3f}\nRMSE = {r['rmse_N']:.1f} N  (n = {r['n']})\n" + (r["aviso"] or "μ identificável (há pontos perto da saturação)") +
                                "\n\nAjuste de modelo aos SEUS dados; não valida o pneu fora da faixa medida.")

    def calc_cfd_veic(self, resultado: dict | None = None):
        from modules import integracao as IG, vehicle_dynamics as VD
        try:
            if resultado is None:
                if not self._store or not self.pj.currentText(): raise ValueError("crie um projeto com resultado de CFD em 'Solvers, vitrine e projetos…'")
                res = [r for r in self._store.open(self.pj.currentText())["results"] if r.get("classe") in ("SIMULACAO_NUMERICA", "VALIDADO") and ("cd_total_estimado" in (r.get("valores") or {}) or "cd" in (r.get("valores") or {}))]
                if not res: raise ValueError("o projeto não tem resultado de CFD com Cd")
                resultado = res[-1]
            g = {k: w.value() for k, w in self.lg.items()}
            base = VD.Veiculo(massa=g["massa"], cd=0.3, area=g["area"], crr=g["crr"], forca_motriz=g["fm"], potencia=g["pot"], mu=g["mu"])
            v, prov = IG.veiculo_com_cfd(base, IG.de_resultado_projeto(resultado), area_real=g["area"])
            h = VD.simular(v, 40.0); vmax = max(x[2] for x in h)
        except ValueError as e:
            self.out_c.setPlainText(f"ERRO: {e}"); return
        self.out_c.setPlainText(f"Cd usado = {prov['cd']:.4f}  ({prov['base']})\nclasse do CFD: {prov['classe_cfd']}\nárea usada = {prov['area_usada_m2']:.3f} m² ({prov['area_origem']})\n"
                                f"v máx em 40 s = {vmax*3.6:.1f} km/h\n\n" + "\n".join("⚠ " + a for a in prov["alertas"]) + "\n\nO Cd carrega os limites do CFD (ESTIMADO, não validado).")

    def calc_volta(self):
        """Volta sintética em PROCESSO ISOLADO (V4.1): a janela não congela e há cancelamento. Use `aguardar_volta()` em testes/API."""
        from PySide6.QtCore import QTimer
        from core.jobs import JobManager
        if getattr(self, "_job", None) is not None and not self._job.terminal:
            return
        try:
            g = {k: w.value() for k, w in self.gg.items()}; g.pop("vel"); pot = g.pop("pot"); cda = g.pop("cda")
            VL.VeiculoLateral(iz=1800.0, k_roll_f=60000.0, k_roll_r=40000.0, **g)        # valida já, antes de criar o processo
        except ValueError as e:
            self.out_g.setPlainText(f"ERRO: {e}"); return
        self.jobs = getattr(self, "jobs", None) or JobManager(1)
        veic = dict(iz=1800.0, k_roll_f=60000.0, k_roll_r=40000.0, **g)
        self._job = self.jobs.submit_python("Volta do veículo (isolado)", "modules.veiculo_job", "volta", dict(veiculo=veic, p_ice=pot, cda=cda, ds=6.0), timeout=1800)
        self.out_g.setPlainText("Executando em processo separado…")
        if not hasattr(self, "_timer"):
            self._timer = QTimer(self); self._timer.setInterval(200); self._timer.timeout.connect(self._poll_volta)
        self._timer.start()

    def cancelar_volta(self):
        if getattr(self, "_job", None) is not None and not self._job.terminal:
            self.jobs.cancel(self._job.id)

    def aguardar_volta(self, timeout=600.0):
        if getattr(self, "_job", None) is not None:
            self._job.wait(timeout); self._poll_volta()
        return self.out_g.toPlainText()

    def _poll_volta(self):
        j = self._job
        if j is None or not j.terminal:
            return
        self._timer.stop()
        if j.state == "CANCELLED":
            self.out_g.setPlainText("Cancelado pelo usuário. Nenhum resultado foi gravado."); return
        if j.state != "DONE":
            self.out_g.setPlainText(f"{j.state}: {j.error}\n\n--- log do processo ---\n" + "\n".join(j.log.splitlines()[-25:])); return
        r = j.result()
        if "_erro" in r:
            self.out_g.setPlainText(f"ERRO: {r['_erro']}"); return
        x = r["valores"]
        self.out_g.setPlainText(f"Volta (circuito SINTÉTICO): {x['tempo_s']:.2f} s · v média {x['v_media_kmh']:.1f} km/h · v máx {x['v_max_kmh']:.0f} · v mín {x['v_min_kmh']:.0f}\n\n" +
                                "\n".join("⚠ " + l for l in r["limitacoes"]) + "\n" + "\n".join("• " + l for l in r["premissas"]))
