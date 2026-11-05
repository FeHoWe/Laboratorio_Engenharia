"""Aba "Simulação de fadiga" (V2.0): tensões nominais, S-N, dano acumulado (Miner) e molas helicoidais.

Todas as resistências são digitadas pelo usuário; o banco de materiais fornece só a densidade (ver modules/fatigue.py).
"""
from __future__ import annotations

import math
from typing import Callable, Optional

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QScrollArea, QSplitter, QTableWidget, QTableWidgetItem, QTabWidget,
                               QVBoxLayout, QWidget)

from modules import fatigue as ft
from modules import valvetrain as vt
from modules.material_manager import MaterialLibrary


def _spin(lo: float, hi: float, val: float, dec: int = 2, suffix: str = "", step: Optional[float] = None) -> QDoubleSpinBox:
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setDecimals(dec)
    s.setValue(val)
    if suffix:
        s.setSuffix(" " + suffix)
    if step:
        s.setSingleStep(step)
    s.setKeyboardTracking(False)
    return s


def _fmt_cycles(n: float) -> str:
    return "∞ (vida infinita)" if math.isinf(n) else f"{n:,.0f}".replace(",", ".")


class SNPlot(QWidget):
    """Curva S-N (log N × σ) com o ponto de operação do caso atual."""

    def __init__(self) -> None:
        super().__init__()
        self.curve: Optional[ft.SNCurve] = None
        self.point: Optional[tuple[float, float]] = None     # (N, σ_ar)
        self.sigma_ar: Optional[float] = None
        self.setMinimumHeight(220)

    def set_data(self, curve: Optional[ft.SNCurve], sigma_ar: Optional[float], cycles: Optional[float]) -> None:
        self.curve, self.sigma_ar = curve, sigma_ar
        self.point = (cycles, sigma_ar) if (cycles is not None and sigma_ar is not None and not math.isinf(sigma_ar)) else None
        self.update()

    def paintEvent(self, ev) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#06121c"))
        if self.curve is None:
            p.setPen(QColor("#8fb4c8"))
            p.drawText(self.rect(), Qt.AlignCenter, "Informe o material (Su, Sy, Se') e a seção para ver a curva S-N")
            p.end()
            return
        c = self.curve
        L, R, T, B = 56, 10, 8, 26
        box = QRectF(L, T, self.width() - L - R, self.height() - T - B)
        pts = ft.sn_points(c, 1e3, 1e8)
        smax = max(c.sf1e3, (self.sigma_ar if self.sigma_ar and not math.isinf(self.sigma_ar) else 0)) * 1.08
        smin = max(1.0, min(c.se, min(s for _, s in pts)) * 0.6)
        lx0, lx1 = 3.0, 8.0
        ly0, ly1 = math.log10(smin), math.log10(smax)

        def X(n: float) -> float:
            return box.left() + (math.log10(max(n, 1e3)) - lx0) / (lx1 - lx0) * box.width()

        def Y(s: float) -> float:
            return box.bottom() - (math.log10(max(s, smin)) - ly0) / (ly1 - ly0) * box.height()

        p.setPen(QPen(QColor("#1d3a4d"), 1))
        p.drawRect(box)
        font = p.font()
        font.setPointSize(8)
        p.setFont(font)
        for e in range(3, 9):
            p.drawLine(QPointF(X(10.0 ** e), box.top()), QPointF(X(10.0 ** e), box.bottom()))
            p.setPen(QColor("#8fb4c8"))
            p.drawText(QPointF(X(10.0 ** e) - 8, self.height() - 10), f"1e{e}")
            p.setPen(QPen(QColor("#1d3a4d"), 1))
        p.setPen(QPen(QColor("#37d6ff"), 2))
        p.drawPolyline([QPointF(X(n), Y(s)) for n, s in pts])
        p.setPen(QPen(QColor("#ffb347"), 1, Qt.DashLine))
        p.drawLine(QPointF(box.left(), Y(c.se)), QPointF(box.right(), Y(c.se)))
        p.setPen(QColor("#ffb347"))
        p.drawText(QPointF(box.left() + 4, Y(c.se) - 3), f"Se = {c.se:.0f} MPa")
        p.setPen(QColor("#8fb4c8"))
        p.drawText(QPointF(2, box.top() + 10), f"{smax:.0f}")
        p.drawText(QPointF(2, box.bottom()), f"{smin:.0f}")
        p.drawText(QPointF(2, box.center().y()), "σ (MPa)")
        if self.sigma_ar is not None and not math.isinf(self.sigma_ar):
            p.setPen(QPen(QColor("#ff4d6d"), 1, Qt.DashLine))
            p.drawLine(QPointF(box.left(), Y(self.sigma_ar)), QPointF(box.right(), Y(self.sigma_ar)))
            if self.point and not math.isinf(self.point[0]):
                px, py = X(self.point[0]), Y(self.point[1])
                p.setBrush(QColor("#ff4d6d"))
                p.drawEllipse(QPointF(px, py), 4, 4)
                p.drawLine(QPointF(px, py), QPointF(px, box.bottom()))
        p.end()


