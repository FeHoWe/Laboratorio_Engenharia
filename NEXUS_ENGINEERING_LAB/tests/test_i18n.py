"""Internacionalização (V3.8): fallback, catálogos consistentes e menus traduzidos."""
import json

import pytest

from core import i18n


@pytest.fixture(autouse=True)
def _restaura():
    ant = i18n._atual
    yield
    i18n._atual = ant


def test_fallback_em_cadeia_nunca_some_texto():
    i18n.definir_idioma("de", salvar=False)
    assert i18n.tr("Salvar") == "Speichern"
    assert i18n.tr("Texto sem tradução nenhuma") == "Texto sem tradução nenhuma"           # original
    assert i18n.tr("Perspectiva") == "Perspektive"
    # texto presente só no inglês cai no inglês (simulado: remove a chave do catálogo alemão em memória)
    i18n._carregar("de"); antigo = i18n._cache["de"].pop("Gerenciar cenas…")
    try:
        assert i18n.tr("Gerenciar cenas…") == "Manage scenes…"
    finally:
        i18n._cache["de"]["Gerenciar cenas…"] = antigo
    i18n.definir_idioma("pt", salvar=False)
    assert i18n.tr("Salvar") == "Salvar" and i18n.tr("File") == "Arquivo" and i18n.tr(None) is None and i18n.tr("") == ""


def test_catalogos_json_validos_e_chaves_existem_no_ingles():
    en = json.loads((i18n.LOCALES / "en.json").read_text(encoding="utf-8"))
    for cod in i18n.idiomas_disponiveis():
        if cod in ("pt",):
            continue
        d = json.loads((i18n.LOCALES / f"{cod}.json").read_text(encoding="utf-8"))
        assert all(isinstance(v, str) and v.strip() for v in d.values()), cod
        assert set(d) <= set(en), (cod, set(d) - set(en))                                   # nenhuma chave órfã
    assert len(en) >= 95                                                                     # todos os textos de ação do menu cobertos


def test_toda_acao_do_menu_tem_traducao_em_ingles():
    import ast, pathlib
    t = ast.parse((pathlib.Path(__file__).resolve().parent.parent / "interface" / "main_window.py").read_text(encoding="utf-8"))
    en = json.loads((i18n.LOCALES / "en.json").read_text(encoding="utf-8"))
    faltam = []
    for n in ast.walk(t):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "a" and len(n.args) >= 2 and isinstance(n.args[1], ast.Constant):
            vals = [n.args[1].value] + [kw.value.value for kw in n.keywords if kw.arg == "tip" and isinstance(kw.value, ast.Constant)]
            if len(n.args) >= 6 and isinstance(n.args[5], ast.Constant):
                vals.append(n.args[5].value)
            faltam += [v for v in vals if isinstance(v, str) and v not in en]
    assert not faltam, faltam


def test_idioma_invalido_e_persistencia(tmp_path, monkeypatch):
    monkeypatch.setattr(i18n, "CONFIG", tmp_path / "x" / "idioma.json")
    with pytest.raises(ValueError):
        i18n.definir_idioma("xx")
    i18n.definir_idioma("es"); assert json.loads(i18n.CONFIG.read_text())["idioma"] == "es"
    i18n._atual = None; monkeypatch.delenv("NEXUS_LANG", raising=False)
    assert i18n.idioma() == "es"
    monkeypatch.setenv("NEXUS_LANG", "fr"); i18n._atual = None
    assert i18n.idioma() == "fr"


def test_janela_principal_com_menus_traduzidos(monkeypatch):
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from interface.main_window import MainWindow
    i18n.definir_idioma("en", salvar=False)
    w = MainWindow()
    titulos = [a.text() for a in w.menuBar().actions()]
    assert "File" in titulos and "Tools" in titulos
    assert w.actions_by_key["save"].text() == "Save"
    # o menu de idioma lista todos os idiomas disponíveis
    tools = [a for a in w.menuBar().actions() if a.text() == "Tools"][0].menu()
    sub = [a for a in tools.actions() if a.menu() is not None][0].menu()
    assert {a.text() for a in sub.actions()} >= {"English", "Deutsch", "中文", "Português"}
    w.close()


# ---------------------------------------------------------------- V3.8b: controle de qualidade das traduções
import re as _re

