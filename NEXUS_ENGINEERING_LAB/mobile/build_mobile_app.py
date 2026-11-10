"""Gera o app de celular completo (V2.5): index.html + data/<projeto>.json + lab.js + materials.json.

Uso: python mobile/build_mobile_app.py <pasta_saida> [chave ...]   (sem chaves = todos)
Regra do projeto: a cada evolução do NEXUS, regenerar e republicar (mesmo link).
Honestidade: o celular exibe modelos pré-calculados no desktop (B-rep -> malha) e roda calculadoras ANALÍTICAS portadas para JS e
validadas contra o Python. Não há CAD paramétrico/booleanas/CFD/FEA no celular.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "mobile"))

from build_mobile_viewer import VERSION, build_data  # noqa: E402


def library_showcase() -> Path:
    """STEP com as 19 peças da biblioteca (parâmetros padrão) dispostas em grade, para visualizar no celular."""
    from core.cad_engine import CadEngine, RawNode
    from core.geometry import translation_matrix
    from samples import geo as g
    from samples.library import PARTS
    nodes, x, row = [], 0.0, 0.0
    for i, pd in enumerate(PARTS.values()):
        shape = pd.make()
        (x0, y0, z0), (x1, y1, z1) = g.bbox(shape)
        col, rw = i % 5, i // 5
        nodes.append(RawNode(pd.title, shape=shape, local_matrix=translation_matrix([col * 260.0 - x0, rw * 260.0 - y0, -z0])))
    out = Path(tempfile.gettempdir()) / "biblioteca_pecas.step"
    CadEngine().write_step(nodes, out)
    return out


def materials_json() -> list:
    c = sqlite3.connect(ROOT / "data" / "materials.db")
    cats = dict(c.execute("select id, name from categories"))
    rows = []
    for name_en, name_pt, cat, lo, hi, typ in c.execute(
            "select name_en, name_pt, category_id, density_min, density_max, density_typ from materials order by category_id, name_pt"):
        d = typ if typ is not None else ((lo + hi) / 2 if lo is not None and hi is not None else lo)
        if d:
            rows.append([name_pt or name_en, cats.get(cat, ""), round(float(d), 1), lo, hi])
    return rows


def main(out: Path, keys: list[str]) -> None:
    from samples.projects import all_projects
    (out / "data").mkdir(parents=True, exist_ok=True)
    reg = []
    for p in all_projects():
        if keys and p.key not in keys:
            continue
        typical = bool(p.typical)
        mat_for = (lambda name, _p=p: _p.material_for(name)) if typical else None
        data = build_data(p.ensure_step(), typical=False, interf=p.key != "f1", title=p.title)
        data["note"] = p.note
        from modules.appearance import appearance
        for q in data["parts"]:
            q["ap"] = list(appearance(p.key, q["name"]))
        data["description"] = p.description
        (out / "data" / f"{p.key}.json").write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
        reg.append({"key": p.key, "title": p.title, "mech": data["mech"] is not None, "parts": len(data["parts"])})
        print(p.key, len(data["parts"]), "peças", "clashes:", None if data["clashes"] is None else len(data["clashes"]), flush=True)
    if not keys or "biblioteca" in keys:
        data = build_data(library_showcase(), title="Biblioteca de peças (parâmetros padrão)")
        from modules.appearance import appearance
        for q in data["parts"]:
            q["ap"] = list(appearance("biblioteca", q["name"]))
        data["note"] = "Vitrine das 19 peças paramétricas do NEXUS desktop com valores padrão; para mudar parâmetros use o desktop (Ctrl+L)."
        data["description"] = "Parafusos, rolamentos, engrenagens, perfis, molas…"
        (out / "data" / "biblioteca.json").write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
        reg.append({"key": "biblioteca", "title": data["name"], "mech": False, "parts": len(data["parts"])})
    reg = []
    for key in [q.key for q in all_projects()] + ["biblioteca"]:      # registro a partir dos arquivos existentes (todos os projetos predefinidos)
        f = out / "data" / f"{key}.json"
        if f.exists():
            d = json.loads(f.read_text(encoding="utf-8"))
            reg.append({"key": key, "title": d["name"], "mech": d["mech"] is not None, "parts": len(d["parts"])})
    (out / "data" / "registry.json").write_text(json.dumps(reg), encoding="utf-8")
    html = (ROOT / "mobile" / "app_template.html").read_text(encoding="utf-8").replace("__VER__", VERSION)
    (out / "index.html").write_text(html, encoding="utf-8")
    for f in ("lab.js", "ui.js"):
        (out / f).write_text((ROOT / "mobile" / f).read_text(encoding="utf-8"), encoding="utf-8")
    from mobile.build_f1sim import build as build_f1sim
    build_f1sim(out)
    from modules.units import export_table
    (out / "units.json").write_text(export_table(), encoding="utf-8")
    (out / "materials.json").write_text(json.dumps(materials_json(), separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    main(Path(args[0]), args[1:])
