"""NEXUS INTELLIGENCE — assistente técnico BASEADO EM REGRAS (auditável; NÃO é IA generativa).

Lê resultados já calculados pelo NEXUS (TracedResult / projeto) e devolve um parecer: o que é, quão confiável é, alertas, o que falta e próximos
passos. Regra de ouro: NUNCA inventa número — toda afirmação cita o campo de onde veio (`evidencia`). Sem dado, diz que não há dado.
"""
from __future__ import annotations

from dataclasses import dataclass, field

INFO, ATENCAO, CRITICO = "INFO", "ATENCAO", "CRITICO"
_ORDEM = {CRITICO: 0, ATENCAO: 1, INFO: 2}


@dataclass
class Achado:
    nivel: str
    texto: str
    evidencia: str = ""


@dataclass
class Parecer:
    titulo: str
    resumo: str
    achados: list = field(default_factory=list)
    proximos_passos: list = field(default_factory=list)

    def pior(self) -> str:
        return min((a.nivel for a in self.achados), key=_ORDEM.get, default=INFO)

    def texto(self) -> str:
        L = [f"{self.titulo}", self.resumo, ""]
        for a in sorted(self.achados, key=lambda a: _ORDEM[a.nivel]):
            L.append(f"[{a.nivel}] {a.texto}" + (f"  (fonte: {a.evidencia})" if a.evidencia else ""))
        if self.proximos_passos:
            L += ["", "Próximos passos sugeridos:"] + [f"  - {p}" for p in self.proximos_passos]
        L += ["", "Parecer gerado por regras do NEXUS (não é IA generativa); apoia a decisão, não a substitui."]
        return "\n".join(L)


def _g(r, k, d=None):
    return r.get(k, d) if isinstance(r, dict) else getattr(r, k, d)


def nivel_fs(fs: float) -> str:
    """Regra única do fator de segurança (espelhada em mobile/lab.js): <1 crítico, <1,5 atenção, senão informativo."""
    return CRITICO if fs < 1 else (ATENCAO if fs < 1.5 else INFO)


