# NEXUS V120.0 — Auditoria (Fase A) e estado por fase

Classificação: **FEITO+TESTADO** (testes automatizados headless) · **PARCIAL** · **NÃO FEITO** (declarado). Nada abaixo foi validado em Windows 11 real.

| Fase | Pedido (resumo) | Estado | Onde / limite |
|---|---|---|---|
| A | Auditoria | FEITO | este arquivo |
| B | CAD 3D interativo: seleção de face/aresta/vértice com mouse, croqui, features no viewport | **NÃO FEITO** | exige interação real com o viewport VTK/OCP; não é verificável sem display. Permanece o que já existia (operações paramétricas por diálogo). |
| C | FEA 3D integrada ao viewport com barra | **PARCIAL (herdado)** | campo/deformada/regiões críticas/consulta de ponto existem desde V110 (`campo_analise`, `analisar_campo`); barra de ferramentas no viewport **não** foi construída. |
| D | Dinâmica veicular 3D animada pelos estados do simulador | **PARCIAL** | séries de estado prontas e testadas (`modules/estados_veiculo.py`: longitudinal e degrau de esterço com trajetória x,y,ψ; CSV; quadros). **Animação 3D que as consuma NÃO foi construída** (não verificável sem display). |
| E | F1 Telemetry Lab: A×B sincronizado, setores, voltas, CSV com mapeamento/unidades | **PARCIAL** | dados e cálculo FEITO+TESTADO (`modules/telemetria_ab.py` + CLI `telemetria-ab`): delta, setores, frenagem, aceleração lateral (só simulação), consulta de ponto, CSV com colunas/unidades. **Gráficos A×B sincronizados na GUI NÃO feitos.** |
| F | Suspensão → Volta | **FEITO+TESTADO (modelo reduzido)** | `modules/suspensao_volta.py`: RC → transferência lateral → perda de aderência (k_carga SEU) → volta (bicicleta). Linearizado em um ay; camber só reportado. Não é elastocinemática. |
| G | Gêmeo Digital 2.0 persistido no .nexus | **FEITO+TESTADO** | `modules/gemeo_registro.py`, `core/project_manager.py` (chave opcional `gemeo_digital`, FORMAT_VERSION 1 inalterado, abertura tolerante), estados ATUALIZADO/MODIFICADO/NECESSITA_NOVA_SIMULACAO/RESULTADO_HISTORICO/DADOS_INCOMPLETOS, restauração só de materiais. |
| H | AI Engineer 2.0 | **FEITO+TESTADO (sem IA generativa)** | `ai_engenheiro.responder_gemeo` com os cinco blocos; CLI `diagnostico --pergunta`. |
| I | Central de Controle 2.0 (painéis, favoritos, busca global) | **PARCIAL** | botões do Gêmeo na Home; histórico/recentes (V101). Favoritos e busca global **NÃO feitos**. |
| J | Relatórios; validação Windows 11 | **PARCIAL** | relatório técnico (V110); Windows 11 **NÃO VALIDADO** (checklist em docs/WINDOWS_VALIDACAO.md). |

Honestidade: telemetria simulada não é telemetria de equipe; nenhum resultado desta versão é VALIDADO; materiais nunca são atribuídos automaticamente.
