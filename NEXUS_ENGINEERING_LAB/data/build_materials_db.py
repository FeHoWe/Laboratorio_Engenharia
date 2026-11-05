"""Gera data/materials.db (SQLite) e data/materials.sql a partir de raw_sources.py.

    python data/build_materials_db.py

Cada linha guarda o valor na unidade ORIGINAL da fonte (orig_text) e o valor convertido para
g/cm³. Nenhum valor é estimado. 1 g/cm³ = 1000 kg/m³ = 1 g/mL; 1 lb/in³ = 27,6799 g/cm³.
"""
from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from raw_sources import BLOCKS, SOURCES, UNIT_FACTOR  # noqa: E402

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE sources (
    id    TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    url   TEXT NOT NULL
);
CREATE TABLE categories (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);
CREATE TABLE materials (
    id            INTEGER PRIMARY KEY,
    name_en       TEXT NOT NULL,
    name_pt       TEXT,
    category_id   INTEGER NOT NULL REFERENCES categories(id),
    density_min   REAL NOT NULL CHECK (density_min > 0),   -- g/cm3
    density_max   REAL NOT NULL CHECK (density_max >= density_min),
    density_typ   REAL NOT NULL,                            -- ponto médio da faixa, g/cm3
    ref_temp_c    REAL,                                     -- temperatura de referência, se a fonte informar
    orig_text     TEXT NOT NULL,                            -- valor e unidade como na fonte
    source_id     TEXT NOT NULL REFERENCES sources(id),
    note          TEXT,
    UNIQUE (name_en, source_id)
);
CREATE INDEX idx_materials_category ON materials(category_id);
CREATE INDEX idx_materials_name ON materials(name_en);
CREATE VIEW v_materials AS
SELECT m.id, COALESCE(m.name_pt, m.name_en) AS display_name, m.name_en, m.name_pt,
       c.name AS category, m.density_min, m.density_max, m.density_typ,
       m.density_typ * 1000.0 AS density_kg_m3, m.ref_temp_c, m.orig_text,
       s.title AS source_title, s.url AS source_url, m.note