def interpretar(res) -> Parecer:
    """`res`: TracedResult ou dict (to_dict)."""
    nome, cls = _g(res, "nome", "?"), _g(res, "classe", "?")
    v, ent = _g(res, "valores", {}) or {}, _g(res, "entradas", {}) or {}
    lim = _g(res, "limitacoes", []) or []
    A: list[Achado] = []
    P: list[str] = []
    if cls == "NAO_EXECUTADO":
        A.append(Achado(CRITICO, "A análise NÃO foi executada: não há valores para interpretar.", "classe=NAO_EXECUTADO"))
        for x in lim[:3]:
            A.append(Achado(INFO, f"Motivo registrado: {x[:200]}", "limitacoes"))
        P.append("Instale/corrija o solver indicado e execute novamente (nenhum número foi inventado no lugar).")
        return Parecer(f"Parecer — {nome}", "Sem resultado numérico.", A, P)
    desc = {"ANALITICO": "estimativa por fórmula fechada (não resolve o campo)", "SIMULACAO_NUMERICA": "simulação numérica NÃO validada contra referência",
            "VALIDADO": "validada contra referência informada", "ANIMACAO_PRESCRITA": "animação de movimento prescrito (não é dinâmica resolvida)"}.get(cls, cls)
    A.append(Achado(INFO, f"Classe do resultado: {cls} — {desc}.", "classe"))
    if cls == "SIMULACAO_NUMERICA":
        P.append("Para elevar a VALIDADO: compare com uma referência publicada ou medição, informando a fonte, e faça estudo de malha.")
    if _g(res, "status_geometria") == "OBSOLETO":
        A.append(Achado(CRITICO, "Resultado OBSOLETO: a geometria mudou depois dele.", "status_geometria"))
        P.append("Reexecute a análise na geometria atual antes de decidir.")
    elif _g(res, "status_geometria") == "SEM_VINCULO":
        A.append(Achado(ATENCAO, "Resultado sem vínculo com a versão da geometria (anterior à V3.0): não dá para afirmar que vale para a peça atual.", "status_geometria"))
    # convergência (CFD)
    if "convergiu" in v:
        if v["convergiu"]:
            A.append(Achado(INFO, "O solver declarou convergência.", "valores.convergiu"))
        else:
            A.append(Achado(CRITICO, f"NÃO convergiu em {v.get('iteracoes', '?')} iterações: números são do último passo, não de regime.", "valores.convergiu"))
            P.append("Aumente as iterações e confira se os resíduos caem e os coeficientes estabilizam.")
    if v.get("erro_fatal"):
        A.append(Achado(CRITICO, "O log do solver registra erro fatal/NaN.", "valores.erro_fatal"))
    for k in ("cd", "cd_total_estimado", "cd_pressao"):
        if k in v:
            A.append(Achado(INFO, f"{k} = {v[k]:.4g}" + (" (inclui atrito ESTIMADO por lei da parede)" if k == "cd_total_estimado" else
                      (" (apenas pressão; sem atrito)" if k == "cd_pressao" else "")), f"valores.{k}"))
            break
    if "cd_dif_pct" in v:
        A.append(Achado(INFO if v["cd_dif_pct"] <= 10 else ATENCAO, f"Diferença para o Cd de referência: {v['cd_dif_pct']:.1f} %.", "valores.cd_dif_pct"))
    if "cl_total_estimado" in v and "cd_total_estimado" in v and abs(v["cl_total_estimado"]) > 0.3 * abs(v["cd_total_estimado"]):
        A.append(Achado(ATENCAO, f"Sustentação |Cl|={abs(v['cl_total_estimado']):.3g} é grande frente ao Cd; se a geometria é simétrica, isso indica não convergência ou malha assimétrica.", "valores.cl_total_estimado"))
    if ent.get("bloqueio_pct", 0) > 5:
        A.append(Achado(ATENCAO, f"Bloqueio do domínio {ent['bloqueio_pct']:.1f} % (>5 %): as paredes alteram o escoamento.", "entradas.bloqueio_pct"))
        P.append("Aumente o domínio ou reduza o corpo.")
    if "a_ref_origem" in ent and "caixa" in str(ent["a_ref_origem"]).replace("não a da caixa", ""):
        A.append(Achado(ATENCAO, "A área de referência é a da CAIXA frontal (só normalização): o Cd não é comparável a valores publicados com a área frontal real.", "entradas.a_ref_origem"))
    # estrutural
    if "vm_max_MPa" in v:
        A.append(Achado(INFO, f"von Mises máximo: {v['vm_max_MPa']:.4g} MPa ({v.get('vm_max_tipo', '')}).", "valores.vm_max_MPa"))
        fs = v.get("fator_seguranca_escoamento_ref")
        if fs is None:
            A.append(Achado(ATENCAO, "Sem limite de escoamento informado: não há fator de segurança.", "entradas"))
            P.append("Informe o limite de escoamento do SEU material (o NEXUS não atribui material sozinho).")
        elif nivel_fs(fs) == CRITICO:
            A.append(Achado(CRITICO, f"Fator de segurança {fs:.2f} < 1: escoamento previsto no ponto de máxima tensão.", "valores.fator_seguranca_escoamento_ref"))
        elif nivel_fs(fs) == ATENCAO:
            A.append(Achado(ATENCAO, f"Fator de segurança {fs:.2f}: margem baixa (depende de cargas reais, fadiga e concentração).", "valores.fator_seguranca_escoamento_ref"))
        else:
            A.append(Achado(INFO, f"Fator de segurança {fs:.2f} sobre o escoamento (estático, sem fadiga).", "valores.fator_seguranca_escoamento_ref"))
    if v.get("erro_volume_malha_pct", 0) > 5:
        A.append(Achado(ATENCAO, f"Malha reproduz o volume com erro de {v['erro_volume_malha_pct']:.1f} %: geometria discretizada pobremente.", "valores.erro_volume_malha_pct"))
    if "voxel" in str(ent.get("malhador", "")):
        A.append(Achado(ATENCAO, "Malha de voxels (escada): tensão local NÃO é confiável.", "entradas.malhador"))
        P.append("Refaça com malhador Gmsh e Tet10.")
    if ent.get("ordem") == 1 and "vm_max_MPa" in v:
        A.append(Achado(ATENCAO, "Elemento Tet4 trava em flexão e subestima deslocamentos.", "entradas.ordem"))
    for x in lim[:6]:
        A.append(Achado(INFO, f"Limitação declarada: {x[:220]}", "limitacoes"))
    resumo = f"{nome}: resultado de classe {cls}; {sum(a.nivel == CRITICO for a in A)} crítico(s), {sum(a.nivel == ATENCAO for a in A)} atenção."
    return Parecer(f"Parecer — {nome}", resumo, A, P)


