"""Aba "Laboratório de testes" (V2.2): aerodinâmica, desempenho e testes estruturais ANALÍTICOS.

Não é CFD nem FEA: cada teste mostra as hipóteses usadas e todos os coeficientes/propriedades são digitados por você.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Optional

from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel, QFileDialog, QPlainTextEdit, QPushButton, QTabWidget,
                               QVBoxLayout, QWidget)

from modules import aero, structural as st, truss_fem


@dataclass
class Field:
    key: str
    label: str
    default: float
    unit: str = ""
    lo: float = 0.0
    hi: float = 1e9
    decimals: int = 3


@dataclass
class Calc:
    key: str
    title: str
    fields: list
    run: Callable[[dict], str]
    choices: list = field(default_factory=list)       # [(key, label, [opções])]
    intro: str = ""


def _hdr(t: str) -> str:
    return f"{t}\n" + "─" * len(t) + "\n"


def _row(label: str, value, unit: str = "", nd: int = 3) -> str:
    v = f"{value:.{nd}f}" if isinstance(value, float) and math.isfinite(value) else str(value)
    return f"  {label:<44}{v:>14} {unit}\n"


HONEST = ("\nHipóteses: modelo analítico clássico, NÃO é CFD/FEA; entradas digitadas por você (nada é deduzido da geometria 3D).\n")


# ------------------------------------------------------------------ cálculos
def run_isa(v: dict) -> str:
    a = aero.isa(v["h"], v["dT"])
    ms = v["v"] / 3.6
    out = _hdr("Atmosfera padrão ISA")
    out += _row("Temperatura", a["T"] - 273.15, "°C", 2) + _row("Pressão", a["p"] / 100, "hPa", 2) + _row("Densidade ρ", a["rho"], "kg/m³", 4)
    out += _row("Viscosidade dinâmica μ", a["mu"] * 1e6, "µPa·s", 3) + _row("Velocidade do som", a["a"], "m/s", 2)
    out += _row("Mach", ms / a["a"], "", 3) + _row("Pressão dinâmica q", aero.dynamic_pressure(a["rho"], ms), "Pa", 1)
    if ms / a["a"] > 0.3:
        out += "  ⚠ Mach > 0,3: compressibilidade importa; os modelos incompressíveis do laboratório perdem validade.\n"
    return out + HONEST


def _vehicle(v: dict) -> aero.Vehicle:
    a = aero.isa(v["h"])
    return aero.Vehicle(mass=v["mass"], cda=v["cda"], cla=v["cla"], power=v["power"] * 1000.0, mu_tyre=v["mu"], crr=v["crr"], rho=a["rho"])


def run_vehicle(v: dict) -> str:
    veh = _vehicle(v)
    out = _hdr("Veículo — aerodinâmica e desempenho")
    out += _row("ρ do ar", veh.rho, "kg/m³", 4)
    if v["cda"] > 0:
        out += _row("Eficiência aerodinâmica ClA/CdA", v["cla"] / v["cda"], "", 2)
    out += _row("Velocidade máxima (potência = resistência)", veh.top_speed() * 3.6, "km/h", 1)
    if v["radius"] > 0:
        vc = veh.corner_speed(v["radius"])
        out += _row(f"Velocidade máx. em curva R={v['radius']:.0f} m", vc * 3.6 if math.isfinite(vc) else "ilimitada (downforce domina)", "km/h", 1)
    out += "\n  v[km/h]   q[Pa]   arrasto[N]  downforce[N]  P_req[kW]  desacel.[m/s²]\n"
    for kmh in (50, 100, 150, 200, 250, 300, 350):
        ms = kmh / 3.6
        out += f"  {kmh:>6} {aero.dynamic_pressure(veh.rho, ms):>8.0f} {veh.drag(ms):>11.0f} {veh.downforce(ms):>12.0f} {veh.power_required(ms) / 1000:>10.1f} {veh.braking_decel(ms):>14.2f}\n"
    out += ("\nHipóteses: CdA, ClA, μ do pneu, Crr e potência na roda são SEUS valores, constantes com a velocidade; sem transferência de carga, "
            "sem balanço de frenagem, sem limite de tração/marcha, sem variação do coeficiente com altura de rodagem/yaw. Não é simulação de volta.\n")
    return out


def run_wing(v: dict) -> str:
    a = aero.isa(v["h"])
    c_root, taper = v["chord"], v["taper"]
    chords = lambda s: c_root * (1 - (1 - taper) * abs(s))             # noqa: E731
    twist = lambda s: v["twist"] * abs(s)                               # washout linear (negativo = reduz incidência na ponta)  # noqa: E731
    al0 = math.degrees(aero.naca4_alpha_l0(v["camber"] / 100, v["camber_pos"] / 100))
    hg = v["h_ground"] / 1000.0 if v["h_ground"] > 0 else None
    r = aero.lifting_line(v["span"], chords, v["alpha"], al0, twist, n_terms=40, h_ground=hg)
    f = aero.wing_forces(r, a["rho"], v["v"] / 3.6, v["cd0"])
    out = _hdr("Asa finita — linha sustentadora de Prandtl (Glauert, 40 termos)")
    out += _row("Área em planta S", r.area, "m²", 4) + _row("Alongamento AR", r.ar, "", 3)
    out += _row("α de sustentação nula do perfil (perfil fino)", al0, "°", 3)
    out += _row("CL da asa", r.cl, "", 4) + _row("CDi (induzido)", r.cdi, "", 5) + _row("Eficiência de envergadura e", r.e, "", 3)
    out += _row("Sustentação (módulo = downforce se invertida)", f["lift"], "N", 1) + _row("Arrasto total (CD0 + CDi)", f["drag"], "N", 1)
    out += _row("L/D", f["ld"], "", 2)
    if hg:
        out += "  (efeito solo: CDi reduzido por fator de aeronave — aproximação grosseira para asas de carro; CL NÃO é corrigido)\n"
    out += ("\nHipóteses: asa reta simétrica, perfil NACA 4 dígitos por teoria de perfil fino (a0=2π), escoamento incompressível e sem descolamento "
            "(sem estol), arrasto de perfil CD0 = valor digitado. Elementos múltiplos (flaps), endplates e interação com roda/carroceria NÃO são modelados.\n")
    return out


def run_beam(v: dict) -> str:
    sec = {"Retangular": lambda: st.rect(v["b"], v["h"]), "Barra circular": lambda: st.circle(v["b"]),
           "Tubo redondo": lambda: st.tube_round(v["b"], v["t"]), "Tubo retangular": lambda: st.tube_rect(v["b"], v["h"], v["t"]),
           "Perfil I": lambda: st.i_beam(v["b"], v["h"], v["t"], v["tw"])}[v["_sec"]]()
    case = st.BEAM_CASES[v["_case"]]
    r = st.beam(case, v["load"], v["L"], v["E"], sec, v["sy"] or None)
    out = _hdr("Viga — Euler-Bernoulli")
    out += _row("Área", sec.area, "mm²", 1) + _row("Momento de inércia I", sec.inertia, "mm⁴", 1) + _row("Flecha máxima", r["deflection"], "mm", 4)
    out += _row("Momento máximo", r["moment"] / 1000, "N·m", 2) + _row("Tensão de flexão máxima", r["sigma"], "MPa", 2) + _row("Rigidez", r["stiffness"], "N/mm", 2)
    if "safety_factor" in r:
        out += _row("Coeficiente de segurança (escoamento)", r["safety_factor"], "", 2)
    out += "\nHipóteses: pequenas deformações, material linear elástico, seção constante, sem cisalhamento/instabilidade lateral, sem concentração de tensão.\n"
    return out


def run_column(v: dict) -> str:
    sec = {"Barra circular": lambda: st.circle(v["b"]), "Retangular": lambda: st.rect(v["b"], v["h"]),
           "Tubo redondo": lambda: st.tube_round(v["b"], v["t"])}[v["_sec"]]()
    if v["_sec"] == "Retangular":                         # flamba no eixo fraco (menor inércia)
        sec = st.Section(sec.area, min(v["b"] * v["h"] ** 3, v["h"] * v["b"] ** 3) / 12, min(v["b"], v["h"]) / 2, float("nan"))
    r = st.column_buckling(v["E"], sec, v["L"], st.END_K[v["_end"]], v["sy"])
    out = _hdr("Flambagem de coluna")
    out += _row("Raio de giração", r["r"], "mm", 3) + _row("Esbeltez KL/r", r["slenderness"], "", 1) + _row("Esbeltez crítica", r["slenderness_crit"], "", 1)
    out += f"  Regime: {r['regime']}\n" + _row("Carga crítica", r["p_crit"], "N", 0) + _row("Carga de Euler (referência)", r["p_euler"], "N", 0)
    if v["P"] > 0:
        out += _row("Coeficiente de segurança à flambagem", r["p_crit"] / v["P"], "", 2)
    return out + "\nHipóteses: coluna reta, carga axial centrada, material elástico-perfeito, sem imperfeição inicial (use fator de segurança alto).\n"


def run_bolt(v: dict) -> str:
    d = int(v["d"])
    r = st.bolt_joint(d, v["T"], v["K"], v["sp"], v["Pe"], v["kr"])
    out = _hdr(f"Junta parafusada M{d} (Shigley)")
    out += _row("Área de tensão At", r["At"], "mm²", 1) + _row("Pré-carga Fi = T/(K·d)", r["preload"], "N", 0) + _row("Tensão de pré-carga", r["preload_stress"], "MPa", 1)
    out += _row("Fi / carga de prova", r["preload_ratio"], "", 2) + _row("Constante de rigidez da junta C", r["C"], "", 3)
    out += _row("Carga no parafuso com Pe", r["bolt_load"], "N", 0) + _row("Coef. de segurança à carga de prova", r["n_proof"], "", 2)
    out += _row("Força de aperto residual", r["clamp_load"], "N", 0) + _row("Carga externa de separação", r["separation_load"], "N", 0)
    if r["preload_ratio"] > 0.9:
        out += "  ⚠ Pré-carga acima de 90 % da carga de prova.\n"
    return out + "\nHipóteses: K (fator de torque) e km/kb são SEUS valores — K varia muito com lubrificação/acabamento (±25 %). Sem relaxação, sem fadiga (use a aba de fadiga).\n"


def run_shaft(v: dict) -> str:
    r = st.shaft_torsion(v["T"] * 1000.0, v["d"], v["L"], v["G"], v["di"])
    out = _hdr("Eixo em torção")
    out += _row("Tensão de cisalhamento máxima", r["tau"], "MPa", 2) + _row("Ângulo de torção", r["theta_deg"], "°", 4) + _row("Rigidez torcional", r["stiffness"] / 1000, "N·m/rad", 1)
    if v["sy"] > 0:
        out += _row("Coef. de segurança (Tresca: 0,5·Sy/τ)", 0.5 * v["sy"] / r["tau"], "", 2)
    return out + "\nHipóteses: seção circular, torque puro e constante, sem rasgo de chaveta/concentração de tensão.\n"


def run_vessel(v: dict) -> str:
    r = st.thin_vessel(v["p"], v["d"], v["t"])
    out = _hdr("Vaso cilíndrico de parede fina")
    out += _row("Tensão circunferencial", r["hoop"], "MPa", 2) + _row("Tensão axial", r["axial"], "MPa", 2)
    if v["sy"] > 0:
        out += _row("Coef. de segurança (circunferencial)", v["sy"] / r["hoop"], "", 2)
    if not r["thin_ok"]:
        out += "  ⚠ t ≥ d/20: parede NÃO é fina; use Lamé.\n"
    return out + "\nHipóteses: pressão interna estática, sem soldas/bocais/tampos.\n"


def run_vib(v: dict) -> str:
    sec = st.rect(v["b"], v["h"])
    out = _hdr("Vibração — frequências naturais")
    out += _row("Massa-mola f = √(k/m)/2π", st.spring_mass_fn(v["k"], v["m"]), "Hz", 3)
    for mode in (1, 2, 3):
        out += _row(f"Viga em balanço retangular, modo {mode}", st.cantilever_fn(v["E"], sec, v["L"], v["rho"], mode), "Hz", 2)
    return out + "\nHipóteses: sistemas lineares sem amortecimento, massa da mola desprezada; viga uniforme em balanço (flexão na direção h).\n"


def calcs() -> list[Calc]:
    f = Field
    mat = [f("E", "Módulo de Young E", 210000, "MPa", 1, 1e7, 0), f("sy", "Tensão de escoamento Sy (0 = ignorar)", 250, "MPa", 0, 1e5, 1)]
    return [
        Calc("isa", "Atmosfera ISA", [f("h", "Altitude", 0, "m", -500, 20000, 0), f("dT", "Desvio de temperatura", 0, "K", -60, 60, 1), f("v", "Velocidade", 100, "km/h", 0, 5000, 1)], run_isa),
        Calc("vehicle", "Veículo (aero + desempenho)",
             [f("mass", "Massa do veículo", 800, "kg", 1, 1e5, 1), f("cda", "CdA (arrasto)", 1.1, "m²", 0.01, 100, 3), f("cla", "ClA (downforce, positivo)", 3.5, "m²", 0, 100, 3),
              f("power", "Potência na roda", 700, "kW", 1, 5000, 0), f("mu", "μ pneu–solo", 1.6, "", 0.1, 4, 2), f("crr", "Crr", 0.012, "", 0, 0.1, 4),
              f("h", "Altitude", 0, "m", -500, 5000, 0), f("radius", "Raio de curva (0 = pular)", 100, "m", 0, 10000, 0)], run_vehicle,
             intro="Valores iniciais são EXEMPLOS genéricos para você substituir pelos seus dados; não representam um carro específico."),
        Calc("wing", "Asa — linha sustentadora",
             [f("span", "Envergadura b", 1.6, "m", 0.1, 100, 3), f("chord", "Corda na raiz", 0.35, "m", 0.01, 20, 3), f("taper", "Afilamento (ponta/raiz)", 1.0, "", 0.1, 1, 2),
              f("alpha", "Incidência na raiz", 8, "°", -20, 30, 2), f("twist", "Torção linear na ponta", 0, "°", -10, 10, 2), f("camber", "Camber NACA m", 4, "% corda", 0, 9, 2),
              f("camber_pos", "Posição do camber p", 40, "% corda", 10, 90, 1), f("cd0", "CD0 do perfil (digitado)", 0.012, "", 0, 0.2, 4),
              f("h_ground", "Altura ao solo (0 = sem efeito solo)", 0, "mm", 0, 5000, 0), f("v", "Velocidade", 200, "km/h", 1, 1500, 1), f("h", "Altitude", 0, "m", -500, 5000, 0)],
             run_wing, intro="Sinal: valores de CL/forças são em módulo para a convenção da asa; para asa invertida (downforce) use o mesmo módulo como downforce."),
        Calc("beam", "Viga",
             [f("load", "Carga (N, ou N/mm se distribuída)", 1000, "", 0, 1e9, 3), f("L", "Comprimento", 1000, "mm", 1, 1e6, 1), f("b", "Dimensão b / diâmetro", 40, "mm", 1, 1e4, 2),
              f("h", "Altura h", 60, "mm", 1, 1e4, 2), f("t", "Espessura t / mesa tf", 4, "mm", 0.1, 1e3, 2), f("tw", "Alma tw (perfil I)", 3, "mm", 0.1, 1e3, 2)] + mat, run_beam,
             choices=[("_case", "Caso de carga", list(st.BEAM_CASES)), ("_sec", "Seção", ["Retangular", "Barra circular", "Tubo redondo", "Tubo retangular", "Perfil I"])]),
        Calc("column", "Flambagem de coluna",
             [f("L", "Comprimento", 1000, "mm", 1, 1e6, 1), f("b", "Dimensão b / diâmetro", 20, "mm", 1, 1e4, 2), f("h", "Altura h", 30, "mm", 1, 1e4, 2), f("t", "Espessura t", 2, "mm", 0.1, 1e3, 2),
              f("P", "Carga aplicada (0 = pular)", 5000, "N", 0, 1e9, 0)] + mat[:1] + [f("sy", "Tensão de escoamento Sy", 250, "MPa", 1, 1e5, 1)], run_column,
             choices=[("_end", "Condição de extremidades", list(st.END_K)), ("_sec", "Seção", ["Barra circular", "Retangular", "Tubo redondo"])]),
        Calc("bolt", "Junta parafusada",
             [f("d", "Diâmetro nominal M", 10, "mm", 3, 24, 0), f("T", "Torque de aperto", 40, "N·m", 0.1, 5000, 1), f("K", "Fator de torque K (digitado)", 0.2, "", 0.05, 0.5, 3),
              f("sp", "Tensão de prova Sp", 640, "MPa", 100, 2000, 0), f("Pe", "Carga externa de tração na junta", 0, "N", 0, 1e7, 0), f("kr", "km/kb (rigidez junta/parafuso)", 4, "", 0.5, 20, 2)], run_bolt),
        Calc("shaft", "Eixo em torção",
             [f("T", "Torque", 200, "N·m", 0, 1e7, 1), f("d", "Diâmetro externo", 30, "mm", 1, 1e4, 2), f("di", "Diâmetro interno", 0, "mm", 0, 1e4, 2), f("L", "Comprimento", 500, "mm", 1, 1e6, 1),
              f("G", "Módulo de cisalhamento G", 80000, "MPa", 1, 1e6, 0), f("sy", "Sy (0 = pular)", 250, "MPa", 0, 1e5, 1)], run_shaft),
        Calc("vessel", "Vaso de pressão (parede fina)",
             [f("p", "Pressão interna", 2.0, "MPa", 0, 1000, 3), f("d", "Diâmetro interno", 200, "mm", 1, 1e5, 1), f("t", "Espessura", 3, "mm", 0.1, 1e3, 2), f("sy", "Sy (0 = pular)", 250, "MPa", 0, 1e5, 1)], run_vessel),
        Calc("vib", "Vibração",
             [f("k", "Rigidez da mola", 10, "N/mm", 0.001, 1e7, 3), f("m", "Massa", 1, "kg", 0.001, 1e6, 3), f("b", "Viga: largura b", 20, "mm", 1, 1e4, 2), f("h", "Viga: altura h (direção de flexão)", 5, "mm", 0.1, 1e4, 2),
              f("L", "Viga: comprimento", 300, "mm", 1, 1e6, 1), f("E", "E", 210000, "MPa", 1, 1e7, 0), f("rho", "Densidade", 7850, "kg/m³", 1, 30000, 0)], run_vib),
    ]


class CalcWidget(QWidget):
    def __init__(self, calc: Calc, context: Optional[Callable[[], str]] = None) -> None:
        super().__init__()
        self.calc, self.context = calc, context
        root = QVBoxLayout(self)
        if calc.intro:
            lab = QLabel(calc.intro)
            lab.setWordWrap(True)
            root.addWidget(lab)
        host = QWidget()
        form = QFormLayout(host)
        self.boxes: dict[str, QDoubleSpinBox] = {}
        self.combos: dict[str, QComboBox] = {}
        for key, label, opts in calc.choices:
            cb = QComboBox()
            cb.addItems(opts)
            form.addRow(label, cb)
            self.combos[key] = cb
        for fl in calc.fields:
            sp = QDoubleSpinBox()
            sp.setDecimals(fl.decimals)
            sp.setRange(fl.lo, fl.hi)
            sp.setValue(fl.default)
            sp.setSuffix(f" {fl.unit}" if fl.unit else "")
            form.addRow(fl.label, sp)
            self.boxes[fl.key] = sp
        root.addWidget(host)
        row = QHBoxLayout()
        self.btn = QPushButton("Calcular")
        self.btn.clicked.connect(self.compute)
        row.addWidget(self.btn)
        self.btn_export = QPushButton("Exportar relatório (.md)…")
        self.btn_export.clicked.connect(lambda: self.export_report())
        row.addWidget(self.btn_export)
        row.addStretch(1)
        root.addLayout(row)
        self.out = QPlainTextEdit()
        self.out.setReadOnly(True)
        self.out.setStyleSheet("font-family: Consolas, 'DejaVu Sans Mono', monospace;")
        root.addWidget(self.out, 1)

    def values(self) -> dict:
        v = {k: b.value() for k, b in self.boxes.items()}
        v.update({k: c.currentText() for k, c in self.combos.items()})
        return v

    def set_value(self, key: str, value) -> None:
        if key in self.boxes:
            self.boxes[key].setValue(value)
        elif key in self.combos:
            self.combos[key].setCurrentText(value)

    def report_text(self) -> str:
        """Relatório rastreável: entradas + resultado + hipóteses (reprodutível)."""
        from datetime import datetime
        ins = "\n".join(f"- {f.label}: {self.boxes[f.key].value():g} {f.unit}" for f in self.calc.fields) + "".join(
            f"\n- {lab}: {self.combos[k].currentText()}" for k, lab, _ in self.calc.choices)
        return (f"# {self.calc.title}\n\nGerado pelo NEXUS ENGINEERING LAB em {datetime.now():%Y-%m-%d %H:%M}\n\n## Entradas\n{ins}\n\n"
                f"## Resultado\n\n```\n{self.out.toPlainText() or self.compute()}\n```\n")

    def export_report(self, path: Optional[str] = None) -> Optional[str]:
        if path is None:
            path, _ = QFileDialog.getSaveFileName(self, "Exportar relatório", f"{self.calc.key}.md", "Markdown (*.md)")
        if not path:
            return None
        from pathlib import Path
        Path(path).write_text(self.report_text(), encoding="utf-8")
        return path

    def compute(self) -> str:
        try:
            text = self.calc.run(self.values())
        except Exception as exc:
            text = f"Não foi possível calcular: {exc}"
        who = self.context() if self.context else ""
        if who:
            text = f"Peça selecionada: {who}\n\n" + text
        self.out.setPlainText(text)
        return text


class TrussWidget(QWidget):
    """Treliça espacial de barras (método da rigidez direta). Entrada em texto; ver modules/truss_fem.py para o formato."""

    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        lab = QLabel("Treliça de barras articuladas (MEF de barras, linear). Formato: NODE id x y z [fix=xyz] · BAR id n1 n2 A E [I=…] · LOAD nó fx fy fz  (mm, N, MPa). "
                     "O exemplo traz uma Warren plana com valores genéricos — troque pelos seus.")
        lab.setWordWrap(True)
        root.addWidget(lab)
        self.edit = QPlainTextEdit()
        self.edit.setPlainText(truss_fem.warren_example())
        self.edit.setStyleSheet("font-family: Consolas, 'DejaVu Sans Mono', monospace;")
        root.addWidget(self.edit, 2)
        row = QHBoxLayout()
        self.sy = QDoubleSpinBox()
        self.sy.setRange(0, 1e5)
        self.sy.setValue(250)
        self.sy.setSuffix(" MPa (Sy, 0 = ignorar)")
        row.addWidget(self.sy)
        for text, slot in (("Resolver", lambda: self.compute()), ("Carregar exemplo Warren", lambda: self.edit.setPlainText(truss_fem.warren_example())),
                           ("Exportar relatório (.md)…", lambda: self.export_report())):
            b = QPushButton(text)
            b.clicked.connect(slot)
            row.addWidget(b)
        row.addStretch(1)
        root.addLayout(row)
        self.out = QPlainTextEdit()
        self.out.setReadOnly(True)
        self.out.setStyleSheet("font-family: Consolas, 'DejaVu Sans Mono', monospace;")
        root.addWidget(self.out, 3)

    def compute(self) -> str:
        try:
            t = truss_fem.parse(self.edit.toPlainText())
            text = truss_fem.report(t, truss_fem.solve(t), self.sy.value())
        except Exception as exc:
            text = f"Não foi possível calcular: {exc}"
        self.out.setPlainText(text)
        return text

    def export_report(self, path: Optional[str] = None) -> Optional[str]:
        if path is None:
            path, _ = QFileDialog.getSaveFileName(self, "Exportar relatório", "trelica.md", "Markdown (*.md)")
        if not path:
            return None
        from datetime import datetime
        from pathlib import Path
        Path(path).write_text(f"# Treliça (MEF de barras)\n\nGerado pelo NEXUS ENGINEERING LAB em {datetime.now():%Y-%m-%d %H:%M}\n\n## Modelo\n\n```\n"
                              f"{self.edit.toPlainText()}\n```\n\n## Resultado\n\n```\n{self.out.toPlainText() or self.compute()}\n```\n", encoding="utf-8")
        return path


class LabTab(QWidget):
    def __init__(self, primary_name: Optional[Callable[[], str]] = None) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        banner = QLabel("Laboratório de testes — cálculos analíticos clássicos (não é CFD nem elementos finitos). "
                        "Todos os coeficientes e propriedades são digitados por você; cada resultado lista suas hipóteses.")
        banner.setWordWrap(True)
        root.addWidget(banner)
        self.tabs = QTabWidget()
        self.widgets: dict[str, CalcWidget] = {}
        for c in calcs():
            w = CalcWidget(c, primary_name)
            self.widgets[c.key] = w
            self.tabs.addTab(w, c.title)
        self.truss = TrussWidget()
        self.widgets["truss"] = self.truss
        self.tabs.addTab(self.truss, "Treliça (MEF de barras)")
        root.addWidget(self.tabs, 1)

    def run_all(self) -> dict:
        return {k: w.compute() for k, w in self.widgets.items()}
