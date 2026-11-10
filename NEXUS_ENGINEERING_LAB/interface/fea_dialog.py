"""Estudo FEA 3D de peça da biblioteca (NEXUS-Tet4). Material e carga: SEMPRE digitados pelo usuário."""
from __future__ import annotations
from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QProgressBar, QHBoxLayout, QDialog, QDoubleSpinBox, QFormLayout, QLabel, QMessageBox, QPushButton,
                               QTextEdit, QVBoxLayout, QWidget)
from samples.library import PARTS
from modules import fea_study, fea3d, fea_voxel, fea_gmsh, fea_tet10


class _Worker(QThread):
    finished_ok = Signal(object); failed = Signal(object)

    def __init__(self, job) -> None:
        super().__init__(); self.job = job

    def run(self) -> None:
        try: self.finished_ok.emit(self.job())
        except Exception as e: self.failed.emit(e)


def _spin(v, lo=-1e9, hi=1e9, dec=3):
    s = QDoubleSpinBox(); s.setRange(lo, hi); s.setDecimals(dec); s.setValue(v); return s


class FeaDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Estudo FEA 3D de peça (NEXUS-Tet4)"); self.resize(560, 640)
        v = QVBoxLayout(self)
        v.addWidget(QLabel("Análise linear-elástica por voxels→tetraedros. NÃO é CalculiX; classe: SIMULAÇÃO NUMÉRICA (código verificado em casos-padrão; não validado para a sua geometria)."))
        self.part = QComboBox(); [self.part.addItem(p.title, p.key) for p in PARTS.values()]
        form = QFormLayout(); form.addRow("Peça", self.part)
        self.pw = QWidget(); self.pf = QFormLayout(self.pw); v.addLayout(form); v.addWidget(self.pw)
        self.E = _spin(0, 0, 1e7, 1); self.nu = _spin(0, 0, 0.499, 3); self.sy = _spin(0, 0, 1e5, 1); self.h = _spin(3.0, 0.1, 1000, 2)
        f2 = QFormLayout()
        f2.addRow("E (MPa) — informe", self.E); f2.addRow("ν — informe", self.nu); f2.addRow("Escoamento MPa (0 = sem FS)", self.sy); f2.addRow("Aresta do voxel h (mm)", self.h)
        self.ff = QComboBox(); self.lf = QComboBox()
        for c in (self.ff, self.lf): c.addItems(list(fea_study.FACES))
        self.ff.setCurrentText("xmin"); self.lf.setCurrentText("xmax")
        self.mesher = QComboBox(); self.mesher.addItem("Voxel (escada)", "voxel")
        if fea_gmsh.available(): self.mesher.insertItem(0, "Gmsh (superfície real)", "gmsh"); self.mesher.setCurrentIndex(0)
        self.order = QComboBox(); self.order.addItem("Tet10 quadrático (recomendado)", 2); self.order.addItem("Tet4 linear (trava em flexão)", 1)
        f2.addRow("Malhador", self.mesher); f2.addRow("Elemento", self.order)
        f2.addRow("Face engastada", self.ff); f2.addRow("Face carregada", self.lf)
        self.F = [_spin(0, -1e9, 1e9, 2) for _ in range(3)]
        for n, s in zip("XYZ", self.F): f2.addRow(f"Força F{n} total (N)", s)
        v.addLayout(f2)
        self.rho = _spin(0, 0, 1e-3, 12); f2.addRow("Densidade t/mm³ (modal; aço≈7.85e-9) — informe", self.rho)
        b = QPushButton("Executar (estático)"); b.clicked.connect(self.run); v.addWidget(b)
        iso = QHBoxLayout()
        self.b_iso = QPushButton("Executar em PROCESSO ISOLADO (cancelável, com progresso)"); self.b_iso.clicked.connect(self.run_isolated); iso.addWidget(self.b_iso)
        self.b_cancel = QPushButton("Cancelar"); self.b_cancel.setEnabled(False); self.b_cancel.clicked.connect(self.cancel_isolated); iso.addWidget(self.b_cancel)
        v.addLayout(iso)
        self.chk_ccx = QCheckBox("Repetir no CalculiX e comparar (se instalado)"); v.addWidget(self.chk_ccx)
        self.progress = QProgressBar(); self.progress.setRange(0, 100); self.progress.setVisible(False); v.addWidget(self.progress)
        self._job = None; self.jobs = None; self._timer = QTimer(self); self._timer.setInterval(200); self._timer.timeout.connect(self._poll)
        b2 = QPushButton("Estudo de convergência de malha (h, 1,5h, 2h)"); b2.clicked.connect(self.conv); v.addWidget(b2)
        b3 = QPushButton("Frequências naturais (engaste na face fixa)"); b3.clicked.connect(self.modal); v.addWidget(b3)
        b5 = QPushButton("Exportar último estudo estático para ParaView (.vtk)…"); b5.clicked.connect(self.export_vtk); v.addWidget(b5)
        self.data = None
        b4 = QPushButton("Salvar último resultado em um projeto…"); b4.clicked.connect(self.save_result); v.addWidget(b4)
        self.last = None
        self.out = QTextEdit(); self.out.setReadOnly(True); v.addWidget(self.out)
        self.part.currentIndexChanged.connect(self.rebuild); self.rebuild()

    def rebuild(self) -> None:
        while self.pf.rowCount(): self.pf.removeRow(0)
        self.pspin = {}
        for p in PARTS[self.part.currentData()].params:
            s = _spin(p.default, p.lo, p.hi, p.decimals); self.pspin[p.key] = s; self.pf.addRow(f"{p.label} ({p.unit})", s)

    # ---- execução assíncrona (a interface não congela)
    sync = False                       # True nos testes (executa na thread atual)

    def _go(self, job, store_data: bool = False) -> None:
        """job: callable sem argumentos → (TracedResult, dados|None). Lê os widgets ANTES (thread principal)."""
        if getattr(self, "_busy", False):
            return
        def done(res, err):
            self._busy = False
            for b in self.findChildren(QPushButton): b.setEnabled(True)
            self.unsetCursor()
            if err is not None:
                self.out.setPlainText(f"ERRO: {err}"); return
            r, d = res
            self.last = r
            if store_data: self.data = d
            self.out.setPlainText(r.to_json())
        self._busy = True
        if self.sync:
            try: res = job()
            except Exception as e: done(None, e)
            else: done(res, None)
            return
        for b in self.findChildren(QPushButton): b.setEnabled(False)
        self.setCursor(Qt.BusyCursor); self.out.setPlainText("Calculando…")
        self._worker = _Worker(job); self._worker.finished_ok.connect(lambda r: done(r, None)); self._worker.failed.connect(lambda e: done(None, e))
        self._worker.start()

    def _vals(self) -> dict:
        return dict(E=self.E.value(), nu=self.nu.value(), h=self.h.value(), ff=self.ff.currentText(), lf=self.lf.currentText(),
                    F=[s.value() for s in self.F], sy=self.sy.value() or None, mesher=self.mesher.currentData(), order=self.order.currentData(),
                    rho=self.rho.value())

    def run(self) -> None:
        if self.E.value() <= 0 or self.nu.value() <= 0:
            QMessageBox.warning(self, "FEA", "Informe E e ν do material (o NEXUS não atribui material sozinho)."); return
        try: shape = self._shape(); v = self._vals()
        except Exception as e:
            self.out.setPlainText(f"ERRO: {e}"); return
        self._go(lambda: fea_study.run(shape, v["h"], v["E"], v["nu"], v["ff"], v["lf"], v["F"], v["sy"], mesher=v["mesher"], order=v["order"]), True)

    # ---- execução em processo separado (V3.1): um travamento/erro do solver não derruba o NEXUS; há progresso e cancelamento
    def run_isolated(self) -> None:
        if self.E.value() <= 0 or self.nu.value() <= 0:
            QMessageBox.warning(self, "FEA", "Informe E e ν do material (o NEXUS não atribui material sozinho)."); return
        if self._job is not None and not self._job.terminal:
            return
        from core.jobs import JobManager
        v = self._vals()
        args = dict(part_key=self.part.currentData(), part_params={k: s.value() for k, s in self.pspin.items()}, h=v["h"], E=v["E"], nu=v["nu"],
                    ff=v["ff"], lf=v["lf"], force=v["F"], sy=v["sy"], mesher=v["mesher"], order=v["order"], ccx=self.chk_ccx.isChecked())
        self.jobs = self.jobs or JobManager(1)
        self._job = self.jobs.submit_python("FEA estático (isolado)", "modules.fea_job", "run_static", args, timeout=3600)
        self.progress.setValue(0); self.progress.setVisible(True); self.b_iso.setEnabled(False); self.b_cancel.setEnabled(True)
        self.out.setPlainText("Executando em processo separado…")
        self._timer.start()

    def cancel_isolated(self) -> None:
        if self._job is not None and not self._job.terminal:
            self.jobs.cancel(self._job.id)

    def _poll(self) -> None:
        j = self._job
        if j is None:
            self._timer.stop(); return
        self.progress.setValue(int(j.progress))
        if not j.terminal:
            return
        self._timer.stop(); self.b_iso.setEnabled(True); self.b_cancel.setEnabled(False)
        if j.state == "DONE":
            import json
            from modules.result_trace import TracedResult
            r = j.result()
            self.last = TracedResult(**{k: x for k, x in r["result"].items() if k in TracedResult.__dataclass_fields__})
            txt = self.last.to_json()
            if r.get("ccx"):
                txt += "\n\n--- CalculiX ---\n" + json.dumps(r["ccx"], ensure_ascii=False, indent=2)
            self.out.setPlainText(txt)
        elif j.state == "CANCELLED":
            self.out.setPlainText("Cancelado pelo usuário. Nenhum resultado foi gravado.")
        else:
            self.out.setPlainText(f"{j.state}: {j.error}\n\n--- log do processo ---\n" + "\n".join(j.log.splitlines()[-25:]))

    def _shape(self):
        return PARTS[self.part.currentData()].make(**{k: s.value() for k, s in self.pspin.items()})

    def conv(self) -> None:
        if self.E.value() <= 0 or self.nu.value() <= 0:
            QMessageBox.warning(self, "FEA", "Informe E e ν."); return
        try: shape = self._shape(); v = self._vals()
        except Exception as e:
            self.out.setPlainText(f"ERRO: {e}"); return
        h = v["h"]
        self._go(lambda: (fea_study.convergencia(shape, [2 * h, 1.5 * h, h], v["E"], v["nu"], v["ff"], v["lf"], v["F"], mesher=v["mesher"], order=v["order"]), None))

    def modal(self) -> None:
        if min(self.E.value(), self.nu.value(), self.rho.value()) <= 0:
            QMessageBox.warning(self, "FEA", "Informe E, ν e densidade."); return
        try: shape = self._shape(); v = self._vals()
        except Exception as e:
            self.out.setPlainText(f"ERRO: {e}"); return

        def job():
            from modules.result_trace import TracedResult
            mesh, info = fea_study._mesh(shape, v["h"], v["mesher"], v["order"])
            quad = mesh.tets.shape[1] == 10
            fx = {i: (0, 1, 2) for i in fea_study.face_nodes(mesh, v["ff"])}
            f = (fea_tet10 if quad else fea3d).modal(mesh, v["E"], v["nu"], v["rho"], fx, 6)
            lim = ["Tet4 sobrestima frequências (rigidez de flexão)"] if not quad else ["massa consistente assume arestas retas"]
            if v["mesher"] == "voxel": lim.append("voxels em escada")
            return TracedResult("Frequências naturais", "SIMULACAO_NUMERICA", "Autovalores generalizados K φ = ω² M φ (massa consistente)",
                                {"freq_Hz": [float(x) for x in f], "tetraedros": info["tetraedros"]}, {"E_MPa": v["E"], "nu": v["nu"], "rho_t_mm3": v["rho"]},
                                ["engaste total na face fixa"], lim, solver=fea_tet10.SOLVER10 if quad else fea3d.SOLVER, solver_versao=fea3d.SOLVER_VER), None
        self._go(job)

    def save_result(self) -> None:
        from PySide6.QtWidgets import QInputDialog
        from interface.solvers_dialog import PROJECTS_DIR
        from modules.workspace import ProjectStore
        if self.last is None:
            QMessageBox.information(self, "FEA", "Execute uma análise primeiro."); return
        st = ProjectStore(PROJECTS_DIR); names = st.list()
        if not names:
            QMessageBox.information(self, "FEA", "Crie um projeto em 'Solvers, vitrine e projetos…'."); return
        n, ok = QInputDialog.getItem(self, "Projeto", "Salvar em:", names, 0, False)
        if ok:
            st.attach_result(st.open(n), self.last)

    def export_vtk(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        if not self.data:
            QMessageBox.information(self, "FEA", "Execute o estudo estático primeiro."); return
        p, _ = QFileDialog.getSaveFileName(self, "Exportar VTK", "resultado.vtk", "VTK (*.vtk)")
        if p:
            fea3d.export_vtk(p, self.data["mesh"], self.data["u"], self.data["vm"])
