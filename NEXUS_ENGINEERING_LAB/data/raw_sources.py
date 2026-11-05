"""Dados brutos de densidade, exatamente como publicados nas fontes (com a unidade original).

Cada bloco: (id_fonte, unidade, categoria_padrao|None, texto) e cada linha do texto é
"nome | valor ou faixa | temperatura °C (opcional)".
Nada aqui é estimado: se a fonte não trouxe valor, a linha não existe.
"""

SOURCES = {
    "ETB-METAIS": ("Engineering ToolBox — Densities of Metals and Alloys", "https://www.engineeringtoolbox.com/metal-alloys-densities-d_50.html"),
    "ETB-SOLIDOS": ("Engineering ToolBox — Densities of Solids", "https://www.engineeringtoolbox.com/density-solids-d_1265.html"),
    "ETB-LIQUIDOS": ("Engineering ToolBox — Densities of Liquids", "https://www.engineeringtoolbox.com/liquids-densities-d_743.html"),
    "ETB-MADEIRAS": ("Engineering ToolBox — Densities of Wood Species", "https://www.engineeringtoolbox.com/wood-density-d_40.html"),
    "MECHANICALC": ("MechaniCalc — Material Properties Tables", "https://mechanicalc.com/reference/material-properties-tables"),
    "UNIONFAB": ("Unionfab — Density of Metals", "https://unionfab.com/blog/2024/10/density-of-metals"),
    "GREAT-CERAMIC": ("Great Ceramic — Advanced Ceramics Properties Table", "https://great-ceramic.com/advanced-ceramics-materials/properties/properties-table"),
    "KUGELPOMPEL": ("Data sheet rubber materials V1-00", "https://www.kugelpompel.at/img/cms/Datenbl%C3%A4tter%20Gummi/Data%20sheet%20rubber%20materials%20V1-00.pdf"),
    "CHEVRON": ("Chevron Product Weights (2021)", "https://latinamerica.chevronlubricants.com/content/dam/external/industrial/common/sales-material/sales-sheet/Chevron_Product_Weights.pdf"),
    "POWERSPORTS": ("Powersportsguide — Brake fluid weight", "https://powersportsguide.com/brake-fluid-weight"),
    "PMC-COMPOSITOS": ("Materials 2021, 14, 7268 — Table 1", "https://pmc.ncbi.nlm.nih.gov/articles/PMC8658207/table/materials-14-07268-t001"),
}

UNIT_FACTOR = {"kg/m³": 0.001, "10³ kg/m³": 1.0, "g/cm³": 1.0, "g/ml": 1.0, "lb/in³": 27.6799}

BLOCKS = []

BLOCKS.append(("ETB-METAIS", "kg/m³", "Metais e ligas", """
Actinium | 10070
Admiralty Brass | 8525
Aluminum | 2712
Aluminum - melted | 2560 - 2640
Aluminum alloy - 1100 | 2720
Aluminum alloy 2014, annealed | 2800
Aluminum alloy 3003, rolled | 2730
Aluminum alloy 360 | 2640
Aluminum alloy 2024-T6 | 2770
Aluminum alloy - 6061 | 2720
Aluminum alloy - 7050 | 2800
Aluminum alloy - 7178 | 2830
Aluminum bronze (3-10% Al) | 7700 - 8700
Aluminum foil | 2700 - 2750
Antifriction metal | 9130 - 10600
Antimony | 6690
Antimonial lead (hard lead) | 10900
Babbitt | 7272
Barium | 3594
Beryllium | 1840
Beryllium copper | 8100 - 8250
Bismuth | 9750
Brass - casting | 8400 - 8700
Brass - rolled and drawn | 8430 - 8730
Brass 60/40 | 8520
Bronze - lead | 7700 - 8700
Bronze - phosphorous | 8780 - 8920
Bronze (8-14% Sn) | 7400 - 8900
Brushed metal | 7860
Cadmium | 8640
Caesium | 1873
Calcium | 1540
Cartridge brass (70% Cu, 30% Zn) | 8530
Cast iron | 6800 - 7800
Cerium | 6770
Chemical Lead | 11340
Chromium | 7190
Cobalt | 8746
Constantan | 8880 - 8920
Columbium | 8600
Copper | 8940
Cupronickel | 8908 - 8940
Delta metal | 8600
Duralumin | 2790
Dysprosium | 8550
Electrum (natural alloy silver and gold) | 12500 - 15000
Erbium | 9070
Eroded metal | 7860
Europium | 5243
Gadolinium | 7900
Gallium | 5907
Germanium | 5323
Gold | 19320
Hafnium | 13310
Hastelloy C | 8940
Holmium | 8800
Indium | 7310
Inconel | 8497
Incoloy | 8027
Iridium | 22650
Iron | 7850
Lanthanum | 6145
Lead | 11340
Light alloy based on Al | 2560 - 2800
Light alloy based on Mg | 1760 - 1870
Lithium | 534
Lutetium | 9840
Magnesium | 1738
Magnesium alloy AZ31B | 1770
Manganese | 7440
Manganese Bronze | 8359
Manganin | 8500
Mercury | 13593
Molybdenum | 10188
Monel | 8360 - 8840
Neodymium | 7007
Neptunium | 20200
Nichrome | 8400
Nickel | 8908
Nickel 20 | 8090
Nickel 200 | 8890
Nickel silver | 8400 - 8900
Nickeline | 8770
Nimonic | 8100
Niobium | 8570
Osmium | 22610
Palladium | 12160
Phosphor bronze | 8900
Platinum | 21400
Plutonium | 19816
Polonium | 9200
Potassium | 890
Praseodymium | 6770
Promethium | 7260
Protactinium | 15400
Radium | 5000
Red Brass | 8746
Rhenium | 20800
Rhodium | 12400
Rubidium | 1530
Ruthenium | 12100
Samarium | 7520
Scandium | 2990
Silver | 10490
Sodium | 971
Solder 50/50 Pb Sn | 8885
Stainless Steel | 7480 - 8000
Steel | 7850
Strontium | 2640
Tantalum | 16400
Technetium | 11000
Terbium | 8230
Tin | 7280
Titanium | 4500
Thallium | 11873
Thorium | 11700
Thulium | 9320
Tungsten | 19600
Uranium | 18900
Vanadium | 5494
White metal | 7100
Wrought Iron | 7750
Yellow Brass | 8470
Ytterbium | 6900
Yttrium | 4470
Zinc | 7135
Zirconium | 6570
"""))

