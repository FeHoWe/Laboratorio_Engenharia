# NEXUS ENGINEERING LAB — Arquitetura (V3.0)

## Camadas (dependências só apontam para baixo)
```
interface/   telas Qt/VTK (sem cálculo)
modules/     regras de engenharia (CAD, Arsenal, FEA, CFD, veículo, resultados)
core/        modelo, CAD (OCP), projetos .nexus, **jobs** (fila de processos), **doctor** (ambiente)
nexus_f1/    pacote F1 (volta, pneus, ERS, telemetria, análise)
mobile/      versão de celular (JS espelhando o Python, validada por paridade)
```

## NEXUS CORE (novo na V3.0)
- `core/jobs.py` — `JobManager`: fila com limite de paralelismo, **processo separado por job**, cancelamento (grupo de processos), tempo limite, log, progresso (`NEXUS_PROGRESS n`), resultado JSON (`NEXUS_RESULT_JSON:`). Estados: QUEUED→RUNNING→DONE/FAILED/CANCELLED/TIMEOUT. Falha, crash ou solver ausente de um job nunca derruba os demais nem o NEXUS; callback de UI que lança exceção não quebra o gerenciador. `submit` retorna na hora (UI não congela).
- `core/job_worker.py` — executa `módulo.função(**json)` em interpretador separado.
- `core/doctor.py` — diagnóstico somente leitura (Python, bibliotecas, OCP funcional, Gmsh, CalculiX, OpenFOAM, WSL2, ParaView) com instrução de instalação por item e `verify()`. Nada é instalado automaticamente.

## Fluxo de dados e validade dos resultados
1. Peça = receita paramétrica (`part_key + params`, biblioteca/Arsenal) ou B-Rep importado.
2. `result_store.fingerprint_recipe/fingerprint_shape` produz a impressão digital da geometria.
3. Resultado (`TracedResult`) é anexado com essa impressão (`ProjectStore.attach_result(..., geometry_fp, label)`).
4. `ProjectStore.refresh_results` marca como **OBSOLETO** (preservado, nunca apagado) o que depende de geometria alterada; resultados antigos sem vínculo ficam `SEM_VINCULO` (não afirmamos validade). `result_store.compare` cruza versões.

## Motores
| Motor | Implementação | Execução externa |
|---|---|---|
| CAD | `core/cad_engine.py` (OCP), `modules/cad_history.py`, `samples/library.py` | — |
| Arsenal | `modules/arsenal.py` (SQLite, versionado) | — |
| FEA | `fea3d.py` (Tet4), `fea_tet10.py`, `fea_gmsh.py` (malha conforme) | `calculix_io.py` → `ccx` (testado de verdade) |
| CFD | `cfd_case.py` (níveis 1–2 analíticos; nível 3 OpenFOAM `simpleFoam` k-ω SST) | OpenFOAM via `solver_registry.openfoam_shell` (carrega `etc/bashrc`; no Windows via WSL2) |
| Veículo | `vehicle_dynamics.py` (long.), `vehicle_lateral.py` (lateral), `nexus_f1/` | — |

## Classes de resultado (`TracedResult`)
`ANALITICO` · `SIMULACAO_NUMERICA` (exige solver+versão) · `VALIDADO` (exige referência) · `NAO_EXECUTADO` (sem números) · `ANIMACAO_PRESCRITA`.

## Dinâmica lateral (`vehicle_lateral.py`)
Modelo de uma pista, pneu de escova (Fiala), transferência de carga lateral de Milliken (parcela geométrica pelos centros de rolagem + elástica pela rigidez de rolagem), regime permanente (δ, β, K), limite de aderência e eixo que satura, skidpad com downforce, degrau de esterçamento RK4. Hipóteses: pequenos ângulos no equilíbrio, sem cambagem/convergência, rolagem em regime, velocidade constante.

## Decisões
- OCP em vez de FreeCAD/CadQuery (mesmo kernel, instala via pip, Windows ok).
- Execução externa sempre por subprocesso com `timeout`; falhas viram resultado explícito.
- JS do celular é espelho do Python e é validado numericamente (`mobile/validate_lab.py`).
