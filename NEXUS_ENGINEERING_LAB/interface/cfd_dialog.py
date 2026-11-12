"""Diálogo de CFD (OpenFOAM simpleFoam) — roda em PROCESSO ISOLADO, com progresso, cancelamento e mapa de Cp no visualizador 3D."""
from __future__ import annotations

import json

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                               QProgressBar, QPushButton, QSpinBox, QTextEdit, QVBoxLayout)

from modules import solver_registry as sr
from samples.library import PARTS


def _spin(v, lo, hi, dec=3):
    s = QDoubleSpinBox(); s.setRange(lo, hi); s.setDecimals(dec); s.setValue(v); return s


class CfdDialog(QDialog):
    sync = False                       # True nos testes: não abre processo de verdade quando o teste só valida a lógica

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("CFD — OpenFOAM simpleFoam (k-ω SST)"); self.resize(600, 700)
        v = QVBoxLayout(self)
        st = sr.detect("OpenFOAM")
        self.lbl = QLabel(("OpenFOAM: " + (st.versao or "instalado")) if st.instalado else "OpenFOAM NÃO INSTALADO — o caso não será executado (nenhum número é inventado). " + (st.instrucao or ""))
        self.lbl.setWordWrap(True); v.addWidget(self.lbl)
        v.addWidget(QLabel("RANS permanente incompressível, malha cartesiana + snappyHexMesh. Classe: SIMULAÇÃO NUMÉRICA. Sem estudo de malha e sem referência, NÃO é validado."))
        f = QFormLayout()
        self.part = QComboBox(); self.part.addItem("— usar STL —", "")
        [self.part.addItem(p.title, p.key) for p in PARTS.values()]
        f.addRow("Peça da biblioteca (mm)", self.part)
        row = QHBoxLayout(); self.stl = QLineEdit(); b = QPushButton("STL…"); b.clicked.connect(self.pick_stl); row.addWidget(self.stl); row.addWidget(b)
        f.addRow("ou arquivo STL", row)
        self.unit = QComboBox(); self.unit.addItems(["m", "mm"]); f.addRow("Unidade do STL", self.unit)
        self.v = _spin(20.0, 0.1, 400, 2); f.addRow("Velocidade V∞ (m/s)", self.v)
        self.rho = _spin(1.225, 0.01, 2000, 4); f.addRow("ρ (kg/m³)", self.rho)
        self.nu = _spin(1.5e-5, 1e-9, 1e-2, 9); f.addRow("ν (m²/s)", self.nu)
        self.it = QSpinBox(); self.it.setRange(10, 20000); self.it.setValue(300); f.addRow("Iterações", self.it)
        self.cx, self.cy, self.cz = (QSpinBox() for _ in range(3))
        for s, val in zip((self.cx, self.cy, self.cz), (60, 24, 18)): s.setRange(8, 400); s.setValue(val)
        cr = QHBoxLayout(); [cr.addWidget(s) for s in (self.cx, self.cy, self.cz)]; f.addRow("Células de fundo (x,y,z)", cr)
        self.gap = _spin(0.0, 0.0, 100, 4); f.addRow("Folga do solo (m)", self.gap)
        from PySide6.QtWidgets import QCheckBox
        self.cam = QSpinBox(); self.cam.setRange(0, 12); self.cam.setValue(0); self.cam.setToolTip("Camadas prismáticas na parede (0 = sem). Aproxima a 1ª célula da parede; confira a cobertura no log do snappyHexMesh.")
        f.addRow("Camadas prismáticas", self.cam)
        self.livre = QCheckBox("Ar livre (sem solo; corpo centrado — recomendado para corpos isolados)"); f.addRow(self.livre)
        self.aref = _spin(0.0, 0.0, 1e4, 5); f.addRow("Área de referência m² (0 = área frontal projetada da malha)", self.aref)
        self.cdref = _spin(0.0, 0.0, 100, 4); f.addRow("Cd de referência (0 = nenhum)", self.cdref)
        self.reft = QLineEdit(); f.addRow("Fonte da referência (obrigatória p/ VALIDADO)", self.reft)
        v.addLayout(f)
        r = QHBoxLayout()
        self.b_run = QPushButton("Executar CFD (processo isolado)"); self.b_run.clicked.connect(self.run); r.addWidget(self.b_run)
        self.b_cancel = QPushButton("Cancelar"); self.b_cancel.setEnabled(False); self.b_cancel.clicked.connect(self.cancel); r.addWidget(self.b_cancel)
        v.addLayout(r)
        self.progress = QProgressBar(); self.progress.setRange(0, 100); self.progress.setVisible(False); v.addWidget(self.progress)
        self.b_view = QPushButton("Mostrar Cp no corpo, no visualizador 3D"); self.b_view.clicked.connect(self.show_cp); v.addWidget(self.b_view)
        self.b_save = QPushButton("Salvar resultado em um projeto…"); self.b_save.clicked.connect(self.save_result); v.addWidget(self.b_save)
        self.out = QTextEdit(); self.out.setReadOnly(True); v.addWidget(self.out)
        self.jobs = None; self._job = None; self.last = None; self.campo = None; self.last_field_info = None
        self._timer = QTimer(self); self._timer.setInterval(500); self._timer.timeout.connect(self._poll)

    def pick_stl(self) -> None:
        p, _ = QFileDialog.getOpenFileName(self, "STL", "", "STL (*.stl)")
        if p:
            self.stl.setText(p)

    def _args(self) -> dict:
        return dict(part_key=self.part.currentData() or "", part_params={}, stl_path=self.stl.text().strip() if not self.part.currentData() else "",
                    stl_unit=self.unit.currentText(), v_inf=self.v.value(), iteracoes=self.it.value(),
                    celulas=[self.cx.value(), self.cy.value(), self.cz.value()], gap_m=self.gap.value(), a_ref=self.aref.value() or None,
                    rho=self.rho.value(), nu=self.nu.value(), ar_livre=self.livre.isChecked(), camadas=self.cam.value(), cd_ref=self.cdref.value() or None, ref_texto=self.reft.text().strip())

    def run(self) -> None:
        a = self._args()
        if not a["part_key"] and not a["stl_path"]:
            QMessageBox.warning(self, "CFD", "Escolha uma peça da biblioteca ou um arquivo STL."); return
        if a["cd_ref"] and not a["ref_texto"]:
            QMessageBox.warning(self, "CFD", "Cd de referência exige a FONTE da referência (senão o resultado não pode ser validado)."); return
        if self._job is not None and not self._job.terminal:
            return
        from core.jobs import JobManager
        self.jobs = self.jobs or JobManager(1)
        self._job = self.jobs.submit_python("CFD OpenFOAM (isolado)", "modules.cfd_job", "run_case", a, timeout=6 * 3600)
        self.progress.setValue(0); self.progress.setVisible(True); self.b_run.setEnabled(False); self.b_cancel.setEnabled(True)
        self.out.setPlainText("Executando OpenFOAM em processo separado (malha + solver)…")
        self.campo = None
        self._timer.start()

    def cancel(self) -> None:
        if self._job is not None and not self._job.terminal:
            self.jobs.cancel(self._job.id)

    def _poll(self) -> None:
        j = self._job
        if j is None:
            self._timer.stop(); return
        self.progress.setValue(int(j.progress))
        if not j.terminal:
            return
        self._timer.stop(); self.b_run.setEnabled(True); self.b_cancel.setEnabled(False)
        if j.state == "DONE":
            from modules.result_trace import TracedResult
            r = j.result()
            self.last = TracedResult(**{k: x for k, x in r["result"].items() if k in TracedResult.__dataclass_fields__})
            txt = self.last.to_json()
            if r.get("pressao"):
                txt += "\n\n--- pressão integrada (sem atrito viscoso) ---\n" + json.dumps(r["pressao"], ensure_ascii=False, indent=2)
            if r.get("campo_erro"):
                txt += "\n\n[mapa de Cp indisponível: " + r["campo_erro"] + "]"
            self.out.setPlainText(txt)
            self.campo = r.get("campo")
        elif j.state == "CANCELLED":
            self.out.setPlainText("Cancelado pelo usuário. Nenhum resultado foi gravado.")
        else:
            self.out.setPlainText(f"{j.state}: {j.error}\n\n--- log do processo ---\n" + "\n".join(j.log.splitlines()[-25:]))

    def show_cp(self) -> None:
        if not self.campo:
            QMessageBox.information(self, "CFD", "Não há campo de pressão (execute o CFD primeiro; sem OpenFOAM não há resultado)."); return
        import numpy as np
        w = self.parent()
        while w is not None and not hasattr(w, "viewport"):
            w = w.parent() if hasattr(w, "parent") else None
        if w is None:
            QMessageBox.information(self, "CFD", "Visualizador 3D indisponível neste contexto."); return
        z = np.load(self.campo)
        ends = np.cumsum(z["faces_len"]); starts = ends - z["faces_len"]
        polys = [z["faces_idx"][a:b] for a, b in zip(starts, ends)]
        # coordenadas ORIGINAIS da geometria (mesma unidade/posição das peças): o Cp fica sobre a peça, sem esconder as demais
        self.last_field_info = w.viewport.show_surface_field(z["pontos_orig"], polys, z["cp"], title="Cp", unit="", hide_parts=False)
        self.out.append(f"\n[Cp no visualizador ({str(z['unidade'])}, posição original da geometria): {self.last_field_info['min']:.3g} a {self.last_field_info['max']:.3g}; "
                        "pressão de referência = 0 na saída; só pressão (sem atrito).]")
        if not self.sync:
            self.accept()

    def save_result(self) -> None:
        if not self.last:
            QMessageBox.information(self, "CFD", "Execute o CFD primeiro."); return
        from PySide6.QtWidgets import QInputDialog
        from interface.solvers_dialog import PROJECTS_DIR
        from modules.workspace import ProjectStore
        st = ProjectStore(PROJECTS_DIR); names = st.list()
        if not names:
            QMessageBox.information(self, "CFD", "Crie um projeto em 'Solvers, vitrine e projetos…'."); return
        n, ok = QInputDialog.getItem(self, "Projeto", "Salvar em:", names, 0, False)
        if ok:
            st.attach_result(st.open(n), self.last)