BLOCKS.append(("MECHANICALC", "lb/in³", None, """
AISI 1020 carbon steel | 0.283 | | Aço carbono
AISI 1045 carbon steel | 0.283 | | Aço carbono
ASTM A36 steel | 0.283 | | Aço carbono
ASTM A516 steel | 0.283 | | Aço carbono
AISI 4130 alloy steel | 0.283 | | Aço-liga
AISI 4140 alloy steel | 0.283 | | Aço-liga
ASTM A242 steel | 0.282 | | Aço-liga
ASTM A302 steel | 0.282 | | Aço-liga
ASTM A514 steel | 0.283 | | Aço-liga
ASTM A517 steel | 0.280 | | Aço-liga
ASTM A533 steel | 0.282 | | Aço-liga
ASTM A572 steel | 0.283 | | Aço-liga
ASTM A588 steel | 0.280 | | Aço-liga
ASTM A633 steel | 0.280 | | Aço-liga
ASTM A656 steel | 0.282 | | Aço-liga
ASTM A710 steel | 0.280 | | Aço-liga
HY-80 steel | 0.280 | | Aço-liga
HY-100 steel | 0.284 | | Aço-liga
AISI 201 stainless steel | 0.289 | | Aço inoxidável
AISI 202 stainless steel | 0.289 | | Aço inoxidável
AISI 302 stainless steel | 0.289 | | Aço inoxidável
AISI 304 stainless steel | 0.289 | | Aço inoxidável
AISI 304L stainless steel | 0.289 | | Aço inoxidável
AISI 316 stainless steel | 0.289 | | Aço inoxidável
AISI 316L stainless steel | 0.289 | | Aço inoxidável
AISI 405 stainless steel | 0.282 | | Aço inoxidável
AISI 410 stainless steel | 0.282 | | Aço inoxidável
AISI 430 stainless steel | 0.282 | | Aço inoxidável
AISI 446 stainless steel | 0.282 | | Aço inoxidável
15-5PH stainless steel | 0.283 | | Aço inoxidável
17-4PH stainless steel | 0.282 | | Aço inoxidável
17-7PH stainless steel | 0.276 | | Aço inoxidável
A-286 stainless steel | 0.287 | | Aço inoxidável
Alloy 2205 duplex stainless steel | 0.287 | | Aço inoxidável
Ferrallium 255 duplex stainless steel | 0.287 | | Aço inoxidável
ASTM A159 gray cast iron | 0.264 | | Ferros fundidos
ASTM A536 ductile cast iron | 0.256 | | Ferros fundidos
Aluminum 2014 | 0.101 | | Ligas de alumínio
Aluminum 2024 | 0.100 | | Ligas de alumínio
Aluminum 5052 | 0.097 | | Ligas de alumínio
Aluminum 5083 | 0.096 | | Ligas de alumínio
Aluminum 6061 | 0.098 | | Ligas de alumínio
Aluminum 7075 | 0.101 | | Ligas de alumínio
Hastelloy C-276 | 0.321 | | Ligas de níquel
Inconel 625 | 0.305 | | Ligas de níquel
Inconel 686 | 0.315 | | Ligas de níquel
Inconel 718 | 0.297 | | Ligas de níquel
Inconel 725 | 0.300 | | Ligas de níquel
Monel 400 | 0.319 | | Ligas de níquel
Monel K-500 | 0.306 | | Ligas de níquel
Copper-Nickel 70/30 | 0.323 | | Ligas de cobre
Copper-Nickel 90/10 | 0.323 | | Ligas de cobre
Aluminum Bronze (MechaniCalc) | 0.269 | | Ligas de cobre
Beryllium Copper (MechaniCalc) | 0.298 | | Ligas de cobre
Nickel Aluminum Bronze 632 | 0.274 | | Ligas de cobre
Titanium Grade 2 (commercially pure) | 0.163 | | Ligas de titânio
Titanium Ti-5Al-2.5Sn | 0.162 | | Ligas de titânio
Titanium Ti-6Al-4V (Grade 5) | 0.160 | | Ligas de titânio
Titanium Ti-6Al-4V ELI (Grade 23) | 0.160 | | Ligas de titânio
Titanium Ti-5-1-1-1 (Grade 32) | 0.160 | | Ligas de titânio
"""))

