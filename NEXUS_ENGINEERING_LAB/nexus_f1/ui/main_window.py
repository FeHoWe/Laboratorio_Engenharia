"""Janela principal — NEXUS F1 Performance Simulator (PySide6)."""
from __future__ import annotations

import json
import time
import traceback
from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QFont
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox,
                               QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QMainWindow, QMessageBox,
                               QPushButton, QScrollArea, QSlider, QSpinBox, QSplitter, QTableWidget, QTableWidgetItem,
                               QTabWidget, QTextEdit, QVBoxLayout, QWidget)

from ..core import circuits, regulations, report
from ..core import tires as T
from ..core.api import simulate_lap
from ..core.compare import compare_configs
from ..core.config import AERO_PRESETS, CarConfig, Environment, default_car
from ..core.laptime import format_time
from ..core.regulations import RegulationError
from ..core.strategy import StrategyModel, default_strategies
from ..engine_audio import AudioSettings, PROFILES, RealtimeEngineSynth, SimulationAudio, write_wav
from ..engine_audio.player import AudioPlayer
from . import style
from .analysis_tab import AnalysisTab
from .widgets import PlotStack, TrackView


class _Sig(QObject):
    done = Signal(object)
    fail = Signal(str)


class Job(QRunnable):
    def __init__(self, fn):
        super().__init__()
        self.fn, self.sig = fn, _Sig()

    def run(self):
        try:
            self.sig.done.emit(self.fn())
        except Exception as e:  # noqa: BLE001
            self.sig.fail.emit(str(e) if isinstance(e, RegulationError) else f"{e}\n{traceback.format_exc()}")