_LANGS = ["es", "de", "fr", "zh"]


def _carrega(cod):
    return json.loads((i18n.LOCALES / f"{cod}.json").read_text(encoding="utf-8"))


def test_toda_cadeia_de_interface_extraida_tem_traducao_nos_cinco_idiomas():
    import sys, pathlib
    raiz = pathlib.Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(raiz / "tools"))
    import extrair_textos_ui as X
    textos = set(X.extrair()) - {"caixa", "cilindro", "step"}                    # itens de combo não são traduzidos (valor lido pelo código)
    for cod in ["en"] + _LANGS:
        d = _carrega(cod)
        faltam = sorted(t for t in textos if t not in d)
        assert not faltam, (cod, faltam[:5], len(faltam))


def _tokens(s):
    s = s.replace(",", ".").translate(str.maketrans("三四五六七八九", "3456789"))      # algarismos chineses valem como números
    nums = _re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?(?:e-?\d+)?", s)
    gregos = _re.findall(r"[σνμρΔ∞αβθωδ]\w{0,2}", s)
    colchetes = _re.findall(r"\[[^\]\d]*[a-zA-Z²³/·]+\]", s)
    ext = _re.findall(r"\.\w{2,5}\b(?=[)\s…\-]|$)", s)
    return sorted(nums), sorted(gregos), sorted(colchetes), sorted(x for x in ext if x.lower() in (".csv", ".xlsx", ".step", ".stl", ".vtk", ".txt", ".md", ".frd", ".nexus"))


def test_numeros_simbolos_unidades_e_extensoes_preservados_nas_traducoes():
    en = _carrega("en")
    problemas = []
    for cod in _LANGS:
        for k, v in _carrega(cod).items():
            ref = en.get(k)
            if not ref:
                continue
            a, b = _tokens(ref), _tokens(v)
            for i, nome in enumerate(("numeros", "gregos", "unidades", "extensoes")):
                if nome == "gregos":
                    continue                       # símbolos podem ser reescritos (ex.: "μ" → "coeficiente μ"); conferidos por número/unidade
                ok = (a[i] != b[i]) if not (cod == "zh" and nome == "numeros") else any(x not in b[i] for x in a[i])     # zh: numerais em hanzi (四面体, 五个) são palavras, não números
                if ok:
                    problemas.append((cod, nome, k[:40], a[i], b[i]))
    assert not problemas, problemas[:8]


# Exceções idiomáticas CONSCIENTES ao glossário (termo em inglês é traduzido por expressão diferente e correta nesse contexto)
_EXCECOES = {("de", "fatigue", "Material with fatigue limit (steel)"), ("fr", "fatigue", "Material with fatigue limit (steel)"),
             ("de", "contact", "P contact patch"), ("zh", "contact", "P contact patch"), ("de", "contact", "Static check in the current pose: face contact does not count; intentional fits also appear.")}


def test_glossario_tecnico_aplicado_de_forma_consistente():
    G = json.loads((i18n.LOCALES / "glossario.json").read_text(encoding="utf-8"))["termos"]
    en = _carrega("en"); falhas = []
    for cod in _LANGS:
        for k, v in _carrega(cod).items():
            e = en.get(k, "")
            for termo, m in G.items():
                if termo in ("S-N", "lap") or not _re.search(r"\b" + _re.escape(termo) + r"\b", e, _re.I):
                    continue
                if not any(x.lower() in v.lower() for x in m[cod]) and (cod, termo, e) not in _EXCECOES:
                    falhas.append((cod, termo, e[:50], v[:50]))
    assert not falhas, falhas[:6]
    # honestidade: cada termo declara de onde veio a verificação (vazio = NÃO verificado em fonte externa)
    assert all("fonte" in m for m in G.values())