BLOCKS.append(("UNIONFAB", "g/cm³", "Metais e ligas", """
Carbon Steel (Unionfab) | 7.85
Alloy Steel (Unionfab) | 7.85
304 Stainless Steel (Unionfab) | 7.75 - 8.1
316 Stainless Steel (Unionfab) | 7.75 - 8.1
Cartridge Brass (Unionfab) | 8.4 - 8.7
Admiralty Brass (Unionfab) | 8.4 - 8.7
Phosphor Bronze (Unionfab) | 8.7 - 8.9
Aluminum Bronze (Unionfab) | 8.7 - 8.9
6061 Aluminum (Unionfab) | 2.6 - 2.9
7075 Aluminum (Unionfab) | 2.6 - 2.9
Ti-6Al-4V (Unionfab) | 4.43 - 4.5
Inconel 625 (Unionfab) | 8.2 - 8.9
Monel 400 (Unionfab) | 8.2 - 8.9
"""))

BLOCKS.append(("GREAT-CERAMIC", "g/cm³", "Cerâmicas técnicas", """
Alumina 96% | 3.75
Alumina 99.7% | 3.95
Alumina 99.95% | 3.98
ZTA (zirconia toughened alumina) | 4.1
Zirconia 3YZ | 6.05
Zirconia Mg-PSZ | 5.7
Black Zirconia | 6.0
Beryllium oxide (BeO) | 2.86
Aluminum nitride AL170 | 3.3
Aluminum nitride AL200 | 3.3
Aluminum nitride AL230 | 3.3
Silicon nitride GPSN | 3.2
Silicon nitride HPSN | 3.3
Boron nitride 99% purity (HP) | 2.0
Boron nitride 99.5% purity | 2.1
Boron nitride 99.8% purity | 2.2
Boron nitride pyrolytic (PBN) | 2.1 - 2.2
Boron nitride BN+AlN | 2.25 - 2.35
Boron nitride BN-B | 2.40 - 2.50
Boron nitride BN-C | 2.80 - 2.90
Boron nitride BN-D | 2.80 - 2.90
Boron nitride BN-S | 2.20 - 2.30
Boron nitride BN-S2 | 2.55 - 2.65
Boron nitride BN-S+ | 2.75 - 2.85
Silicon carbide sintered | 3.1
Silicon carbide reaction bonded | 3.1
Macor (machinable glass-ceramic) | 2.52
MGC (machinable glass-ceramic) | 2.6
"""))

BLOCKS.append(("KUGELPOMPEL", "g/cm³", "Borrachas e elastômeros", """
Polychloroprene (CR) | 1.36
EPDM | 1.2
Fluorocarbon (FPM / FKM) | 1.84
Nitrile rubber (NBR) | 1.2 - 1.4
Natural rubber (NR) | 1.32
Polyurethane rubber (PUR) | 1.28
Styrene-butadiene rubber (SBR) | 1.23
Silicone rubber (polysiloxane) | 1.2
"""))

BLOCKS.append(("PMC-COMPOSITOS", "kg/m³", "Compósitos", """
Glass fiber (fiber) | 2600
Epoxy (matrix) | 1250
GFRP (glass fiber reinforced polymer) | 1925
"""))

BLOCKS.append(("POWERSPORTS", "g/ml", "Fluidos automotivos", """
Brake fluid DOT 3 | 1.02 - 1.04
Brake fluid DOT 4 | 1.04 - 1.08
Brake fluid DOT 5 (silicone) | 0.95 - 0.98
Brake fluid DOT 5.1 | 1.05 - 1.08
"""))

