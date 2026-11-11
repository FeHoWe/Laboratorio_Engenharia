# CHANGELOG

## V3.3 — 2026-11-11 (visão de produto + pendências da V3.2)
Adicionado
- **Cinco produtos** (`core/products.py`, `interface/hub_dialog.py`, menu Analyze → *NEXUS — Produtos…*): NEXUS CAD, STRUCTURAL, AERODYNAMICS, VEHICLE e INTELLIGENCE. Cada capacidade aponta para uma ação REAL da janela e declara PRONTO / PARCIAL / PLANEJADO; teste garante que nada "pronto" fica sem função atrás.
- **NEXUS INTELLIGENCE** (`modules/intelligence.py`, diálogo no menu): assistente técnico **por regras** (não é IA generativa). Interpreta um resultado (classe, validade, convergência, bloqueio, área de referência, fator de segurança, malha), revisa um projeto (sem material, resultados obsoletos/sem vínculo/não validados/não executados), compara resultados e explica termos. Cada alerta cita o campo de origem; sem dado, não inventa.
- **Celular**: aba *Produtos* (mapa dos 5 produtos) e *INTELLIGENCE* (fator de segurança + glossário). Regra do fator de segurança com paridade JS×Python (8/8 casos, incluindo fronteiras).
- **Atrito viscoso estimado** no CFD (`cfd_case.forcas_viscosas`, lei da parede): Cd/Cl totais ESTIMADOS = pressão (exata do campo) + atrito (1ª ordem). Rotulado como estimativa.
- **Cp sobre as peças**: pontos devolvidos à posição e unidade originais (mm), sem esconder as demais peças.
- **Arsenal**: `export_to_file` / `import_file` / `import_component` (ID novo sempre, nunca sobrescreve; valida tudo antes de gravar; backup antes de importar) e botões Exportar/Importar no diálogo.
- **Windows 11 / WSL2 / GPU (lógica; NÃO testada em Windows real)**: `openfoam_shell` e `detect` usam o OpenFOAM do WSL2 quando o NEXUS roda no Windows; `doctor` ganhou o item *GPU / OpenGL* (detecta renderização por software); `tools/verificar_windows.py` (+ `.bat`) roda diagnóstico e provas funcionais na SUA máquina e gera `verificacao_windows.txt`.
- `NEXUS_CFD_SPHERE_STUDY.md` + `tools/estudo_esfera.py`: estudo de malha da esfera (3 refinos).

Esclarecimentos
- O erro de console "Failed to load resource" do celular era do SANDBOX (fontes Google e three.js em CDN bloqueados aqui); não ocorre no app publicado.
- Esfera: só a malha fina convergiu (Cd≈0,51 vs ≈0,47 clássico), mas Cd não é monotônico com o refino e há Cl≠0 → **permanece NÃO VALIDADO** (ver o estudo).

## V3.2 — 2026-11-10 (resultados dentro do NEXUS)
Adicionado
- **Mapa de tensões no visualizador 3D**: `SceneController.set_field` / `Viewport.show_field` pintam von Mises (nodal Tet10, ou média por elemento no Tet4) na superfície da malha, com barra de cores e deformada opcional (só exibição). No diálogo de FEA: botão "Mostrar mapa de tensões…", escolha da origem NEXUS ou CalculiX (.frd) e fator de deformada. Menu "Limpar mapa…" devolve as peças.
- **Diálogo de CFD** (`interface/cfd_dialog.py`, aberto em *Solvers…*): peça da biblioteca ou STL, malha/iterações/referências, execução em **processo isolado** (`modules/cfd_job.py`) com progresso (iterações lidas do `log.simpleFoam`), **Cancelar**, resultado rastreável e botão para **Cp no corpo** no visualizador. Sem OpenFOAM: NAO_EXECUTADO, sem números.
- **Backup do Arsenal** (`core/backup.backup_sqlite`): ao abrir (se o conteúdo mudou) e antes de excluir um componente; rotação de 10; `Arsenal.list_backups` / `restore_backup`.
- `fea_job` grava o campo (`campo_nexus.npz`, `campo_ccx.npz`); `forcas_pressao(detalhe=True)` devolve geometria e Cp por face.

Corrigido
- OpenFOAM: `locationInMesh` fixo (x0+0,5; z1−0,5) caía fora do domínio quando o corpo não tem ~1 m — achado ao rodar o diálogo de verdade; agora é relativo ao domínio.

Limites (honestos)
- A área de referência padrão do CFD é a da caixa envolvente frontal (só normalização). Cd da esfera segue NÃO validado; Cd/Cl totais indisponíveis neste build (só pressão). Nenhum teste em Windows 11/GPU/WSL2.
- Cp é exibido em metros, na posição do caso (não sobreposto às peças em mm).

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
