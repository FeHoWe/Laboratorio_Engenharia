"""Gera o visualizador de celular (HTML único, somente leitura) a partir de um modelo.

Uso:  python mobile/build_mobile_viewer.py modelo.step [saida.html]

Importa o modelo com o próprio motor do NEXUS, separa sólidos compostos, calcula a explosão
radial e embute malha + deslocamentos na página. Regra do projeto: a cada nova versão do
NEXUS, regenerar e publicar este visualizador para testes sem o computador.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.cad_engine import CadEngine  # noqa: E402
from core.project_manager import ProjectManager  # noqa: E402
from modules.explode_engine import ExplodeParams  # noqa: E402
from modules.importer import ProjectImporter  # noqa: E402
from modules.measure_engine import MeasureEngine, axis_label  # noqa: E402
from modules.solid_analyzer import can_split, split_into_solids  # noqa: E402

VERSION = "2.8"


def build_data(model: Path, typical: bool = False, material_for=None, interf: bool = False, title: str | None = None) -> dict:
    """Gera o dicionário do projeto (malhas + peças + mecanismo). ``interf``: calcula interferências exatas (lento)."""
    eng = CadEngine()
    project = ProjectManager(eng).new_project(model.stem)
    project.set_root(ProjectImporter(eng, project.ids).import_file(str(model)).root)
    for node in [n for n in project.components.root.walk() if can_split(n)]:
        split_into_solids(node, eng, project.ids)
    project.components.reindex()
    totals = None
    mass_by_id: dict = {}
    if typical:
        from modules.bom import BomBuilder
        material_for = material_for or __import__('samples.motor_materials', fromlist=['material_for']).material_for
        for leaf in project.components.leaves():
            mat = material_for(leaf.name)
            if mat and project.materials.get(mat):
                project.components.set_material(leaf.id, mat)
        bom = BomBuilder(project.components, project.materials).build()
        for ln in bom.lines:
            for cid in ln.ids:
                mass_by_id[cid] = (ln.material, ln.mass_unit_g)
        totals = {"mass_g": round(bom.total_mass_g, 1), "complete": bom.complete,
                  "with_mass": bom.parts_with_mass, "n": bom.total_parts}
    offsets = project.assembly.target_explode_all(ExplodeParams(factor=1.0, mode="radial"))
    parts, geoms = [], []
    me = MeasureEngine(project.components)
    shared_off: dict = {}
    shared: dict = {}          # assinatura geométrica -> (índice da geometria, origem da 1ª instância)

    def signature(comp, box):
        """Assinatura invariante à translação: volume, área, nº de faces, caixa e centroide relativo à caixa.

        Instâncias do mesmo B-Rep (molas, válvulas, pistões...) saem do STEP como cópias independentes,
        cuja triangulação difere em ruído; esta assinatura as reconhece sem comparar malhas.
        """
        if comp.shape is None:
            return None
        pr = eng.properties(comp.shape)
        if pr.volume is None:
            return None
        rel = np.asarray(pr.centroid, dtype=float) - box.min
        return (round(pr.volume, 2), round(pr.area, 1), eng.count_faces(comp.shape),
                tuple(np.round(box.size, 2)), tuple(np.round(rel, 1)))

    for comp in project.components.leaves():
        box = project.components.bbox(comp)
        diams = me.diameters(comp)
        principal = me.principal_axis(comp)
        ikey = signature(comp, box)
        if ikey is not None and ikey in shared:
            gi = shared[ikey]
            origin = np.asarray(box.min, dtype=float) - shared_off[gi]
        else:
            if comp.name.startswith("Mola"):          # molas: malha mais grossa no celular (cada variante pesaria ~600 KB)
                mesh = eng.tessellate(comp.shape, 0.12)
            else:
                mesh = project.components.render_mesh(comp)
            verts = np.asarray(mesh.vertices, dtype=float)
            origin = verts.min(axis=0)
            local = np.round(verts - origin, 2)
            faces = np.asarray(mesh.faces).ravel()
            gi = len(geoms)
            geoms.append({"v": [round(float(x), 2) for x in local.ravel()],
                          "n": [round(float(x), 2) for x in np.asarray(mesh.normals).ravel()],
                          "f": [int(x) for x in faces]})
            shared_off[gi] = np.asarray(box.min, dtype=float) - origin     # caixa da peça - origem da malha
            if ikey is not None:
                shared[ikey] = gi
        pr_ = eng.properties(comp.shape) if comp.shape is not None else None
        parts.append({
            "vol": None if pr_ is None or pr_.volume is None else round(float(pr_.volume), 1),
            "area": None if pr_ is None or pr_.area is None else round(float(pr_.area), 1),
            "id": comp.id, "name": comp.name, "size": [round(float(x), 2) for x in box.size],
            "g": gi, "pos": [round(float(x), 2) for x in origin],
            "dia": [{"d": round(d.diameter, 3), "axis": axis_label(d.axis)} for d in diams[:4]],
            "axis": None if principal is None else [round(float(x), 6) for x in principal[0]],
            "axisBasis": None if principal is None else principal[1],
            "off": [round(float(x), 2) for x in offsets.get(comp.id, np.zeros(3))],
            **({"mat": mass_by_id[comp.id][0], "mass": round(mass_by_id[comp.id][1], 2)}
               if mass_by_id.get(comp.id) and mass_by_id[comp.id][1] is not None else {}),
        })
    mech = None
    try:
        from samples.mechanisms import build_mechanism
        index_of = {p["id"]: n for n, p in enumerate(parts)}
        mech = build_mechanism(project.components).mobile_spec(index_of)
    except Exception:  # noqa: BLE001 - modelo sem mecanismo: o visualizador funciona sem animação
        mech = None
    clashes = None
    if interf:
        from modules.interference import find_interferences
        index_of = {p["id"]: n for n, p in enumerate(parts)}
        clashes = [[index_of[c.a_id], index_of[c.b_id], round(c.volume, 1)] for c in find_interferences(project.components)]
    return {"name": title or model.stem, "version": VERSION, "geoms": geoms, "parts": parts, "totals": totals, "mech": mech,
            "clashes": clashes}


def build(model: Path, out: Path, typical: bool = False) -> Path:
    """Compatibilidade: HTML único antigo (somente o visualizador 3D)."""
    data = json.dumps(build_data(model, typical), separators=(",", ":"))
    html = (ROOT / "mobile" / "viewer_template.html").read_text(encoding="utf-8").replace("__DATA__", data)
    out.write_text(html, encoding="utf-8")
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    src = Path([a for a in sys.argv[1:] if not a.startswith("--")][0])
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dst = Path(args[1]) if len(args) > 1 else ROOT / "exports" / f"{src.stem}_mobile.html"
    dst.parent.mkdir(parents=True, exist_ok=True)
    print("Gerado:", build(src, dst, typical="--typical" in sys.argv))
