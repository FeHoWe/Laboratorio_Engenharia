"""Engenharia F1 (V2.8): conformidade geométrica, massa/CG/inércia e simulação de volta.

Ferramentas de ESTUDO com parâmetros seus — não substituem os sistemas de uma equipe nem a homologação da FIA (veja os avisos em cada aba).
"""
from __future__ import annotations

from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QApplication, QFileDialog, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QTableWidget,
                               QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

from modules import f1_mass, f1_regs, lapsim, telemetria

COLORS = {"CONFORME": "#1b7f3b", "NAO_CONFORME": "#b3261e", "SEM_MEDIDA": "#7a7a7a", "LIMITE_NAO_VERIFICADO": "#a86b00"}


def _num(edit: QLineEdit):
    t = edit.text().strip().replace(",", ".")
    return float(t) if t else None


class SpeedPlot(QWidget):
    def __init__(self):
        super().__init__()
        self.s, self.v = [], []
        self.setMinimumHeight(140)

    def set_data(self, s, v):
        self.s, self.v = s, v
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#0b1620"))
        if len(self.s) < 2:
            return
        w, h = self.width() - 10, self.height() - 10
        vmax, smax = max(self.v) * 1.05, self.s[-1]
        p.setPen(QPen(QColor("#33e0ff"), 1.5))
        pts = [(5 + w * a / smax, 5 + h * (1 - b / vmax)) for a, b in zip(self.s, self.v)]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            p.drawLine(int(x0), int(y0), int(x1), int(y1))
        p.setPen(QColor("#9fb4c4"))
        p.drawText(8, 16, f"v(s)  máx {vmax / 1.05 * 3.6:.0f} km/h")


class StripPlot(QWidget):
    """Gráfico de telemetria em faixas empilhadas (como os painéis de engenharia): velocidade, pedais, marcha e g."""
    LANES = [("Velocidade km/h", ["v_kmh"], ["#33e0ff"]), ("Acelerador % (verde) / Freio % (vermelho) — estimados", ["acelerador_pct", "freio_pct"], ["#3ddc84", "#ff5c5c"]),
             ("Marcha — ilustrativa", ["marcha"], ["#ffd24d"]), ("g longitudinal (laranja) / lateral (azul)", ["g_long", "g_lat"], ["#ff9f43", "#6c8cff"])]

    def __init__(self):
        super().__init__()
        self.ch = None
        self.setMinimumHeight(330)

    def set_data(self, ch):
        self.ch = ch
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#0b1620"))
        if not self.ch or len(self.ch["s_m"]) < 2:
            return
        s = self.ch["s_m"]
        smax = s[-1] or 1.0
        lh = self.height() / len(self.LANES)
        for li, (title, keys, cols) in enumerate(self.LANES):
            y0 = li * lh
            lo = min(min(self.ch[k]) for k in keys)
            hi = max(max(self.ch[k]) for k in keys)
            if hi - lo < 1e-9:
                hi = lo + 1.0
            p.setPen(QColor("#9fb4c4"))
            p.drawText(8, int(y0 + 13), f"{title}  [{lo:.1f} … {hi:.1f}]")
            for k, col in zip(keys, cols):
                p.setPen(QPen(QColor(col), 1.3))
                pts = [(5 + (self.width() - 10) * a / smax, y0 + 18 + (lh - 24) * (1 - (b - lo) / (hi - lo))) for a, b in zip(s, self.ch[k])]
                for (x0, ya), (x1, yb) in zip(pts, pts[1:]):
                    p.drawLine(int(x0), int(ya), int(x1), int(yb))
            p.setPen(QColor("#22384a"))
            p.drawLine(0, int(y0 + lh), self.width(), int(y0 + lh))


