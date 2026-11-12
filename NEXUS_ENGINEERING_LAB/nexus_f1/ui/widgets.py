"""Widgets de desenho: pista animada com HUD e gráficos de telemetria (QPainter, sem dependências extras)."""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from . import style


def speed_color(u: float) -> QColor:
    """0 (lento) -> azul, 0.5 -> verde/ciano, 1 (rápido) -> âmbar/vermelho."""
    u = float(np.clip(u, 0, 1))
    if u < 0.5:
        a, b, k = (40, 90, 255), (25, 211, 245), u / 0.5
    else:
        a, b, k = (25, 211, 245), (255, 176, 46), (u - 0.5) / 0.5
    return QColor(*[int(a[i] + (b[i] - a[i]) * k) for i in range(3)])


class TrackView(QWidget):
    """Vista superior do circuito com mapa de velocidade, carro sincronizado e HUD."""
    observer_picked = Signal(float)   # abscissa s (m) clicada

    def __init__(self):
        super().__init__()
        self.setMinimumSize(420, 360)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.res = None
        self.t_now = 0.0
        self.observer_s = None
        self.ghosts = []          # [(nome, res, cor)] opcional

    def set_result(self, res):
        self.res = res
        self.t_now = 0.0
        self.update()

    def set_time(self, t: float):
        self.t_now = t
        self.update()

    # ------------------------------------------------------------------ geometria
    def _xf(self):
        tel = self.res.tel
        x, y = tel["x"], tel["y"]
        w, h = self.width() - 60, self.height() - 150
        sx, sy = np.ptp(x) or 1.0, np.ptp(y) or 1.0
        sc = min(w / sx, h / sy)
        ox = 30 + (w - sx * sc) / 2 - x.min() * sc
        oy = 20 + (h - sy * sc) / 2 + y.max() * sc
        return lambda px, py: QPointF(ox + px * sc, oy - py * sc), sc

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(style.PANEL))
        if self.res is None:
            p.setPen(QColor(style.MUTED))
            p.drawText(self.rect(), Qt.AlignCenter, "Execute uma simulação para ver o circuito")
            return
        tel = self.res.tel
        f, sc = self._xf()
        v = tel["v_kmh"]
        vmin, vmax = v.min(), v.max()
        n = len(v)
        # faixa de asfalto
        path = QPainterPath(f(tel["x"][0], tel["y"][0]))
        for i in range(1, n):
            path.lineTo(f(tel["x"][i], tel["y"][i]))
        path.closeSubpath()
        p.setPen(QPen(QColor("#0d2a3b"), 15, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(path)
        # linha colorida por velocidade
        for i in range(n):
            j = (i + 1) % n
            p.setPen(QPen(speed_color((v[i] - vmin) / (vmax - vmin + 1e-9)), 5, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(f(tel["x"][i], tel["y"][i]), f(tel["x"][j], tel["y"][j]))
        # setores e linha de chegada
        L = self.res.track.length_m
        p.setPen(QPen(QColor(style.AMBER), 2))
        for sb in self.res.track.sector_bounds()[:3]:
            k = int(np.argmin(np.abs(tel["s"] - sb)))
            a = tel["heading"][k]
            c = f(tel["x"][k], tel["y"][k])
            nx, ny = -np.sin(a), np.cos(a)
            p.drawLine(QPointF(c.x() + nx * 12, c.y() - ny * 12), QPointF(c.x() - nx * 12, c.y() + ny * 12))
        # observador de áudio
        if self.observer_s is not None:
            k = int(np.argmin(np.abs(tel["s"] - self.observer_s)))
            c = f(tel["x"][k], tel["y"][k])
            p.setBrush(QColor(style.GREEN)); p.setPen(Qt.NoPen)
            p.drawEllipse(c, 6, 6)
            p.setPen(QColor(style.GREEN)); p.drawText(c + QPointF(9, -6), "ouvinte")
        # carro
        t = np.clip(self.t_now, 0, tel["t"][-1])
        k = int(np.clip(np.searchsorted(tel["t"], t) - 1, 0, n - 1))
        frac = 0.0
        if k < n - 1:
            frac = (t - tel["t"][k]) / max(tel["t"][k + 1] - tel["t"][k], 1e-9)
        k2 = (k + 1) % n
        cx = tel["x"][k] + (tel["x"][k2] - tel["x"][k]) * frac
        cy = tel["y"][k] + (tel["y"][k2] - tel["y"][k]) * frac
        c = f(cx, cy)
        p.setPen(QPen(QColor("white"), 2)); p.setBrush(QColor(style.RED))
        p.drawEllipse(c, 8, 8)
        # legenda de velocidade
        g = QLinearGradient(20, self.height() - 128, 160, self.height() - 128)
        g.setColorAt(0, speed_color(0)); g.setColorAt(0.5, speed_color(0.5)); g.setColorAt(1, speed_color(1))
        p.fillRect(QRectF(20, self.height() - 132, 140, 6), QBrush(g))
        p.setPen(QColor(style.MUTED)); p.setFont(QFont("Segoe UI", 8))
        p.drawText(20, self.height() - 108, f"{vmin:.0f}")
        p.drawText(130, self.height() - 108, f"{vmax:.0f} km/h")
        self._hud(p, k, t)

    def _hud(self, p: QPainter, k: int, t: float):
        tel = self.res.tel
        W, H = self.width(), self.height()
        y0 = H - 96
        p.setPen(QPen(QColor(style.CYAN_DIM), 1)); p.drawLine(10, y0 - 6, W - 10, y0 - 6)
        # velocidade
        p.setPen(QColor(style.CYAN)); p.setFont(QFont("Segoe UI", 28, QFont.Bold))
        p.drawText(QRectF(14, y0, 150, 50), Qt.AlignLeft | Qt.AlignVCenter, f"{tel['v_kmh'][k]:.0f}")
        p.setFont(QFont("Segoe UI", 9)); p.setPen(QColor(style.MUTED))
        p.drawText(14, y0 + 62, "km/h")
        # marcha
        p.setFont(QFont("Segoe UI", 28, QFont.Bold)); p.setPen(QColor(style.AMBER))
        p.drawText(QRectF(130, y0, 60, 50), Qt.AlignCenter, f"{int(tel['gear'][k])}")
        p.setFont(QFont("Segoe UI", 9)); p.setPen(QColor(style.MUTED)); p.drawText(140, y0 + 62, "marcha")
        # barras
        def bar(x, label, val, col, w=170):
            p.setPen(QColor(style.MUTED)); p.setFont(QFont("Segoe UI", 8)); p.drawText(x, y0 + 8, label)
            p.setPen(QPen(QColor("#14465c"), 1)); p.setBrush(Qt.NoBrush); p.drawRect(QRectF(x + 56, y0, w, 10))
            p.fillRect(QRectF(x + 57, y0 + 1, max(0, w - 2) * float(np.clip(val, 0, 1)), 8), QColor(col))
        bx = 215
        r = self.res
        bar(bx, "RPM", tel["rpm"][k] / r.car.redline_rpm, style.CYAN)
        p.setPen(Qt.NoPen)
        # throttle / brake
        def bar2(y, label, val, col):
            p.setPen(QColor(style.MUTED)); p.setFont(QFont("Segoe UI", 8)); p.drawText(bx, y + 9, label)
            p.setPen(QPen(QColor("#14465c"), 1)); p.setBrush(Qt.NoBrush); p.drawRect(QRectF(bx + 56, y, 170, 10))
            p.fillRect(QRectF(bx + 57, y + 1, 168 * float(np.clip(val, 0, 1)), 8), QColor(col))
        bar2(y0 + 16, "ACELERADOR", tel["throttle"][k], style.GREEN)
        bar2(y0 + 32, "FREIO", tel["brake"][k], style.RED)
        bar2(y0 + 48, "GRIP USO", tel["util"][k], style.AMBER)
        # tempo e setor
        from ..core.laptime import format_time
        p.setFont(QFont("Consolas", 18, QFont.Bold)); p.setPen(QColor("white"))
        p.drawText(QRectF(W - 220, y0 - 2, 210, 32), Qt.AlignRight | Qt.AlignVCenter, format_time(max(t, 0)))
        sec = 1 + int(tel["s"][k] >= r.track.sector_bounds()[1]) + int(tel["s"][k] >= r.track.sector_bounds()[2])
        p.setFont(QFont("Segoe UI", 9)); p.setPen(QColor(style.MUTED))
        seg = r.segments[int(tel["seg_id"][k])] if int(tel["seg_id"][k]) < len(r.segments) else None
        p.drawText(QRectF(W - 330, y0 + 30, 320, 16), Qt.AlignRight, f"Setor {sec}   |   a_lat {tel['ay_g'][k]:.1f} g   a_long {tel['ax_g'][k]:+.1f} g")
        p.drawText(QRectF(W - 330, y0 + 48, 320, 16), Qt.AlignRight, f"Pneus {tel['Tm'][k]:.0f} °C   |   {'ASA ABERTA' if tel['aero_open'][k] > 0.5 else 'asa fechada'}")

    def mousePressEvent(self, e):
        if self.res is None:
            return
        tel = self.res.tel
        f, _ = self._xf()
        best, bi = 1e18, 0
        for i in range(0, len(tel["x"]), 2):
            q = f(tel["x"][i], tel["y"][i])
            d = (q.x() - e.position().x()) ** 2 + (q.y() - e.position().y()) ** 2
            if d < best:
                best, bi = d, i
        if best < 30 ** 2:
            self.observer_s = float(tel["s"][bi])
            self.observer_picked.emit(self.observer_s)
            self.update()


class PlotStack(QWidget):
    """Gráficos empilhados (eixo x = distância) com cursor sincronizado ao tempo de reprodução."""
    cursor_s = Signal(float)

    PANELS = [
        ("Velocidade (km/h)", [("v_kmh", style.CYAN)], None),
        ("Acelerador / Freio", [("throttle", style.GREEN), ("brake", style.RED)], (0, 1.05)),
        ("RPM (marcha)", [("rpm", style.AMBER)], None),
        ("Aceleração (g)", [("ax_g", style.GREEN), ("ay_g", "#b388ff")], None),
        ("Pneus (°C)", [("Tf", style.CYAN), ("Tr", style.AMBER)], None),
    ]

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(420)
        self.setMouseTracking(True)
        self.res = None
        self.cursor = 0.0
        self.overlay = []   # [(nome, res, cor)] para comparar voltas na mesma figura (somente velocidade)

    def set_result(self, res, overlay=None):
        self.res = res
        self.overlay = overlay or []
        self.update()

    def set_cursor_s(self, s):
        self.cursor = s
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(style.PANEL))
        if self.res is None:
            p.setPen(QColor(style.MUTED)); p.drawText(self.rect(), Qt.AlignCenter, "Sem dados de telemetria"); return
        tel = self.res.tel
        s = tel["s"]; L = self.res.track.length_m
        n = len(self.PANELS)
        m = 8
        ph = (self.height() - 2 * m) / n
        left, right = 60, self.width() - 14
        for pi, (title, series, rng) in enumerate(self.PANELS):
            top = m + pi * ph
            rect = QRectF(left, top + 14, right - left, ph - 22)
            p.setPen(QPen(QColor("#12394d"), 1)); p.setBrush(QColor("#07141f")); p.drawRect(rect)
            p.setPen(QColor(style.CYAN)); p.setFont(QFont("Segoe UI", 8, QFont.Bold)); p.drawText(left, int(top + 10), title)
            data = [(k, c, np.asarray(tel[k], float)) for k, c in series]
            lo = min(d.min() for _, _, d in data); hi = max(d.max() for _, _, d in data)
            if rng: lo, hi = rng
            if hi - lo < 1e-9: hi = lo + 1
            pad = (hi - lo) * 0.06; lo -= pad; hi += pad
            for g in range(5):
                gy = rect.top() + rect.height() * g / 4
                p.setPen(QPen(QColor("#0f2a3a"), 1)); p.drawLine(QPointF(rect.left(), gy), QPointF(rect.right(), gy))
                p.setPen(QColor(style.MUTED)); p.setFont(QFont("Segoe UI", 7))
                p.drawText(QRectF(0, gy - 7, left - 4, 14), Qt.AlignRight | Qt.AlignVCenter, f"{hi - (hi - lo) * g / 4:.3g}")
            step = max(len(s) // 700, 1)
            for k, c, d in data:
                path = QPainterPath()
                for i in range(0, len(s), step):
                    pt = QPointF(rect.left() + rect.width() * s[i] / L, rect.bottom() - rect.height() * (d[i] - lo) / (hi - lo))
                    path.moveTo(pt) if i == 0 else path.lineTo(pt)
                p.setPen(QPen(QColor(c), 1.4)); p.setBrush(Qt.NoBrush); p.drawPath(path)
            if pi == 0:
                for name, r2, c in self.overlay:
                    d2 = np.asarray(r2.tel["v_kmh"], float); s2 = r2.tel["s"]
                    path = QPainterPath()
                    for i in range(0, len(s2), step):
                        pt = QPointF(rect.left() + rect.width() * s2[i] / L, rect.bottom() - rect.height() * (d2[i] - lo) / (hi - lo))
                        path.moveTo(pt) if i == 0 else path.lineTo(pt)
                    p.setPen(QPen(QColor(c), 1.2, Qt.DashLine)); p.drawPath(path)
            if pi == 2:   # marcha como degraus finos
                pass
            cx = rect.left() + rect.width() * (self.cursor / L)
            p.setPen(QPen(QColor("white"), 1)); p.drawLine(QPointF(cx, rect.top()), QPointF(cx, rect.bottom()))
        p.setPen(QColor(style.MUTED)); p.setFont(QFont("Segoe UI", 8))
        p.drawText(left, self.height() - 1, "distância ao longo da volta (m)")

    def mouseMoveEvent(self, e):
        if self.res is not None and e.buttons():
            self._pick(e)

    def mousePressEvent(self, e):
        if self.res is not None:
            self._pick(e)

    def _pick(self, e):
        left, right = 60, self.width() - 14
        u = np.clip((e.position().x() - left) / (right - left), 0, 1)
        self.cursor = u * self.res.track.length_m
        self.cursor_s.emit(self.cursor)
        self.update()
