# NEXUS — Roadmap e status por fase do Master Prompt

## Visão de produto (V3.3)
| Produto | Estado | Já existe | Falta |
|---|---|---|---|
| NEXUS CAD | 🟡 | Biblioteca B-rep, histórico paramétrico, **sketch 2D (retângulo/círculo/polígono, furos) + extrusão e booleanas (união/corte/interseção com caixa, cilindro, esfera ou STEP) no histórico (V3.5)**, Arsenal, montagem/BOM | Arco livre por 3 pontos, graus de liberdade do sketch; booleanas escolhendo a peça importada com o mouse |
| NEXUS STRUCTURAL | 🟡 | FEA Tet10+Gmsh, CalculiX real, modal, mapa de von Mises no 3D, fadiga (aba), **plasticidade bilinear, multimaterial por região e contato nó-superfície (CalculiX real, módulo `calculix_nl`, V3.5)** | Contato/plasticidade em peça importada na interface (existe `contato_automatico` por API); plasticidade cinemática/cíclica |
| NEXUS AERODYNAMICS | 🟡 | Níveis 1–2 analíticos, CFD OpenFOAM isolado, Cp sobre as peças, atrito estimado | Validação formal (placa plana: atrito 60–67 % do alvo mesmo com camadas absolutas e cunha; esfera: GCI 2,8 %, Cl≈0, mas sem convergência de resíduos e com atrito estimado), camada limite, forceCoeffs funcional (OpenFOAM ≥ v2306) |
| NEXUS VEHICLE | 🟡 | Longitudinal, lateral, volta, skidpad, simulador F1, **pneu combinado Fx–Fy e suspensão duplo-A 2D (V3.5, diálogo + celular)** | Suspensão 3D completa (convergência, elastocinemática; caster/KPI só por API); sensibilidade de μ à carga e arfagem; acoplar a `nexus_f1` e à dinâmica transitória |
| NEXUS INTELLIGENCE | 🟡 | Interpretação, revisão de projeto, comparação, glossário (regras) | Camada generativa existe como OPCIONAL (chave própria + checagem de números); falta avaliá-la em uso real |

Legenda: ✅ feito e testado · 🟡 parcial · ⬜ não feito.

| Fase | Estado | O que existe | O que falta |
|---|---|---|---|
| 0 Auditoria | ✅ | `NEXUS_TECHNICAL_AUDIT.md` | — |
| 1 NEXUS CORE | 🟡 | Fila de processos isolados, diagnóstico, vínculo resultado↔geometria, **FEA isolado na UI com progresso/cancelar (V3.1)**, **log central**, **backup de projetos ao salvar** | **CFD isolado na UI e backup do Arsenal (V3.2)**; relatório central de execuções; teste no Windows 11 |
| 2 CAD | 🟡 | OCP: leitura/escrita STEP, STL/OBJ como malha, primitivas/extrusão/revolução/furos/booleanas nas peças da biblioteca, histórico paramétrico com undo/redo, montagem e posicionamento | Operações booleanas e extrusão *interativas* sobre peça importada na GUI; edição de sketch; CadQuery/FreeCAD não adotados |
| 3 Arsenal | ✅ | Cadastro, versões, restauração, duplicação, comparação, exportação, categorias, exclusão controlada, uso por projeto | — (importação existe desde a V3.3) |
| 4 FEA | 🟡 | Gmsh→Tet10 (NEXUS) e →CalculiX **executado de verdade**; **campo `.frd` completo lido (U e von Mises nodal) e exportado em VTK**; verificação contra Timoshenko e Peterson | **Mapa de von Mises no viewport do NEXUS (V3.2)**; pressões/gravidade/múltiplos corpos e materiais por região |
| 5 CFD | 🟡 | **Diálogo de CFD na UI com progresso/cancelar e mapa de Cp (V3.2)**; caso OpenFOAM gerado e **executado de verdade** (esfera, bloco da biblioteca); resíduos/convergência; pressão integrada | Cd/Cl totais dependem de função-objeto (quebrada neste build); camada limite (addLayers) desativada; validação por malha e referência; linhas de corrente/ParaView; WSL2 não testado |
| 6 Veículo | 🟡 | Longitudinal RK4, volta quase-estacionária, **lateral (bicicleta/escova/rolagem)**, skidpad, degrau de esterçamento | Pneu combinado curva+tração, rolagem/arfagem dinâmicas, suspensão com geometria, animação alimentada pelos estados calculados |
| 7 Integração | 🟡 | Resultados ligados à versão da geometria; comparação entre versões | Fluxo único na GUI (Arsenal→FEA→versão→comparar) e CFD→Veículo automático |
| 8 Testes/empacotamento | 🟡 | Suíte + paridade JS×Python | Empacotamento Windows (instalador), teste em Windows 11 real, GPU |

## Feito na V50.0
- Ponte CAD→carro (CLI/API). Pendente: inércia própria das peças, GUI dedicada.

## Feito na V40.0
- Calibração com identificabilidade (CLI/API). Pendente: GUI/celular, calibração multi-volta, ruído colorido nas incertezas.

## Feito na V30.0
- Validação com telemetria real do usuário (CLI/API). Pendente: GUI/celular para validação, várias voltas, sincronismo automático.

