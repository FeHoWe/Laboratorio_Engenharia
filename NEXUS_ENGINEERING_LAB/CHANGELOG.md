# CHANGELOG

## V3.6 — 2026-11-12 (lista de melhorias)
- **CFD**: `camadas` prismáticas (addLayers) em `gerar_caso_openfoam`/`run_case`/diálogo; critério de resíduo `classificar_residuos` (CONVERGIDO / DECAINDO / ESTAGNADO / DIVERGINDO / INSUFICIENTE) no log do simpleFoam. Placa plana (Re_L 1,33e6): atrito estimado foi de 29 % do alvo (sem camadas) para 55 % (5 camadas) e 49 % (9 camadas); convergiu nos resíduos. **Continua NÃO VALIDADO** — causa provável do que resta (borda de ataque romba de 10 mm, camadas incompletas: 1ª célula de 0,6 a 9 mm) NÃO confirmada. Ver `NEXUS_CFD_PLATE_STUDY.md` (rev. 2).
- **STRUCTURAL**: diálogo *Plasticidade, multimaterial e contato* (`casos_nl`, `nl_dialog`) com a solução analítica ao lado (CalculiX real); `fatigue_fea.avaliar` leva a tensão de von Mises do FEA para Goodman/Gerber/SWT e vida (recusa resultado NAO_EXECUTADO; avisa singularidade de malha).
- **VEHICLE**: `vehicle_combined` — limite lateral sob tração/frenagem (círculo de atrito exato em saturação; reduz ao modelo lateral em Fx=0), diagrama g-g, rigidez de rolagem por molas+barra, geometria estática 3D do pino-mestre (caster, KPI, trail, scrub; verificada analiticamente); `tire_fit` ajusta C_α e μ a CSV MEDIDO (avisa quando μ não é identificável); `integracao` leva Cd do CFD ao modelo longitudinal com proveniência e alertas. Diálogo com abas g-g e ajuste CSV; celular com diagrama g-g (paridade JS×Python).
- **CAD**: sketch com arcos exatos (`rrect`, `slot`) e restrições em sequência (horizontal, vertical, comprimento, raio igual, concêntrico, ponto fixo) com reverificação — NÃO é um solver geral; conflitos são reportados.
- **PRODUTO**: relatório PDF de resultados e **laudo simplificado** (`report_resultados`, botões no INTELLIGENCE; aviso "estimativa de engenharia, não homologação"); banco de casos de referência com selos por módulo (`modules.referencias`; CFD sempre NAO_EXECUTADO ali); `nexus.spec`, `tools/empacotar_windows.bat` e `tools/nexus_instalador.iss` — **empacotamento NÃO testado** (sem Windows).
- Windows 11/WSL2/GPU: continua sem teste em máquina real (computador não conectado a esta sessão).

## V3.5 — 2026-11-12 (CAD, estrutural, CFD, veículo)
- **CAD**: `modules/sketch2d.py` (retângulo, círculo, polígono; aninhamento vira furo; planos XY/XZ/YZ com deslocamento; recusa auto-interseção e área zero) + `SketchDialog`; operações `sketch_extrude` e `boolean` (união/corte/interseção com caixa, cilindro, esfera ou STEP) no histórico paramétrico. Volumes verificados exatamente. Limites: sem restrições geométricas nem arcos livres.
- **STRUCTURAL**: `modules/calculix_nl.py` — plasticidade bilinear, multimaterial por região e contato nó-superfície/penalidade, executados no `ccx` real e comparados com soluções analíticas de barra (força plástica ±2 %, série aço/alumínio ±3 %, contato fechado ±3 % com K=1e7). Exige travar o corpo rígido de blocos que só se tocam; resultado que não chega ao tempo final é descartado (NAO_EXECUTADO). Sem diálogo na interface ainda.
- **CFD**: estudo da placa plana (`NEXUS_CFD_PLATE_STUDY.md`): o atrito estimado dá 29 % (malha média) e 40 % (fina, não convergida) do alvo de Schlichting → **estimador NÃO validado**, mantido como ESTIMADO. Camada prismática e critério de resíduo seguem pendentes.
- **VEHICLE**: pneu combinado Fx–Fy (`tire_combined`, círculo de atrito respeitado, reduz exatamente ao modelo lateral em κ=0) e suspensão duplo-A 2D (`suspension`: camber, Δbitola, centro de rolagem; |ganho de camber|≈1/FVSA verificado). Diálogo no menu Analyze e aba no celular, com paridade JS×Python (6e-11).
- Produtos/hub atualizados; APP_VERSION e celular 3.5.

## V3.4 — 2026-11-11 (melhorias nas pendências)
- **Esfera**: domínio de **ar livre simétrico** (`ar_livre`) → Cl de −0,18 para ≈0; **área frontal projetada real** como referência padrão (antes: caixa); 3 refinos de razão 1,5 → sequência **monotônica** (0,503 → 0,481 → 0,470), **GCI 2,8 %**, Cd extrapolado ≈0,459 (`modules/cfd_gci.py`, que se recusa a calcular em sequência oscilatória). Continua NÃO VALIDADO (sem convergência de resíduos em 1500 it., atrito estimado, `forceCoeffs` indisponível). Ver `NEXUS_CFD_SPHERE_STUDY.md` rev. 2.
- **NEXUS INTELLIGENCE generativo OPCIONAL** (`modules/intelligence_llm.py`): exige `ANTHROPIC_API_KEY` e confirmação de envio; recebe só os fatos do parecer; **a resposta é verificada** — número que não esteja nos resultados/pergunta é marcado como sem fundamento. Sem chave, o assistente por regras continua.
- Diálogo de CFD: opção *Ar livre*; área de referência 0 = projetada. Guia passo a passo de **Windows 11 + WSL2 + OpenFOAM** em `NEXUS_INSTALLATION.md`.
- Não mudou: nada foi testado em Windows real (computador não conectado).

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