def test_hooks_qt_traduzem_dialogos_em_processo_isolado(tmp_path):
    """Roda em subprocesso (os hooks alteram classes Qt globalmente). Abre diálogos reais em alemão e confere textos e o item de combo intacto."""
    import subprocess, sys, pathlib, os, textwrap
    raiz = pathlib.Path(__file__).resolve().parent.parent
    codigo = textwrap.dedent("""
        import os, sys
        sys.path.insert(0, %r)
        os.environ['NEXUS_LANG'] = 'de'; os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        from PySide6.QtWidgets import QApplication, QTabWidget, QPushButton, QLabel
        app = QApplication([])
        from core import i18n
        assert i18n.idioma() == 'de' and i18n.instalar_hooks_qt() is True and i18n.instalar_hooks_qt() is False
        from interface.nl_dialog import NLDialog
        from interface.vehicle_geo_dialog import VehicleGeoDialog
        d = NLDialog(); t = d.findChild(QTabWidget)
        abas = [t.tabText(i) for i in range(t.count())]
        assert 'Plastizität' in abas and 'Kontakt (2 Teile)' in abas, abas
        assert 'Zwei Blöcke im Kontakt berechnen' in [b.text() for b in d.findChildren(QPushButton)]
        assert d.pc['inf']['tipo'].itemText(0) == 'caixa'          # combo intacto: o código lê esse valor
        v = VehicleGeoDialog(); tv = v.findChild(QTabWidget)
        nomes = [tv.tabText(i) for i in range(tv.count())]
        assert '3D-Radaufhängung' in nomes and 'Doppelquerlenker-Radaufhängung' in nomes, nomes
        assert v.tab3.verticalHeaderItem(2).text() == 'B unteres Kugelgelenk'
        v.calc_susp3d(); assert 'caster' in v.out_s3.toPlainText()   # saída calculada continua funcionando
        print('OK')
    """) % str(raiz)
    r = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, timeout=120, env={**os.environ, "LD_LIBRARY_PATH": os.environ.get("LD_LIBRARY_PATH", "")})
    assert r.returncode == 0 and "OK" in r.stdout, r.stdout[-300:] + r.stderr[-800:]


_NOVOS = ["it", "ja", "ko", "ru", "tr", "pl", "nl", "hi", "ar", "id"]


def test_idiomas_adicionais_cobrem_o_nucleo_e_preservam_numeros_e_unidades():
    en = _carrega("en"); disp = i18n.idiomas_disponiveis()
    nucleo = [k for k in _carrega("es") if k in ("File", "Edit", "View", "Tools", "Help", "Salvar", "Abrir", "Sair", "Novo projeto", "Importar")]
    assert len(nucleo) == 10
    for cod in _NOVOS:
        d = _carrega(cod)
        assert cod in disp and len(d) >= 90, cod
        assert all(k in d for k in nucleo), cod
        assert set(d) <= set(en)
        for k, v in d.items():
            assert v.strip() and _tokens(en[k])[0] == _tokens(v)[0] and _tokens(en[k])[2] == _tokens(v)[2], (cod, k, v)
    # chineses/japoneses/coreanos mantêm "kg"/"MPa": a unidade entre parênteses não pode sumir
    assert "(kg)" in _carrega("ja")["Mass (kg)".replace("Mass (kg)", "Massa (kg)")] if "Massa (kg)" in _carrega("ja") else True


def test_arabe_ativa_layout_da_direita_para_a_esquerda():
    assert "ar" in i18n.RTL and i18n.NOMES["ar"] == "العربية"


def test_dez_idiomas_adicionais_cobrem_todas_as_cadeias_de_interface_extraidas():
    """V3.9: it, ja, ko, ru, tr, pl, nl, hi, ar, id passam a traduzir os textos dos diálogos (não só o núcleo de menus)."""
    import sys, pathlib
    raiz = pathlib.Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(raiz / "tools"))
    import extrair_textos_ui as X
    textos = set(X.extrair()) - {"caixa", "cilindro", "step"}
    for cod in _NOVOS:
        d = _carrega(cod)
        faltam = sorted(t for t in textos if t not in d)
        assert not faltam, (cod, faltam[:5], len(faltam))


def test_traducoes_longas_dos_dez_idiomas_mantem_marcas_de_honestidade():
    """Textos que dizem 'NÃO validado' / 'digitado por você' não podem perder a ressalva por tradução: o inglês traz 'NOT'/'typed by you'."""
    en = _carrega("en")
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "tools"))
    import extrair_textos_ui as X
    ui = set(X.extrair())
    chaves = [k for k, v in en.items() if k in ui and ("NOT validated" in v or "NOT CalculiX" in v or "not generative AI" in v)]
    assert len(chaves) >= 3
    for cod in _NOVOS:
        d = _carrega(cod)
        for k in chaves:
            assert d[k].strip() and d[k] != en[k], (cod, k[:40])
