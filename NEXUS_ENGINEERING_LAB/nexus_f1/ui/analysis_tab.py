"""Aba "Análise" — ferramentas no estilo MoTeC i2 / ATLAS / OptimumLap sobre o simulador NEXUS F1 (dados SINTÉTICOS, parâmetros estimados)."""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from ..core import analysis as A
from ..core.api import simulate_lap
from . import style

MODOS = ["Δ tempo entre voltas (A × B)", "Diagrama g-g", "Histograma de canal (ponderado pelo tempo)", "Canal matemático × distância",
         "Varredura de parâmetro", "Sensibilidade (±2 %)", "Otimizar nível de asa", "Otimizar relação final"]
PARAMS = ["mass_kg", "cda", "cla", "ice_pmax_kw", "mguk_kw", "final_drive", "brake_bias_front", "front_weight_frac", "cog_height_m", "crr", "drivetrain_eff"]


class XYPlot(QWidget):
    """Gráfico simples (linhas / pontos / barras) em QPainter, com eixos e rótulos."""

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(300)
        self.series, self.title, self.xl, self.yl, self.kind = [], "", "", "", "line"

    def set_data(self, series, title="", xl="", yl="", kind="line"):
        self.series, self.title, self.xl, self.yl, self.kind = series, title, xl, yl, kind
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#0b1620"))
        p.setPen(QColor("#9fb4c4")); p.setFont(QFont("Segoe UI", 9))
        p.drawText(10, 16, self.title)
        if not self.series:
            return
        xs = np.concatenate([np.asarray(s[1], float) for s in self.series]); ys = np.concatenate([np.asarray(s[2], float) for s in self.series])
        x0, x1, y0, y1 = float(xs.min()), float(xs.max()), float(ys.min()), float(ys.max())
        if self.kind == "bar":
            y0 = min(y0, 0.0)
        if x1 - x0 < 1e-12:
            x1 = x0 + 1
        if y1 - y0 < 1e-12:
            y1 = y0 + 1
        L, R, T, B = 52, 14, 26, 36
        w, h = self.width() - L - R, self.height() - T - B
        px = lambda x: L + w * (x - x0) / (x1 - x0)  # noqa: E731
        py = lambda y: T + h * (1 - (y - y0) / (y1 - y0))  # noqa: E731
        p.setPen(QPen(QColor("#22384a"), 1))
        for i in range(5):
            gy = T + h * i / 4; gx = L + w * i / 4
            p.drawLine(L, int(gy), L + w, int(gy)); p.drawLine(int(gx), T, int(gx), T + h)
            p.setPen(QColor("#9fb4c4"))
            p.drawText(2, int(gy + 4), f"{y1 - (y1 - y0) * i / 4:.3g}"); p.drawText(int(gx - 14), T + h + 14, f"{x0 + (x1 - x0) * i / 4:.4g}")
            p.setPen(QPen(QColor("#22384a"), 1))
        if y0 < 0 < y1:
            p.setPen(QPen(QColor("#55708a"), 1.4)); p.drawLine(L, int(py(0)), L + w, int(py(0)))
        p.setPen(QColor("#9fb4c4")); p.drawText(L, self.height() - 4, self.xl); p.drawText(L + w // 2, 16, self.yl)
        cols = ["#33e0ff", "#ffb02e", "#3ddc84", "#ff5c5c", "#c58bff"]
        for k, (name, x, y) in enumerate(self.series):
            col = QColor(cols[k % len(cols)])
            x, y = np.asarray(x, float), np.asarray(y, float)
            if self.kind == "scatter":
                p.setPen(Qt.NoPen); p.setBrush(col)
                for a, b in zip(x[::2], y[::2]):
                    p.drawEllipse(int(px(a)) - 1, int(py(b)) - 1, 3, 3)
            elif self.kind == "bar":
                bw = max(2, int(w / max(len(x), 1) * 0.8)); p.setPen(Qt.NoPen); p.setBrush(col)
                for a, b in zip(x, y):
                    p.drawRect(int(px(a)) - bw // 2, int(py(max(b, 0))), bw, abs(int(py(b) - py(0))) + 1)
            else:
                p.setPen(QPen(col, 1.6))
                for i in range(len(x) - 1):
                    p.drawLine(int(px(x[i])), int(py(y[i])), int(px(x[i + 1])), int(py(y[i + 1])))
            if len(self.series) > 1 or name:
                p.setPen(col); p.drawText(L + 6 + 150 * k, T + 12, name)


class AnalysisTab(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        v = QVBoxLayout(self)
        n = QLabel("Ferramentas inspiradas em MoTeC i2 / ATLAS / OptimumLap / Simulink. Dados SINTÉTICOS do simulador quase-estático com parâmetros ESTIMADOS: "
                   "mostram tendências, não valores de uma equipe real. Varreduras rodam em modo experimental (não bloqueiam por regulamento).")
        n.setWordWrap(True); n.setStyleSheet(f"color:{style.AMBER}"); v.addWidget(n)
        f = QFormLayout()
        self.cb = QComboBox(); self.cb.addItems(MODOS); f.addRow("Análise", self.cb)
        self.ed = QLineEdit("v_kmh"); f.addRow("Canal / expressão (ex.: v*3.6, ax_g*ay_g, p_ice/1e3)", self.ed)
        self.cp = QComboBox(); self.cp.addItems(PARAMS); f.addRow("Parâmetro", self.cp)
        self.lo = QDoubleSpinBox(); self.lo.setRange(-1e6, 1e6); self.lo.setDecimals(4); self.lo.setValue(0.0)
        self.hi = QDoubleSpinBox(); self.hi.setRange(-1e6, 1e6); self.hi.setDecimals(4); self.hi.setValue(0.0)
        self.nn = QSpinBox(); self.nn.setRange(3, 40); self.nn.setValue(9)
        h = QHBoxLayout(); h.addWidget(QLabel("mín")); h.addWidget(self.lo); h.addWidget(QLabel("máx")); h.addWidget(self.hi); h.addWidget(QLabel("pontos")); h.addWidget(self.nn)
        f.addRow("Faixa (0 e 0 = ±15 % do valor atual)", h)
        v.addLayout(f)
        b = QPushButton("EXECUTAR ANÁLISE"); b.setObjectName("primary"); b.clicked.connect(self.run); v.addWidget(b)
        self.out = QLabel(""); self.out.setWordWrap(True); v.addWidget(self.out)
        self.plot = XYPlot(); v.addWidget(self.plot, 1)
        self.tb = QTableWidget(); self.tb.setMaximumHeight(170); v.addWidget(self.tb)

    # ---------------------------------------------------------------------------------------------
    def _ctx(self):
        w = self.win
        return w.cb_track.currentData(), w.current_car(), w.current_env(), w.sp_fuel.value()

    def run(self):
        try:
            m = self.cb.currentIndex()
            key, car, env, fuel = self._ctx()
            w = self.win
            if m == 0:
                a, b = w.slots.get("A"), w.slots.get("B")
                if a is None:
                    raise ValueError("Salve configurações em A (e opcionalmente B) na aba Comparar. Sem B, compara A com o carro atual.")
                b = b or car
                ra = simulate_lap(key, a.copy(mode="experimental"), env, fuel_kg=fuel); rb = simulate_lap(key, b.copy(mode="experimental"), env, fuel_kg=fuel)
                d = A.delta_time(ra, rb)
                self.plot.set_data([("Δt (B − A) s", d["s"], d["delta"])], f"Ganho/perda de tempo — {ra.track.name}", "distância (m)", "s")
                self.out.setText(f"Volta A {ra.fmt_time()} · B {rb.fmt_time()} · Δ final {d['final']:+.3f} s (positivo = B mais lento). "
                                 f"Maior perda em {d['where_max_loss_m']:.0f} m, maior ganho em {d['where_max_gain_m']:.0f} m.")
                self._table([["Segmento", "Δ (s)", "A (s)", "B (s)"]] + [[x["nome"], f"{x['dt']:+.3f}", f"{x['t_ref']:.2f}", f"{x['t_cmp']:.2f}"] for x in A.segment_deltas(ra, rb)])
                return
            r = w.res or simulate_lap(key, car, env, fuel_kg=fuel)
            if m == 1:
                g = A.gg_diagram(r)
                self.plot.set_data([("uso", np.abs(g["ay"]), g["ax"]), ("envelope +", g["ay_centers"], g["ax_max"]), ("envelope −", g["ay_centers"], g["ax_min"])], "Diagrama g-g (|ay| × ax)", "|ay| (g)", "ax (g)", "scatter")
                self.out.setText(f"Aceleração lateral máx. {np.abs(g['ay']).max():.2f} g · frenagem máx. {-g['ax'].min():.2f} g · tração máx. {g['ax'].max():.2f} g")
                self._table([["Marcha", "Tempo (s)"]] + [[str(k), f"{t:.2f}"] for k, t in A.gear_usage(r).items()])
            elif m == 2:
                hh = A.histogram(r, self.ed.text().strip() or "v_kmh", 24)
                c = 0.5 * (hh["edges"][1:] + hh["edges"][:-1])
                self.plot.set_data([("tempo (s)", c, hh["counts_s"])], f"Histograma de {self.ed.text()}", self.ed.text(), "s", "bar")
                st = A.throttle_brake_stats(r)
                self.out.setText(f"Acelerador pleno {st['acelerador_pleno_pct']:.0f} % · freio {st['freio_pct']:.0f} % · coasting {st['coasting_pct']:.0f} % do tempo")
                self.tb.setRowCount(0)
            elif m == 3:
                y = A.math_channel(r, self.ed.text())
                self.plot.set_data([(self.ed.text(), r.tel["s"], y)], f"{self.ed.text()} × distância — {r.track.name}", "distância (m)", self.ed.text())
                self.out.setText(f"mín {y.min():.4g} · máx {y.max():.4g} · média (no tempo) {np.average(y, weights=r.tel['dt']):.4g}")
                self.tb.setRowCount(0)
            elif m == 4:
                p = self.cp.currentText(); v0 = getattr(car, p)
                lo, hi = (self.lo.value(), self.hi.value()) if self.lo.value() != self.hi.value() else (0.85 * v0, 1.15 * v0)
                s = A.sweep(key, car, p, np.linspace(lo, hi, self.nn.value()), env, fuel)
                self.plot.set_data([("volta (s)", s["values"], s["lap_times"])], f"Tempo de volta × {p}", p, "s")
                self.out.setText(f"Melhor valor na faixa: {s['best_value']:.4g} → {s['best_time']:.3f} s (atual {v0:.4g}).")
                self.tb.setRowCount(0)
            elif m == 5:
                rows = A.sensitivity(key, car, None, 0.02, env, fuel)
                self.plot.set_data([("s por +1 %", list(range(len(rows))), [x["d_lap_por_pct"] for x in rows])], "Impacto de +1 % em cada parâmetro (s/volta; positivo = piora)", "parâmetros (ordem da tabela)", "s", "bar")
                self.out.setText("Barras na ordem da tabela, do maior ao menor impacto absoluto.")
                self._table([["Parâmetro", "Valor", "Δ volta por +1 % (s)"]] + [[x["param"], f"{x['valor']:.4g}", f"{x['d_lap_por_pct']:+.4f}"] for x in rows])
            elif m == 6:
                o = A.optimize_aero(key, car, env, fuel)
                self.plot.set_data([("volta (s)", o["levels"], o["lap_times"])], "Tempo de volta × nível de asa (0 baixo arrasto … 1 alta carga)", "nível de asa", "s")
                self.out.setText(f"Melhor nível neste circuito: {o['best_level']:.2f} → {o['best_time']:.3f} s (coeficientes dos presets ESTIMADOS).")
                self.tb.setRowCount(0)
            else:
                v0 = car.final_drive
                o = A.optimize_param(key, car, "final_drive", 0.7 * v0, 1.3 * v0, env, fuel)
                self.plot.set_data([], "")
                self.out.setText(f"Relação final ótima (seção áurea, {o['evaluations']} simulações): {o['best_value']:.3f} → {o['best_time']:.3f} s (atual {v0:.3f}). "
                                 "Com a rotação de troca fixa, a faixa de velocidade das marchas muda — confira a velocidade final.")
                self.tb.setRowCount(0)
        except Exception as e:  # noqa: BLE001
            self.out.setText(f"⚠ {e}")

    def _table(self, rows):
        self.tb.setRowCount(len(rows) - 1); self.tb.setColumnCount(len(rows[0])); self.tb.setHorizontalHeaderLabels(rows[0])
        for i, r in enumerate(rows[1:]):
            for j, t in enumerate(r):
                self.tb.setItem(i, j, QTableWidgetItem(t))
