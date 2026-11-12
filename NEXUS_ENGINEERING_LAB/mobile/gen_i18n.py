"""Gera a parte de catálogos de mobile/i18n.js a partir de mobile/i18n_cat.json ({idioma: {texto_pt: tradução}}).
Uso: python3 mobile/gen_i18n.py   (o seletor/observador fica no mesmo arquivo, após a linha 'window.NEXUS_I18N=')."""
import json
import re
from pathlib import Path

D = Path(__file__).resolve().parent
JS = D / "i18n.js"
CAT = D / "i18n_cat.json"


def extrair() -> dict:
    t = JS.read_text(encoding="utf-8")
    m = re.search(r"^window\.NEXUS_I18N=(\{.*\});\s*$", t, re.M)
    return json.loads(m.group(1))


def escrever(cat: dict) -> None:
    t = JS.read_text(encoding="utf-8")
    novo = "window.NEXUS_I18N=" + json.dumps(cat, ensure_ascii=False) + ";"
    t2 = re.sub(r"^window\.NEXUS_I18N=\{.*\};\s*$", lambda _m: novo, t, count=1, flags=re.M)
    JS.write_text(t2, encoding="utf-8")
    CAT.write_text(json.dumps(cat, ensure_ascii=False, indent=0), encoding="utf-8")


if __name__ == "__main__":
    escrever(json.loads(CAT.read_text(encoding="utf-8")) if CAT.exists() else extrair())
    print("ok", {k: len(v) for k, v in json.loads(CAT.read_text(encoding="utf-8")).items()})
