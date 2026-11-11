# NEXUS — Relatório de testes (V3.4, 2026-11-11)

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
