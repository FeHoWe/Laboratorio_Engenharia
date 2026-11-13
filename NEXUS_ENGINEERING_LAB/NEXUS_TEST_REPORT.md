# NEXUS — Relatório de testes (V3.4, 2026-11-11)

## V110.0
Resultado da suíte completa (principal + `test_v22`): **841 passed, 4 skipped** (800 principal + 41 test_v22; 0 falhas; 4 skips = ferramentas externas ausentes no sandbox)
Não testado: Windows 11, WSL2, instalador.

## V106.0
Resultado da suíte completa (principal + `test_v22`): __RESULT__
Não testado: Windows 11, WSL2, instalador.

## V103.0
Resultado da suíte completa (principal + `test_v22`): não executada isoladamente: código acumulado e verificado na suíte da V106.0
Não testado: Windows 11, WSL2, instalador.

## V102.0
Resultado da suíte completa (principal + `test_v22`): não executada isoladamente: código acumulado e verificado na suíte da V106.0
Não testado: Windows 11, WSL2, instalador.

## V101.0
Resultado da suíte completa (principal + `test_v22`): **808 passed, 4 skipped** (767 + 41; 0 falhas)
Não testado: Windows 11, WSL2, instalador.

## V100.0
Resultado da suíte completa (principal + `test_v22`): **798 passed, 4 skipped** (757 + 41; 0 falhas)
Não testado: Windows 11, WSL2, instalador.

## V90.0
Resultado da suíte completa (principal + `test_v22`): **793 passed, 4 skipped** (752 + 41; 0 falhas)
Não testado: Windows 11, WSL2, instalador.

## V80.0
Resultado da suíte completa (principal + `test_v22`): **782 passed, 4 skipped** (741 + 41; 0 falhas)
Não testado: Windows 11, WSL2, instalador.

## V70.0
Resultado da suíte completa (principal + `test_v22`): **773 passed, 4 skipped** (732 + 41; 0 falhas)
Não testado: Windows 11, WSL2, instalador.

## V60.0
Resultado da suíte completa (principal + `test_v22`): **763 passed, 4 skipped** (722 + 41; 0 falhas)
Não testado: Windows 11, WSL2, instalador.

## V50.0
Resultado da suíte completa (principal + `test_v22`): **754 passed, 4 skipped** (713 + 41; 0 falhas)
Não testado: Windows 11, WSL2, instalador.

## V40.0
Resultado da suíte completa (principal + `test_v22`): **747 passed, 4 skipped** (706 + 41 test_v22; 0 falhas)
Não testado: Windows 11, WSL2, instalador.

## V30.0
Resultado da suíte completa (principal + `test_v22`): **738 passed, 4 skipped** (697 principal + 41 test_v22; 0 falhas; 4 skips = ferramentas externas ausentes no sandbox)
Não testado: Windows 11, WSL2, instalador.

## V20.0 — 2026-11-13
Resultado da suíte completa (principal + `test_v22`): **726 passed, 4 skipped** (685 + 4 skipped na suíte principal, 41 em test_v22; 0 falhas)
Novos desde a V10.0: `test_doe`, `test_pista_io`, ampliações em `test_cli`, `test_estudos_export`, `test_comparacao`. `mobile/validate_lab.py`: paridade JS×Python incluindo fatorial e Monte Carlo (≈8,5e‑12). PRNG mulberry32 conferido com Node.
Não testado: Windows 11, WSL2, instalador.

## V10.0 — 2026-11-13
Resultado da suíte completa (principal + `test_v22`): **693 passed, 4 skipped** (652 + 4 skipped na suíte principal, 41 em test_v22; 0 falhas)
Novos desde a V6.0: `test_otimizacao`, `test_cli`, `test_cad_multi`, `test_estudos_export`, aba Estudos (`test_comparacao`). `mobile/validate_lab.py`: paridade JS×Python incluindo tornado e seção áurea (≈1,9e‑13). Aba F1 do celular carregada no Chromium (A/B, tornado e otimização) sem erros de script.
Não testado: Windows 11, WSL2, instalador.

