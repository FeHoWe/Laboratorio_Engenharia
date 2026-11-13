"""Diálogo de FEA não linear (V3.6): barra elastoplástica, barras em série e blocos em contato — CalculiX real, com a solução analítica ao lado."""
from __future__ import annotations
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QTabWidget, QWidget, QFormLayout, QDoubleSpinBox, QPushButton, QTextEdit, QLabel, QComboBox,
                               QLineEdit, QFileDialog, QHBoxLayout, QProgressBar)
from PySide6.QtCore import QTimer
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
        # --- contato entre DUAS PEÇAS (caixa / cilindro / arquivo STEP) — V3.8
        w4 = QWidget(); f4 = QFormLayout(w4)
        f4.addRow(QLabel("A peça SUPERIOR é apoiada automaticamente sobre a INFERIOR (eixo z). Faces de apoio planas e horizontais. Materiais: SEUS."))
        self.pc = {}
        for lado in ("inf", "sup"):
            tipo = QComboBox(); tipo.addItems(["caixa", "cilindro", "step"])
            dims = {k: _s(v) for k, v in dict(dx=10, dy=10, dz=10, r=5, h=10).items()}
            path = QLineEdit(); path.setPlaceholderText("caminho do arquivo .step")
            br = QPushButton("..."); br.clicked.connect(lambda _=False, p=path: p.setText(QFileDialog.getOpenFileName(self, "STEP", "", "STEP (*.step *.stp)")[0]))
            E, nu = _s(210000), _s(0.0, 0.0, 0.499)
            self.pc[lado] = dict(tipo=tipo, dims=dims, path=path, E=E, nu=nu)
            n = "INFERIOR" if lado == "inf" else "SUPERIOR"
            f4.addRow(f"Peça {n}", tipo)
            f4.addRow("  dx, dy, dz [mm] (caixa)", self._linha([dims["dx"], dims["dy"], dims["dz"]]))
            f4.addRow("  r, h [mm] (cilindro)", self._linha([dims["r"], dims["h"]]))
            pl = QHBoxLayout(); pl.addWidget(path); pl.addWidget(br); wp = QWidget(); wp.setLayout(pl); f4.addRow("  arquivo STEP", wp)
            f4.addRow(f"  E {n.lower()} [MPa], ν", self._linha([E, nu]))
        self.pc_F, self.pc_h, self.pc_K, self.pc_mu = _s(800), _s(3.0), _s(1e7), _s(0.0, 0.0, 2.0)
        for t, w in (("força [N] (para baixo, no topo da superior)", self.pc_F), ("tamanho de elemento [mm]", self.pc_h), ("rigidez de penalidade K", self.pc_K), ("atrito μ (0 = sem atrito)", self.pc_mu)):
            f4.addRow(t, w)
        b4 = QPushButton("Rodar contato entre as duas peças"); b4.clicked.connect(self.run_contato2); f4.addRow(b4); T.addTab(w4, "Contato (2 peças)")
        # V4.0: os casos rodam em PROCESSO ISOLADO (a interface não congela; há barra e cancelamento)
        self._job = None; self.jobs = None
        self._timer = QTimer(self); self._timer.setInterval(200); self._timer.timeout.connect(self._poll)
        bl = QHBoxLayout(); self.progress = QProgressBar(); self.progress.setVisible(False); bl.addWidget(self.progress)
        self.b_cancel = QPushButton("Cancelar"); self.b_cancel.setEnabled(False); self.b_cancel.clicked.connect(self.cancelar); bl.addWidget(self.b_cancel)
        L.addLayout(bl)
        self.out = QTextEdit(); self.out.setReadOnly(True); L.addWidget(self.out)

    @staticmethod
    def _linha(ws):
        w = QWidget(); h = QHBoxLayout(w); h.setContentsMargins(0, 0, 0, 0)
        for x in ws: h.addWidget(x)
        return w

    def _spec(self, lado):
        d = self.pc[lado]; t = d["tipo"].currentText(); k = d["dims"]
        return {"caixa": dict(tipo="caixa", dx=k["dx"].value(), dy=k["dy"].value(), dz=k["dz"].value()),
                "cilindro": dict(tipo="cilindro", r=k["r"].value(), h=k["h"].value()),
                "step": dict(tipo="step", path=d["path"].text())}[t]

    def run_contato2(self):
        i, s_ = self.pc["inf"], self.pc["sup"]
        self._submete("Contato (2 peças)", "contato2", dict(inferior=self._spec("inf"), superior=self._spec("sup"), E1=i["E"].value(), nu1=i["nu"].value(),
                      E2=s_["E"].value(), nu2=s_["nu"].value(), forca=self.pc_F.value(), tamanho=self.pc_h.value(), K=self.pc_K.value(), mu=self.pc_mu.value() or None))

    def run_plastico(self):
        p = self.p; self._submete("Barra elastoplástica", "plastico", dict(E=p["E"].value(), nu=p["nu"].value(), sigma_y=p["sy"].value(), Et=p["Et"].value(),
                                  comprimento=p["L"].value(), lado=p["a"].value(), deformacao=p["eps"].value()))

    def run_serie(self):
        s = self.s; self._submete("Barras em série", "serie", dict(E1=s["E1"].value(), E2=s["E2"].value(), nu=s["nu"].value(), comprimento=s["L"].value(),
                                  lado=s["a"].value(), forca=s["F"].value()))

    def run_contato(self):
        c = self.c; self._submete("Blocos em contato", "contato", dict(E=c["E"].value(), nu=c["nu"].value(), comprimento_bloco=c["L"].value(),
                                  lado=c["a"].value(), forca=c["F"].value(), K=c["K"].value()))

    # ---- execução isolada
    def _submete(self, nome, caso, params):
        if self._job is not None and not self._job.terminal:
            return
        from core.jobs import JobManager
        self.jobs = self.jobs or JobManager(1)
        self._job = self.jobs.submit_python(f"{nome} (isolado)", "modules.nl_job", "run", dict(caso=caso, params=params), timeout=3600)
        self.progress.setRange(0, 100); self.progress.setValue(0); self.progress.setVisible(True); self.b_cancel.setEnabled(True)
        self.out.setPlainText("Executando em processo separado…")
        self._timer.start()

    def cancelar(self):
        if self._job is not None and not self._job.terminal:
            self.jobs.cancel(self._job.id)

    def aguardar(self, timeout=600.0):
        """Espera o job terminar e mostra o resultado (usado pelos testes e por quem chama por API)."""
        if self._job is not None:
            self._job.wait(timeout)
            self._poll()
        return self.out.toPlainText()

    def _poll(self):
        j = self._job
        if j is None:
            self._timer.stop(); return
        self.progress.setValue(int(j.progress))
        if not j.terminal:
            return
        self._timer.stop(); self.b_cancel.setEnabled(False); self.progress.setVisible(False)
        if j.state == "CANCELLED":
            self.out.setPlainText("Cancelado pelo usuário. Nenhum resultado foi gravado."); return
        if j.state != "DONE":
            self.out.setPlainText(f"{j.state}: {j.error}\n\n--- log do processo ---\n" + "\n".join(j.log.splitlines()[-25:])); return
        r = j.result()
        if "_erro" in r:
            self.out.setPlainText(f"ERRO: {r['_erro']}"); return
        self.out.setPlainText("\n".join(f"{k}: {v:.5g}" if isinstance(v, float) else f"{k}: {v}" for k, v in r.items()) +
                              "\n\nCalculiX real × solução analítica de barra. Malha grosseira de verificação: NÃO é validação de peça real.")
