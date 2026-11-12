"""Pneu combinado (Fx–Fy) e suspensão duplo-A (V3.5). Valores iniciais são ILUSTRATIVOS — o usuário informa os dados do seu carro."""
from __future__ import annotations
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget, QFormLayout, QDoubleSpinBox, QPushButton,
                               QTextEdit, QTableWidget, QTableWidgetItem, QLabel)
from modules import tire_combined as TC, suspension as SU


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
