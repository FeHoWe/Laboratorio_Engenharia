"""Lista de materiais (BOM) com massa — V1.5.

Regras (mesmas do projeto): massa só existe com material escolhido pelo usuário E volume
conhecido. Peças sem massa NÃO entram nos totais; elas são listadas à parte e o total é
rotulado "parcial" enquanto houver pendências. Nada é estimado.

Unidades: mm³ -> cm³ no relatório; massa em g (e kg nos totais).
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from core.component_manager import ComponentManager
from core.model import Component
from modules.component_inspector import ComponentInspector
from modules.material_manager import MaterialLibrary


@dataclass
class BomLine:
    item: int
    name: str
    group: str                       # caminho do grupo-pai (ex.: "Motor / Estrutura")
    qty: int
    material: Optional[str]
    density: Optional[float]         # g/cm³
    volume_cm3: Optional[float]      # por unidade
    mass_unit_g: Optional[float]     # por unidade
    mass_total_g: Optional[float]    # qty * unidade
    pct: Optional[float] = None      # % da massa total conhecida
    note: str = ""
    ids: list[str] = field(default_factory=list)


@dataclass
class BomReport:
    project: str
    lines: list[BomLine]
    total_parts: int
    parts_with_mass: int
    total_mass_g: float                                  # só das peças com massa
    complete: bool                                       # todas as peças têm massa?
    missing: list[str]                                   # nomes das peças sem massa
    by_material: list[tuple[str, int, float]]            # (material, nº peças, g)
    by_group: list[tuple[str, float]]                    # (grupo de 1º nível, g)
    center_of_mass: Optional[tuple[float, float, float]] # mm, mundo, em repouso (só peças com massa)

    @property
    def total_mass_kg(self) -> float:
        return self.total_mass_g / 1000.0

    def summary(self) -> str:
        kind = "total" if self.complete else "PARCIAL"
        br = lambda v, f: format(v, f).replace(",", "X").replace(".", ",").replace("X", ".")  # noqa: E731
        s = (f"Massa {kind}: {br(self.total_mass_g, ',.1f')} g ({br(self.total_mass_kg, '.3f')} kg) — "
             f"{self.parts_with_mass}/{self.total_parts} peças com massa")
        if not self.complete:
            s += f"; {len(self.missing)} sem material/volume"
        return s


class BomBuilder:
    def __init__(self, components: ComponentManager, materials: MaterialLibrary,
                 inspector: Optional[ComponentInspector] = None) -> None:
        self.components = components
        self.materials = materials
        self.inspector = inspector or ComponentInspector(components, materials)

    def build(self, only_visible: bool = False) -> BomReport:
        groups: dict[tuple, BomLine] = {}
        order: list[tuple] = []
        missing: list[str] = []
        total_parts = 0
        weighted = [0.0, 0.0, 0.0]
        mass_for_com = 0.0
        by_mat: dict[str, list] = {}
        by_grp: dict[str, float] = {}

        for leaf in self.components.leaves():
            if only_visible and not leaf.visible:
                continue
            total_parts += 1
            rep = self.inspector.inspect(leaf)
            vol = rep.volume / 1000.0 if rep.volume is not None else None
            nodes = list(leaf.ancestors())[::-1]                   # raiz -> pai
            chain = [a.name for a in nodes]
            group = " / ".join(chain)
            # grupo de 1º nível = primeiro ancestral cujo pai tem mais de um filho (pula envoltórios de 1 filho)
            top = chain[-1] if chain else "—"
            for a in nodes:
                if a.parent is not None and len(a.parent.children) > 1:
                    top = a.name
                    break
            key = (re.sub(r"[\s#_-]*\d+$", "", leaf.name) or leaf.name, group, leaf.material,
                   round(vol, 3) if vol is not None else None)
            if rep.mass is None:
                missing.append(leaf.name)
            else:
                by_mat.setdefault(leaf.material or "—", [0, 0.0])
                by_mat[leaf.material][0] += 1
                by_mat[leaf.material][1] += rep.mass
                by_grp[top] = by_grp.get(top, 0.0) + rep.mass
                if rep.centroid is not None:
                    for i in range(3):
                        weighted[i] += rep.centroid[i] * rep.mass
                    mass_for_com += rep.mass
            line = groups.get(key)
            if line is None:
                line = BomLine(0, key[0], group, 0, leaf.material, rep.density, vol,
                               rep.mass, None, note=rep.mass_note if rep.mass is None else "")
                groups[key] = line
                order.append(key)
            line.qty += 1
            line.ids.append(leaf.id)

        lines = [groups[k] for k in order]
        total = 0.0
        for i, ln in enumerate(lines, 1):
            ln.item = i
            if ln.mass_unit_g is not None:
                ln.mass_total_g = ln.mass_unit_g * ln.qty
                total += ln.mass_total_g
        for ln in lines:
            if ln.mass_total_g is not None and total > 0:
                ln.pct = 100.0 * ln.mass_total_g / total
        com = tuple(w / mass_for_com for w in weighted) if mass_for_com > 0 else None
        return BomReport(
            project="", lines=lines, total_parts=total_parts,
            parts_with_mass=total_parts - len(missing), total_mass_g=total,
            complete=not missing and total_parts > 0, missing=missing,
            by_material=sorted(((m, n, g) for m, (n, g) in by_mat.items()), key=lambda x: -x[2]),
            by_group=sorted(by_grp.items(), key=lambda x: -x[1]),
            center_of_mass=com)  # type: ignore[arg-type]


# ----------------------------------------------------------------------------- exportação
HEADERS = ["Item", "Componente", "Grupo", "Qtd", "Material", "Densidade (g/cm³)",
           "Volume unit. (cm³)", "Massa unit. (g)", "Massa total (g)", "% da massa", "Observação"]


def _row(ln: BomLine) -> list:
    return [ln.item, ln.name, ln.group, ln.qty, ln.material or "", ln.density, ln.volume_cm3,
            ln.mass_unit_g, ln.mass_total_g, ln.pct, ln.note]


def export_csv(report: BomReport, path: str | Path) -> Path:
    """CSV com ';' e vírgula decimal opcional não é usado: números ficam em formato máquina (ponto)."""
    path = Path(path)
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:      # BOM p/ o Excel abrir em UTF-8
        w = csv.writer(fh, delimiter=";")
        w.writerow(HEADERS)
        for ln in report.lines:
            w.writerow(["" if v is None else (f"{v:.4f}" if isinstance(v, float) else v) for v in _row(ln)])
        w.writerow([])
        w.writerow(["", report.summary()])
    return path


def export_xlsx(report: BomReport, path: str | Path, project_name: str = "") -> Path:
    """XLSX com fórmulas vivas nos totais (SOMA) e abas de resumo."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    path = Path(path)
    wb = Workbook()
    ws = wb.active
    ws.title = "BOM"
    ws.append([f"NEXUS ENGINEERING LAB — Lista de materiais — {project_name or report.project}"])
    ws["A1"].font = Font(bold=True, size=13)
    ws.append([report.summary()])
    ws.append([])
    ws.append(HEADERS)
    head_row = ws.max_row
    fill = PatternFill("solid", fgColor="0B2A3A")
    for c in ws[head_row]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = fill
        c.alignment = Alignment(horizontal="center", wrap_text=True)
    first = head_row + 1
    for ln in report.lines:
        ws.append(_row(ln))
        r = ws.max_row
        if ln.mass_unit_g is not None:                       # massa total viva: qtd × unitária
            ws.cell(r, 9).value = f"=D{r}*H{r}"
    last = ws.max_row
    ws.append([])
    ws.append(["", "TOTAL" + ("" if report.complete else " PARCIAL (só peças com massa)"), "",
               f"=SUM(D{first}:D{last})", "", "", "", "", f"=SUM(I{first}:I{last})"])
    tr = ws.max_row
    for c in ws[tr]:
        c.font = Font(bold=True)
    ws.append(["", "Total em kg", "", "", "", "", "", "", f"=I{tr}/1000"])
    for row in ws.iter_rows(min_row=first, max_row=ws.max_row):
        for c in row[5:9]:
            c.number_format = "0.0000"
        row[9].number_format = "0.0"
    for col, wdt in zip("ABCDEFGHIJK", (6, 34, 32, 6, 34, 12, 14, 12, 14, 10, 42)):
        ws.column_dimensions[col].width = wdt
    ws.freeze_panes = ws.cell(first, 1)

    ws2 = wb.create_sheet("Por material")
    ws2.append(["Material", "Nº de peças", "Massa (g)", "% da massa conhecida"])
    for m, n, g in report.by_material:
        ws2.append([m, n, round(g, 4), round(100 * g / report.total_mass_g, 1) if report.total_mass_g else None])
    ws3 = wb.create_sheet("Por grupo")
    ws3.append(["Grupo (1º nível)", "Massa (g)"])
    for g, m in report.by_group:
        ws3.append([g, round(m, 4)])
    ws4 = wb.create_sheet("Pendências")
    ws4.append(["Peças SEM massa (falta material ou volume) — não entram nos totais"])
    for n in report.missing:
        ws4.append([n])
    if report.center_of_mass:
        ws.append([])
        ws.append(["", "Centro de massa (mm, mundo, em repouso)" + ("" if report.complete else " — parcial"),
                   "", *[round(x, 2) for x in report.center_of_mass]])
    wb.save(path)
    return path