def revisar_projeto(proj: dict) -> Parecer:
    """Revisão de um projeto (dict do ProjectStore): peças sem material, resultados obsoletos/sem vínculo/não validados."""
    A: list[Achado] = []
    P: list[str] = []
    partes, res = proj.get("parts", []), proj.get("results", [])
    A.append(Achado(INFO, f"Projeto '{proj.get('name', '?')}': {len(partes)} peça(s), {len(res)} resultado(s).", "projeto"))
    sem_mat = [p.get("name", "?") for p in partes if not p.get("material")]
    if sem_mat:
        A.append(Achado(ATENCAO, f"{len(sem_mat)} peça(s) sem material informado: {', '.join(sem_mat[:6])}{'…' if len(sem_mat) > 6 else ''}. Massa e FEA ficam parciais.", "parts[].material"))
        P.append("Informe o material de cada peça (o NEXUS nunca atribui material sozinho).")
    if not partes:
        A.append(Achado(ATENCAO, "Projeto sem peças.", "parts"))
    if not res:
        A.append(Achado(ATENCAO, "Nenhum resultado de simulação anexado.", "results"))
        P.append("Rode uma análise (FEA/CFD/Laboratório) e anexe ao projeto.")
    obs = [r for r in res if r.get("status_geometria") == "OBSOLETO"]
    sv = [r for r in res if r.get("status_geometria") == "SEM_VINCULO"]
    nv = [r for r in res if r.get("classe") == "SIMULACAO_NUMERICA"]
    val = [r for r in res if r.get("classe") == "VALIDADO"]
    if obs:
        A.append(Achado(CRITICO, f"{len(obs)} resultado(s) OBSOLETO(s) — geometria mudou: {', '.join(r.get('nome', '?') for r in obs[:5])}.", "results[].status_geometria"))
        P.append("Reexecute os resultados obsoletos.")
    if sv:
        A.append(Achado(ATENCAO, f"{len(sv)} resultado(s) sem vínculo com a versão da geometria.", "results[].status_geometria"))
    if nv:
        A.append(Achado(ATENCAO, f"{len(nv)} resultado(s) numérico(s) NÃO validado(s): não use como prova de conformidade.", "results[].classe"))
    if val:
        A.append(Achado(INFO, f"{len(val)} resultado(s) VALIDADO(S) (com referência registrada).", "results[].classe"))
    nr = [r for r in res if r.get("classe") == "NAO_EXECUTADO"]
    if nr:
        A.append(Achado(ATENCAO, f"{len(nr)} análise(s) NÃO executada(s) (solver ausente/falha).", "results[].classe"))
    pior = "crítico" if obs else ("com atenções" if len(A) > 1 and any(a.nivel == ATENCAO for a in A) else "sem pendências detectadas")
    return Parecer(f"Revisão — {proj.get('name', '?')}", f"Estado do projeto: {pior}.", A, P)


def comparar(a, b) -> Parecer:
    """Compara os valores numéricos comuns de dois resultados (A→B)."""
    va, vb = _g(a, "valores", {}) or {}, _g(b, "valores", {}) or {}
    A: list[Achado] = []
    for k in sorted(set(va) & set(vb)):
        x, y = va[k], vb[k]
        if isinstance(x, (int, float)) and isinstance(y, (int, float)) and not isinstance(x, bool):
            d = y - x
            pct = f" ({100 * d / x:+.1f} %)" if x else ""
            A.append(Achado(INFO, f"{k}: {x:.5g} → {y:.5g}{pct}", f"valores.{k}"))
    if not A:
        A.append(Achado(ATENCAO, "Os resultados não têm valores numéricos em comum.", "valores"))
    if _g(a, "classe") != _g(b, "classe"):
        A.append(Achado(ATENCAO, f"Classes diferentes ({_g(a, 'classe')} × {_g(b, 'classe')}): comparação com cautela.", "classe"))
    return Parecer(f"Comparação — {_g(a, 'nome', 'A')} × {_g(b, 'nome', 'B')}", "Variação de A para B nos campos comuns.", A, [])


GLOSSARIO = {
    "von mises": "Tensão equivalente que resume o estado multiaxial para comparar com o limite de escoamento de materiais dúcteis (critério da energia de distorção).",
    "fator de segurança": "Razão limite/solicitação (aqui: escoamento ÷ von Mises máximo). Abaixo de 1 indica escoamento previsto; a adequação depende de cargas reais, fadiga e normas.",
    "cp": "Coeficiente de pressão: (p − p∞)/(½ρV²). Positivo = sobrepressão (ex.: ponto de estagnação, Cp≈1); negativo = sucção.",
    "cd": "Coeficiente de arrasto: F_arrasto/(½ρV²·A_ref). Só é comparável entre estudos com a MESMA área de referência.",
    "reynolds": "Re = ρVL/μ: razão inércia/viscosidade; define o regime e o arrasto de formas como a esfera (muda muito perto de Re≈3·10⁵).",
    "y+": "Distância adimensional da 1ª célula à parede; funções de parede pedem y+ ≈ 30–300, resolução da subcamada viscosa pede y+ ≈ 1.",
    "convergência": "Estado em que resíduos caem e os coeficientes param de variar com as iterações. Sem convergência, o resultado não é de regime.",
    "tet10": "Tetraedro quadrático de 10 nós: sem o travamento (locking) do Tet4 em flexão; é o elemento recomendado.",
    "classe": "Rótulo de confiança do resultado: ANALÍTICO, SIMULAÇÃO NUMÉRICA, VALIDADO, NÃO EXECUTADO, ANIMAÇÃO PRESCRITA.",
    "validado": "Só significa que concorda, dentro de tolerância, com uma referência INFORMADA e citada — não que a peça real está aprovada.",
    "understeer": "Subesterço: o veículo faz curva com raio maior que o comandado; o gradiente K > 0 no modelo de bicicleta.",
}


def explicar(termo: str) -> str:
    t = termo.strip().lower()
    for k, d in GLOSSARIO.items():
        if k in t or t in k:
            return f"{k}: {d}"
    return f"Termo '{termo}' não está no glossário do NEXUS. Disponíveis: {', '.join(sorted(GLOSSARIO))}."
