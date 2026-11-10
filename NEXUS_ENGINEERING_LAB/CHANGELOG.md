# CHANGELOG

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