## Feito na V20.0 (V11–V19)
- Fatorial 2^k, Monte Carlo, Pareto, stint, pistas de arquivo, relatório consolidado, celular com fatorial/Monte Carlo.
- Pendente: Windows 11 real, correlação entre incertezas, superfície de resposta, pista a partir de dados reais (GPS) com validação, interface para `ajustar_multi`, seleção de face no 3D, tradução nativa revisada, i18n do celular para os textos novos.

## Feito na V10.0 (V6.1–V9.0)
- CLI headless, ajuste multivariável no CAD (API), sensibilidade + otimização da volta, exportação de estudos CSV/JSON/PDF, tornado/otimização 1‑D no celular.
- Pendente: Windows 11 real, interface para `ajustar_multi`, seleção de face no 3D, otimização multi‑parâmetro no celular, interações na sensibilidade (DOE), tradução nativa revisada.

## Feito na V6.0 (V5.1–V5.5)
- Portabilidade Windows (código), seção de consistência no PDF, `ajustar` de uma variável no CAD, diálogos do CAD em 5 idiomas, A/B no celular.
- Pendente: verificação em Windows 11 real, seleção de face no 3D, solver de restrições multivariável, tradução nativa revisada, consistência no celular.

## Feito na V5.0
CAD (varredura, loft, filete variável), comparação A/B + varredura de parâmetro, verificação de consistência do projeto e NEXUS HOME.
**Depois da 5.0 (nada disso foi feito):** validação real no Windows 11 + instalador; redesenho completo em ambientes com barras próprias; seleção de entidades CAD clicando no 3D; solver paramétrico de restrições; A/B e verificação no celular; relatório PDF do projeto incluindo o parecer de consistência; tradução completa das caixas de entrada simples.

## Feito na V4.1b
Nomes persistentes de faces/arestas por rastreio do histórico do OpenCascade, revolução de esboço, variáveis/expressões e restrições verificadas.
**Próximo no CAD:** varredura (sweep) e loft, filete de raio variável, restrições que *resolvem* (solver paramétrico), seleção de entidade clicando no visualizador 3D, tradução completa dos diálogos de entrada.

## Feito na V4.1
Volta do veículo em processo isolado (auditoria mostrou que era o único diálogo realmente pesado); CAD avançado fatia 1: furo escareado, padrões linear/circular, espelho, casca, seletores topo/base.
**Próximo (V4.1b/V4.2):** nomeação topológica persistente, revolução de esboço, restrições paramétricas entre operações, filete de raio variável; depois ambientes Estrutural/CFD integrados à geometria, Veículo/F1 com comparação A/B, Intelligence.

## Feito na V4.0 (fundação)
Casos não lineares em processo isolado com cancelamento; autosave + recuperação após falha; backup ao salvar; versões com comparação e restauração (detalhes no CHANGELOG).
**Restante do prompt-mestre V4.0, em ordem sugerida pelo próprio prompt:** V4.1 CAD avançado (booleanas, furos, filetes, chanfros, padrões, restrições) → V4.2 ambientes Estrutural/CFD com malha e resultados integrados à geometria → V4.3 Veículo e F1 (comparação A/B, relatórios) → V4.4 Intelligence (checagem de consistência, pareceres). Antes disso: mover os diálogos de veículo/F1/solvers para jobs (auditar bloqueio), validar tudo no Windows 11 (`tools\verificar_windows.bat`) e testar o empacotamento.

## Feito na V3.9
Relatórios PDF em 5 idiomas (fontes CJK padrão do PDF para zh/ja/ko), ~340 textos a mais no celular (en/es/de/fr/zh) e diálogos completos nos 10 idiomas adicionais.
Restam: PDF em it/ja/ko/ru/tr/pl/nl/hi/ar/id (hoje em inglês; árabe/hindi exigem fonte embutida e layout RTL no PDF), parecer do INTELLIGENCE e premissas dos módulos (texto livre em português), nomes de peças no celular, revisão por falantes nativos.

## Feito na V3.8
Sensibilidade de μ à carga (linear), suspensão duplo-A 3D com elastocinemática linear, contato entre duas peças (caixa/cilindro/STEP) na interface.
Também: internacionalização (menus + textos fixos dos diálogos em 5 idiomas; celular parcial). Restam: relatórios PDF, resultados calculados e o restante do celular (~540 textos já listados por `tools/extrair_textos_ui.py` e pela coleta no navegador); verificação do glossário em fontes externas; multibraço/pushrod/buchas, centro de rolagem 3D, μ(Fz) a partir de ensaio, contato em montagem arbitrária, validação do atrito CFD, Windows real.

## Próximos passos sugeridos (ordem)
0. (V3.6 feita) CFD com camadas, g-g, ajuste CSV, laudo PDF, selos de referência.
1. **Testar no Windows 11 real** (inclui o empacotamento `nexus.spec`, também nunca executado) (nada foi executado lá) e corrigir instalação/dependências.
2. Importação de Arsenal exportado; Cp sobreposto às peças na mesma escala.
3. Botão "Anexar resultado à versão" (`attach_result(..., geometry_fp)`).
4. Estudo de malha automático no CFD + validação contra caso de referência (cilindro/esfera/placa).
5. Acoplar o pneu combinado ao modelo lateral e a `nexus_f1`; diálogo de contato/plasticidade; camada limite (prismas) no CFD.
