# CHANGELOG

## V3.1 — 2026-11-10 (estabilidade e integração)
Adicionado
- **FEA em processo isolado na interface**: botão "Executar em PROCESSO ISOLADO" no diálogo de FEA, com barra de progresso, **Cancelar**, e erro real do solver mostrado (`modules/fea_job.py`). Opção de repetir no CalculiX e comparar.
- **Leitura completa do `.frd` do CalculiX** (`calculix_io.parse_frd`, `vm_nodal`, `export_vtk_frd`): deslocamento e von Mises NODAIS, exportação VTK para ParaView. Verificado contra o `ccx` real: campo de deslocamento inteiro coincide com o NEXUS-Tet10 (<1e-4 do máximo) e von Mises nodal máx. dentro de 3 %.
- `core/logs.py`: log central rotativo (`~/.nexus_engineering_lab/logs/nexus.log`); `JobManager` registra o desfecho de cada job.
- `core/backup.py`: backup com carimbo e rotação; `ProjectStore.save` guarda a versão anterior do projeto (5 mais recentes); `restore_latest`.

Esclarecimento (correção de uma afirmação da V3.0)
- O diálogo de FEA **já executava em thread** (não congelava a interface). O que faltava — e agora existe — era isolamento de processo (um travamento do solver não derruba o NEXUS), progresso e cancelamento. O diálogo de **CFD ainda não existe na interface** (só a API `cfd_case`).

## V3.0 — 2026-11-10 (Master Prompt: plataforma de engenharia computacional)
Adicionado
- `core/jobs.py`, `core/job_worker.py`: fila de processos isolados com cancelamento, timeout, log e progresso.
- `core/doctor.py`: diagnóstico de ambiente completo (somente leitura) + botão em *Solvers…*.
- `modules/result_store.py`: impressão digital de geometria; resultados ficam OBSOLETOS (preservados) quando a geometria muda; comparação entre versões. `ProjectStore.attach_result` aceita `geometry_fp`; novos `part_fingerprints` e `refresh_results`.
- `modules/vehicle_lateral.py`: dinâmica lateral (bicicleta, pneu de escova, transferência de carga de Milliken, skidpad, degrau de esterçamento). Calculadora "Curva em regime" no Laboratório; aba Veículo do celular; paridade JS×Python ≈ 3e-15.
- `modules/cfd_case.py`: execução real do OpenFOAM com leitura de log (iterações, resíduos, convergência), `forcas_pressao` (integração própria de pressão), `solver_registry.openfoam_shell` (carrega `etc/bashrc`).
- Testes: `test_jobs`, `test_doctor`, `test_result_store`, `test_vehicle_lateral`, `test_calculix_real` e novos casos em `test_cfd_case`.
- Documentos: AUDIT, ARCHITECTURE, INSTALLATION, USER_GUIDE, TEST_REPORT, ROADMAP.

Corrigido
- OpenFOAM: patch `sides` não coplanar (agora `sideL`/`sideR`); faltava `turbulenceProperties`/`RASModel` para ESI ≤ v1912; resultado ignorava Cd/convergência.
- Celular: matrizes de pose do F1 2027 perdiam rigidez (~0,2%) → reortonormalização (Gram–Schmidt).
- Textos: biblioteca tem 18 peças (docs diziam 19).

Validado de verdade neste ciclo
- CalculiX 2.21: deslocamento de ponta de viga tubular, NEXUS-Tet10 × `ccx` concordam (≈1e-5 %), ambos a poucos % de Timoshenko.
- OpenFOAM v1912: malha snappyHexMesh + simpleFoam k-ω SST executam (esfera, 120–300 iterações). **Não é validação de Cd.**

## V2.9 e anteriores
Ver README.md.