BLOCKS.append(("CHEVRON", "g/ml", "Fluidos automotivos", """
Havoline Motor Oil SAE 10W-30 | 0.8730 | 15.6
Havoline ATF+4 (automatic transmission fluid) | 0.8470 | 15.6
Delo Gear ESI SAE 80W-90 (gear oil) | 0.8882 | 15.6
Havoline Gear Oil SAE 85W-140 | 0.9080 | 15.6
Hydraulic Oil AW 32 | 0.8615 | 15.6
Delo Grease EP 00 | 0.8140 | 15.6
Black Pearl Grease EP 2 | 0.9780 | 15.6
Grease (Chevron typical average) | 0.8825 | 15.6
"""))

BLOCKS.append(("ETB-SOLIDOS", "10³ kg/m³", None, """
ABS - copolymer of acrylonitrile, butadiene and styrene | 1.06
Acetals | 1.42
Agate | 2.5 - 2.7
Acrylic | 1.19
Agate (second entry) | 2.6
Alabaster carbonate | 2.7 - 2.8
Alabaster sulfate | 2.3
Alum, lumpy | 0.881
Alum, pulverized | 0.752
Alumina (aluminium oxide) | 3.95 - 4.1
Aluminum (solids table) | 2.7
Aluminum Alloys (solids table) | 2.6 - 2.85
Aluminum Bronze (solids table) | 7.7
Albite | 2.6 - 2.65
Amber | 1.06 - 1.1
Amphiboles | 2.9 - 3.2
Andesite, solid | 2.77
Anorthite | 2.74 - 2.76
Antimony, cast | 6.7
Arsenic | 4.7
Artificial Wool | 1.5
Asbestos | 2.0 - 2.8
Asbestos, shredded | 0.35
Asbestos, solid | 2.45
Ashes | 0.65
Asphalt, compacted | 2.36
Asphalt, crushed | 0.72
Bakelite | 1.36
Baking powder | 0.72
Balsa Wood (solids table) | 0.13
Barite, crushed | 2.89
Barium (solids table) | 3.78
Barium chloride | 3.86
Bark, wood refuse | 0.24
Barytes | 4.5
Basalt | 2.4 - 3.1
Bauxite, crushed | 1.28
Beef tallow (solid) | 0.9 - 0.97
Beeswax | 0.96
Beryl | 2.7
Beryllia | 3.0
Beryllium (solids table) | 1.85
Biotite | 2.7 - 3.1
Bismuth (solids table) | 9.8
Bitumen | 1.05
Boiler scale | 2.5
Bone | 1.7 - 2.0
Bone, pulverized | 0.88
Borax, fine | 0.85
Boron | 2.34
Brasses (solids table) | 8.4 - 8.75
Bronzes (solids table) | 8.74 - 8.89
Brown iron ore | 5.1
Brick | 1.4 - 2.4
Brick, fire | 2.3
Brick, hard | 2
Brick, pressed | 2.2
Brickwork in cement | 1.8
Brickwork in mortar | 1.6
Butter | 0.86 - 0.87
Cadmium (solids table) | 8.64
Calamine | 4.1 - 4.5
Calcium (solids table) | 1.55
Calcium chloride | 2.15
Calcspar | 2.6 - 2.8
Camphor | 1
Carbon | 3.51
Caoutchouc | 0.9 - 1
Cardboard | 0.7
Cast Iron (solids table) | 7.2
Celluloid | 1.4
Cellulose, cotton, wood pulp, regenerated | 1.48 - 1.53
Cellulose acetate, moulded | 1.22 - 1.34
Cellulose acetate, sheet | 1.28 - 1.32
Cellulose nitrate, celluloid | 1.35 - 1.4
Chlorinated polyether | 1.4
Cement, set | 2.7 - 3
Cement, Portland | 1.5
Cerium (solids table) | 6.77
Chalk | 1.9 - 2.8
Chamotte, fireclay | 1.7 - 2.4
Charcoal, oak | 0.6
Charcoal, pine | 0.3 - 0.4
Chromium (solids table) | 7.1
Chrome oxide | 5.21
Cinnabar | 8.1
Clay | 1.8 - 2.6
Coal, anthracite | 1.4 - 1.8
Coal, bituminous | 1.2 - 1.5
Cobalt (solids table) | 8.8
Cocoa butter (solid) | 0.9
Coke | 1.6 - 1.9
Concrete, lightweight | 0.45 - 1.0
Concrete, medium | 1.3 - 1.7
Concrete, dense | 2.0 - 2.4
Constantan (solids table) | 8.89
Copal | 1 - 1.15
Copper (solids table) | 8.79
Cork | 0.2 - 0.25
Cork, linoleum | 0.55
Corundum | 4.0
Cotton | 0.08
CPVC - chlorinated polyvinyl chloride | 1.6
Lead crystal | 3.1
Diamond | 3 - 3.5
Dolomite | 2.8
Duralium | 2.8
Earth, loose | 1.2
Earth, rammed | 1.6
Ebonite | 1.15
Emery | 4
Electron (Mg alloy) | 1.8
Epidote | 3.2 - 3.5
Epoxy cast resin | 1.11 - 1.4
Epoxy glass fibre | 1.5
Expanded polystyrene | 0.015 - 0.03
Feldspar | 2.6 - 2.8
Fire brick | 1.8 - 2.2
Flint | 2.6
Fluorite | 3.2
Galena | 7.3 - 7.6
Gallium (solids table) | 5.9
Gamboge | 1.2
Garnet | 3.2 - 4.3
Gas carbon | 1.9
Gelatin | 1.3
Germanium (solids table) | 5.32
Glass, common | 2.4 - 2.8
Glass, flint | 2.9 - 5.9
Glass, Pyrex | 2.21
Glass-wool | 0.025
Glue | 1.3
Gneiss | 2.69
Gold (solids table) | 19.29
Granite | 2.6 - 2.8
Graphite | 2.3 - 2.7
Gum arabic | 1.3 - 1.4
Gypsum | 2.3
Hardboard | 1.0
Hematite | 4.9 - 5.3
Hornblende | 3
Ice | 0.917
Indium (solids table) | 7.29
Iron, cast | 7.0 - 7.4
Iodine | 4.95
Iridium (solids table) | 22.5
Ivory | 1.8 - 1.9
Kaolin | 2.6
Lead (solids table) | 11.35
Leather, dry | 0.86
Lime, slaked | 1.35
Limestone | 2.7 - 2.8
Linoleum | 1.2
Lithium (solids table) | 0.53
Magnesia | 3.2 - 3.6
Magnesium (solids table) | 1.74
Magnetite | 4.9 - 5.2
Malachite | 3.7 - 4.1
Manganese (solids table) | 7.43
Marble | 2.6 - 2.8
Meerschaum | 1 - 1.3
Mica | 2.6 - 3.2
Mineral wool | 0.22 - 0.39
Mineral wool quilt | 0.05
Molybdenum (solids table) | 10.2
Muscovite | 2.8 - 3
Nickel (solids table) | 8.9
Nylon 6 | 1.12 - 1.17
Nylon 6,6 | 1.13 - 1.15
Oak (solids table) | 0.72
Ochre | 3.5
Opal | 2.2
Osmium (solids table) | 22.48
Palladium (solids table) | 12.0
Paper | 0.7 - 1.15
Paraffin | 0.9
Peat blocks | 0.85
Phenolic cast resin | 1.24 - 1.32
Phosphor bronze (solids table) | 8.8
Phosphorus | 1.82
Pinchbeck | 8.65
Pitch | 1.1
Pit coal | 1.35
Plaster board | 0.80
Platinum (solids table) | 21.5
Plywood | 0.54
Polyacrylonitrile | 1.16 - 1.18
Polyamides | 1.15 - 1.25
PC - polycarbonate | 1.2
PBT - polybutylene terephthalate | 1.35
LDPE - low density polyethylene | 0.91
HDPE - high density polyethylene | 0.96
PET - polyethylene terephthalate | 1.35
PMMA - polymethyl methacrylate | 1.2
POM - polyoxymethylene | 1.4
PP - polypropylene | 0.91 - 0.94
PPO - polyphenylene ether | 1.1
PS - polystyrene | 1.03
PTFE - polytetrafluoroethylene (Teflon) | 2.28 - 2.30
PU - polyurethane foam | 0.03
PVDF - polyvinylidene fluoride | 1.76
Porcelain | 2.3 - 2.5
Porphyry | 2.6 - 2.9
Potassium (solids table) | 0.86
Pressed wood, pulp board | 0.19
PVC - polyvinyl chloride | 1.39 - 1.42
Pyrex | 2.25
Pyrite | 4.9 - 5.1
Quartz | 2.65
Radium (solids table) | 5
Red lead | 8.6 - 9.1
Red metal | 8.8
Resin | 1.07
Rhenium (solids table) | 21.4
Rhodium (solids table) | 12.3
Rock salt | 2.2
Rosin | 1.07
Rubber, hard | 1.2
Rubber, soft commercial | 1.1
Rubber, pure gum | 0.91 - 0.93
Rubber, foam | 0.06 - 0.25
Rubidium (solids table) | 1.52
Sand, dry | 1.4 - 1.6
Sandstone | 2.1 - 2.4
Sapphire | 3.98
Selenium | 4.4
Serpentine | 2.5 - 2.65
Silica, fused transparent | 2.2
Silica, translucent | 2.1
Silicon carbide | 3.16
Silicon | 2.33
Silver (solids table) | 10.5
Slag | 2 - 3.9
Slate | 2.6 - 3.3
Snow | 0.1
Soapstone | 2.6 - 2.8
Sodium (solids table) | 0.98
Soil | 2.05
Solder | 8.7 - 9.4
Soot | 1.6 - 1.7
Spermaceti | 0.95
Starch | 1.5
Steatite | 2.6 - 2.7
Steel (solids table) | 7.82
Stone | 2.3 - 2.8
Sulfur, crystalline | 2.0
Sugar | 1.6
Talc | 2.7 - 2.8
Tallow, beef (solid) | 0.95
Tallow, mutton (solid) | 0.95
Tantalum (solids table) | 16.6
Tar (solids table) | 1.05
Teflon (solids table) | 2.20
Tellurium | 6.25
Thoria | 4.16
Thorium (solids table) | 11.7
Tin (solids table) | 7.28
Titanium (solids table) | 4.5
Tombac | 8.65
Topaz | 3.5 - 3.6
Tourmaline | 3 - 3.2
Tungsten (solids table) | 19.2
Tungsten carbide | 14.0 - 15.0
Uranium (solids table) | 19.1
Urethane foam (urea formaldehyde foam) | 0.08
Vanadium (solids table) | 6.1
Vermiculite | 0.12
Wax, sealing | 1.8
White metal (solids table) | 7.5 - 10
Wood wool slab | 0.5 - 0.8
Zinc (solids table) | 7.12
Zirconium (solids table) | 6.51
"""))

