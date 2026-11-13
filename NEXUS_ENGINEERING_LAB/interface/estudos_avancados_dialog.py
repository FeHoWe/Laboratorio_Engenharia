"""V110 (Fase B) — Estudos avançados: interface gráfica para o que só existia na API/CLI (V30–V100).

Só chama os módulos existentes (`validacao_dados`, `calibracao`, `carro_do_projeto`, `freio_termico`, `dinamica_lateral`, `dossie`); NENHUM cálculo novo aqui.
Os valores de exemplo do carro e do disco são ILUSTRATIVOS (não são de um carro/freio real). A classe do resultado aparece no texto de cada módulo.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (QDialog, QFileDialog, QFormLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QTabWidget, QVBoxLayout, QWidget)

from core.i18n import tr

CARRO_EXEMPLO = "massa=800 p_ice=500000 cda=1.0 cla=3.0 mu=1.6 p_ers=300000 e_ers=4000000"


def parse_kv(texto: str, nome: str = "campo") -> dict:
    """'a=1 b=2,5' → {'a': 1.0, 'b': 2.5}. Erro claro em vez de ignorar texto estranho."""
    out = {}
    for tok in texto.replace(";", " ").split():
        if "=" not in tok:
            raise ValueError(f"{nome}: use campo=valor (recebido '{tok}')")
        k, v = tok.split("=", 1)
        try:
            out[k.strip()] = float(v.replace(",", "."))
        except ValueError:
            raise ValueError(f"{nome}: valor inválido em '{tok}'")
    return out


class EstudosAvancadosDialog(QDialog):
    def __init__(self, window=None) -> None:
        super().__init__(window)
        self.w = window
        self.setWindowTitle(tr("Estudos avançados"))
        self.resize(820, 640)
        v = QVBoxLayout(self)
        v.addWidget(QLabel(tr("Carro (campo=valor, SI; exemplo ilustrativo, não é de um carro real):")))
        self.carro_txt = QLineEdit(CARRO_EXEMPLO); v.addWidget(self.carro_txt)
        self.tabs = QTabWidget(); v.addWidget(self.tabs)
        self.saida = QPlainTextEdit(); self.saida.setReadOnly(True); v.addWidget(self.saida, 1)
        self.tabs.addTab(self._tab_validacao(), tr("Validação"))
        self.tabs.addTab(self._tab_calibracao(), tr("Calibração"))
        self.tabs.addTab(self._tab_projeto(), tr("Projeto → carro"))
        self.tabs.addTab(self._tab_freios(), tr("Freios"))
        self.tabs.addTab(self._tab_lateral(), tr("Dinâmica lateral"))
        self.tabs.addTab(self._tab_comparar(), tr("Comparar A/B"))
        self.tabs.addTab(self._tab_dossie(), tr("Dossiê"))

    # ---------- utilidades ----------
    def _carro(self):
        from modules import lapsim
        try:
            return lapsim.Carro(**parse_kv(self.carro_txt.text(), "carro"))
        except TypeError as e:
            raise ValueError(f"carro: parâmetro desconhecido ou faltando ({e})")

    def _executar(self, fn) -> None:
        try:
            self.saida.setPlainText(fn())
            from core import atividade
            atividade.registrar("estudo", f"Estudos avançados — {self.tabs.tabText(self.tabs.currentIndex())}")
        except Exception as e:  # noqa: BLE001 - a janela nunca deve fechar por erro de cálculo
            self.saida.setPlainText(f"Não foi possível calcular: {e}")

    def _form(self, *campos):
        w = QWidget(); f = QFormLayout(w)
        edits = []
        for rot, padrao in campos:
            e = QLineEdit(padrao); f.addRow(tr(rot), e); edits.append(e)
        return w, f, edits

    def _escolher(self, titulo: str, filtro: str) -> str:
        p, _ = QFileDialog.getOpenFileName(self, titulo, "", filtro)
        return p

    # ---------- validação ----------
    def _tab_validacao(self):
        w, f, (self.v_tol,) = self._form(("Tolerâncias SUAS (rmse_kmh=… vies_kmh_abs=… tempo_pct_abs=… max_abs_kmh=…)", ""))
        b = QPushButton(tr("Validar com telemetria…")); b.clicked.connect(lambda: self.run_validacao()); f.addRow(b)
        return w

    def run_validacao(self, caminho: str | None = None) -> None:
        caminho = caminho or self._escolher("Telemetria do usuário", "CSV/Texto (*.csv *.txt)")
        if not caminho:
            return

        def go():
            from modules import validacao_dados as VD
            r = VD.validar(self._carro(), VD.ler_telemetria(Path(caminho)), None, 3.0, parse_kv(self.v_tol.text(), "tolerâncias") or None)
            return VD.texto(r)
        self._executar(go)

    # ---------- calibração ----------
    def _tab_calibracao(self):
        w, f, (self.k_param, self.k_treino) = self._form(("Parâmetros e faixas (campo=lo:hi, separados por espaço)", "mu=1.2:1.9"), ("Fração usada no treino (0,3–1,0)", "0.7"))
        b = QPushButton(tr("Calibrar com telemetria…")); b.clicked.connect(lambda: self.run_calibracao()); f.addRow(b)
        return w

    def run_calibracao(self, caminho: str | None = None) -> None:
        caminho = caminho or self._escolher("Telemetria do usuário", "CSV/Texto (*.csv *.txt)")
        if not caminho:
            return

        def go():
            from modules import calibracao as KB, validacao_dados as VD
            faixas = {}
            for tok in self.k_param.text().split():
                if "=" not in tok or ":" not in tok:
                    raise ValueError(f"use campo=lo:hi (recebido '{tok}')")
                k, r = tok.split("=", 1); lo, hi = r.split(":", 1)
                faixas[k] = (float(lo.replace(",", ".")), float(hi.replace(",", ".")))
            r = KB.calibrar(self._carro(), faixas, VD.ler_telemetria(Path(caminho)), None, 3.0, float(self.k_treino.text().replace(",", ".")))
            return KB.texto(r)
        self._executar(go)

    # ---------- projeto → carro ----------
    def _tab_projeto(self):
        w, f, (self.p_yd, self.p_yt) = self._form(("Posição do eixo dianteiro (mm, no eixo longitudinal do projeto)", ""), ("Posição do eixo traseiro (mm)", ""))
        b = QPushButton(tr("Levantar massa/CG/inércia do projeto aberto")); b.clicked.connect(lambda: self.run_projeto()); f.addRow(b)
        f.addRow(QLabel(tr("Só entram peças com material atribuído por você; as demais são listadas como ignoradas.")))
        return w

    def run_projeto(self) -> None:
        def go():
            from modules import carro_do_projeto as CP
            if self.w is None or not hasattr(self.w, "project"):
                raise ValueError("abra esta janela a partir do NEXUS com um projeto aberto")
            yd, yt = float(self.p_yd.text().replace(",", ".")), float(self.p_yt.text().replace(",", "."))
            lev = CP.levantar(self.w.project, yd, yt)
            c = CP.carro_do_projeto(self._carro(), lev)
            partes = [f"{k}={v:g}" for k, v in vars(c).items() if isinstance(v, (int, float)) and not isinstance(v, bool)]
            self.carro_txt.setText(" ".join(partes))              # o carro passa a usar a massa do projeto
            return CP.texto(lev) + "\n\nCampo 'Carro' atualizado com a massa do projeto (demais campos mantidos)."
        self._executar(go)

    # ---------- freios ----------
    def _tab_freios(self):
        w, f, (self.f_d, self.f_t, self.f_voltas) = self._form(
            ("Disco dianteiro (massa= cp= area= [h0= h1= emissividade= f_disco= lim_T_C=])", "massa=1.4 cp=800 area=0.045"),
            ("Disco traseiro", "massa=1.1 cp=800 area=0.04"), ("Voltas", "5"))
        b = QPushButton(tr("Calcular energia e temperatura")); b.clicked.connect(lambda: self.run_freios()); f.addRow(b)
        f.addRow(QLabel(tr("Valores de exemplo ilustrativos: use as propriedades do SEU disco.")))
        return w

    def run_freios(self) -> None:
        def go():
            from modules import freio_termico as FT
            r = FT.termica(self._carro(), FT.Disco(**parse_kv(self.f_d.text(), "disco dianteiro")), FT.Disco(**parse_kv(self.f_t.text(), "disco traseiro")),
                           0.6, None, 3.0, int(self.f_voltas.text()))
            return FT.texto(r)
        self._executar(go)

    # ---------- dinâmica lateral ----------
    def _tab_lateral(self):
        w, f, (self.l_par, self.l_u) = self._form(("Parâmetros (massa= a= b= iz= cf= cr=; Cf/Cr em N/rad POR EIXO, seus)", "massa=800 a=1.6 b=1.7 iz=900 cf=120000 cr=140000"),
                                                 ("Velocidades (m/s)", "20 40 60"))
        b = QPushButton(tr("Calcular resposta ao degrau")); b.clicked.connect(lambda: self.run_lateral()); f.addRow(b)
        return w

    def run_lateral(self) -> None:
        def go():
            from modules import dinamica_lateral as DL
            p = DL.ParamsLat(**parse_kv(self.l_par.text(), "parâmetros"))
            us = [float(x.replace(",", ".")) for x in self.l_u.text().split()]
            var = DL.varredura_velocidade(p, us)
            return "\n".join(DL.texto(g) for g in var[1:]) + ("\n" if len(var) > 1 else "") + DL.texto(DL.degrau(p, us[0]))
        self._executar(go)

    # ---------- comparação A/B de veículos ----------
    def _tab_comparar(self):
        w, f, _ = self._form()
        f.addRow(QLabel(tr("Duas configurações em JSON (blocos carro, bicicleta, lateral, U_ms, freios): compara só o que existe nas DUAS, cada métrica com o modelo e as hipóteses.")))
        b = QPushButton(tr("Comparar configurações A e B…")); b.clicked.connect(lambda: self.comparar_veiculos()); f.addRow(b)
        return w

    def comparar_veiculos(self, a: str | None = None, b: str | None = None) -> None:
        a = a or self._escolher("Configuração A", "JSON (*.json)")
        if not a:
            return
        b = b or self._escolher("Configuração B", "JSON (*.json)")
        if not b:
            return

        def go():
            import json
            from modules import veiculo_comparacao as VC
            return VC.texto(VC.comparar(json.loads(Path(a).read_text(encoding="utf-8")), json.loads(Path(b).read_text(encoding="utf-8"))))
        self._executar(go)

    # ---------- dossiê ----------
    def _tab_dossie(self):
        w, f, _ = self._form()
        b1 = QPushButton(tr("Criar dossiê a partir de especificação JSON…")); b1.clicked.connect(lambda: self.criar_dossie())
        b2 = QPushButton(tr("Verificar dossiê…")); b2.clicked.connect(lambda: self.verificar_dossie())
        f.addRow(b1); f.addRow(b2)
        return w

    def criar_dossie(self, espec: str | None = None, saida: str | None = None) -> None:
        espec = espec or self._escolher("Especificação do dossiê", "JSON (*.json)")
        if not espec:
            return
        if not saida:
            saida, _ = QFileDialog.getSaveFileName(self, tr("Salvar dossiê"), "", "Dossiê (*.dossie.json)")
        if not saida:
            return

        def go():
            import json
            from modules import dossie as DS
            e = json.loads(Path(espec).read_text(encoding="utf-8"))
            d = DS.criar(e["tipo"], e["parametros"], e.get("nota", ""))
            DS.salvar(d, saida)
            return DS.texto(d) + f"\n\nGravado em {saida}"
        self._executar(go)

    def verificar_dossie(self, caminho: str | None = None) -> None:
        caminho = caminho or self._escolher("Dossiê", "Dossiê (*.json)")
        if not caminho:
            return

        def go():
            from modules import dossie as DS
            d = DS.carregar(caminho)
            return DS.texto(d, DS.verificar(d))
        self._executar(go)
