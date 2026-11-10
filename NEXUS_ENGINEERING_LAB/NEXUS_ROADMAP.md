# NEXUS — Roadmap e status por fase do Master Prompt

Legenda: ✅ feito e testado · 🟡 parcial · ⬜ não feito.

| Fase | Estado | O que existe | O que falta |
|---|---|---|---|
| 0 Auditoria | ✅ | `NEXUS_TECHNICAL_AUDIT.md` | — |
| 1 NEXUS CORE | 🟡 | Fila de processos isolados, diagnóstico, vínculo resultado↔geometria, **FEA isolado na UI com progresso/cancelar (V3.1)**, **log central**, **backup de projetos ao salvar** | Diálogo de **CFD** (não existe na UI; só API); backup também do Arsenal; relatório central de execuções; teste no Windows 11 |
| 2 CAD | 🟡 | OCP: leitura/escrita STEP, STL/OBJ como malha, primitivas/extrusão/revolução/furos/booleanas nas peças da biblioteca, histórico paramétrico com undo/redo, montagem e posicionamento | Operações booleanas e extrusão *interativas* sobre peça importada na GUI; edição de sketch; CadQuery/FreeCAD não adotados |
| 3 Arsenal | ✅ | Cadastro, versões, restauração, duplicação, comparação, exportação, categorias, exclusão controlada, uso por projeto | Importação de Arsenal exportado (só exportação existe) |
| 4 FEA | 🟡 | Gmsh→Tet10 (NEXUS) e →CalculiX **executado de verdade**; **campo `.frd` completo lido (U e von Mises nodal) e exportado em VTK**; verificação contra Timoshenko e Peterson | Mapa de von Mises **dentro do viewport do NEXUS** (hoje só ParaView/VTK); pressões/gravidade/múltiplos corpos e materiais por região |
| 5 CFD | 🟡 | Caso OpenFOAM gerado e **executado de verdade** (esfera); resíduos/convergência; pressão integrada | Cd/Cl totais dependem de função-objeto (quebrada neste build); camada limite (addLayers) desativada; validação por malha e referência; linhas de corrente/ParaView; WSL2 não testado |
| 6 Veículo | 🟡 | Longitudinal RK4, volta quase-estacionária, **lateral (bicicleta/escova/rolagem)**, skidpad, degrau de esterçamento | Pneu combinado curva+tração, rolagem/arfagem dinâmicas, suspensão com geometria, animação alimentada pelos estados calculados |
| 7 Integração | 🟡 | Resultados ligados à versão da geometria; comparação entre versões | Fluxo único na GUI (Arsenal→FEA→versão→comparar) e CFD→Veículo automático |
| 8 Testes/empacotamento | 🟡 | Suíte + paridade JS×Python | Empacotamento Windows (instalador), teste em Windows 11 real, GPU |

## Próximos passos sugeridos (ordem)
1. **Testar no Windows 11 real** (nada foi executado lá) e corrigir instalação/dependências.
2. Diálogo de CFD na UI usando `JobManager`.
3. Mostrar von Mises (do `.frd`) no viewport e botão "Anexar resultado à versão" (`attach_result(..., geometry_fp)`).
4. Estudo de malha automático no CFD + validação contra caso de referência (cilindro/esfera/placa).
5. Pneu combinado (elipse de atrito) no modelo lateral e acoplamento com `nexus_f1`.
