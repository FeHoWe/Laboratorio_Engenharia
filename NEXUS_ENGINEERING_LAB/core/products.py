"""Visão de produto do NEXUS: cinco produtos sobre um núcleo comum. Cada capacidade aponta para uma AÇÃO real da janela principal
(`actions_by_key`) e declara um estado HONESTO: PRONTO (existe e é testado), PARCIAL (existe com limites declarados) ou PLANEJADO (não existe).
Nada aqui executa cálculo — é o mapa que a interface (Hub) e a documentação usam, para o produto não prometer o que não entrega.
"""
from __future__ import annotations

from dataclasses import dataclass, field

PRONTO, PARCIAL, PLANEJADO = "PRONTO", "PARCIAL", "PLANEJADO"


@dataclass(frozen=True)
class Capacidade:
    rotulo: str
    acao: str | None          # chave em MainWindow.actions_by_key (None = ainda não existe)
    estado: str
    nota: str = ""


@dataclass(frozen=True)
class Produto:
    chave: str
    nome: str
    missao: str
    capacidades: tuple = field(default_factory=tuple)
    lacunas: tuple = field(default_factory=tuple)

    def estado(self) -> str:
        es = {c.estado for c in self.capacidades}
        return PLANEJADO if es <= {PLANEJADO} else (PRONTO if es == {PRONTO} else PARCIAL)


PRODUTOS: tuple = (
    Produto("cad", "NEXUS CAD", "Desenvolvimento e edição de componentes mecânicos.",
            (Capacidade("Biblioteca de peças paramétricas (B-rep real)", "library", PRONTO, "18 peças; parâmetros editáveis"),
             Capacidade("Editor paramétrico com histórico (undo/redo, STEP)", "solvers", PRONTO, "dentro de Solvers…"),
             Capacidade("Sketch 2D (retângulo, círculo, polígono, rrect, rasgo, furos), restrições em sequência e booleanas no histórico", "solvers", PARCIAL, "restrições não são um solver geral; sem arco livre por 3 pontos"),
             Capacidade("Arsenal de componentes versionados (exportar/importar, backup)", "arsenal", PRONTO),
             Capacidade("Montagem, BOM, interferência, juntas", "bom", PRONTO),
             Capacidade("Booleanas escolhendo a peça importada com o mouse", None, PLANEJADO)),
            ("Sketch sem solver de restrições/arco livre por 3 pontos", "Booleanas só pelo histórico (ferramenta caixa/cilindro/esfera/STEP)")),
    Produto("structural", "NEXUS STRUCTURAL", "Análise estrutural, resistência e fadiga.",
            (Capacidade("FEA 3D estático (Tet10, Gmsh) + CalculiX real", "solvers", PRONTO, "verificado vs Timoshenko/Peterson; mapa de von Mises no 3D"),
             Capacidade("Frequências naturais e convergência de malha", "solvers", PRONTO),
             Capacidade("Fadiga (aba)", "fatigue", PARCIAL, "modelos de vida por tensão; dados de material são do usuário"),
             Capacidade("Resultados ligados à versão da geometria", "solvers", PRONTO),
             Capacidade("Plasticidade bilinear, multimaterial e contato (CalculiX)", "nlfea", PARCIAL, "casos de barra/blocos prontos; contato em peça importada ainda não"),
             Capacidade("Fadiga a partir do pico de tensão do FEA (API fatigue_fea)", None, PLANEJADO)),
            ("Contato/plasticidade só em casos prontos de caixa (verificação), não em peça importada; fadiga-FEA só por Python", "Tensão em quina viva é singular (depende da malha)")),
    Produto("aero", "NEXUS AERODYNAMICS", "Dinâmica dos fluidos e aerodinâmica.",
            (Capacidade("Aerodinâmica analítica (níveis 1 e 2)", "lab", PRONTO, "classe ANALÍTICO — não é CFD"),
             Capacidade("CFD OpenFOAM isolado, progresso/cancelar, Cp sobre as peças", "solvers", PARCIAL, "Cd/Cl por integração própria; sem validação ampla"),
             Capacidade("Camadas prismáticas (addLayers) e critério de resíduo (CONVERGIDO/DECAINDO/ESTAGNADO/DIVERGINDO)", "solvers", PARCIAL, "placa plana: atrito subiu de 29 % para ~50 % do alvo, ainda NÃO validado"),
             Capacidade("Linhas de corrente", None, PLANEJADO)),
            ("Cd da esfera: GCI 2,8 % e Cl≈0, mas sem VALIDADO (resíduos não convergidos, atrito estimado)", "Atrito viscoso é estimativa de 1ª ordem")),
    Produto("vehicle", "NEXUS VEHICLE", "Dinâmica veicular e desempenho.",
            (Capacidade("Dinâmica longitudinal e volta quase-estacionária", "f1tools", PRONTO),
             Capacidade("Dinâmica lateral (bicicleta, pneu de escova, Milliken)", "lab", PRONTO),
             Capacidade("Simulador F1 (volta, pneus, estratégia, telemetria sintética)", "f1sim", PARCIAL, "telemetria é SINTÉTICA, não real"),
             Capacidade("Pneu combinado Fx–Fy e suspensão duplo-A (camber, bitola, centro de rolagem)", "vehgeo", PARCIAL, "suspensão 2D vista frontal; sem elastocinemática"),
             Capacidade("Diagrama g-g (aderência sob tração/frenagem) e ajuste de pneu por CSV", "vehgeo", PARCIAL, "sem arrasto/arfagem; pino-mestre 3D e CFD→Veículo só por API Python"),
             Capacidade("Suspensão 3D completa (convergência, elastocinemática; caster/KPI só por API)", None, PLANEJADO)),
            ("Ferramentas não substituem sistemas da equipe nem homologação FIA",)),
    Produto("intelligence", "NEXUS INTELLIGENCE", "Assistente técnico para interpretar projetos, resultados e auxiliar nas decisões de engenharia.",
            (Capacidade("Interpretar um resultado (classe, validade, alertas, próximos passos)", "intelligence", PRONTO, "baseado em REGRAS auditáveis"),
             Capacidade("Revisar um projeto (resultados obsoletos, materiais não informados, não validados)", "intelligence", PRONTO),
             Capacidade("Comparar resultados e explicar termos de engenharia", "intelligence", PRONTO),
             Capacidade("Perguntas em linguagem natural (IA generativa OPCIONAL)", "intelligence", PARCIAL,
                        "exige ANTHROPIC_API_KEY e sua confirmação de envio; resposta é verificada: números fora dos resultados são marcados")),
            ("O núcleo é por regras (não inventa números); a camada generativa é opcional e suas respostas só valem se 'aprovadas' na checagem de números",)),
)


def produto(chave: str) -> Produto:
    for p in PRODUTOS:
        if p.chave == chave:
            return p
    raise KeyError(chave)


def resumo() -> list[dict]:
    return [{"chave": p.chave, "nome": p.nome, "estado": p.estado(), "pronto": sum(c.estado == PRONTO for c in p.capacidades),
             "parcial": sum(c.estado == PARCIAL for c in p.capacidades), "planejado": sum(c.estado == PLANEJADO for c in p.capacidades)} for p in PRODUTOS]