def _spin(lo, hi, val, step=1.0, dec=1, suffix=""):
    s = QDoubleSpinBox(); s.setRange(lo, hi); s.setDecimals(dec); s.setSingleStep(step); s.setValue(val)
    if suffix: s.setSuffix(suffix)
    return s


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NEXUS F1 PERFORMANCE SIMULATOR")
        self.resize(1480, 900)
        self.pool = QThreadPool.globalInstance()
        self.res = None
        self.slots: dict[str, CarConfig] = {}
        self.audio = AudioPlayer()
        self._audio_cache = {}
        self.playing = False
        self._t0_wall = 0.0
        self._t0_sim = 0.0
        self._audio_on_play = False
        self.timer = QTimer(self); self.timer.setInterval(16); self.timer.timeout.connect(self._tick)
        self._build_ui()
        self._on_season_changed()
        self._menu()
        self.statusBar().showMessage("Pronto. Configure o carro e clique em SIMULAR VOLTA.")

    # =========================================================================== UI
    def _build_ui(self):
        central = QWidget(); self.setCentralWidget(central)
        root = QHBoxLayout(central); root.setContentsMargins(8, 8, 8, 8)
        split = QSplitter(Qt.Horizontal); root.addWidget(split)
        # ---------------- painel de configuração
        left = QWidget(); lv = QVBoxLayout(left); lv.setContentsMargins(0, 0, 0, 0)
        t = QLabel("NEXUS  F1"); t.setObjectName("title"); lv.addWidget(t)
        s = QLabel("Simulador de desempenho · engenharia · telemetria · áudio"); s.setObjectName("sub"); lv.addWidget(s)
        sc = QScrollArea(); sc.setWidgetResizable(True); inner = QWidget(); il = QVBoxLayout(inner); sc.setWidget(inner)
        lv.addWidget(sc, 1)

        g = QGroupBox("REGULAMENTO"); f = QFormLayout(g)
        self.cb_season = QComboBox(); self.cb_season.addItems(list(regulations.list_seasons()))
        self.cb_mode = QComboBox(); self.cb_mode.addItem("Regulamentar", "regulatory"); self.cb_mode.addItem("Experimental", "experimental")
        f.addRow("Temporada", self.cb_season); f.addRow("Modo", self.cb_mode)
        self.lb_reg = QLabel(""); self.lb_reg.setWordWrap(True); f.addRow(self.lb_reg)
        il.addWidget(g)

        g = QGroupBox("CIRCUITO E AMBIENTE"); f = QFormLayout(g)
        self.cb_track = QComboBox()
        for k in circuits.list_circuits():
            self.cb_track.addItem(circuits._C[k]["name"], k)
        self.sp_air = _spin(-5, 50, 25, 1, 0, " °C"); self.sp_trk = _spin(0, 70, 38, 1, 0, " °C")
        self.sp_wet = _spin(0, 1, 0, 0.05, 2); self.sp_wear = _spin(0, 1.5, 0, 0.05, 2)
        f.addRow("Circuito", self.cb_track); f.addRow("Ar", self.sp_air); f.addRow("Pista", self.sp_trk)
        f.addRow("Umidade (0-1)", self.sp_wet); f.addRow("Desgaste inicial", self.sp_wear)
        il.addWidget(g)

        g = QGroupBox("CARRO"); f = QFormLayout(g)
        self.cb_aero = QComboBox(); self.cb_aero.addItems(list(AERO_PRESETS)); self.cb_aero.addItem("custom")
        self.sp_cda = _spin(0.5, 2.0, 1.1, 0.01, 2, " m²"); self.sp_cla = _spin(1.0, 6.0, 3.8, 0.05, 2, " m²")
        self.sp_mass = _spin(500, 1000, 800, 1, 0, " kg"); self.sp_fuel = _spin(0, 120, 40, 1, 0, " kg")
        self.sp_ice = _spin(100, 800, 560, 5, 0, " kW"); self.sp_k = _spin(0, 500, 120, 5, 0, " kW")
        self.cb_comp = QComboBox()
        self.sp_shift = _spin(8000, 16000, 13200, 100, 0, " rpm"); self.sp_fd = _spin(2.5, 6, 4.0, 0.05, 2)
        self.ed_gears = QLineEdit(); self.sp_bias = _spin(0.4, 0.75, 0.58, 0.01, 2)
        for lab, w in (("Aero", self.cb_aero), ("Cd·A", self.sp_cda), ("Cl·A", self.sp_cla), ("Massa (sem comb.)", self.sp_mass),
                       ("Combustível", self.sp_fuel), ("Motor (pico)", self.sp_ice), ("MGU-K", self.sp_k), ("Pneu", self.cb_comp),
                       ("Troca de marcha", self.sp_shift), ("Relação final", self.sp_fd), ("Marchas", self.ed_gears),
                       ("Balanço de freio", self.sp_bias)):
            f.addRow(lab, w)
        il.addWidget(g); il.addStretch(1)

        self.btn_sim = QPushButton("SIMULAR VOLTA"); self.btn_sim.setObjectName("primary")
        lv.addWidget(self.btn_sim)
        row = QHBoxLayout()
        self.btn_csv = QPushButton("CSV"); self.btn_json = QPushButton("JSON"); self.btn_rep = QPushButton("Relatório"); self.btn_mob = QPushButton("Mobile")
        for b in (self.btn_csv, self.btn_json, self.btn_rep, self.btn_mob): row.addWidget(b)
        lv.addLayout(row)
        left.setMinimumWidth(300); left.setMaximumWidth(380)
        split.addWidget(left)

        # ---------------- centro
        right = QWidget(); rv = QVBoxLayout(right); rv.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget(); rv.addWidget(self.tabs, 1)
        self.track_view = TrackView(); self.plots = PlotStack()
        self.tabs.addTab(self.track_view, "Pista")
        self.tabs.addTab(self.plots, "Telemetria")
        self.tabs.addTab(self._tab_summary(), "Resultados")
        self.tabs.addTab(self._tab_compare(), "Comparar")
        self.tabs.addTab(AnalysisTab(self), "Análise")
        self.tabs.addTab(self._tab_tyres(), "Pneus")
        self.tabs.addTab(self._tab_strategy(), "Estratégia")
        self.tabs.addTab(self._tab_regs(), "Regulamento")
        self.tabs.addTab(self._tab_audio(), "Áudio")
        self.tabs.addTab(self._tab_report(), "Relatório")
        # barra de reprodução
        bar = QHBoxLayout()
        self.btn_play = QPushButton("▶  Reproduzir"); self.btn_stop = QPushButton("⏮")
        self.chk_audio = QCheckBox("com áudio"); self.chk_audio.setChecked(True)
        self.cb_speed = QComboBox()
        for sp in (0.25, 0.5, 1.0, 2.0, 4.0): self.cb_speed.addItem(f"{sp}x", sp)
        self.cb_speed.setCurrentIndex(2)
        self.sl_time = QSlider(Qt.Horizontal); self.sl_time.setRange(0, 1000)
        self.lb_time = QLabel("0:00.000")
        for w in (self.btn_stop, self.btn_play, self.chk_audio, QLabel("vel."), self.cb_speed): bar.addWidget(w)
        bar.addWidget(self.sl_time, 1); bar.addWidget(self.lb_time)
        rv.addLayout(bar)
        split.addWidget(right); split.setStretchFactor(1, 1)

        # ---------------- sinais
        self.cb_season.currentIndexChanged.connect(self._on_season_changed)
        self.cb_mode.currentIndexChanged.connect(self._refresh_reg_label)
        self.cb_aero.currentTextChanged.connect(self._on_aero)
        self.btn_sim.clicked.connect(self.simulate)
        self.btn_play.clicked.connect(self.toggle_play)
        self.btn_stop.clicked.connect(self.restart)
        self.sl_time.sliderMoved.connect(self._seek_slider)
        self.plots.cursor_s.connect(self._seek_s)
        self.track_view.observer_picked.connect(self._observer_picked)
        self.btn_csv.clicked.connect(lambda: self._export("csv"))
        self.btn_json.clicked.connect(lambda: self._export("json"))
        self.btn_rep.clicked.connect(lambda: self._export("md"))
        self.btn_mob.clicked.connect(self.export_mobile)

    def _menu(self):
        m = self.menuBar().addMenu("&Arquivo")
        a = QAction("Salvar configuração...", self); a.triggered.connect(self.save_cfg); m.addAction(a)
        a = QAction("Carregar configuração...", self); a.triggered.connect(self.load_cfg); m.addAction(a)
        m.addSeparator()
        a = QAction("Sair", self); a.triggered.connect(self.close); m.addAction(a)

    # ---- abas -----------------------------------------------------------------
    def _table(self):
        t = QTableWidget(); t.setEditTriggers(QTableWidget.NoEditTriggers); t.setAlternatingRowColors(False)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); t.verticalHeader().setVisible(False)
        return t

    def _tab_summary(self):
        w = QWidget(); v = QVBoxLayout(w)
        self.lb_big = QLabel("—"); self.lb_big.setFont(QFont("Consolas", 34, QFont.Bold)); self.lb_big.setStyleSheet(f"color:{style.CYAN}")
        self.lb_status = QLabel(""); self.lb_status.setWordWrap(True)
        self.tb_sum = self._table(); self.tb_seg = self._table()
        v.addWidget(self.lb_big); v.addWidget(self.lb_status)
        h = QHBoxLayout(); h.addWidget(self.tb_sum, 1); h.addWidget(self.tb_seg, 2); v.addLayout(h, 1)
        return w

    def _tab_compare(self):
        w = QWidget(); v = QVBoxLayout(w)
        h = QHBoxLayout()
        self.slot_btns = {}
        for n in "ABC":
            b = QPushButton(f"Salvar atual como {n}"); b.clicked.connect(lambda _=False, n=n: self._save_slot(n)); h.addWidget(b); self.slot_btns[n] = b
        self.btn_cmp = QPushButton("COMPARAR NO CIRCUITO SELECIONADO"); self.btn_cmp.setObjectName("primary"); self.btn_cmp.clicked.connect(self.run_compare)
        h.addWidget(self.btn_cmp); v.addLayout(h)
        self.lb_slots = QLabel("Nenhuma configuração salva. Ajuste o carro, salve em A/B/C e compare."); self.lb_slots.setWordWrap(True)
        v.addWidget(self.lb_slots)
        self.lb_cmp = QLabel(""); self.lb_cmp.setFont(QFont("Segoe UI", 12, QFont.Bold)); v.addWidget(self.lb_cmp)
        self.tb_cmp = self._table(); v.addWidget(self.tb_cmp, 1)
        return w

    def _tab_tyres(self):
        w = QWidget(); v = QVBoxLayout(w)
        self.btn_tyres = QPushButton("COMPARAR COMPOSTOS (condições e carro atuais)"); self.btn_tyres.setObjectName("primary")
        self.btn_tyres.clicked.connect(self.run_tyres); v.addWidget(self.btn_tyres)
        self.tb_tyre = self._table(); v.addWidget(self.tb_tyre, 1)
        self.lb_tyre = QLabel(""); self.lb_tyre.setWordWrap(True); v.addWidget(self.lb_tyre)
        return w

    def _tab_strategy(self):
        w = QWidget(); v = QVBoxLayout(w)
        h = QHBoxLayout()
        self.sp_laps = QSpinBox(); self.sp_laps.setRange(5, 90); self.sp_laps.setValue(52)
        self.sp_pit = _spin(10, 40, 22, 0.5, 1, " s"); self.sp_stops = QSpinBox(); self.sp_stops.setRange(1, 3); self.sp_stops.setValue(2)
        for lab, wd in (("Voltas", self.sp_laps), ("Perda no box (parâmetro)", self.sp_pit), ("Máx. paradas", self.sp_stops)):
            h.addWidget(QLabel(lab)); h.addWidget(wd)
        self.btn_strat = QPushButton("COMPARAR / OTIMIZAR"); self.btn_strat.setObjectName("primary"); self.btn_strat.clicked.connect(self.run_strategy)
        h.addWidget(self.btn_strat); v.addLayout(h)
        self.tb_strat = self._table(); v.addWidget(self.tb_strat, 1)
        self.lb_strat = QLabel(""); self.lb_strat.setWordWrap(True); v.addWidget(self.lb_strat)
        return w

    def _tab_regs(self):
        w = QWidget(); v = QVBoxLayout(w)
        self.lb_season_doc = QLabel(""); self.lb_season_doc.setWordWrap(True); v.addWidget(self.lb_season_doc)
        self.tb_regs = self._table(); v.addWidget(self.tb_regs, 1)
        b = QPushButton("Criar nova temporada a partir da atual..."); b.clicked.connect(self.new_season); v.addWidget(b)
        return w

    def _tab_audio(self):
        w = QWidget(); f = QFormLayout(w)
        self.chk_au_on = QCheckBox("Áudio ativado"); self.chk_au_on.setChecked(True)
        self.cb_prof = QComboBox()
        for k, p in PROFILES.items(): self.cb_prof.addItem(p.label, k)
        self.cb_mode_au = QComboBox(); self.cb_mode_au.addItem("Ao lado da pista (Doppler)", "trackside"); self.cb_mode_au.addItem("Onboard", "onboard")
        self.sl_master = self._vol(80); self.sl_eng = self._vol(100); self.sl_amb = self._vol(35); self.sl_fx = self._vol(60); self.sl_int = self._vol(100)
        self.sp_off = _spin(5, 150, 25, 5, 0, " m"); self.lb_obs = QLabel("Clique na pista (aba Pista) para escolher onde está o ouvinte.")
        self.btn_test = QPushButton("Testar som do motor"); self.btn_wav = QPushButton("Exportar áudio da volta (WAV)")
        for lab, wd in (("", self.chk_au_on), ("Perfil sonoro", self.cb_prof), ("Perspectiva", self.cb_mode_au), ("Volume geral", self.sl_master),
                        ("Motor", self.sl_eng), ("Ambiente", self.sl_amb), ("Efeitos", self.sl_fx), ("Intensidade do motor", self.sl_int),
                        ("Distância lateral do ouvinte", self.sp_off), ("", self.lb_obs), ("", self.btn_test), ("", self.btn_wav)):
            f.addRow(lab, wd)
        info = QLabel("Som sintetizado proceduralmente a partir do RPM, carga, marcha e posição do carro (sem loops de arquivo). "
                      "Reprodução local via QtMultimedia/sounddevice quando houver saída de áudio; sempre é possível exportar WAV.")
        info.setWordWrap(True); info.setObjectName("sub"); f.addRow(info)
        self.btn_test.clicked.connect(self.test_engine); self.btn_wav.clicked.connect(self.export_wav)
        self.sl_master.valueChanged.connect(lambda v: self.audio.set_volume(v / 100))
        return w

    def _vol(self, v):
        s = QSlider(Qt.Horizontal); s.setRange(0, 150); s.setValue(v); return s

    def _tab_report(self):
        self.tx_rep = QTextEdit(); self.tx_rep.setReadOnly(True); self.tx_rep.setFont(QFont("Consolas", 10)); return self.tx_rep

    # =========================================================================== estado <-> controles
    def _on_season_changed(self):
        sid = self.cb_season.currentText()
        self.season = regulations.get_season(sid)
        car = default_car(sid if sid in ("2025", "2026") else "2025"); car.season = sid
        self.cb_comp.clear()
        for c in self.season.compounds["allowed"]:
            self.cb_comp.addItem(self.season.compounds["labels"].get(c, c), c)
        self.cb_comp.setCurrentIndex(self.season.compounds["allowed"].index("medium"))
        self._load_car_into_ui(car)
        self._refresh_reg_label()
        self._fill_regs()

    def _load_car_into_ui(self, car: CarConfig):
        self.cb_aero.blockSignals(True)
        self.cb_aero.setCurrentText(car.aero_preset if car.aero_preset in AERO_PRESETS else "custom")
        self.cb_aero.blockSignals(False)
        self.sp_cda.setValue(car.cda); self.sp_cla.setValue(car.cla); self.sp_mass.setValue(car.mass_kg)
        self.sp_fuel.setValue(min(car.fuel_start_kg, 40)); self.sp_ice.setValue(car.ice_pmax_kw); self.sp_k.setValue(car.mguk_kw)
        self.sp_shift.setValue(car.shift_rpm); self.sp_fd.setValue(car.final_drive); self.sp_bias.setValue(car.brake_bias_front)
        self.ed_gears.setText(", ".join(f"{g:.2f}" for g in car.gear_ratios))
        self._base_car = car
        i = self.cb_comp.findData(car.compound)
        if i >= 0: self.cb_comp.setCurrentIndex(i)

    def _on_aero(self, name):
        if name in AERO_PRESETS:
            p = AERO_PRESETS[name]
            self.sp_cda.setValue(p["cda"]); self.sp_cla.setValue(p["cla"])

    def current_car(self) -> CarConfig:
        c = self._base_car.copy()
        c.season = self.cb_season.currentText(); c.mode = self.cb_mode.currentData()
        c.aero_preset = self.cb_aero.currentText()
        if c.aero_preset in AERO_PRESETS:
            c.aero_front_frac = AERO_PRESETS[c.aero_preset]["front"]
        c.cda, c.cla = self.sp_cda.value(), self.sp_cla.value()
        c.mass_kg, c.fuel_start_kg = self.sp_mass.value(), max(self.sp_fuel.value(), self._base_car.fuel_start_kg if False else 0)
        c.ice_pmax_kw, c.mguk_kw = self.sp_ice.value(), self.sp_k.value()
        c.shift_rpm, c.final_drive, c.brake_bias_front = self.sp_shift.value(), self.sp_fd.value(), self.sp_bias.value()
        c.compound = self.cb_comp.currentData()
        try:
            c.gear_ratios = [float(x) for x in self.ed_gears.text().replace(";", ",").split(",") if x.strip()]
        except ValueError:
            pass
        if c.mode == "experimental" or True:
            pass
        c.name = "Atual"
        return c

    def current_env(self) -> Environment:
        return Environment(self.sp_air.value(), self.sp_trk.value(), self.sp_wet.value())

    def _refresh_reg_label(self):
        if self.cb_mode.currentData() == "regulatory":
            self.lb_reg.setText("Somente configurações compatíveis com o regulamento selecionado."); self.lb_reg.setObjectName("good")
        else:
            self.lb_reg.setText("EXPERIMENTAL: a configuração pode não ser regulamentar (desvios serão listados)."); self.lb_reg.setObjectName("warn")
        self.lb_reg.setStyleSheet(f"color:{style.GREEN if self.cb_mode.currentData() == 'regulatory' else style.AMBER}")

    def _fill_regs(self):
        s = self.season
        self.lb_season_doc.setText(f"<b>{s.name}</b><br>Documento: {s.official_document}<br>{s.notes}")
        keys = list(s.params)
        self.tb_regs.setColumnCount(4); self.tb_regs.setHorizontalHeaderLabels(["Parâmetro", "Valor", "Status", "Fonte / observação"])
        self.tb_regs.setRowCount(len(keys) + 1)
        col = {"regulation_reference": style.AMBER, "estimate": style.MUTED, "unconfirmed": style.RED}
        for r, k in enumerate(keys):
            p = s.params[k]
            vals = [k, "—" if p.get("v") is None else json.dumps(p["v"], ensure_ascii=False), p.get("status", ""), p.get("src", "")]
            for c, t in enumerate(vals):
                it = QTableWidgetItem(t)
                if c == 2: it.setForeground(QColor(col.get(t, style.TEXT)))
                self.tb_regs.setItem(r, c, it)
        r = len(keys)
        for c, t in enumerate(["pneus (compostos)", ", ".join(s.compounds["allowed"]), s.compounds.get("status", ""), s.compounds.get("src", "")]):
            self.tb_regs.setItem(r, c, QTableWidgetItem(t))

    # =========================================================================== simulação
    def _async(self, fn, done, busy: str):
        self.statusBar().showMessage(busy)
        QApplication.setOverrideCursor(Qt.BusyCursor)
        job = Job(fn)
        def ok(r):
            QApplication.restoreOverrideCursor(); done(r)
        def bad(msg):
            QApplication.restoreOverrideCursor(); self.statusBar().showMessage("Erro."); QMessageBox.warning(self, "Não foi possível executar", msg[:1500])
        job.sig.done.connect(ok); job.sig.fail.connect(bad)
        self.pool.start(job)

    def simulate(self):
        car, env, key = self.current_car(), self.current_env(), self.cb_track.currentData()
        wear, fuel = self.sp_wear.value(), self.sp_fuel.value()
        self._async(lambda: simulate_lap(key, car, env, wear=wear, fuel_kg=fuel), self._on_result, "Simulando volta...")

    def _on_result(self, res):
        self.stop_playback()
        self.res = res
        self._audio_cache.clear()
        self.track_view.set_result(res)
        self.plots.set_result(res)
        s = res.summary
        self.lb_big.setText(res.fmt_time())
        txt = f"{res.track.name} · {res.compound} · {'REGULAMENTAR' if res.compliant else 'NÃO REGULAMENTAR'}"
        if res.violations:
            txt += "\n" + "\n".join(f"• [{v.severity}] {v.message}" for v in res.violations)
        self.lb_status.setText(txt)
        self.lb_status.setStyleSheet(f"color:{style.GREEN if res.compliant and not res.violations else style.AMBER}")
        rows = [("Velocidade máxima", f"{s['v_max_kmh']:.1f} km/h"), ("Velocidade média", f"{s['v_avg_kmh']:.1f} km/h"),
                ("Velocidade mínima", f"{s['v_min_kmh']:.1f} km/h"), ("Acel. longitudinal máx.", f"{s['a_long_max_g']:.2f} g"),
                ("Desaceleração máx.", f"{s['a_brake_max_g']:.2f} g"), ("Acel. lateral máx.", f"{s['a_lat_max_g']:.2f} g"),
                ("Downforce máx.", f"{s['downforce_max_kn']:.1f} kN"), ("Frenagem total", f"{s['braking_distance_total_m']:.0f} m / {s['n_braking_zones']} zonas"),
                ("Setor 1 / 2 / 3", " / ".join(format_time(t) for t in res.sectors)), ("Tempo curvas / retas", f"{s['time_corners_s']:.2f} / {s['time_straights_s']:.2f} s"),
                ("Combustível", f"{s['fuel_used_kg']:.2f} kg"), ("MGU-K recup./entrega", f"{s['harvest_mj']:.2f} / {s['ers_deploy_mj']:.2f} MJ"),
                ("Temp. pneus", f"{s['tyre_temp_mean_c']:.0f} °C ({s['tyre_temp_min_c']:.0f}-{s['tyre_temp_max_c']:.0f})"),
                ("Desgaste/volta", f"{s['tyre_wear_per_lap'] * 100:.2f} %")]
        self.tb_sum.setColumnCount(2); self.tb_sum.setHorizontalHeaderLabels(["Métrica", "Valor"]); self.tb_sum.setRowCount(len(rows))
        for r, (a, b) in enumerate(rows):
            self.tb_sum.setItem(r, 0, QTableWidgetItem(a)); self.tb_sum.setItem(r, 1, QTableWidgetItem(b))
        self.tb_seg.setColumnCount(6); self.tb_seg.setHorizontalHeaderLabels(["Segmento", "Comp (m)", "Tempo (s)", "V mín", "V máx", "ay máx (g)"])
        self.tb_seg.setRowCount(len(res.segments))
        for r, g in enumerate(res.segments):
            for c, t in enumerate([g["name"], f"{g['length']:.0f}", f"{g['time']:.2f}", f"{g['v_min']:.0f}", f"{g['v_max']:.0f}", f"{g['ay_max']:.2f}"]):
                self.tb_seg.setItem(r, c, QTableWidgetItem(t))
        self.tx_rep.setPlainText(report.lap_report_md(res))
        self.lb_time.setText(format_time(0))
        self.statusBar().showMessage(f"Volta calculada: {res.fmt_time()}  (S1 {format_time(res.sectors[0])} · S2 {format_time(res.sectors[1])} · S3 {format_time(res.sectors[2])})")

    # ---- comparações -------------------------------------------------------------
    def _save_slot(self, n):
        self.slots[n] = self.current_car().copy(name=n)
        self.lb_slots.setText("<br>".join(
            f"<b>{k}</b>: aero {c.aero_preset} (CdA {c.cda:.2f}/ClA {c.cla:.2f}) · pneu {c.compound} · massa {c.mass_kg:.0f} kg · motor {c.ice_pmax_kw:.0f}+{c.mguk_kw:.0f} kW · {c.mode}"
            for k, c in sorted(self.slots.items())))

    def run_compare(self):
        if len(self.slots) < 2:
            QMessageBox.information(self, "Comparar", "Salve pelo menos duas configurações (A, B, C)."); return
        key, env, fuel = self.cb_track.currentData(), self.current_env(), self.sp_fuel.value()
        slots = dict(self.slots)
        self._async(lambda: compare_configs(key, slots, env, fuel), self._on_compare, "Comparando configurações...")

    def _on_compare(self, cmp):
        self.lb_cmp.setText(f"Melhor desempenho calculado: {cmp.winner}  ({format_time(cmp.results[cmp.winner].lap_time)})")
        hdr = ["Config", "Tempo", "Δ (s)", "Vmax", "Vmédia", "Curvas (s)", "Retas (s)", "Frenagem (m)", "ay máx (g)", "T pneu", "Degrad. (s/volta)", "Regulamentar"]
        self.tb_cmp.setColumnCount(len(hdr)); self.tb_cmp.setHorizontalHeaderLabels(hdr); self.tb_cmp.setRowCount(len(cmp.ranking))
        for r, n in enumerate(cmp.ranking):
            m = cmp.metrics[n]
            vals = [n, format_time(m["lap_time"]), f"+{cmp.deltas[n]:.3f}", f"{m['v_max_kmh']:.0f}", f"{m['v_avg_kmh']:.1f}", f"{m['time_corners']:.2f}",
                    f"{m['time_straights']:.2f}", f"{m['braking_distance_m']:.0f}", f"{m['a_lat_max_g']:.2f}", f"{m['tyre_temp_c']:.0f}",
                    f"{m['degradation_s_per_lap']:.3f}", "sim" if m["compliant"] else "NÃO"]
            for c, t in enumerate(vals):
                it = QTableWidgetItem(t)
                if r == 0: it.setForeground(QColor(style.GREEN))
                self.tb_cmp.setItem(r, c, it)
        cols = [style.CYAN, style.AMBER, style.GREEN]
        self.plots.set_result(self.res or cmp.results[cmp.ranking[0]],
                              [(n, cmp.results[n], cols[i % 3]) for i, n in enumerate(cmp.ranking)])
        self.tx_rep.setPlainText(report.comparison_report_md(cmp))
        self.statusBar().showMessage("Comparação concluída; velocidade das voltas sobreposta na aba Telemetria.")

    def run_tyres(self):
        car, env, key, fuel = self.current_car(), self.current_env(), self.cb_track.currentData(), self.sp_fuel.value()
        comps = [c for c in self.season.compounds["allowed"]]
        cfgs = {c: car.copy(compound=c, name=c) for c in comps}
        def work():
            from ..core.compare import compare_configs as cc
            out = {}
            for c, cf in cfgs.items():
                cf.mode = "experimental" if False else cf.mode
                out[c] = cc(key, {c: cf}, env, fuel)
            return out
        self._async(work, self._on_tyres, "Comparando compostos...")

    def _on_tyres(self, out):
        rows = sorted(out.items(), key=lambda kv: kv[1].results[kv[0]].lap_time)
        hdr = ["Composto", "Tempo", "Δ", "T pneu (°C)", "Uso de aderência", "Desgaste/volta", "Degradação (s/volta)", "Vida est. (voltas)", "ay máx (g)"]
        self.tb_tyre.setColumnCount(len(hdr)); self.tb_tyre.setHorizontalHeaderLabels(hdr); self.tb_tyre.setRowCount(len(rows))
        best = rows[0][1].results[rows[0][0]].lap_time
        for r, (c, cmp) in enumerate(rows):
            res = cmp.results[c]; m = cmp.metrics[c]; s = res.summary
            life = 1.0 / max(s["tyre_wear_per_lap"], 1e-6)
            vals = [self.season.compounds["labels"].get(c, c), format_time(res.lap_time), f"+{res.lap_time - best:.3f}", f"{s['tyre_temp_mean_c']:.0f}",
                    f"{s['tyre_util_mean'] * 100:.0f} %", f"{s['tyre_wear_per_lap'] * 100:.2f} %", f"{m['degradation_s_per_lap']:.3f}", f"{life:.0f}", f"{s['a_lat_max_g']:.2f}"]
            for k, t in enumerate(vals):
                it = QTableWidgetItem(t)
                if r == 0: it.setForeground(QColor(style.GREEN))
                self.tb_tyre.setItem(r, k, it)
        self.lb_tyre.setText("Tempos resultam da simulação (não são fixos por composto). Parâmetros dos compostos são estimativas. "
                             "Intermediário e chuva só fazem sentido com umidade > 0.")

    def run_strategy(self):
        car, env, key = self.current_car(), self.current_env(), self.cb_track.currentData()
        laps, pit, stops = self.sp_laps.value(), self.sp_pit.value(), self.sp_stops.value()
        def work():
            sm = StrategyModel(key, car, env, pit_loss_s=pit, race_laps=laps)
            res = sm.compare(default_strategies(sm))
            opt = sm.optimize(max_stops=stops, top=6)
            return sm, res, opt
        self._async(work, self._on_strategy, "Ajustando modelo de pneus e comparando estratégias (alguns segundos)...")

    def _on_strategy(self, packed):
        sm, base, opt = packed
        rows = [("Padrão", r) for r in base] + [("Otimizada", r) for r in opt]
        hdr = ["Origem", "Estratégia", "Tempo total", "Δ vs melhor", "Box (voltas)", "Observações"]
        self.tb_strat.setColumnCount(len(hdr)); self.tb_strat.setHorizontalHeaderLabels(hdr); self.tb_strat.setRowCount(len(rows))
        best = min(r.total_time for _, r in rows if r.valid)
        for i, (o, r) in enumerate(rows):
            vals = [o, r.strategy.name, r.fmt(), f"+{r.total_time - best:.1f} s", str(r.pit_laps), " ".join(r.notes)[:90]]
            for c, t in enumerate(vals): self.tb_strat.setItem(i, c, QTableWidgetItem(t))
        self.lb_strat.setText(f"Voltas: {sm.race_laps} · perda por pit stop {sm.pit_loss:.1f} s (parâmetro configurável, não oficial) · "
                              "tempos de volta vêm do simulador físico com desgaste e queima de combustível.")
        self.tx_rep.setPlainText(report.strategy_report_md(opt or base, sm.pit_loss))

    # =========================================================================== reprodução
    def _audio_settings(self) -> AudioSettings:
        return AudioSettings(enabled=self.chk_au_on.isChecked(), profile=self.cb_prof.currentData(), mode=self.cb_mode_au.currentData(),
                             observer_s=self.track_view.observer_s if self.track_view.observer_s is not None else self._default_observer(),
                             observer_offset=self.sp_off.value(), master=self.sl_master.value() / 100, engine_vol=self.sl_eng.value() / 100,
                             ambient_vol=self.sl_amb.value() / 100, fx_vol=self.sl_fx.value() / 100, intensity=self.sl_int.value() / 100)

    def _default_observer(self):
        if self.res is None: return 0.0
        k = int(np.argmax(self.res.tel["v"]))
        return float(self.res.tel["s"][k])

    def _observer_picked(self, s):
        self.lb_obs.setText(f"Ouvinte em s = {s:.0f} m. A volta será renderizada de novo no próximo ▶.")
        self._audio_cache.clear()

    def toggle_play(self):
        if self.res is None:
            self.statusBar().showMessage("Simule uma volta primeiro."); return
        if self.playing:
            self.pause(); return
        T_ = self.res.lap_time
        t = self.sl_time.value() / 1000 * T_
        if t >= T_ - 0.05: t = 0.0
        speed = float(self.cb_speed.currentData())
        use_audio = self.chk_audio.isChecked() and self.chk_au_on.isChecked() and self.audio.available and abs(speed - 1.0) < 1e-6
        if use_audio:
            st = self._audio_settings()
            sig = (id(self.res), st.profile, st.mode, round(st.observer_s), st.observer_offset, round(st.engine_vol, 2), round(st.ambient_vol, 2),
                   round(st.fx_vol, 2), round(st.intensity, 2), round(st.master, 2))
            if sig in self._audio_cache:
                self._start(t, self._audio_cache[sig], st)
            else:
                res = self.res
                def work():
                    return SimulationAudio(res, st).render_all()
                def done(buf):
                    self._audio_cache = {sig: buf}
                    self._start(t, buf, st)
                self._async(work, done, "Sintetizando o áudio da volta...")
        else:
            self._start(t, None, None)
            if self.chk_audio.isChecked() and abs(speed - 1.0) > 1e-6:
                self.statusBar().showMessage("Áudio só em 1.0x (a velocidade alteraria o tom). Reproduzindo sem som.")

    def _start(self, t, buf, st):
        self._audio_on_play = buf is not None
        if buf is not None:
            self.audio.set_volume(1.0)
            self.audio.play_buffer(buf, t + st.loop_pad_s)
            self._pad = st.loop_pad_s
        self._t0_wall = time.perf_counter(); self._t0_sim = t
        self.playing = True; self.btn_play.setText("⏸  Pausar"); self.timer.start()

    def pause(self):
        self.playing = False; self.timer.stop(); self.audio.stop(); self.btn_play.setText("▶  Reproduzir")

    def stop_playback(self):
        self.pause(); self.sl_time.setValue(0)
        if self.res is not None: self.track_view.set_time(0); self.plots.set_cursor_s(0)

    def restart(self):
        self.pause(); self.sl_time.setValue(0); self._set_t(0.0)

    def _tick(self):
        speed = float(self.cb_speed.currentData())
        if self._audio_on_play:
            t = self.audio.position_s() - getattr(self, "_pad", 0.0)
            if self.audio.position_s() <= 0.0:
                t = self._t0_sim
        else:
            t = self._t0_sim + (time.perf_counter() - self._t0_wall) * speed
        if t >= self.res.lap_time:
            t = self.res.lap_time; self.pause()
        self._set_t(max(t, 0.0), from_play=True)

    def _set_t(self, t, from_play=False):
        T_ = self.res.lap_time
        self.track_view.set_time(t)
        k = int(np.clip(np.searchsorted(self.res.tel["t"], t) - 1, 0, len(self.res.tel["s"]) - 1))
        self.plots.set_cursor_s(float(self.res.tel["s"][k]))
        self.lb_time.setText(format_time(t))
        self.sl_time.blockSignals(True); self.sl_time.setValue(int(t / T_ * 1000)); self.sl_time.blockSignals(False)

    def _seek_slider(self, v):
        if self.res is None: return
        was = self.playing
        if was: self.pause()
        self._set_t(v / 1000 * self.res.lap_time)

    def _seek_s(self, s):
        if self.res is None: return
        k = int(np.argmin(np.abs(self.res.tel["s"] - s)))
        if self.playing: self.pause()
        self._set_t(float(self.res.tel["t"][k]))

    # =========================================================================== áudio / exportação
    def test_engine(self):
        prof = self.cb_prof.currentData()
        buf = RealtimeEngineSynth.test_sweep(prof, 6.0)
        if self.audio.available:
            self.audio.set_volume(self.sl_master.value() / 100)
            self.audio.play_buffer(buf * 0.9, 0.0)
            self.statusBar().showMessage("Teste do motor: aceleração com trocas de marcha e desaceleração.")
        else:
            p, _ = QFileDialog.getSaveFileName(self, "Salvar teste do motor", "teste_motor.wav", "WAV (*.wav)")
            if p: write_wav(p, buf, 44100)

    def export_wav(self):
        if self.res is None:
            self.statusBar().showMessage("Simule uma volta primeiro."); return
        p, _ = QFileDialog.getSaveFileName(self, "Exportar áudio da volta", "volta.wav", "WAV (*.wav)")
        if not p: return
        res, st = self.res, self._audio_settings()
        self._async(lambda: SimulationAudio(res, st).render_all(), lambda a: (write_wav(p, a, st.sr), self.statusBar().showMessage(f"Áudio salvo em {p}")), "Renderizando WAV...")

    def _export(self, kind):
        if self.res is None:
            self.statusBar().showMessage("Simule uma volta primeiro."); return
        ext = {"csv": "CSV (*.csv)", "json": "JSON (*.json)", "md": "Markdown (*.md)"}[kind]
        p, _ = QFileDialog.getSaveFileName(self, "Exportar", f"volta.{kind}", ext)
        if not p: return
        if kind == "csv": report.export_csv(self.res, p)
        elif kind == "json": report.export_json(self.res, p)
        else: Path(p).write_text(report.lap_report_md(self.res), encoding="utf-8")
        self.statusBar().showMessage(f"Exportado: {p}")

    def export_mobile(self):
        if self.res is None:
            self.statusBar().showMessage("Simule uma volta primeiro."); return
        from ..mobile.export import build_mobile_html
        p, _ = QFileDialog.getSaveFileName(self, "Versão mobile (somente leitura)", "nexus_f1_mobile.html", "HTML (*.html)")
        if p:
            Path(p).write_text(build_mobile_html([self.res]), encoding="utf-8")
            self.statusBar().showMessage(f"Visualizador mobile salvo em {p} — abra no celular.")

    def save_cfg(self):
        p, _ = QFileDialog.getSaveFileName(self, "Salvar configuração", "carro.json", "JSON (*.json)")
        if p: Path(p).write_text(self.current_car().to_json(), encoding="utf-8")

    def load_cfg(self):
        p, _ = QFileDialog.getOpenFileName(self, "Carregar configuração", "", "JSON (*.json)")
        if p:
            car = CarConfig.from_dict(json.loads(Path(p).read_text(encoding="utf-8")))
            i = self.cb_season.findText(car.season)
            if i >= 0: self.cb_season.setCurrentIndex(i)
            self._load_car_into_ui(car)

    def new_season(self):
        nid, ok = QInputDialog.getText(self, "Nova temporada", "Identificador da nova temporada (ex.: 2027):")
        if not ok or not nid.strip(): return
        try:
            regulations.create_season(nid.strip(), base_id=self.cb_season.currentText())
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "Temporada", str(e)); return
        self.cb_season.addItem(nid.strip()); self.cb_season.setCurrentText(nid.strip())
        QMessageBox.information(self, "Temporada criada", f"'{nid}' criada como cópia independente. As anteriores não foram alteradas.\n"
                                "Revise os valores contra o regulamento oficial.")