FROM materials m JOIN categories c ON c.id = m.category_id JOIN sources s ON s.id = m.source_id;
"""

# traduções dos nomes mais usados em engenharia mecânica (o resto fica no nome original da fonte)
PT = {
    "Aluminum": "Alumínio", "Copper": "Cobre", "Iron": "Ferro", "Steel": "Aço", "Titanium": "Titânio",
    "Nickel": "Níquel", "Zinc": "Zinco", "Tin": "Estanho", "Lead": "Chumbo", "Gold": "Ouro",
    "Silver": "Prata", "Platinum": "Platina", "Tungsten": "Tungstênio", "Magnesium": "Magnésio",
    "Chromium": "Cromo", "Cobalt": "Cobalto", "Molybdenum": "Molibdênio", "Mercury": "Mercúrio",
    "Beryllium": "Berílio", "Lithium": "Lítio", "Silicon": "Silício", "Brass - casting": "Latão fundido",
    "Brass - rolled and drawn": "Latão laminado/trefilado", "Cast iron": "Ferro fundido",
    "Wrought Iron": "Ferro forjado", "Stainless Steel": "Aço inoxidável", "Phosphor bronze": "Bronze fosforoso",
    "Duralumin": "Duralumínio", "Cartridge brass (70% Cu, 30% Zn)": "Latão de cartucho (70Cu-30Zn)",
    "Yellow Brass": "Latão amarelo", "Red Brass": "Latão vermelho", "Solder 50/50 Pb Sn": "Solda 50/50 Pb-Sn",
    "AISI 1020 carbon steel": "Aço carbono AISI 1020", "AISI 1045 carbon steel": "Aço carbono AISI 1045",
    "ASTM A36 steel": "Aço ASTM A36", "AISI 4130 alloy steel": "Aço-liga AISI 4130",
    "AISI 4140 alloy steel": "Aço-liga AISI 4140", "AISI 304 stainless steel": "Aço inox AISI 304",
    "AISI 316 stainless steel": "Aço inox AISI 316", "AISI 316L stainless steel": "Aço inox AISI 316L",
    "AISI 430 stainless steel": "Aço inox AISI 430", "ASTM A159 gray cast iron": "Ferro fundido cinzento ASTM A159",
    "ASTM A536 ductile cast iron": "Ferro fundido nodular ASTM A536", "Aluminum 6061": "Alumínio 6061",
    "Aluminum 7075": "Alumínio 7075", "Aluminum 2024": "Alumínio 2024", "Titanium Ti-6Al-4V (Grade 5)": "Titânio Ti-6Al-4V (Grau 5)",
    "Water - pure": "Água pura (4 °C)", "Sea water 25C": "Água do mar (25 °C)", "Ethylene glycol": "Etilenoglicol",
    "Glycerol": "Glicerol", "Olive oil": "Azeite de oliva", "Castor oil": "Óleo de mamona",
    "Gasoline, vehicle": "Gasolina automotiva", "Kerosene (paraffin)": "Querosene", "Lubricating oil": "Óleo lubrificante",
    "Transformer oil": "Óleo de transformador", "Silicone oil": "Óleo de silicone",
    "Brake fluid DOT 3": "Fluido de freio DOT 3", "Brake fluid DOT 4": "Fluido de freio DOT 4",
    "Brake fluid DOT 5 (silicone)": "Fluido de freio DOT 5 (silicone)", "Brake fluid DOT 5.1": "Fluido de freio DOT 5.1",
    "Havoline Motor Oil SAE 10W-30": "Óleo de motor SAE 10W-30 (Havoline)",
    "Havoline ATF+4 (automatic transmission fluid)": "Fluido de câmbio automático ATF+4 (Havoline)",
    "Natural rubber (NR)": "Borracha natural (NR)", "Silicone rubber (polysiloxane)": "Borracha de silicone",
    "Nitrile rubber (NBR)": "Borracha nitrílica (NBR)", "Polychloroprene (CR)": "Policloropreno (CR)",
    "Fluorocarbon (FPM / FKM)": "Fluorelastômero (FPM/FKM)", "Polyurethane rubber (PUR)": "Borracha de poliuretano",
    "Styrene-butadiene rubber (SBR)": "Borracha estireno-butadieno (SBR)",
    "Alumina 96%": "Alumina 96%", "Silicon carbide sintered": "Carbeto de silício sinterizado",
    "Silicon nitride GPSN": "Nitreto de silício GPSN", "Glass, common": "Vidro comum", "Glass, Pyrex": "Vidro Pyrex",
    "Granite": "Granito", "Marble": "Mármore", "Limestone": "Calcário", "Sandstone": "Arenito", "Quartz": "Quartzo",
    "Diamond": "Diamante", "Graphite": "Grafite", "Ice": "Gelo", "Cork": "Cortiça", "Plywood": "Compensado",
    "Concrete, dense": "Concreto denso", "Porcelain": "Porcelana", "Paper": "Papel", "Cardboard": "Papelão",
    "ABS - copolymer of acrylonitrile, butadiene and styrene": "ABS", "Nylon 6": "Nylon 6 (PA6)",
    "Nylon 6,6": "Nylon 6,6 (PA66)", "PC - polycarbonate": "Policarbonato (PC)", "PMMA - polymethyl methacrylate": "Acrílico (PMMA)",
    "POM - polyoxymethylene": "Poliacetal (POM)", "PP - polypropylene": "Polipropileno (PP)", "PVC - polyvinyl chloride": "PVC",
    "LDPE - low density polyethylene": "Polietileno de baixa densidade (LDPE)", "HDPE - high density polyethylene": "Polietileno de alta densidade (HDPE)",
    "PET - polyethylene terephthalate": "PET", "PS - polystyrene": "Poliestireno (PS)",
    "PTFE - polytetrafluoroethylene (Teflon)": "PTFE (Teflon)", "Acrylic": "Acrílico", "Epoxy cast resin": "Resina epóxi",
    "GFRP (glass fiber reinforced polymer)": "PRFV / GFRP (fibra de vidro + polímero)",
    "Oak": "Carvalho", "Beech": "Faia", "Birch": "Bétula", "Pine, Scots": "Pinus (Scots)", "Teak, Burma": "Teca (Birmânia)",
    "Balsa": "Balsa", "Walnut": "Nogueira", "Maple": "Bordo", "Ash, white": "Freixo branco", "Mahogany, Honduras": "Mogno (Honduras)",
    "Eucalyptus": "Eucalipto", "Ebony": "Ébano", "Bamboo": "Bambu", "Poplar": "Álamo",
}

KW = [  # (categoria, palavras-chave em minúsculas) — aplicado na ordem
    ("Polímeros e plásticos", ["abs -", "acetal", "acrylic", "bakelite", "celluloid", "cellulose", "chlorinated polyether",
        "cpvc", "ebonite", "epoxy", "nylon", "polyacryl", "polyamide", "pc -", "pbt", "ldpe", "hdpe", "pet -", "pmma", "pom -",
        "pp -", "ppo", "ps -", "ptfe", "teflon", "pu -", "pvdf", "pvc", "phenolic", "expanded polystyrene", "urethane foam",
        "resin", "rosin", "linoleum", "glue", "gelatin"]),
    ("Borrachas e elastômeros", ["rubber", "caoutchouc"]),
    ("Madeiras e derivados", ["balsa wood", "oak (solids", "plywood", "hardboard", "pressed wood", "plaster board", "wood wool", "bark", "cork", "charcoal", "paper", "cardboard"]),
    ("Pedras, minerais e cerâmicas", ["agate", "alabaster", "albite", "amphibole", "andesite", "anorthite", "asbestos", "barite",
        "barytes", "basalt", "bauxite", "beryl", "beryllia", "biotite", "calamine", "calcspar", "chalk", "chamotte", "cinnabar",
        "clay", "corundum", "diamond", "dolomite", "emery", "epidote", "feldspar", "flint", "fluorite", "galena", "garnet",
        "glass", "gneiss", "granite", "graphite", "gypsum", "hematite", "hornblende", "kaolin", "limestone", "magnesia",
        "magnetite", "malachite", "marble", "meerschaum", "mica", "muscovite", "ochre", "opal", "porcelain", "porphyry",
        "pyrex", "pyrite", "quartz", "rock salt", "sandstone", "sapphire", "serpentine", "silica", "silicon carbide", "slate",
        "soapstone", "steatite", "stone", "talc", "thoria", "topaz", "tourmaline", "tungsten carbide", "alumina", "vermiculite",
        "mineral wool", "slag", "lead crystal", "boiler scale", "brown iron ore", "chrome oxide", "tourm"]),
    ("Construção civil e solos", ["asphalt", "brick", "cement", "concrete", "earth", "sand", "soil", "bitumen", "pitch", "tar (solids", "lime, slaked", "fire brick"]),
    ("Combustíveis e carvões", ["coal", "coke", "pit coal", "soot", "gas carbon", "peat"]),
    ("Metais e ligas", ["(solids table)", "antimony", "bismuth", "brasses", "bronzes", "pinchbeck", "red metal", "solder", "tombac",
        "white metal", "electron", "duralium", "iron, cast", "cast iron", "tungsten (", "indium", "gallium", "germanium", "tin", "zinc"]),
    ("Orgânicos, ceras e alimentos", ["alum", "amber", "artificial wool", "baking", "beeswax", "beef tallow", "bone", "borax", "butter",
        "camphor", "carbon", "cocoa", "copal", "cotton", "gamboge", "gum arabic", "ivory", "leather", "paraffin", "snow", "spermaceti",
        "starch", "sugar", "sulfur", "tallow", "wax", "ashes", "ice", "barium chloride", "calcium chloride", "iodine", "phosphorus",
        "selenium", "tellurium", "arsenic", "boron", "glass-wool"]),
]

LIQ_FUEL = ["crude oil", "diesel", "fuel oil", "gas oils", "gasoline", "petrol", "kerosene", "naphtha", "heating oil", "petroleum ether",
            "octane", "heptane", "hexane", "pentane", "iso-octane", "decane", "dodecane", "cyclohexane", "cyclopentane", "butane", "propane", "methane", "ethane (liquid)"]
LIQ_OIL = [" oil", "butter", "tallow", "fat", "lard", "butterfat", "olein", "stearin", "acid, oleic", "linolenic", "palmitic", "stearic", "tall oil"]


def classify(source: str, name: str, default: str | None) -> str:
    if default:
        return default
    n = name.lower()
    if source == "ETB-LIQUIDOS":
        if n.startswith(("automobile oils", "lubricating oil", "machine oil", "oil, lubricating", "transformer oil", "silicone oil")):
            return "Fluidos automotivos"
        if any(k in n for k in LIQ_FUEL):
            return "Combustíveis líquidos"
        if n.startswith("refrigerant") or "r-290" in n:
            return "Fluidos refrigerantes"
        if "water" in n or "sea water" in n or n.startswith("brine"):
            return "Água e soluções salinas"
        if any(k in n for k in LIQ_OIL):
            return "Óleos e gorduras"
        return "Líquidos químicos"
    for cat, kws in KW:
        if any(k in n for k in kws):
            return cat
    return "Outros sólidos"


def parse_range(txt: str) -> tuple[float, float]:
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", txt)]
    if len(nums) == 1:
        return nums[0], nums[0]
    if len(nums) == 2:
        return min(nums), max(nums)
    raise ValueError(f"valor inválido: {txt!r}")


NOTES = {
    ("Copper (solids table)", "ETB-SOLIDOS"): "Valor divergente da própria fonte (8,94 na tabela de metais; cobre puro ≈ 8,96).",
    ("Glass, flint", "ETB-SOLIDOS"): "Faixa muito larga na fonte (depende do teor de chumbo).",
    ("Chlorine (liquid, as listed)", "ETB-LIQUIDOS"): "A fonte lista como 'Chloride'; interpretado como cloro líquido — confira antes de usar.",
    ("Sulfurous acid", "ETB-LIQUIDOS"): "A fonte lista como 'Sulfurus acid'.",
    ("Pine, pitch", "ETB-MADEIRAS"): "A fonte imprime '830 850'; interpretado como faixa 830–850.",
    ("Agate (second entry)", "ETB-SOLIDOS"): "Segunda entrada da mesma fonte.",
}


def build_rows():
    rows = {}
    for src, unit, default_cat, text in BLOCKS:
        f = UNIT_FACTOR[unit]
        for line in text.strip().splitlines():
            parts = [p.strip() for p in line.split("|")]
            name, val = parts[0], parts[1]
            temp = float(parts[2]) if len(parts) > 2 and parts[2] else None
            cat_override = parts[3] if len(parts) > 3 and parts[3] else None
            lo, hi = parse_range(val)
            key = (name, src)
            if key in rows:
                raise ValueError(f"duplicado: {key}")
            cat = cat_override or classify(src, name, default_cat)
            rows[key] = dict(name_en=name, name_pt=PT.get(name), category=cat,
                             lo=round(lo * f, 5), hi=round(hi * f, 5), temp=temp,
                             orig=f"{val} {unit}", source=src, note=NOTES.get(key))
    return list(rows.values())


def build(db_path: Path, sql_path: Path) -> dict:
    rows = build_rows()
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    con.executemany("INSERT INTO sources VALUES (?,?,?)", [(k, v[0], v[1]) for k, v in SOURCES.items()])
    cats = sorted({r["category"] for r in rows})
    con.executemany("INSERT INTO categories(name) VALUES (?)", [(c,) for c in cats])
    cid = dict(con.execute("SELECT name, id FROM categories"))
    con.executemany(
        "INSERT INTO materials(name_en,name_pt,category_id,density_min,density_max,density_typ,ref_temp_c,orig_text,source_id,note)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        [(r["name_en"], r["name_pt"], cid[r["category"]], r["lo"], r["hi"], round((r["lo"] + r["hi"]) / 2, 5),
          r["temp"], r["orig"], r["source"], r["note"]) for r in sorted(rows, key=lambda r: (r["category"], r["name_en"].lower()))],
    )
    con.commit()
    with open(sql_path, "w", encoding="utf-8") as fh:
        fh.write("-- NEXUS ENGINEERING LAB — banco de densidades de materiais (g/cm3)\n"
                 "-- Gerado por data/build_materials_db.py. Valores exatamente como nas fontes (coluna orig_text).\n")
        for line in con.iterdump():
            fh.write(line + "\n")
    stats = {"materiais": con.execute("SELECT COUNT(*) FROM materials").fetchone()[0],
             "categorias": len(cats), "fontes": len(SOURCES)}
    con.close()
    return stats


if __name__ == "__main__":
    print(build(HERE / "materials.db", HERE / "materials.sql"))