class FatigueTab(QWidget):
    def __init__(self, library: Optional[MaterialLibrary] = None, selected_name: Optional[Callable[[], str]] = None) -> None:
        super().__init__()
        self.library = library or MaterialLibrary()
        self._selected_name = selected_name or (lambda: "")
        self.result: Optional[ft.FatigueResult] = None
        self.spring_result: Optional[dict] = None
        self.miner_result: Optional[dict] = None
        self._density: Optional[float] = None
        self._building = True

        root = QVBoxLayout(self)
        banner = QLabel("Análise ANALÍTICA de fadiga por tensões nominais — não é elementos finitos e não lê a geometria do CAD: seção, cargas "
                        "e concentração de tensões são informadas por você. Resistências (Su, Sy, Se', G) são digitadas por você, nunca "
                        "atribuídas pelo NEXUS.")
        banner.setWordWrap(True)
        banner.setStyleSheet("color:#8fb4c8;font-size:11px;")
        root.addWidget(banner)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self.tabs.addTab(self._build_component_tab(), "Peça (S-N / vida)")
        self.tabs.addTab(self._build_miner_tab(), "Espectro de cargas (Miner)")
        self.tabs.addTab(self._build_spring_tab(), "Mola helicoidal")
        self._building = False
        self.recalc()

    # ------------------------------------------------------------------ aba 1: peça
    def _build_component_tab(self) -> QWidget:
        self.part_label = QLabel("Peça: (nenhuma selecionada — selecione no painel de componentes e use 'Usar selecionada')")
        self.use_sel = QPushButton("Usar peça selecionada")
        self.use_sel.clicked.connect(self.use_selected)
        self.mat_name = QLineEdit("Material (digite o nome)")
        self.pick_btn = QPushButton("Banco de materiais (densidade)…")
        self.pick_btn.clicked.connect(self.pick_material)
        self.su = _spin(0, 5000, 0, 0, "MPa")
        self.sy = _spin(0, 5000, 0, 0, "MPa")
        self.se_p = _spin(0, 3000, 0, 0, "MPa")
        self.est = QCheckBox("Estimar Se' = 0,5·Su (só aço) — marcado como estimativa")
        self.knee = QCheckBox("Material com limite de fadiga (aço)")
        self.knee.setChecked(True)
        self.nk = _spin(1.0e4, 1.0e10, 1.0e6, 0, "ciclos")
        self.f_user = _spin(0, 1, 0, 3)
        self.f_user.setSpecialValueText("auto (Shigley)")
        mg = QGroupBox("Material (valores digitados por você)")
        f = QFormLayout(mg)
        f.addRow(self.mat_name)
        f.addRow(self.pick_btn)
        for lab, w in (("Su", self.su), ("Sy", self.sy), ("Se' (corpo de prova)", self.se_p)):
            f.addRow(lab, w)
        f.addRow(self.est)
        f.addRow(self.knee)
        f.addRow("Nk (ciclos de Se')", self.nk)
        f.addRow("f (σ a 10³ = f·Su)", self.f_user)

        self.surface = QComboBox()
        self.surface.addItems(list(ft.SURFACES))
        self.d_eq = _spin(0, 1000, 0, 2, "mm")
        self.load_type = QComboBox()
        self.load_type.addItems(list(ft.LOAD_KC))
        self.load_type.setCurrentText("Combinado")
        self.kd = _spin(0.1, 2, 1, 3)
        self.rel = QComboBox()
        for r in ft.RELIABILITY:
            self.rel.addItem(f"{r:g} %", r)
        self.rel.setCurrentIndex(list(ft.RELIABILITY).index(99.0))
        self.kf_m = _spin(0.1, 2, 1, 3)
        mr = QGroupBox("Fatores de Marin (Shigley)")
        f = QFormLayout(mr)
        f.addRow("Acabamento", self.surface)
        f.addRow("Diâmetro equivalente (kb)", self.d_eq)
        f.addRow("Tipo de carga (kc)", self.load_type)
        f.addRow("kd (temperatura)", self.kd)
        f.addRow("Confiabilidade (ke)", self.rel)
        f.addRow("kf (outros)", self.kf_m)

        self.sec_kind = QComboBox()
        self.sec_kind.addItems(["Círculo cheio", "Tubo", "Retângulo", "Personalizada"])
        self.sd, self.sdi, self.sb, self.sh = (_spin(0, 5000, 0, 2, "mm") for _ in range(4))
        self.cA, self.cI, self.cc, self.cJ, self.cr = (_spin(0, 1e12, 0, 3) for _ in range(5))
        sg = QGroupBox("Seção resistente")
        f = QFormLayout(sg)
        f.addRow("Tipo", self.sec_kind)
        for lab, w in (("d (ou d externo)", self.sd), ("d interno (tubo)", self.sdi), ("b (retângulo)", self.sb), ("h (retângulo, flexão)", self.sh),
                       ("A (mm²)", self.cA), ("I (mm⁴)", self.cI), ("c (mm)", self.cc), ("J (mm⁴)", self.cJ), ("r (mm)", self.cr)):
            f.addRow(lab, w)

        self.ld = {}
        lg = QGroupBox("Carregamento por ciclo (mín … máx)")
        f = QFormLayout(lg)
        for key, lab, unit in (("axial", "Força axial", "N"), ("bending", "Momento fletor", "N·mm"), ("torsion", "Torque", "N·mm")):
            lo, hi = _spin(-1e12, 1e12, 0, 1, unit), _spin(-1e12, 1e12, 0, 1, unit)
            self.ld[key] = (lo, hi)
            row = QHBoxLayout()
            row.addWidget(lo)
            row.addWidget(hi)
            f.addRow(lab, row)
        self.kt, self.q = {}, {}
        cg = QGroupBox("Concentração de tensões (Kt e sensibilidade q)")
        f = QFormLayout(cg)
        for key, lab in (("axial", "Axial"), ("bending", "Flexão"), ("torsion", "Torção")):
            kt, q = _spin(1, 20, 1, 3), _spin(0, 1, 1, 3)
            self.kt[key], self.q[key] = kt, q
            row = QHBoxLayout()
            row.addWidget(QLabel("Kt"))
            row.addWidget(kt)
            row.addWidget(QLabel("q"))
            row.addWidget(q)
            f.addRow(lab, row)
        self.criterion = QComboBox()
        self.criterion.addItems(list(ft.CRITERIA))
        self.life_rule = QComboBox()
        self.life_rule.addItems(list(ft.LIFE_RULES))
        self.freq = _spin(0.001, 1e6, 50, 3, "Hz")
        og = QGroupBox("Critério e frequência")
        f = QFormLayout(og)
        f.addRow("Critério (coef. de segurança)", self.criterion)
        f.addRow("Tensão equivalente p/ vida", self.life_rule)
        f.addRow("Frequência do ciclo", self.freq)

        form = QWidget()
        fl = QVBoxLayout(form)
        for w in (self.part_label, self.use_sel, mg, mr, sg, lg, cg, og):
            fl.addWidget(w)
        fl.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(form)

        self.out = QLabel("")
        self.out.setWordWrap(True)
        self.out.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.out.setStyleSheet("font-family:Consolas,monospace;")
        self.out.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.plot = SNPlot()
        self.export_btn = QPushButton("Exportar relatório (.txt)…")
        self.export_btn.clicked.connect(self.export_report)
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.addWidget(self.plot)
        rl.addWidget(self.export_btn)
        res_scroll = QScrollArea()
        res_scroll.setWidgetResizable(True)
        res_scroll.setWidget(self.out)
        rl.addWidget(res_scroll, 1)
        sp = QSplitter(Qt.Horizontal)
        sp.addWidget(scroll)
        sp.addWidget(right)
        sp.setSizes([430, 650])

        for w in (self.mat_name,):
            w.textChanged.connect(self.recalc)
        for w in (self.su, self.sy, self.se_p, self.nk, self.f_user, self.d_eq, self.kd, self.kf_m, self.sd, self.sdi, self.sb, self.sh,
                  self.cA, self.cI, self.cc, self.cJ, self.cr, self.freq, *[x for t in self.ld.values() for x in t],
                  *self.kt.values(), *self.q.values()):
            w.valueChanged.connect(self.recalc)
        for w in (self.est, self.knee):
            w.toggled.connect(self.recalc)
        for w in (self.surface, self.load_type, self.rel, self.sec_kind, self.criterion, self.life_rule):
            w.currentIndexChanged.connect(self.recalc)
        return sp

    # ------------------------------------------------------------------ aba 2: Miner
    def _build_miner_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        note = QLabel("Cada linha é um bloco do espectro: σa e σm EQUIVALENTES de von Mises (MPa) e ciclos por repetição. Usa o material, "
                      "fatores de Marin e curva S-N da aba 'Peça'. Regra linear de Miner (sem efeito de sequência).")
        note.setWordWrap(True)
        self.m_table = QTableWidget(0, 3)
        self.m_table.setHorizontalHeaderLabels(["σa (MPa)", "σm (MPa)", "Ciclos por repetição"])
        add = QPushButton("+ Bloco")
        add.clicked.connect(lambda: self.add_block())
        cur = QPushButton("+ Bloco com o ciclo atual da aba 'Peça'")
        cur.clicked.connect(self.add_current_block)
        rm = QPushButton("− Remover linha")
        rm.clicked.connect(lambda: self.m_table.removeRow(self.m_table.currentRow()) if self.m_table.currentRow() >= 0 else None)
        calc = QPushButton("Calcular dano")
        calc.clicked.connect(self.calc_miner)
        self.m_out = QLabel("")
        self.m_out.setWordWrap(True)
        self.m_out.setStyleSheet("font-family:Consolas,monospace;")
        row = QHBoxLayout()
        for b in (add, cur, rm, calc):
            row.addWidget(b)
        for x in (note,):
            lay.addWidget(x)
        lay.addLayout(row)
        lay.addWidget(self.m_table, 1)
        lay.addWidget(self.m_out)
        return w

    def add_block(self, sa: float = 0.0, sm: float = 0.0, n: float = 0.0) -> None:
        r = self.m_table.rowCount()
        self.m_table.insertRow(r)
        for c, v in enumerate((sa, sm, n)):
            self.m_table.setItem(r, c, QTableWidgetItem(f"{v:g}"))

    def add_current_block(self) -> None:
        if self.result is None:
            self.m_out.setText("Defina antes um caso válido na aba 'Peça'.")
            return
        self.add_block(round(self.result.stress["sigma_a"], 3), round(self.result.stress["sigma_m"], 3), 1000.0)

    def blocks(self) -> list[ft.Block]:
        out = []
        for r in range(self.m_table.rowCount()):
            try:
                vals = [float(self.m_table.item(r, c).text().replace(",", ".")) for c in range(3)]
            except (AttributeError, ValueError):
                raise ValueError(f"Linha {r + 1}: valores numéricos inválidos.")
            out.append(ft.Block(f"Bloco {r + 1}", *vals))
        return out

    def calc_miner(self) -> Optional[dict]:
        try:
            if self.result is None:
                raise ValueError("Defina antes um caso válido na aba 'Peça'.")
            blocks = self.blocks()
            if not blocks:
                raise ValueError("Adicione ao menos um bloco.")
            res = ft.miner(blocks, self._material(), self.result.curve, self.life_rule.currentText())
        except ValueError as e:
            self.miner_result = None
            self.m_out.setText(f"⚠ {e}")
            return None
        self.miner_result = res
        lines = [f"{r['label']}: σ_ar = {r['sigma_ar']:.1f} MPa · N = {_fmt_cycles(r['N'])} · dano = {r['damage']:.4g}" for r in res["rows"]]
        lines.append(f"Dano por repetição D = {res['damage']:.4g}")
        lines.append("Falha prevista após " + ("— (dano nulo: nenhum ciclo acima do limite de fadiga)" if math.isinf(res["repetitions"]) else
                     f"{res['repetitions']:.4g} repetições ({res['cycles_to_failure']:.4g} ciclos)"))
        if math.isfinite(res["cycles_to_failure"]):
            lines.append(f"≈ {ft.life_hours(res['cycles_to_failure'], self.freq.value()):.4g} h à frequência de {self.freq.value():g} Hz")
        lines += ["• " + n for n in res["notes"]]
        self.m_out.setText("\n".join(lines))
        return res

    # ------------------------------------------------------------------ aba 3: mola
    def _build_spring_tab(self) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        self.sp = {k: _spin(0, 1e7, v, 3, u) for k, v, u in (
            ("wire_d", 0, "mm"), ("coil_d", 0, "mm"), ("active_coils", 0, ""), ("total_coils", 0, ""), ("installed_len", 0, "mm"),
            ("lift", 0, "mm"), ("preload_force", 0, "N"), ("g_mpa", 0, "MPa"), ("su", 0, "MPa"), ("sse", 0, "MPa"), ("ssu", 0, "MPa"))}
        self.sp["ssu"].setSpecialValueText("auto (0,67·Su)")
        self.sp_density = QLabel("Densidade: (escolha no banco)")
        pick = QPushButton("Material do fio (densidade)…")
        pick.clicked.connect(self.pick_material)
        preset = QPushButton("Preencher geometria da mola de válvula do motor de exemplo")
        preset.clicked.connect(self.spring_preset)
        calc = QPushButton("Calcular mola")
        calc.clicked.connect(self.calc_spring)
        self.vt_mass = _spin(0, 5000, 0, 1, "g")
        self.vt_rpm = _spin(100, 40000, 6000, 0, "rpm")
        self.vt_damp = _spin(0, 1e5, 0, 2, "N·s/m")
        self.vt_btn = QPushButton("Dinâmica da válvula (corpo rígido, perfil do came do motor de exemplo)")
        self.vt_btn.clicked.connect(self.calc_valvetrain)
        self.vt_result: Optional[dict] = None
        g = QGroupBox("Mola helicoidal de compressão")
        f = QFormLayout(g)
        for lab, k in (("d do fio", "wire_d"), ("D médio", "coil_d"), ("Espiras ativas Na", "active_coils"), ("Espiras totais Nt", "total_coils"),
                       ("Comprimento montada (válvula fechada)", "installed_len"), ("Curso da válvula", "lift"),
                       ("Força com a válvula fechada (você define)", "preload_force"), ("G do fio (você digita)", "g_mpa"),
                       ("Su do fio", "su"), ("Sse (fadiga em cisalhamento — ensaio/norma)", "sse"), ("Ssu", "ssu")):
            f.addRow(lab, self.sp[k])
        f.addRow(self.sp_density)
        f.addRow(pick)
        f.addRow(preset)
        f.addRow(calc)
        f.addRow("Massa equivalente do trem (você define)", self.vt_mass)
        f.addRow("Rotação do virabrequim", self.vt_rpm)
        f.addRow("Amortecimento c", self.vt_damp)
        f.addRow(self.vt_btn)
        self.s_out = QLabel("")
        self.s_out.setWordWrap(True)
        self.s_out.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.s_out.setStyleSheet("font-family:Consolas,monospace;")
        lay.addWidget(g)
        lay.addWidget(self.s_out, 1)
        return w

    def spring_preset(self) -> None:
        """Geometria da mola modelada no exemplo (fio r=1,5; D=15; 6 espiras; 30 mm montada; curso da came). Resistência: você digita."""
        from samples.motor_4_cilindros import SPRING_Z0, SPRING_Z1, cam_table
        for k, v in (("wire_d", 3.0), ("coil_d", 15.0), ("active_coils", 6.0), ("total_coils", 6.0),
                     ("installed_len", SPRING_Z1 - SPRING_Z0), ("lift", round(max(cam_table(True)), 3))):
            self.sp[k].setValue(v)
        self.s_out.setText("Geometria preenchida a partir do modelo (espiras sem fechamento de ponta: Na = Nt). Faltam os dados do FIO: G, Su, "
                           "Sse e a força de montagem — digite-os a partir da folha de dados.")

    def calc_spring(self) -> Optional[dict]:
        try:
            if self._density is None:
                raise ValueError("Escolha o material do fio no banco (densidade) — ele só fornece a densidade.")
            vals = {k: w.value() for k, w in self.sp.items()}
            vals["ssu"] = vals["ssu"] or None
            res = ft.spring_analysis(ft.SpringInputs(density_g_cm3=self._density, **vals))
        except (ValueError, ZeroDivisionError) as e:
            self.spring_result = None
            self.s_out.setText(f"⚠ {e}")
            return None
        self.spring_result = res
        txt = [f"Índice de mola C = {res['C']:.2f}", f"Taxa k = {res['k']:.3f} N/mm",
               f"Força: {res['f_min']:.1f} N (fechada) → {res['f_max']:.1f} N (máx.)",
               f"Cisalhamento: τa = {res['tau_a']:.1f} MPa (Bergsträsser) · τm = {res['tau_m']:.1f} MPa",
               f"Coef. de segurança à fadiga (Goodman em cisalhamento, Sse={self.sp['sse'].value():.0f}, Ssu={res['ssu']:.0f}) n = {res['n_f']:.2f}",
               f"Altura sólida = {res['solid_len']:.1f} mm · comprimento mínimo em operação = {res['min_len']:.1f} mm · folga até a sólida = "
               f"{res['clearance_to_solid']:.1f} mm",
               f"Massa da mola ≈ {res['mass_kg'] * 1000:.1f} g",
               f"Frequência natural (surto, extremos fixos) fn = {res['fn_hz']:.0f} Hz → rotação do virabrequim sem ressonância pela regra 13× "
               f"(Shigley) ≲ {res['max_rpm_13x']:.0f} rpm"]
        txt += ["⚠ " + w for w in res["warnings"]]
        txt.append("• Não inclui dinâmica de válvula (flutuação), amortecimento, pré-tensão residual nem jateamento (shot peening).")
        self.s_out.setText("\n".join(txt))
        return res

    def calc_valvetrain(self) -> Optional[dict]:
        """Força de contato came–seguidor e rotação de flutuação (corpo rígido); usa k e a força de montagem da mola calculada."""
        try:
            if self.spring_result is None and self.calc_spring() is None:
                raise ValueError("Calcule antes a mola (k vem dela) — preencha o fio e a força de montagem.")
            if self.vt_mass.value() <= 0:
                raise ValueError("Informe a massa equivalente do trem (válvula + prato + 1/3 da mola + seguidor), em g.")
            from samples.motor_mechanism import valve_diagram
            d = valve_diagram(0)
            sr = self.spring_result
            res = vt.analyze_valvetrain(d["int"]["lift"], d["step"], self.vt_rpm.value(), self.vt_mass.value() / 1000.0, sr["k"],
                                        sr["f_min"], self.vt_damp.value())
        except ValueError as e:
            self.vt_result = None
            self.s_out.setText(self.s_out.text().split("\n\n— Dinâmica")[0] + f"\n\n⚠ {e}")
            return None
        self.vt_result = res
        fl = res["float_rpm"]
        extra = [f"— Dinâmica da válvula (corpo rígido) a {self.vt_rpm.value():.0f} rpm, m = {self.vt_mass.value():.1f} g:",
                 f"Força de contato: mín. {res['f_min']:.1f} N (a {res['angle_at_min_deg']:.0f}°) · máx. {res['f_max']:.1f} N",
                 "Rotação de flutuação (força mínima = 0): " + ("não ocorre até 40000 rpm" if math.isinf(fl) else
                                                               "já em repouso (pré-carga insuficiente)" if fl == 0 else f"≈ {fl:.0f} rpm"),
                 ("⚠ FLUTUA nesta rotação: o seguidor perde o contato." if res["floats"] else "Mantém contato nesta rotação (no modelo rígido)."),
                 "• " + res["notes"][0]]
        base = self.s_out.text().split("\n\n— Dinâmica")[0]
        self.s_out.setText(base + "\n\n" + "\n".join(extra))
        return res

    # ------------------------------------------------------------------ ações
    def use_selected(self) -> None:
        name = self._selected_name() or ""
        self.part_label.setText(f"Peça: {name}" if name else "Peça: (nenhuma selecionada)")
        self.recalc()

    def pick_material(self) -> None:
        from interface.material_picker import MaterialPicker
        dlg = MaterialPicker(self.library, self)
        if dlg.exec() and dlg.selected:
            m = self.library.get(dlg.selected)
            self._density = m.density_g_cm3
            self.mat_name.setText(m.name)
            self.sp_density.setText(f"Densidade: {m.density_g_cm3:g} g/cm³ ({m.name})")
            self.recalc()

    def _material(self) -> ft.FatigueMaterial:
        return ft.FatigueMaterial(self.mat_name.text() or "Material", self.su.value(), self.sy.value(), self.se_p.value() or None,
                                  self.est.isChecked(), self.knee.isChecked(), self.nk.value(), self.f_user.value() or None)

    def _inputs(self):
        sec = ft.Section(self.sec_kind.currentText(), d=self.sd.value(), di=self.sdi.value(), b=self.sb.value(), h=self.sh.value(),
                         A=self.cA.value(), I=self.cI.value(), c=self.cc.value(), J=self.cJ.value(), r=self.cr.value())
        load = ft.LoadRange(*[tuple(sorted((self.ld[k][0].value(), self.ld[k][1].value()))) for k in ("axial", "bending", "torsion")])
        conc = ft.Concentration(self.kt["axial"].value(), self.kt["bending"].value(), self.kt["torsion"].value(),
                                self.q["axial"].value(), self.q["bending"].value(), self.q["torsion"].value())
        mar = ft.MarinInputs(self.surface.currentText(), self.d_eq.value(), self.load_type.currentText(), self.kd.value(),
                             float(self.rel.currentData()), self.kf_m.value())
        return self._material(), mar, sec, load, conc

    def recalc(self, *_) -> None:
        if self._building:
            return
        try:
            res = ft.analyze(*self._inputs(), life_rule=self.life_rule.currentText())
        except (ValueError, ZeroDivisionError) as e:
            self.result = None
            self.plot.set_data(None, None, None)
            self.out.setText(f"⚠ {e}")
            return
        self.result = res
        self.plot.set_data(res.curve, res.sigma_ar, res.cycles)
        self.out.setText(self._result_text(res))

    def _result_text(self, r: ft.FatigueResult) -> str:
        se = r.se
        crit = self.criterion.currentText()
        lines = [self.part_label.text(), "",
                 f"Se' = {se['se_prime']:.1f} MPa{' (ESTIMADO)' if se['estimated'] else ''}",
                 f"ka={se['ka']:.3f} kb={se['kb']:.3f} kc={se['kc']:.3f} kd={se['kd']:.3f} ke={se['ke']:.3f} kf={se['kf']:.3f}",
                 f"Se (corrigido) = {se['se']:.1f} MPa", "",
                 f"σa equivalente = {r.stress['sigma_a']:.1f} MPa · σm equivalente = {r.stress['sigma_m']:.1f} MPa · σmax = {r.stress['sigma_max']:.1f} MPa",
                 "Kf: " + " · ".join(f"{k} {v:.3f}" for k, v in r.stress["kf"].items()), "",
                 "Coeficientes de segurança (linha de carga proporcional):"]
        for k, v in r.factors.items():
            mark = "◀" if k == crit else " "
            lines.append(f"  {k:<22} {'∞' if math.isinf(v) else f'{v:.2f}'} {mark}")
        lines += ["", f"σ_ar ({self.life_rule.currentText()}) = {r.sigma_ar:.1f} MPa",
                  "Vida: " + _fmt_cycles(r.cycles) + (f" ciclos = {ft.life_hours(r.cycles, self.freq.value()):.4g} h a {self.freq.value():g} Hz"
                                                       if math.isfinite(r.cycles) and r.cycles > 0 else "")]
        n = r.factors[crit]
        verdict = "ATENDE ao critério (n ≥ 1)" if n >= 1 else "NÃO ATENDE (n < 1)"
        lines += ["", f"Veredito pelo critério {crit}: {verdict} — {'sem fator de projeto adicional' if n >= 1 else 'falha prevista por fadiga'}"]
        lines += ["", *["⚠ " + w for w in r.warnings]]
        return "\n".join(lines)

    def report_text(self) -> str:
        parts = ["NEXUS ENGINEERING LAB — Simulação de fadiga (análise analítica, tensões nominais)", self.part_label.text(), ""]
        parts.append(self.out.text())
        if self.miner_result:
            parts += ["", "--- Espectro de cargas (Miner) ---", self.m_out.text()]
        if self.spring_result:
            parts += ["", "--- Mola helicoidal (e dinâmica da válvula, se calculada) ---", self.s_out.text()]
        parts += ["", "Limites: não é elementos finitos; propriedades digitadas pelo usuário; Marin/S-N de livro-texto para aço; sem efeitos de "
                      "sequência, tensões residuais, corrosão ou temperatura além dos fatores informados."]
        return "\n".join(parts)

    def export_report(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Exportar relatório de fadiga", "fadiga.txt", "Texto (*.txt)")
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.report_text())
