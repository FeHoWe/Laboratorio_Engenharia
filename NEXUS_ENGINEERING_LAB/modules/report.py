"""Relatório PDF do projeto — V1.6.

Páginas: capa com vista geral e resumo de massa · BOM · totais por material/grupo · pendências ·
cenas salvas (imagem de cada uma) · uma ficha por componente (imagem isolada + no conjunto + dados).
Todos os números vêm do Component Inspector / BOM (mesmas regras: nada estimado; sem material não há massa).
"""
from __future__ import annotations

import re
import io
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

from modules.bom import BomBuilder, BomReport
from modules.component_inspector import ComponentInspector, InspectionReport

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
FONT, FONT_B = "Helvetica", "Helvetica-Bold"
try:  # DejaVu embutida: desenha ³ ² Ø × → que a Helvetica padrão perde em alguns leitores
    pdfmetrics.registerFont(TTFont("NexusSans", str(FONT_DIR / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("NexusSans-Bold", str(FONT_DIR / "DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFontFamily("NexusSans", normal="NexusSans", bold="NexusSans-Bold")
    FONT, FONT_B = "NexusSans", "NexusSans-Bold"
except Exception:  # noqa: BLE001 - sem a fonte, segue com Helvetica
    pass

INK = colors.HexColor("#0b2a3a")
CYAN = colors.HexColor("#0a8fb5")
GRID = colors.HexColor("#c9d6dd")
ZEBRA = colors.HexColor("#f2f7f9")
WARN = colors.HexColor("#a35a00")


def _num(v, fmt="{:,.2f}", dash="—") -> str:
    if v is None:
        return dash
    return fmt.format(v).replace(",", "X").replace(".", ",").replace("X", ".")


def _txt(s) -> str:
    """Escapa marcação; sem a fonte DejaVu, cai para o alfabeto da Helvetica (WinAnsi)."""
    s = str(s)
    if FONT == "Helvetica":
        s = s.replace("→", "->").replace("↔", "<->").replace("≈", "~").replace("≥", ">=").replace("≤", "<=")
        s = s.encode("cp1252", "replace").decode("cp1252")
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class ReportBuilder:
    def __init__(self, project, inspector: Optional[ComponentInspector] = None, app_version: str = "") -> None:
        self.project = project
        self.inspector = inspector or ComponentInspector(project.components, project.materials)
        self.version = app_version
        ss = getSampleStyleSheet()
        self.h1 = ParagraphStyle("h1", parent=ss["Heading1"], fontName=FONT_B, textColor=INK, fontSize=20, spaceAfter=6)
        self.h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName=FONT_B, textColor=CYAN, fontSize=13, spaceBefore=8, spaceAfter=4)
        self.body = ParagraphStyle("b", parent=ss["BodyText"], fontName=FONT, fontSize=9, leading=12)
        self.small = ParagraphStyle("s", parent=self.body, fontSize=7.5, leading=9.5, textColor=colors.HexColor("#4a5a63"))
        self.cell = ParagraphStyle("c", parent=self.body, fontSize=7.5, leading=9)
        self.warn = ParagraphStyle("w", parent=self.body, textColor=WARN)

    # ------------------------------------------------------------------ API
    def build(self, path: str | Path, detail_parts: bool = True, include_scenes: bool = True,
              group_equal: bool = True, progress: Optional[Callable[[int, int, str], None]] = None) -> Path:
        from modules.snapshot import SnapshotRenderer
        path = Path(path)
        comps = self.project.components
        bom = BomBuilder(comps, self.project.materials, self.inspector).build()
        bom.project = self.project.name
        leaves = list(comps.leaves())
        scenes = list(self.project.scenes) if include_scenes else []
        steps = 1 + len(scenes) + (len(leaves) if detail_parts else 0)
        done = 0

        def tick(msg: str) -> None:
            nonlocal done
            done += 1
            if progress:
                progress(done, steps, msg)

        snap = SnapshotRenderer(comps)
        story: list = []
        story += self._cover(bom, snap.overview() if snap.ok else None)
        tick("Vista geral")
        story += self._bom_pages(bom)
        story += self._joints_pages()
        for sc in scenes:
            story += self._scene_page(sc, snap.saved_scene(sc) if snap.ok else None)
            tick(f"Cena {sc.name}")
        if detail_parts and leaves:
            story.append(PageBreak())
            story.append(Paragraph("Fichas de componentes", self.h1))
            story.append(Paragraph("Cada ficha mostra a peça isolada e destacada no conjunto, com os dados calculados da geometria.", self.body))
            story.append(Spacer(1, 4 * mm))
            # peças iguais (mesmo nome-base, material e volume) ganham UMA ficha com "×N" (ex.: 96 dentes de correia)
            seen: dict = {}
            reps = {leaf.id: self.inspector.inspect(leaf) for leaf in leaves}
            if group_equal:
                for leaf in leaves:
                    r = reps[leaf.id]
                    key = (re.sub(r"\s*#\d+$", "", leaf.name), r.material, None if r.volume is None else round(r.volume, 1))
                    seen.setdefault(key, []).append(leaf.id)
            first = {ids[0]: len(ids) for ids in seen.values()} if group_equal else {}
            for i, leaf in enumerate(leaves):
                if group_equal and leaf.id not in first:
                    tick(leaf.name)
                    continue
                rep = reps[leaf.id]
                try:
                    iso = snap.part(leaf.id, (560, 400)) if snap.ok else None
                    ctx = snap.part(leaf.id, (560, 400), context=True) if snap.ok else None
                except KeyError:
                    iso = ctx = None
                story.append(self._part_card(leaf, rep, iso, ctx))
                if first.get(leaf.id, 1) > 1:
                    story.append(Paragraph(f"Ficha comum a {first[leaf.id]} peças iguais (mesmo nome-base, material e volume): "
                                           "dimensões e massa valem para cada uma.", self.small))
                story.append(Spacer(1, 3 * mm))
                tick(leaf.name)

        doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm,
                                topMargin=16 * mm, bottomMargin=16 * mm,
                                title=f"NEXUS — {self.project.name}", author="NEXUS ENGINEERING LAB")
        doc.build(story, onFirstPage=self._footer, onLaterPages=self._footer)
        return path

    # -------------------------------------------------------------- partes
    def _footer(self, canvas, doc) -> None:
        canvas.saveState()
        canvas.setFont(FONT, 7.5)
        canvas.setFillColor(colors.HexColor("#5b6b74"))
        canvas.drawString(15 * mm, 9 * mm, _txt(f"NEXUS ENGINEERING LAB {self.version} — {self.project.name}").replace("&amp;", "&"))
        canvas.drawRightString(A4[0] - 15 * mm, 9 * mm, f"Página {doc.page}")
        canvas.restoreState()

    def _img(self, data: Optional[bytes], width_mm: float, ratio: float) -> object:
        if not data:
            return Paragraph("(imagem indisponível)", self.small)
        return Image(io.BytesIO(data), width=width_mm * mm, height=width_mm * mm * ratio)

    def _cover(self, bom: BomReport, overview: Optional[bytes]) -> list:
        p = self.project
        c = p.components.counts()
        out = [Paragraph("NEXUS ENGINEERING LAB", self.small),
               Paragraph(_txt(p.name), self.h1),
               Paragraph(f"Relatório gerado em {datetime.now():%d/%m/%Y %H:%M}", self.body),
               Spacer(1, 4 * mm), self._img(overview, 180, 700 / 1100), Spacer(1, 4 * mm)]
        rows = [["Peças", str(bom.total_parts)],
                ["Componentes (nós)", str(c.get("total", c.get("parts", "—")))],
                ["Arquivos de origem", _txt(", ".join(Path(s).name for s in p.source_files) or "—")],
                ["Massa", _txt(bom.summary().replace("Massa ", ""))],
                ["Cenas salvas", str(len(p.scenes))]]
        if bom.center_of_mass:
            x, y, z = bom.center_of_mass
            rows.append(["Centro de massa" + ("" if bom.complete else " (parcial)"),
                         f"X {_num(x, '{:.1f}')}  Y {_num(y, '{:.1f}')}  Z {_num(z, '{:.1f}')} mm"])
        t = Table([[Paragraph(f"<b>{a}</b>", self.body), Paragraph(b, self.body)] for a, b in rows], colWidths=[48 * mm, 130 * mm])
        t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.25, GRID), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        out.append(t)
        if not bom.complete:
            out += [Spacer(1, 3 * mm), Paragraph(
                "Atenção: a massa é PARCIAL. Peças sem material definido pelo usuário (ou sem volume calculável) "
                "não entram nos totais e estão listadas em “Pendências”.", self.warn)]
        out.append(Paragraph("Valores calculados da geometria importada (mm, mm², mm³) e de densidades nominais de tabelas "
                             "publicadas; ligas reais variam. Documento de apoio, não substitui memorial de cálculo.", self.small))
        return out

    def _bom_pages(self, bom: BomReport) -> list:
        out = [PageBreak(), Paragraph("Lista de materiais (BOM)", self.h1), Paragraph(_txt(bom.summary()), self.body), Spacer(1, 3 * mm)]
        head = ["#", "Componente", "Qtd", "Material", "Vol. cm³", "M. un. g", "M. total g", "%"]
        data = [head]
        for ln in bom.lines:
            data.append([str(ln.item), Paragraph(_txt(ln.name), self.cell), str(ln.qty),
                         Paragraph(_txt(ln.material or "— sem material —"), self.cell),
                         _num(ln.volume_cm3, "{:,.2f}"), _num(ln.mass_unit_g, "{:,.1f}"),
                         _num(ln.mass_total_g, "{:,.1f}"), _num(ln.pct, "{:.1f}")])
        data.append(["", Paragraph("<b>TOTAL" + ("" if bom.complete else " PARCIAL") + "</b>", self.cell),
                     str(sum(l.qty for l in bom.lines)), "", "", "", _num(bom.total_mass_g, "{:,.1f}"), ""])
        t = Table(data, colWidths=[8 * mm, 50 * mm, 9 * mm, 44 * mm, 19 * mm, 19 * mm, 21 * mm, 10 * mm], repeatRows=1)
        st = [("BACKGROUND", (0, 0), (-1, 0), INK), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
              ("FONTSIZE", (0, 0), (-1, -1), 7.5), ("FONTNAME", (0, 0), (-1, 0), FONT_B),
              ("ALIGN", (2, 0), (2, -1), "CENTER"), ("ALIGN", (4, 0), (-1, -1), "RIGHT"),
              ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LINEBELOW", (0, 0), (-1, -1), 0.25, GRID),
              ("FONTNAME", (0, -1), (-1, -1), FONT_B), ("LINEABOVE", (0, -1), (-1, -1), 0.8, INK)]
        for r in range(1, len(data) - 1):
            if r % 2 == 0:
                st.append(("BACKGROUND", (0, r), (-1, r), ZEBRA))
        t.setStyle(TableStyle(st))
        out.append(t)
        if bom.by_material:
            out += [Paragraph("Massa por material", self.h2)]
            md = [["Material", "Peças", "Massa (kg)", "% do total"]]
            for m, n, g in bom.by_material:
                md.append([Paragraph(_txt(m), self.cell), str(n), _num(g / 1000, "{:.3f}"), _num(100 * g / bom.total_mass_g, "{:.1f}")])
            mt = Table(md, colWidths=[95 * mm, 20 * mm, 30 * mm, 30 * mm], repeatRows=1)
            mt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), CYAN), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                                    ("FONTSIZE", (0, 0), (-1, -1), 8), ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                                    ("LINEBELOW", (0, 0), (-1, -1), 0.25, GRID)]))
            out.append(KeepTogether([mt]))
        if bom.by_group:
            out += [Paragraph("Massa por grupo", self.h2)]
            gd = [["Grupo", "Massa (kg)"]] + [[Paragraph(_txt(g), self.cell), _num(m / 1000, "{:.3f}")] for g, m in bom.by_group]
            gt = Table(gd, colWidths=[110 * mm, 30 * mm])
            gt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), CYAN), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                                    ("FONTSIZE", (0, 0), (-1, -1), 8), ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                                    ("LINEBELOW", (0, 0), (-1, -1), 0.25, GRID)]))
            out.append(KeepTogether([gt]))
        if bom.missing:
            out += [Paragraph(f"Pendências — {len(bom.missing)} peça(s) sem massa", self.h2),
                    Paragraph(_txt(", ".join(bom.missing)), self.body),
                    Paragraph("Defina o material de cada uma (Components › Definir material…) para entrarem nos totais.", self.small)]
        return out

    def _joints_pages(self) -> list:
        from modules.joint_finder import JointFinder
        try:
            rep = JointFinder(self.project.components).find()
        except Exception:  # noqa: BLE001 - seção opcional
            return []
        if not rep.joints:
            return []
        out = [PageBreak(), Paragraph("Relações de montagem (inferidas da geometria e/ou gravadas no arquivo)", self.h1),
               Paragraph(_txt(rep.summary()), self.body),
               Paragraph("Linhas Concêntrica/Plano contra plano: deduzidas da geometria exata, não provam intenção de projeto. "
                         "Linhas \"Gravada (FreeCAD)\": lidas do arquivo de origem (leitor não validado com arquivos reais).", self.small), Spacer(1, 3 * mm)]
        data = [["Tipo", "Peça A", "Peça B", "Detalhe"]]
        for j in rep.joints:
            data.append([Paragraph(_txt(j.kind), self.cell), Paragraph(_txt(j.a_name), self.cell),
                         Paragraph(_txt(j.b_name), self.cell), Paragraph(_txt(j.detail), self.cell)])
        t = Table(data, colWidths=[28 * mm, 34 * mm, 34 * mm, 82 * mm], repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), INK), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                               ("FONTNAME", (0, 0), (-1, 0), FONT_B), ("FONTSIZE", (0, 0), (-1, 0), 7.5),
                               ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.2, GRID)]))
        out.append(t)
        if rep.orphans:
            out.append(Paragraph("Peças sem nenhuma junta inferida: " + _txt(", ".join(rep.orphans)), self.small))
        return out

    def _scene_page(self, sc, img: Optional[bytes]) -> list:
        sec = "sem corte" if not sc.section else f"corte no plano {'XYZ'[sc.section['axis']]} a {sc.section['fraction'] * 100:.0f}%"
        return [PageBreak(), Paragraph(f"Cena: {_txt(sc.name)}", self.h1), self._img(img, 180, 700 / 1100), Spacer(1, 3 * mm),
                Paragraph(_txt(f"{len(sc.offsets)} nó(s) deslocado(s) (explosão) · {len(sc.hidden)} oculto(s) · {sec} · "
                               + (f"animação em {sc.kin_deg:.0f}° · " if getattr(sc, "kin_deg", None) is not None else "")
                               + f"{'holograma' if sc.holo else 'sólido técnico'} · salva em {sc.created.replace('T', ' ')}"), self.body)]

    def _part_card(self, leaf, rep: InspectionReport, iso: Optional[bytes], ctx: Optional[bytes]):
        group = " / ".join(a.name for a in list(leaf.ancestors())[::-1])
        size = "—" if not rep.size else " × ".join(_num(x, "{:.2f}") for x in rep.size) + " mm"
        rows = [("Id", rep.id), ("Grupo", group or "—"), ("Geometria", rep.geometry_type), ("Dimensões X × Y × Z", size),
                ("Volume", _num(None if rep.volume is None else rep.volume / 1000.0, "{:,.3f}") + " cm³" if rep.volume is not None else "indisponível"),
                ("Área", _num(None if rep.area is None else rep.area / 100.0, "{:,.2f}") + " cm²" if rep.area is not None else "—"),
                ("Material", rep.material or "— não definido —"),
                ("Densidade", (_num(rep.density, "{:.3f}") + " g/cm³") if rep.density else "—"),
                ("Massa", (_num(rep.mass, "{:,.2f}") + " g") if rep.mass is not None else (rep.mass_note or "—"))]
        if rep.diameters:
            rows.append(("Diâmetros", "; ".join(f"Ø {_num(d, '{:.2f}')} mm (eixo {ax})" for d, ax in rep.diameters[:4])))
        if rep.n_solids is not None:
            rows.append(("Sólidos / faces", f"{rep.n_solids} / {rep.n_faces}"))
        for n in rep.notes:
            rows.append(("Nota", n))
        info = Table([[Paragraph(f"<b>{_txt(a)}</b>", self.cell), Paragraph(_txt(b), self.cell)] for a, b in rows],
                     colWidths=[34 * mm, 140 * mm])
        info.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.2, GRID), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                  ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5)]))
        imgs = Table([[self._img(iso, 86, 400 / 560), self._img(ctx, 86, 400 / 560)]], colWidths=[88 * mm, 88 * mm])
        return KeepTogether([Paragraph(_txt(leaf.name), self.h2), imgs, info])