## V6.0 — 2026-11-12
Resultado da suíte completa (principal + `test_v22`): **660 passed, 4 skipped** (619 + 4 skipped na suíte principal, 41 em test_v22; 0 falhas)
Novos desde a V5.0: `test_portabilidade`, consistência no PDF (`test_scenes`), `ajustar` e traduções do CAD (`test_cad_nomes_restricoes`). `mobile/validate_lab.py`: paridade JS×Python incluindo A/B (≈2,6e‑13).
Não testado: Windows 11, WSL2, instalador.

## V5.0 — 2026-11-12
Suíte completa: **644 passed, 4 skipped** (603 passed + 4 skipped na execução principal em 19 min 26 s com `MALLOC_CHECK_=3`, saída 0; `tests/test_v22.py` separado: 41 passed em 3 min 10 s).
Novos: `test_cad_v42` (varredura reta e em L, loft tronco de cone e prisma, entradas inválidas, filete variável, diálogo), `test_comparacao` (A=B ⇒ delta zero, mais potência/mais massa, fechamento do delta acumulado com o tempo de volta, varredura monotônica, aba no diálogo F1), `test_verificacao_projeto` (projeto vazio, sem material/PARCIAL/não atribui nada, material inexistente crítico, massa completa), `test_home` (primeira aba, resumo, atalhos, verificação, versões).
Não validado: aparência real da Home em Windows/DPI diferentes; fluxo completo de instalação; Windows/WSL2.

## V4.1b — 2026-11-12
Suíte completa: **627 passed, 4 skipped** (586 passed + 4 skipped na execução principal em 18 min 49 s com `MALLOC_CHECK_=3`, saída 0; `tests/test_v22.py` separado: 41 passed em 3 min 10 s).
Novos: `test_cad_nomes_restricoes` (15): rastreio de nomes por transformações, furo e edição de parâmetro; nome apagado → erro explícito sem entrar no histórico; filete e casca por nome após rotação/translação; tipo errado e seletor ambíguo; desfazer; serialização (inclusive arquivo antigo sem os campos novos); revolução (tubo completo, meio tubo, corte, entradas inválidas); variáveis, referência entre operações, restrições com reversão, expressões maliciosas e circulares recusadas; diálogo de esboço.
Não validado: seleção pelo clique no 3D (não existe ainda); STEP reais complexos com muitos nomes; Windows.

## V4.1 — 2026-11-12
Suíte completa: **612 passed, 4 skipped** (571 passed + 4 skipped na execução principal em 18 min 47 s com `MALLOC_CHECK_=3`, código de saída 0; `tests/test_v22.py` separado: 41 passed em 3 min 22 s).
Novos: `test_cad_avancado` (furo escareado, padrão linear e circular, arco parcial, espelho, casca, filete/chanfro no topo e na base, receita serializável — volumes contra fórmula fechada) e 2 testes de volta do veículo em processo isolado (retorno imediato + cancelamento; erro como dado).
Não validado: interface dos novos diálogos de entrada por clique (só a API), geometrias complexas/STEP reais com padrões, Windows.

## V4.0 — 2026-11-12
Suíte completa: **602 passed, 4 skipped** (561 passed + 4 skipped na execução principal em 19 min 49 s com `MALLOC_CHECK_=3`, código de saída 0; `tests/test_v22.py` separado: 41 passed em 3 min 18 s).
Novos: `test_nl_job` (erro como dado, diálogo sem bloquear e com cancelamento, caso plástico real × analítico <5 %, pulado sem ccx), `test_project_safety` (autosave sem efeitos colaterais, projeto vazio, recuperação de queda, backup ao salvar, versões listar/comparar/restaurar, erros), `test_project_safety_ui` (janela principal: autosave só com alterações, recuperação e descarte, salvar limpa o autosave, versões e restauração). `test_i18n` (13) passa com as novas strings.
Não validado: comportamento em Windows (caminho `~/.nexus_lab`, verificação de processo por PID no Windows só por código, não executado); queda real (kill -9) do app completo; Windows/WSL2/empacotamento nunca executados em máquina real.