class F1Dialog(QDialog):
    def __init__(self, window) -> None:
        super().__init__(window)
        self.win = window
        self.setWindowTitle("Engenharia F1 — regulamento, massa/CG e volta")
        self.resize(820, 640)
        self.last_result = None
        tabs = QTabWidget()
        v = QVBoxLayout(self)
        v.addWidget(tabs)
        tabs.addTab(self._regs_tab(), "Regulamento")
        tabs.addTab(self._mass_tab(), "Massa e CG")
        tabs.addTab(self._lap_tab(), "Volta")
        tabs.addTab(self._tel_tab(), "Telemetria")

    # ------------------------------------------------------------------ regulamento
    def _regs_tab(self):
        w = QWidget(); v = QVBoxLayout(w)
        v.addWidget(self._warn("Compara medidas com um conjunto PEQUENO de limites lidos em fontes públicas (FIA 2027 Seção C, emissão 04, C2/C3). NÃO é homologação: "
                               "regras sem medida ficam SEM_MEDIDA; a massa mínima de 2027 não foi lida — digite o limite."))
        top = QHBoxLayout()
        self.season = QComboBox(); self.season.addItems(["2027", "2026"]); top.addWidget(QLabel("Temporada:")); top.addWidget(self.season)
        b = QPushButton("Medir no modelo aberto"); b.clicked.connect(self.measure); top.addWidget(b)
        c = QPushButton("Verificar"); c.clicked.connect(self.run_regs); top.addWidget(c)
        v.addLayout(top)
        form = QFormLayout(); self.fields: dict[str, QLineEdit] = {}
        for f in f1_regs.FIELDS:
            e = QLineEdit(); self.fields[f] = e; form.addRow(f, e)
        self.mass_limit = QLineEdit(); form.addRow("limite de massa (kg) — 2027", self.mass_limit)
        v.addLayout(form)
        self.table = QTableWidget(0, 5); self.table.setHorizontalHeaderLabels(["Regra", "Descrição", "Medido", "Limite", "Estado"]); v.addWidget(self.table)
        return w

    def _warn(self, text):
        l = QLabel(text); l.setWordWrap(True); l.setStyleSheet("color:#e0b050"); return l

    def measure(self):
        comps = self.win.project.components
        parts = []
        for leaf in comps.leaves():
            bb = comps.bbox(leaf)
            if bb is not None:
                parts.append((leaf.name, tuple(bb.min), tuple(bb.max)))
        m = f1_regs.measure_model(parts)
        for k, val in m.items():
            self.fields[k].setText(f"{val:.2f}")

    def run_regs(self):
        meas = {k: _num(e) for k, e in self.fields.items()}
        meas = {k: v for k, v in meas.items() if v is not None}
        res = f1_regs.check(self.season.currentText(), meas, _num(self.mass_limit))
        self.table.setRowCount(len(res))
        for i, r in enumerate(res):
            vals = [r.rule, r.title + ("" if r.verified else "  (limite não verificado no texto)"), "" if r.value is None else f"{r.value:.2f}",
                    "" if r.limit is None else f"{r.op} {r.limit:g}", r.status]
            for j, t in enumerate(vals):
                it = QTableWidgetItem(t); self.table.setItem(i, j, it)
            self.table.item(i, 4).setForeground(QColor(COLORS[r.status]))
        self.table.resizeColumnsToContents()

    # ------------------------------------------------------------------ massa e CG
    def _mass_tab(self):
        w = QWidget(); v = QVBoxLayout(w)
        v.addWidget(self._warn("Só entram peças COM material escolhido por você (o software não atribui material). Inércia = massas pontuais (sem a inércia própria das peças). "
                               "Piloto e lastro são valores seus."))
        form = QFormLayout()
        self.m_driver, self.m_driver_pos = QLineEdit("80"), QLineEdit("0, 1000, 330")
        self.m_target, self.m_ballast_pos = QLineEdit(), QLineEdit("0, 1700, 90")
        self.m_yf, self.m_yr = QLineEdit(), QLineEdit()
        for lab, e in (("Massa do piloto+equip. (kg)", self.m_driver), ("Posição do piloto x,y,z (mm)", self.m_driver_pos), ("Massa-alvo (kg, opcional)", self.m_target),
                       ("Posição do lastro x,y,z (mm)", self.m_ballast_pos), ("y do eixo dianteiro (mm; vazio = pneu)", self.m_yf), ("y do eixo traseiro (mm; vazio = pneu)", self.m_yr)):
            form.addRow(lab, e)
        v.addLayout(form)
        b = QPushButton("Calcular massa, CG, distribuição e inércia"); b.clicked.connect(self.run_mass); v.addWidget(b)
        self.mass_out = QPlainTextEdit(); self.mass_out.setReadOnly(True); v.addWidget(self.mass_out)
        return w

    def _xyz(self, text):
        a = [float(t) for t in text.replace(";", ",").split(",")]
        if len(a) != 3:
            raise ValueError("use x, y, z")
        return tuple(a)

    def run_mass(self):
        try:
            comps = self.win.project.components
            items = f1_mass.items_from_components(comps, self.win.project.materials)
            nparts = sum(1 for _ in comps.leaves())
            drv = _num(self.m_driver) or 0.0
            if drv > 0:
                items.append(("Piloto (informado)", drv, self._xyz(self.m_driver_pos.text())))
            yf, yr = _num(self.m_yf), _num(self.m_yr)
            if yf is None or yr is None:
                ys = {}
                for leaf in comps.leaves():
                    if leaf.name in ("Pneu dianteira direita", "Pneu traseira direita"):
                        bb = comps.bbox(leaf); ys[leaf.name] = (bb.min[1] + bb.max[1]) / 2
                yf, yr = ys["Pneu dianteira direita"], ys["Pneu traseira direita"]
            tgt = _num(self.m_target)
            if tgt:
                r = f1_mass.lastro_para_alvo(items, tgt, self._xyz(self.m_ballast_pos.text()), yf, yr)
                bal = r["balanco"]
                extra = f"Lastro necessário: {r['lastro_kg']:.2f} kg" if r["lastro_kg"] > 0 else f"Já {r['acima_do_alvo_kg']:.2f} kg ACIMA do alvo"
            else:
                bal, extra = f1_mass.balance(items, yf, yr), ""
            I = bal["inercia_kgm2"]
            self.mass_out.setPlainText(
                f"Classe: ANALITICO (massas pontuais)\nPeças com massa: {len(items)} de {nparts}"
                + ("  — PARCIAL: peças sem material ficam de fora\n" if len(items) < nparts else "\n")
                + f"Massa total considerada: {bal['massa_kg']:.2f} kg\nCG (mm): x={bal['cg_mm'][0]:.1f}  y={bal['cg_mm'][1]:.1f}  z={bal['cg_mm'][2]:.1f}\n"
                f"Distribuição: {bal['pct_dianteiro']:.1f} % dianteira / {bal['pct_traseiro']:.1f} % traseira\nAltura do CG: {bal['altura_cg_mm']:.1f} mm\n"
                f"Inércia (kg·m², em torno do CG): Ixx={I[0][0]:.2f} Iyy={I[1][1]:.2f} Izz={I[2][2]:.2f}\n{extra}")
        except Exception as e:  # noqa: BLE001
            self.mass_out.setPlainText(f"Não foi possível calcular: {e}")

    # ------------------------------------------------------------------ volta
    def _lap_tab(self):
        w = QWidget(); v = QVBoxLayout(w)
        v.addWidget(self._warn("Simulação quase-estacionária de ponto material com SEUS parâmetros. Os valores iniciais são EXEMPLOS, não dados de equipe; a pista é sintética. "
                               "Sem pneus reais, transferência de carga, combustível ou degradação."))
        form = QFormLayout(); self.lap: dict[str, QLineEdit] = {}
        for k, lab, d in (("massa", "Massa (kg)", "800"), ("p_ice", "Potência de combustão (kW)", "500"), ("cda", "Cd·A (m²)", "1.0"), ("cla", "Cl·A (m²)", "3.0"),
                          ("mu", "μ de aderência", "1.6"), ("crr", "Crr", "0.012"), ("p_ers", "Implantação elétrica (kW)", "300"), ("e_ers", "Energia elétrica por volta (MJ)", "4")):
            e = QLineEdit(d); self.lap[k] = e; form.addRow(lab, e)
        v.addLayout(form)
        v.addWidget(QLabel("Pista: um segmento por linha — comprimento_m, raio_m (0 = reta)"))
        self.track = QPlainTextEdit("\n".join(f"{a}, {b}" for a, b in lapsim.PISTA_EXEMPLO)); self.track.setMaximumHeight(110); v.addWidget(self.track)
        h = QHBoxLayout()
        b = QPushButton("Simular volta"); b.clicked.connect(self.run_lap); h.addWidget(b)
        c = QPushButton("Copiar resultado (JSON rastreável)"); c.clicked.connect(self.copy_json); h.addWidget(c)
        v.addLayout(h)
        self.lap_out = QLabel(); self.lap_out.setWordWrap(True); v.addWidget(self.lap_out)
        self.plot = SpeedPlot(); v.addWidget(self.plot)
        return w

    def run_lap(self):
        try:
            g = {k: _num(e) for k, e in self.lap.items()}
            car = lapsim.Carro(g["massa"], g["p_ice"] * 1e3, g["cda"], g["cla"], g["mu"], g["crr"], p_ers=g["p_ers"] * 1e3, e_ers=g["e_ers"] * 1e6)
            pista = []
            for ln in self.track.toPlainText().splitlines():
                if ln.strip():
                    a, b = ln.replace(";", ",").split(",")
                    pista.append((float(a), float(b)))
            r = lapsim.volta(car, pista)
            self.last_result = r
            q = r.valores
            m, s = divmod(q["tempo_s"], 60)
            self.lap_out.setText(f"Classe: {r.classe} ({r.solver} {r.solver_versao})\nTempo de volta: {int(m)}:{s:06.3f}  ·  comprimento {q['comprimento_m']:.0f} m\n"
                                 f"v média {q['v_media_kmh']:.1f} km/h · v máx {q['v_max_kmh']:.1f} · v mín {q['v_min_kmh']:.1f} km/h · energia elétrica usada {q['energia_ers_usada_MJ']:.2f} MJ")
            self.plot.set_data(q["s_m"], q["v_ms"])
        except Exception as e:  # noqa: BLE001
            self.lap_out.setText(f"Não foi possível simular: {e}")

    # ------------------------------------------------------------------ telemetria
    def _tel_tab(self):
        w = QWidget(); v = QVBoxLayout(w)
        v.addWidget(self._warn("Simulador de telemetria: canais SINTÉTICOS derivados da volta simulada na aba Volta (mesmos parâmetros e pista). NÃO é telemetria real nem de equipe. "
                               "Pedais são ESTIMADOS; marcha e rotação são ILUSTRATIVAS (razões fixas, topo de cada marcha na rotação máxima que você informar)."))
        form = QFormLayout(); self.tel: dict[str, QLineEdit] = {}
        for k, lab, d in (("n_marchas", "Número de marchas", "8"), ("rpm_max", "Rotação máxima (rpm)", "15000"), ("v_topo", "Velocidade na última marcha (km/h)", "340"), ("setores", "Setores (distâncias iguais)", "3")):
            e = QLineEdit(d); self.tel[k] = e; form.addRow(lab, e)
        v.addLayout(form)
        h = QHBoxLayout()
        b = QPushButton("Gerar telemetria"); b.clicked.connect(self.run_tel); h.addWidget(b)
        c = QPushButton("Exportar CSV…"); c.clicked.connect(self.export_tel); h.addWidget(c)
        v.addLayout(h)
        self.tel_out = QLabel(); self.tel_out.setWordWrap(True); v.addWidget(self.tel_out)
        self.strip = StripPlot(); v.addWidget(self.strip)
        self.last_tel = None
        return w

    def _car_and_track(self):
        g = {k: _num(e) for k, e in self.lap.items()}
        car = lapsim.Carro(g["massa"], g["p_ice"] * 1e3, g["cda"], g["cla"], g["mu"], g["crr"], p_ers=g["p_ers"] * 1e3, e_ers=g["e_ers"] * 1e6)
        pista = []
        for ln in self.track.toPlainText().splitlines():
            if ln.strip():
                a, b = ln.replace(";", ",").split(",")
                pista.append((float(a), float(b)))
        return car, pista

    def run_tel(self):
        try:
            car, pista = self._car_and_track()
            t = {k: _num(e) for k, e in self.tel.items()}
            r = telemetria.telemetria(car, pista, 2.0, int(t["n_marchas"]), t["rpm_max"], t["v_topo"], int(t["setores"]))
            self.last_tel = r
            q = r.valores
            m, s = divmod(q["tempo_s"], 60)
            self.tel_out.setText(f"Classe: {r.classe} ({r.solver} {r.solver_versao}) — dados SINTÉTICOS\nVolta {int(m)}:{s:06.3f} · setores: " + " | ".join(f"S{i + 1} {x:.3f} s" for i, x in enumerate(q["setores_s"]))
                                 + f"\ng lateral máx {q['g_lat_max']:.2f} · frenagem máx {q['g_frenagem_max']:.2f} · aceleração máx {q['g_acel_max']:.2f}\n"
                                 f"acelerador pleno {q['tempo_acelerador_pleno_pct']:.0f} % da distância · freio {q['tempo_freio_pct']:.0f} % · rotação máx {q['rpm_max_visto']:.0f} rpm")
            self.strip.set_data(q["canais"])
        except Exception as e:  # noqa: BLE001
            self.tel_out.setText(f"Não foi possível gerar telemetria: {e}")

    def export_tel(self):
        if self.last_tel is None:
            self.run_tel()
        if self.last_tel is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exportar telemetria sintética", "telemetria_sintetica.csv", "CSV (*.csv)")
        if path:
            telemetria.para_csv(self.last_tel, path)
            self.tel_out.setText(self.tel_out.text() + f"\nCSV gravado: {path}")

    def copy_json(self):
        if self.last_result is not None:
            d = self.last_result.to_dict(); d["valores"] = {k: v for k, v in d["valores"].items() if not isinstance(v, list)}
            import json
            QApplication.clipboard().setText(json.dumps(d, ensure_ascii=False, indent=2))
