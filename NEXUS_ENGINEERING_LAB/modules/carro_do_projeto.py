"""V50 — Ponte CAD → parâmetros do carro: massa, CG, distribuição e inércia a partir do projeto aberto, para alimentar o `lapsim` e o modelo de bicicleta.

Regras do NEXUS mantidas: só entram peças COM material escolhido por você (nunca atribuído automaticamente); o que ficar de fora é LISTADO e a massa
resultante é um PISO (subestima). Massas extras (piloto, combustível, lastro, componentes não modelados) são SUAS e entram com posição declarada.
Eixos: coordenadas do modelo em mm; `eixo_long`/`eixo_alt` dizem qual é longitudinal e qual é altura (padrão: y e z, como no modelo F1).
Inércia = soma de massas pontuais (ignora a inércia própria de cada peça). Classe: ANALITICO.
"""
from __future__ import annotations

from dataclasses import replace

from . import f1_mass, lapsim


def levantar(project, y_dianteiro_mm: float, y_traseiro_mm: float, extras=None, eixo_long: int = 1, eixo_alt: int = 2) -> dict:
    """`extras`: lista de (nome, massa_kg, (x, y, z) em mm) — piloto, combustível, lastro… informados por você."""
    itens_cad = f1_mass.items_from_components(project.components, project.materials)
    folhas = list(project.components.leaves())
    com_massa = {n for n, _, _ in itens_cad}
    ignoradas = [c.name for c in folhas if c.name not in com_massa]
    extras = [(n, float(m), tuple(p)) for n, m, p in (extras or [])]
    for n, m, p in extras:
        if m <= 0 or len(p) != 3:
            raise ValueError(f"extra '{n}': massa deve ser > 0 e posição (x, y, z)")
    itens = itens_cad + extras
    if not itens:
        raise ValueError("nenhuma peça com material (nem extra informado): escolha materiais no projeto — o NEXUS não atribui automaticamente")
    b = f1_mass.balance(itens, y_dianteiro_mm, y_traseiro_mm, eixo_long, eixo_alt)
    entre_eixos = abs(y_traseiro_mm - y_dianteiro_mm) / 1000.0
    sgn = 1.0 if y_traseiro_mm > y_dianteiro_mm else -1.0
    a = sgn * (b["cg_mm"][eixo_long] - y_dianteiro_mm) / 1000.0          # CG → eixo dianteiro [m]
    I = b["inercia_kgm2"]
    izz = I[2][2] if eixo_alt == 2 else I[eixo_alt][eixo_alt]
    avisos = []
    if ignoradas:
        avisos.append(f"{len(ignoradas)} peça(s) SEM material escolhido ficaram de fora (massa = PISO, subestimada): " + ", ".join(ignoradas[:8]) + ("…" if len(ignoradas) > 8 else ""))
    if not extras:
        avisos.append("Nenhuma massa extra informada (piloto, combustível, lastro…): o total pode estar bem abaixo do carro real.")
    if not 0.0 < a < entre_eixos:
        avisos.append("O CG calculado está fora do entre-eixos (confira os eixos e as posições dos eixos dianteiro/traseiro).")
    return {"classe": "ANALITICO", "massa_kg": b["massa_kg"], "cg_mm": list(b["cg_mm"]), "pct_dianteiro": b["pct_dianteiro"], "pct_traseiro": b["pct_traseiro"],
            "altura_cg_m": b["altura_cg_mm"] / 1000.0, "entre_eixos_m": entre_eixos, "a_m": a, "b_m": entre_eixos - a, "inercia_z_kgm2": izz,
            "n_pecas_cad": len(itens_cad), "n_extras": len(extras), "pecas_ignoradas": ignoradas, "avisos": avisos,
            "limitacoes": ["Massa/CG só das peças com material escolhido + extras SEUS; inércia por massas pontuais (sem inércia própria das peças).",
                           "Modelo analítico sobre a geometria do projeto — não é pesagem do carro real."]}


def carro_do_projeto(base: lapsim.Carro, levantamento: dict) -> lapsim.Carro:
    """Devolve `base` com a massa do levantamento (potência, aero, μ… continuam os de `base`: são SEUS)."""
    return replace(base, massa=float(levantamento["massa_kg"]))


def texto(r: dict) -> str:
    L = [f"Levantamento do projeto — {r['classe']}", f"  massa {r['massa_kg']:.2f} kg ({r['n_pecas_cad']} peças com material + {r['n_extras']} extras)",
         f"  CG: {r['pct_dianteiro']:.1f} % dianteiro / {r['pct_traseiro']:.1f} % traseiro · altura {r['altura_cg_m'] * 1000:.0f} mm · a = {r['a_m']:.3f} m, b = {r['b_m']:.3f} m (entre-eixos {r['entre_eixos_m']:.3f} m)",
         f"  Izz ≈ {r['inercia_z_kgm2']:.2f} kg·m²"]
    return "\n".join(L + ["⚠ " + x for x in r["avisos"] + r["limitacoes"]])