## V3.9 — 2026-11-12
Suíte completa: **590 passed, 4 skipped** (549 + 4 skipped na execução principal em 15 min 06 s com `MALLOC_CHECK_=3`, código de saída 0, sem malloc/abort; `tests/test_v22.py` separado: 41 passed em 3 min 12 s). Depois da auditoria (título do laudo, fonte CJK embutida) foram reexecutados os arquivos alterados (laudo, chinês, i18n): 25 passed. Novos: PDF do projeto em pt/en/es/de/fr + chinês, laudo em en/es/de/fr/zh (classe e números intactos), cobertura completa dos diálogos nos 10 idiomas adicionais, ressalvas de honestidade preservadas. Celular: Playwright em 5 idiomas × 16 abas sem erro de JS; cálculo em francês confere.
Não validado: renderização visual do chinês/japonês/coreano com fontes do Windows; PDF em árabe/hindi; qualidade linguística (traduções de IA sem revisão nativa); Windows/WSL2/empacotamento nunca executados em máquina real.

## V3.8 — 2026-11-12
Suíte completa: **575 passed, 4 skipped** (534 + 4 skipped na execução principal em 12 min 50 s com `MALLOC_CHECK_=3` e `-X faulthandler`, código de saída 0, sem malloc/abort; `tests/test_v22.py` separado: 41 passed em 2 min 50 s). Novos: `test_i18n` (11, incluindo os 10 idiomas de núcleo: fallback, cobertura dos 5 idiomas, preservação de números/unidades/extensões, glossário, hooks Qt em subprocesso), `test_suspension3d` (11), `test_casos_nl` (+4 contato de duas peças: caixas, cilindro/STEP, erros, diálogo), `test_vehicle_lateral` (+4 sensibilidade do μ), `test_lapsim_veiculo` (+1), sinal do trail em `test_vehicle_combined`. Paridade JS×Python do modelo lateral inclui um caso com sensibilidade (2,8e-15).
**Malloc no encerramento (V3.7)**: execução instrumentada da suíte principal (`MALLOC_CHECK_=3`, `-X faulthandler`, cópia do repositório, 12 min 53 s): **505 passed, 4 skipped, código de saída 0**, sem erro. Não reproduziu; causa não identificada. Mitigação adicionada em `tests/conftest.py` (limpeza ordenada de Qt/Gmsh) — NÃO comprovada. Se reaparecer, rode como acima e envie o log.

## V3.7 — 2026-11-12
Suíte completa: **546 passed, 4 skipped** (505 + 4 skipped na execução principal em 12 min 39 s; `tests/test_v22.py` separado: 41 passed em 2 min 54 s). Novos: `test_sketch_solver` (5), `test_lapsim_veiculo` (4), contato automático (+2 em `test_calculix_nl`), CFD→Veículo (+1), fadiga no diálogo (+1), conservação de carga com roda levantando (+1). Paridade JS×Python mantida após a correção de `cargas_eixos` (lateral 2,8e-15).
Observação: ao fim da execução principal o processo imprimiu `malloc(): unaligned tcache chunk detected` e abortou NO ENCERRAMENTO do interpretador (depois do resumo dos testes). Apareceu 1 vez nesta execução e 0 nas execuções V3.5/V3.6 e no `test_v22`; 3 reexecuções dos testes de diálogo novos terminaram com código 0 sem o erro. Não reproduzido, causa não identificada (suspeita: encerramento de Qt/VTK) — pendência registrada.
Não validado: atrito CFD (placa: 60–67 % do alvo); Windows/WSL2 e empacotamento nunca executados.

## V3.6 — 2026-11-12
Suíte completa: **532 passed, 4 skipped** (491 + 4 skipped na execução principal em 12 min 28 s; `tests/test_v22.py` separado: 41 passed em 3 min 03 s). Novos: `test_vehicle_combined` (8), `test_tire_fit` (3), `test_fatigue_fea` (4), `test_casos_nl` (3, ccx real), `test_integracao` (3), `test_report_resultados` (3), `test_referencias` (1), sketch arcos/restrições (+2), resíduo CFD (+1). Paridade JS×Python incluindo g-g: pneu/suspensão/g-g 6e-11.
Não validado: atrito CFD (placa: 29 % → ~50 % do alvo com camadas); empacotamento Windows (`nexus.spec`) e Windows/WSL2 nunca executados em máquina real.