BLOCKS.append(("ETB-LIQUIDOS", "kg/m³", None, """
Acetaldehyde | 783 | 18
Acetic Acid | 1049 | 25
Acetone | 784.6 | 25
Acetonitrile | 783 | 20
Acrolein | 840 | 20
Acrylonitrile | 801 | 25
Ethyl alcohol (ethanol) 25C | 785.1 | 25
Methyl alcohol (methanol) 25C | 786.5 | 25
Propyl alcohol | 800.0 | 25
Almond kernel oil | 910 | 25
Allylamine | 758 | 20
Ammonia (aqua) | 823.5 | 25
Aniline | 1019 | 25
Anisole | 994 | 20
Apricot kernel oil | 910 | 25
Argan seed oil | 912 | 20
Automobile oils | 880 - 940 | 15
Avocado pulp oil | 912 | 25
Babassu palm oil | 914 | 25
Beef tallow (liquid) | 902 | 25
Beer | 1010 | 10
Benzaldehyde | 1040 | 25
Benzene | 873.8 | 25
Benzil | 1230 | 15
Blackcurrant oil | 923 | 20
Borneo tallow | 855 | 100
Brine | 1230 | 15
Bromine | 3120 | 25
Butanal | 802 | 20
Butterfat | 934 | 15
Butyric Acid | 959 | 20
Butane | 599 | 25
2,3-Butanedione | 981 | 18
2-Butanone | 800 | 25
n-Butyl Acetate | 880 | 20
n-Butyl Alcohol (Butanol) | 810 | 20
n-Butyl chloride | 886 | 20
Cameline oil | 924 | 15
Canola rapeseed oil | 915 | 20
Caproic acid | 921 | 25
Carbolic acid (phenol) 15C | 956 | 15
Carbon disulfide | 1261 | 25
Carbon tetrachloride | 1584 | 25
Carene | 857 | 25
Cashew nut oil | 914 | 15
Castor oil | 952 | 25
Cherry kernel oil | 918 | 25
Chicken fat | 918 | 15
Chinese vegetable tallow | 887 | 25
Chlorine (liquid, as listed) | 1560 | 25
Chlorobenzene | 1106 | 20
Chloroform 20C | 1489 | 20
Chloroform 25C | 1465 | 25
Citric acid, 50% aqueous solution | 1220 | 15
Cocoa butter (liquid) | 974 | 25
Coconut oil | 930 | 40
Cod liver oil | 924 | 15
Cohune nut oil | 914 | 25
Corn oil | 919 | 20
Coriander seed oil | 908 | 25
Cotton seed oil | 920 | 20
Crambe oil | 906 | 25
Cresol | 1024 | 25
Creosote | 1067 | 15
Crude oil, 48° API | 790 | 15.6
Crude oil, 40° API | 825 | 15.6
Crude oil, 35.6° API | 847 | 15.6
Crude oil, 32.6° API | 862 | 15.6
Crude oil, California | 915 | 15.6
Crude oil, Mexican | 973 | 15.6
Crude oil, Texas | 873 | 15.6
Cumene | 860 | 25
Cyclohexane | 779 | 20
Cyclopentane | 745 | 20
Decane | 726.3 | 25
Diesel fuel oil 20 to 60 | 820 - 950 | 15
Diethanolamine | 1097 | 20
Diethyl ether | 714 | 20
o-Dichlorobenzene | 1306 | 20
Dichloromethane | 1326 | 20
Diethylene glycol | 1120 | 15
Diethylene glycol diethyl ether | 906 | 20
Diisopropyl ether | 719 | 25
Dimethyl acetamide | 942 | 20
N,N-Dimethylformamide | 949 | 20
Dimethyl sulfate | 1332 | 20
Dimethyl sulfide | 848 | 20
Dimethyl sulfoxide | 1100 | 20
Dodecane | 754.6 | 25
Ethane (liquid) | 570 | -89
Ethanol 20C | 790 | 20
Ethanol 95% | 810 | 20
Ether | 713.5 | 25
Ethylamine | 681 | 16
Ethyl Acetate | 901 | 20
Ethyl alcohol (pure) | 789 | 20
Ethyl chloride | 900 | 20
Ethylene Dichloride | 1253 | 20
Ethylene glycol | 1097 | 25
Euphorbia lagascae seed oil | 952 | 25
Refrigerant R-11 (trichlorofluoromethane) | 1476 | 25
Refrigerant R-12 (dichlorodifluoromethane) | 1311 | 25
Refrigerant R-22 (chlorodifluoromethane) | 1194 | 25
Formaldehyde | 812 | 45
Formic acid 10% | 1025 | 20
Formic acid 80% | 1221 | 20
Fuel oil | 890 | 15.6
Furan | 1416 | 25
Furfural | 1155 | 25
Gasoline, natural | 711 | 15.6
Gasoline, vehicle | 737 | 15.6
Gas oils | 890 | 15.6
Glucose | 1350 - 1440 | 15.6
Glycerine (95% glycerol, 5% water) | 1249 | 25
Glycerol | 1261 | 25
Grape seed oil | 923 | 20
Hazelnut oil | 909 | 25
Heating oil | 920 | 20
Hempseed oil | 921 | 25
Heptane | 679.5 | 25
Herring oil | 914 | 20
Hexane | 654.8 | 25
Hexanol | 811 | 25
Hexene | 671 | 25
Hexylamine | 766 | 20
Hydrazine | 795 | 25
Illipe mowrah butter | 862 | 100
Ionene | 932 | 25
Isobutyl Alcohol | 802 | 20
Iso-Octane | 692 | 20
Isopropyl Alcohol | 785 | 20
Isopropylbenzene hydroperoxide | 1030 | 20
Isopropyl Myristate | 853 | 20
Kapok seed oil | 926 | 15
Kerosene (paraffin) | 820.1 | 15.6
Linolenic Acid | 897 | 25
Linseed oil | 924 | 25
Lubricating oil | 910 | 20
Machine oil | 910 | 20
Mango seed oil | 912 | 15
Menhaden oil | 920 | 15
Mercury (liquid) | 13590
Methane (liquid) | 465 | -164
Methanol 20C | 791 | 20
Methylamine | 656 | 25
Methyl chloride | 990 | 20
Methyl Isoamyl Ketone | 888 | 20
Methyl Isobutyl Ketone | 801 | 20
Methyl n-Propyl Ketone | 808 | 20
Methyl t-Butyl Ether | 741 | 20
N-Methylpyrrolidone | 1030 | 20
Methyl Ethyl Ketone | 805 | 20
Milk | 1020 - 1050 | 15
Moringa peregrina seed oil | 903 | 24
Mustard seed oil | 913 | 20
Mutton tallow (liquid) | 946 | 15
Naphtha | 665 | 15
Naphtha, wood | 960 | 25
Naphthalene | 820 | 25
Neem oil | 912 | 30
Niger seed oil | 924 | 15
Nitric acid | 1560 | 0
Oat bran oil | 904 | 25
Oat oil | 917 | 25
Ocimene | 798 | 25
Octane | 698.6 | 15
Oil of resin | 940 | 20
Oil of turpentine | 870 | 20
Oil, lubricating (900) | 900 | 20
Oiticica oil | 972 | 20
Olive oil | 911 | 20
Oxygen (liquid) | 1140 | -183
Palm kernel oil | 922 | 15
Palm oil | 914 | 15
Palm olein | 910 | 40
Palm stearin | 884 | 60
Paraldehyde | 994 | 20
Paraffin oil | 800
Palmitic Acid | 851 | 25
Peanut oil | 914 | 20
Pentane 20C | 626 | 20
Pentane 25C | 625 | 25
Perchloroethylene | 1620 | 20
Perilla oil | 924 | 25
Petroleum ether | 640 | 20
Petrol, natural | 711 | 15.6
Petrol, vehicle | 737 | 15.6
Phenol (carbolic acid) 25C | 1072 | 25
Phosgene | 1378 | 0
Phytadiene | 823 | 25
Phulwara butter | 862 | 100
Pinene | 857 | 25
Pine nut oil | 919 | 15
Poppy seed oil | 916 | 25
Pork lard | 898 | 20
Propanal | 866 | 25
Propane (liquid) | 493.5 | -40
Propane R-290 | 494 | 25
Propanol | 804 | 25
Propylamine | 717 | 20
Propylene carbonate | 1201 | 20
Propylene | 514.4 | 25
Propylene glycol | 1036 | 25
Pyridine | 979 | 25
Pyrrole | 966 | 25
Rapeseed oil | 920 | 20
Resorcinol | 1269 | 25
Rice bran oil | 916 | 25
Rosin oil | 980 | 15
Salmon oil | 924 | 15
Sardine oil | 915 | 25
Sea water 25C | 1025 | 25
Seaflower seed oil | 924 | 15
Shark liver oil | 917 | 25
Sheanut butter | 863 | 100
Silane | 718 | 25
Silicone oil | 965 - 980 | 25
Sodium Hydroxide (caustic soda) | 1250 | 15
Sorbaldehyde | 895 | 25
Soybean oil | 920 | 20
Stearic Acid | 891 | 25
Stillinga seed kernel oil | 937 | 25
Sulfur dichloride | 1620
Sulfuric Acid 95% | 1839 | 20
Sulfurous acid | 1490 | -20
Sulfuryl chloride | 1680
Sugar solution 68 brix | 1338 | 15
Sunflower seed oil | 919 | 20
Styrene | 903 | 25
Tall oil | 969 | 25
Tar (liquid) | 1200 | 20
Terpinene | 847 | 25
Tetrahydrofuran | 888 | 20
Toluene | 867 | 20
Transformer oil | 880 | 20
Trichloroethylene | 1470 | 20
Triethylamine | 728 | 20
Trifluoroacetic Acid | 1489 | 20
Tung oil | 912 | 25
Turpentine oil | 860 | 25
Ucuhuba butter oil | 870 | 100
Vernonia seed oil | 901 | 30
Walnut oil | 921 | 25
Water, heavy | 1105 | 11.6
Water - pure | 1000 | 4
Water - sea 25C | 1022 | 25
Whale oil | 925 | 15
Wheatgerm oil | 926 | 25
o-Xylene | 880 | 20
m-Xylene | 864 | 20
p-Xylene | 861 | 20
"""))

