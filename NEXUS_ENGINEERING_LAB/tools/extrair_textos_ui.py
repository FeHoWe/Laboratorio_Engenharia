"""Extrai os textos de interface (literais passados a widgets Qt) de interface/*.py para tradução. Uso: python tools/extrair_textos_ui.py [saida.json]
Só pega literais ESTÁTICOS ligados a widgets (QLabel, QPushButton, QCheckBox, QGroupBox, addTab, addRow, setWindowTitle, setToolTip, setText, setPlaceholderText,
setHorizontalHeaderLabels, addItems/addItem). Texto montado em tempo de execução (f-strings, concatenação, resultados numéricos) NÃO entra — continua em português."""
import ast, glob, json, sys
from pathlib import Path

WIDGETS = {"QLabel", "QPushButton", "QCheckBox", "QGroupBox", "QRadioButton", "QAction"}
METODOS_1 = {"setWindowTitle", "setToolTip", "setText", "setPlaceholderText", "setTitle", "setStatusTip", "setWhatsThis"}


def _lits(n):
    if isinstance(n, ast.Constant) and isinstance(n.value, str):
        yield n.value
    elif isinstance(n, (ast.List, ast.Tuple)):
        for e in n.elts:
            yield from _lits(e)


def extrair(raiz=Path(__file__).resolve().parent.parent / "interface") -> dict:
    out = {}
    for f in sorted(glob.glob(str(raiz / "*.py"))):
        for n in ast.walk(ast.parse(Path(f).read_text(encoding="utf-8"))):
            if not isinstance(n, ast.Call):
                continue
            nome = n.func.id if isinstance(n.func, ast.Name) else (n.func.attr if isinstance(n.func, ast.Attribute) else "")
            alvos = []
            if nome in WIDGETS and n.args:
                alvos = [n.args[0]]
            elif nome in METODOS_1 and n.args:
                alvos = [n.args[0]]
            elif nome == "addTab" and len(n.args) >= 2:
                alvos = [n.args[1]]
            elif nome == "addRow" and len(n.args) >= 2:
                alvos = [n.args[0]]
            elif nome in ("setHorizontalHeaderLabels", "setVerticalHeaderLabels", "addItems"):
                alvos = [n.args[0]] if n.args else []
            elif nome == "addItem" and n.args:
                alvos = [n.args[0]]
            for a in alvos:
                for s in _lits(a):
                    if len(s.strip()) >= 2 and any(c.isalpha() for c in s):
                        out.setdefault(s, Path(f).name)
    # tabelas de campos: tuplas ("chave_ascii", "Rótulo em português", ...) usadas em laços que criam widgets
    import re
    for f in sorted(glob.glob(str(raiz / "*.py"))):
        for n in ast.walk(ast.parse(Path(f).read_text(encoding="utf-8"))):
            if isinstance(n, ast.Tuple) and 2 <= len(n.elts) <= 5 and all(isinstance(e, ast.Constant) for e in n.elts[:2]):
                k, v = n.elts[0].value, n.elts[1].value
                if isinstance(k, str) and isinstance(v, str) and re.fullmatch(r"[a-z_0-9]{1,14}", k) and re.search(r"[A-Za-zÀ-ÿ]{3}", v) and len(v) < 160 and \
                        (" " in v or "[" in v or re.search(r"[À-ÿ]", v)):
                    out.setdefault(v, Path(f).name)
    return out


if __name__ == "__main__":
    r = extrair()
    dest = sys.argv[1] if len(sys.argv) > 1 else "-"
    txt = json.dumps(r, ensure_ascii=False, indent=1)
    (print(txt) if dest == "-" else Path(dest).write_text(txt, encoding="utf-8"))
    print(f"{len(r)} textos de {len(set(r.values()))} arquivos", file=sys.stderr)