## V3.5 — 2026-11-12
Suíte completa: **504 passed, 4 skipped** (463 + 4 skipped na execução principal em 13 min 31 s; `tests/test_v22.py` separado: 41 passed em 3 min 16 s). Novos: `test_tire_suspension.py` (9), `test_sketch_boolean.py` (8), `test_calculix_nl.py` (6, ccx real). Paridade JS×Python: pneu/suspensão 6e-11; demais inalteradas.
Não validado: atrito CFD (placa plana 29–40 % do alvo, ver `NEXUS_CFD_PLATE_STUDY.md`). Windows/WSL2 nunca testado em máquina real.

Ambiente: Linux headless (Qt offscreen), Python 3.13, OCP 8.0, Gmsh 4.15, **CalculiX 2.21** e **OpenFOAM ESI v1912** instalados só neste ambiente de teste. **Nada foi executado em Windows 11.**

**Suíte completa V3.4: 480 passaram, 4 foram ignorados, 0 falharam** (439 + 41 de `test_v22.py`; novos: test_cfd_gci, test_intelligence_llm, área projetada/ar livre). Windows real: nunca executado. Histórico — V3.3: 470 passaram, 4 foram ignorados, 0 falharam** (429 + 41 de `test_v22.py`; novos: test_products_intelligence, test_windows_wsl, importação do Arsenal, Cp em mm). **Windows 11/WSL2/GPU: lógica testada com Windows SIMULADO; nunca executado em Windows real.** Histórico — V3.2: 457 passaram, 4 foram ignorados, 0 falharam** (416 + 41 de `test_v22.py` em separado; novos: test_field_overlay, test_cfd_dialog com OpenFOAM real, test_arsenal_backup). Histórico — V3.1: 440 passaram, 3 foram ignorados, 0 falharam** (399 + 41 de `test_v22.py` rodados em separado; ~20 min). Na V3.0 eram 433.
Paridade JS × Python (`mobile/validate_lab.py`): máximo ≈ 6e-14 (lateral: 2,8e-15).

| Módulo | Testes | O que prova |
|---|---|---|
| CAD / importação / histórico | test_geometry_and_engine, test_importer_and_solids, test_cad_history, test_v22 | STEP/STL, booleanas, exportação, undo/redo |
| Arsenal / projetos | test_arsenal, test_workspace, test_result_store | cadastro, versões, restauração, exclusão controlada; resultado vira OBSOLETO ao mudar a geometria (preservado) |
| CORE | test_jobs (6), test_doctor (4) | sucesso, falha, crash e solver ausente isolados; timeout; cancelamento; fila; diagnóstico sem fingir motor |
| FEA | test_fea3d, test_fea_tet10, test_fea_gmsh, test_calculix_io, **test_calculix_real** | Tet10 vs Timoshenko/Peterson; **ccx real == NEXUS-Tet10 (~1e-5 %)** e ≈ Timoshenko (<8 %); ccx via fila isolada |
| CFD | test_cfd_case | arquivos do caso; integração de pressão com solução analítica; parser de log; **execução real OpenFOAM (esfera)**: gera, resolve, não inventa |
| V3.1 | test_core_v31, test_fea_study (+2), test_calculix_real (+2) | backup com rotação e restauração; log central; FEA em processo isolado pela interface (progresso, cancelar, falha real exibida); `.frd` completo e VTK; FEA+ccx em job isolado |
| Veículo | test_vehicle_lateral (11) | K de subesterço = fórmula fechada; transferência de carga; skidpad = √(μgR); eixo que satura; degrau converge ao regime; pneu de escova |

## Ignorados (3)
`test_execute_without_openfoam…` (OpenFOAM presente aqui) e dois testes lentos opcionais (`NEXUS_SLOW=1`).

## Não coberto / limites honestos
- **Cd da esfera não é validado**: malha grosseira, não convergiu, Fy lateral grande (~60% do arrasto) indica resultado ruim; o teste só verifica honestidade/estrutura.
- Cd/Cl totais do OpenFOAM indisponíveis neste build (função-objeto quebrada); só pressão.
- UI Qt dos novos recursos testada apenas offscreen (calculadora, diálogo); fila ainda não ligada aos diálogos de FEA/CFD.
- Sem teste em GPU, Windows 11 ou WSL2.