BLOCKS.append(("ETB-MADEIRAS", "kg/m³", "Madeiras", """
Alder | 420 - 680
Afrormosia | 710
Agba | 510
Apple | 650 - 850
Ash, white | 650 - 850
Ash, black | 540
Ash, European | 710
Aspen | 420
Balsa | 110 - 140
Bamboo | 310 - 400
Basswood | 320 - 590
Beech | 700 - 900
Birch | 510 - 770
Birch, British | 670
Birch, European | 670
Blue gum | 1000
Box | 950 - 1160
Butternut | 380
Cedar | 490 - 570
Cedar of Lebanon | 580
Cedar, western red | 380
Cherry | 630 - 900
Cherry, European | 630
Chestnut, sweet | 560
Cottonwood | 410
Cypress | 510
Dogwood | 760
Douglas Fir | 530
Ebony | 1110 - 1330
Elm | 540 - 600
Elm, American | 570
Elm, English | 550 - 600
Elm, Dutch | 560
Elm, Wych | 690
Elm, Rock | 820
Gaboon | 430
Greenheart | 1040
Gum, Black | 590
Gum, Blue | 820
Gum, Red | 540
Hackberry | 620
Hemlock, western | 500
Hickory | 600 - 930
Holly | 760
Iroko | 660
Juniper | 560
Keruing | 740
Larch | 500 - 560
Lignum Vitae | 1170 - 1330
Lime, European | 560
Locust | 670 - 710
Logwood | 910
Madrone | 740
Magnolia | 570
Mahogany, African | 500 - 850
Mahogany, Cuban | 660
Mahogany, Honduras | 650
Mahogany, Spanish | 850
Maple | 620 - 750
Meranti, dark red | 710
Myrtle | 660
Oak | 600 - 900
Oak, American Red | 740
Oak, American White | 770
Oak, English Brown | 740
Obeche | 390
Oregon Pine | 530
Parana Pine | 560
Pear | 610 - 730
Pecan | 770
Persimmon | 900
Philippine Red Luan | 590
Pine, pitch | 830 - 850
Pine, Corsican | 510
Pine, radiata | 480
Pine, Scots | 510
Pine, white | 350 - 500
Pine, yellow | 420
Plane, European | 640
Plum | 660 - 780
Poplar | 350 - 500
Ramin | 670
Redwood, American | 450
Redwood, European | 510
Rosewood, Bolivian | 820
Rosewood, East Indian | 900
Sapele | 640
Satinwood | 950
Spruce | 480 - 780
Spruce, Canadian | 450
Spruce, Norway | 430
Spruce, Sitka | 450
Spruce, western white | 450
Sycamore | 400 - 600
Tanguile | 640
Teak, Indian | 660 - 980
Teak, African | 980
Teak, Burma | 740
Utile | 660
Walnut | 640 - 700
Walnut, American Black | 630
Walnut, Claro | 490
Walnut, European | 570
Water gum | 1000
Whitewood, European | 470
Willow | 400 - 600
Yew | 670
Zebrawood | 790
"""))
