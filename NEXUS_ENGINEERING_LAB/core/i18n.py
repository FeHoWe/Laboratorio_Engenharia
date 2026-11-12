"""Internacionalização (V3.8) — `tr(texto)` traduz o texto-fonte (português/inglês do código) com catálogos JSON em `locales/<código>.json`.

Cadeia de fallback: idioma escolhido → inglês (`en`) → texto original. Texto sem tradução NUNCA some: aparece no original. Para contribuir com um idioma
basta copiar `locales/en.json` para `locales/<código>.json` (ex.: `it.json`, `ja.json`) e traduzir os VALORES; o idioma aparece sozinho no menu.
Idioma: variável NEXUS_LANG, ou o salvo em ~/.nexus_lab/idioma.json (menu Tools → Idioma / Language), ou o do sistema, ou `pt`. Mudança vale após reiniciar.
As traduções incluídas foram escritas por IA e NÃO foram revisadas por falantes nativos nem por engenheiros de cada área: revise antes de uso crítico.
"""
from __future__ import annotations

import json
import locale
import os
from pathlib import Path

LOCALES = Path(__file__).resolve().parent.parent / "locales"
CONFIG = Path.home() / ".nexus_lab" / "idioma.json"
NOMES = {"pt": "Português", "en": "English", "es": "Español", "de": "Deutsch", "fr": "Français", "it": "Italiano", "zh": "中文", "ja": "日本語", "ko": "한국어", "ru": "Русский", "tr": "Türkçe", "pl": "Polski", "nl": "Nederlands", "hi": "हिन्दी", "ar": "العربية", "id": "Bahasa Indonesia"}
RTL = {"ar", "he", "fa", "ur"}
_cache: dict[str, dict] = {}
_atual: str | None = None


def _carregar(cod: str) -> dict:
    if cod not in _cache:
        p = LOCALES / f"{cod}.json"
        try:
            _cache[cod] = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        except (OSError, ValueError):
            _cache[cod] = {}
    return _cache[cod]


def idiomas_disponiveis() -> dict[str, str]:
    """{código: nome} do português (fonte) mais todo `locales/*.json`."""
    r = {"pt": NOMES["pt"]}
    if LOCALES.exists():
        for p in sorted(LOCALES.glob("*.json")):
            if p.stem == "glossario":
                continue
            r[p.stem] = NOMES.get(p.stem, p.stem)
    return r


def idioma() -> str:
    global _atual
    if _atual is None:
        cod = os.environ.get("NEXUS_LANG", "")
        if not cod:
            try:
                cod = json.loads(CONFIG.read_text(encoding="utf-8")).get("idioma", "")
            except (OSError, ValueError):
                cod = ""
        if not cod:
            try:
                cod = (locale.getlocale()[0] or "pt")[:2]
            except Exception:
                cod = "pt"
        _atual = cod.lower()[:2] if cod.lower()[:2] in idiomas_disponiveis() else "pt"
    return _atual


def definir_idioma(cod: str, salvar: bool = True) -> None:
    global _atual
    if cod not in idiomas_disponiveis():
        raise ValueError(f"idioma '{cod}' indisponível")
    _atual = cod
    if salvar:
        try:
            CONFIG.parent.mkdir(parents=True, exist_ok=True)
            CONFIG.write_text(json.dumps({"idioma": cod}), encoding="utf-8")
        except OSError:
            pass


def tr(texto: str | None) -> str | None:
    """Traduz `texto`; sem tradução devolve o original (nunca falha nem some)."""
    if not texto:
        return texto
    cod = idioma()
    cadeia = (cod,) if cod == "pt" else (cod, "en")
    for c in cadeia:
        v = _carregar(c).get(texto)
        if v:
            return v
    return texto


# ---------------------------------------------------------------- tradução automática dos textos ESTÁTICOS de widgets Qt
_instalado = False


def instalar_hooks_qt() -> bool:
    """Faz os widgets Qt traduzirem, por CORRESPONDÊNCIA EXATA, o texto estático que recebem (rótulos, botões, caixas, abas, títulos, dicas, cabeçalhos de tabela).
    Texto montado em tempo de execução (f-strings, resultados) não bate com nenhuma chave e fica como está. Itens de ComboBox e campos de entrada NÃO são tocados
    (o código lê esses valores de volta). Idempotente; não faz nada em português (idioma de origem). Devolve True se instalou."""
    global _instalado
    if _instalado or idioma() == "pt":
        return False
    from PySide6 import QtWidgets as W
    from PySide6.QtCore import Qt
    if idioma() in RTL:
        W.QApplication.setLayoutDirection(Qt.RightToLeft)          # árabe: interface espelhada da direita para a esquerda

    def wrap_setter(cls, nome):
        orig = getattr(cls, nome)
        def novo(self, texto, *a, **k):
            return orig(self, tr(texto) if isinstance(texto, str) else texto, *a, **k)
        setattr(cls, nome, novo)

    def wrap_init(cls):
        orig = cls.__init__
        def novo(self, *a, **k):
            if a and isinstance(a[0], str):
                a = (tr(a[0]),) + a[1:]
            return orig(self, *a, **k)
        cls.__init__ = novo

    for c in (W.QLabel, W.QPushButton, W.QCheckBox, W.QRadioButton, W.QGroupBox):
        wrap_init(c)
    for c, ms in ((W.QLabel, ("setText",)), (W.QAbstractButton, ("setText", "setToolTip")), (W.QGroupBox, ("setTitle",)),
                  (W.QWidget, ("setWindowTitle", "setToolTip", "setStatusTip")), (W.QLineEdit, ("setPlaceholderText",))):
        for m in ms:
            wrap_setter(c, m)
    o_tab = W.QTabWidget.addTab
    def add_tab(self, w, *a):
        a = tuple(tr(x) if isinstance(x, str) else x for x in a)
        return o_tab(self, w, *a)
    W.QTabWidget.addTab = add_tab
    o_row = W.QFormLayout.addRow
    def add_row(self, *a):
        if a and isinstance(a[0], str):
            a = (tr(a[0]),) + a[1:]
        return o_row(self, *a)
    W.QFormLayout.addRow = add_row
    for nome in ("setHorizontalHeaderLabels", "setVerticalHeaderLabels"):
        o = getattr(W.QTableWidget, nome)
        def mk(o):
            def novo(self, labels):
                return o(self, [tr(x) if isinstance(x, str) else x for x in labels])
            return novo
        setattr(W.QTableWidget, nome, mk(o))
    _instalado = True
    return True
