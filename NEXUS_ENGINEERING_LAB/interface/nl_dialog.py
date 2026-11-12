"""Diálogo de FEA não linear (V3.6): barra elastoplástica, barras em série e blocos em contato — CalculiX real, com a solução analítica ao lado."""
from __future__ import annotations
from PySide6.QtWidgets import QDialog, QVBoxLayout, QTabWidget, QWidget, QFormLayout, QDoubleSpinBox, QPushButton, QTextEdit, QLabel
from modules import casos_nl as CN


def _s(v, lo=1e-9, hi=1e9, d=4):
    s = QDoubleSpinBox(); s.setDecimals(d); s.setRange(lo, hi); s.setValue(v); return s


class NLDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent); self.setWindowTitle("NEXUS STRUCTURAL — Plasticidade, multimaterial e contato"); self.resize(640, 560)
        L = QVBoxLayout(self)
        L.addWidget(QLabel("Digite os SEUS materiais (nada é atribuído automaticamente). Valores iniciais são exemplos ILUSTRATIVOS. Unidades: mm, N, MPa."))
        T = QTabWidget(); L.addWidget(T)
        self.p = {k: _s(v) for k, v in dict(E=210000, nu=0.3, sy=250, Et=2100, L=20, a=4, eps=0.006).items()}
        w = QWidget(); f = QFormLayout(w)
        for k, t in (("E", "E [MPa]"), ("nu", "ν"), ("sy", "σ escoamento [MPa]"), ("Et", "módulo tangente Et [MPa]"), ("L", "comprimento [mm]"), ("a", "lado [mm]"), ("eps", "deformação imposta")): f.addRow(t, self.p[k])
        b = QPushButton("Rodar barra elastoplástica"); b.clicked.connect(self.run_plastico); f.addRow(b); T.addTab(w, "Plasticidade")
        self.s = {k: _s(v) for k, v in dict(E1=210000, E2=70000, nu=0.0, L=20, a=4, F=1000).items()}
        w2 = QWidget(); f2 = QFormLayout(w2)
        for k, t in (("E1", "E região 1 [MPa]"), ("E2", "E região 2 [MPa]"), ("nu", "ν"), ("L", "comprimento total [mm]"), ("a", "lado [mm]"), ("F", "força [N]")): f2.addRow(t, self.s[k])
        b2 = QPushButton("Rodar barras em série"); b2.clicked.connect(self.run_serie); f2.addRow(b2); T.addTab(w2, "Multimaterial")
        self.c = {k: _s(v) for k, v in dict(E=210000, nu=0.0, L=10, a=4, F=800, K=1e7).items()}
        w3 = QWidget(); f3 = QFormLayout(w3)
        for k, t in (("E", "E [MPa]"), ("nu", "ν"), ("L", "comprimento de cada bloco [mm]"), ("a", "lado [mm]"), ("F", "força [N]"), ("K", "rigidez de penalidade K")): f3.addRow(t, self.c[k])
        b3 = QPushButton("Rodar dois blocos em contato"); b3.clicked.connect(self.run_contato); f3.addRow(b3); T.addTab(w3, "Contato")
        self.out = QTextEdit(); self.out.setReadOnly(True); L.addWidget(self.out)

    def _mostra(self, fn):
        try: r = fn()
        except ValueError as e: self.out.setPlainText(f"ERRO: {e}"); return
        self.out.setPlainText("\n".join(f"{k}: {v:.5g}" if isinstance(v, float) else f"{k}: {v}" for k, v in r.items()) +
                              "\n\nCalculiX real × solução analítica de barra. Malha grosseira de verificação: NÃO é validação de peça real.")

    def run_plastico(self): p = self.p; self._mostra(lambda: CN.barra_plastica(p["E"].value(), p["nu"].value(), p["sy"].value(), p["Et"].value(), p["L"].value(), p["a"].value(), p["eps"].value()))
    def run_serie(self): s = self.s; self._mostra(lambda: CN.serie_materiais(s["E1"].value(), s["E2"].value(), s["nu"].value(), s["L"].value(), s["a"].value(), s["F"].value()))
    def run_contato(self): c = self.c; self._mostra(lambda: CN.blocos_contato(c["E"].value(), c["nu"].value(), c["L"].value(), c["a"].value(), c["F"].value(), c["K"].value()))
