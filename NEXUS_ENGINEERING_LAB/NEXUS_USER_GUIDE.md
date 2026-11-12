# NEXUS — Guia do usuário (V3.0)

## Antes de tudo
1. Abra *Ferramentas ▸ Solvers…* e leia o **Diagnóstico completo**: ele mostra quais motores existem na sua máquina.
2. Nenhum material, coeficiente ou parâmetro de pneu é atribuído sozinho. Valores iniciais das calculadoras são **exemplos ILUSTRATIVOS**.

## Fluxo CAD → Arsenal → projeto → FEA → versão → comparação
1. Crie/edite uma peça na biblioteca (Ctrl+L) ou no editor paramétrico com histórico (undo/redo). STL é malha triangulada: **não** é editável parametricamente.
2. Salve no Arsenal (Ctrl+Shift+A); cada alteração cria uma nova versão e o histórico é preservado.
3. Defina o material (você escolhe) e insira a peça num projeto.
4. FEA: *Estudo FEA 3D…* (Tet10 + malha Gmsh). Com `ccx` instalado, o mesmo caso pode ser exportado/executado no CalculiX e os deslocamentos são comparados (`calculix_io.compare`).
   - **Executar em PROCESSO ISOLADO**: roda o estudo fora do NEXUS, com barra de progresso e **Cancelar**; marque "Repetir no CalculiX e comparar" para cruzar com o `ccx` (se instalado). O campo completo do CalculiX (`.frd`) é lido e salvo em VTK para o ParaView.
   - Log central: `~/.nexus_engineering_lab/logs/nexus.log`. Ao salvar um projeto, a versão anterior vai para a pasta `backups/` ao lado dele.
5. Anexe o resultado ao projeto **com a impressão digital da geometria**. Se alterar a peça, o resultado antigo fica **OBSOLETO** (preservado) e o novo é vigente. `result_store.compare` mostra a diferença entre versões.

## Produtos e NEXUS INTELLIGENCE (V3.3)
- *Analyze → NEXUS — Produtos…* (Ctrl+Shift+H): mapa dos cinco produtos; selecione uma capacidade e *Abrir*. ✅ pronto · 🟡 parcial · ⬜ planejado (não existe).
- *Analyze → NEXUS INTELLIGENCE…* (Ctrl+Shift+I): escolha um projeto → *Revisar projeto*, *Interpretar último resultado*, *Comparar os dois últimos* ou *Explicar termo*. É um assistente por REGRAS: cada alerta mostra a fonte; não inventa números e não substitui julgamento de engenharia.
- Arsenal: *Exportar…* grava o componente (todas as versões) em JSON; *Importar…* o recria com ID novo (nunca sobrescreve).
- Windows 11: rode `tools\verificar_windows.bat` e envie o `verificacao_windows.txt` gerado.

## Novidades da V3.6
- **Menu Analyze → NEXUS STRUCTURAL — Plasticidade, multimaterial e contato…**: três casos prontos com CalculiX real e a solução analítica ao lado. Digite SEUS materiais.
- **NEXUS VEHICLE** ganhou abas *Aderência g-g* e *Ajuste de pneu (CSV)* (colunas `alpha_graus,fz_N,fy_N` MEDIDAS; se não houver pontos perto da saturação o μ NÃO é identificável e a tela avisa).
- **INTELLIGENCE**: *Relatório PDF de resultados*, *Laudo simplificado PDF* (estimativa de engenharia, não homologação) e *Selos de referência* (coerência com a teoria; NÃO é validação).
- **CFD**: campo *Camadas prismáticas*. O log agora classifica o resíduo (CONVERGIDO/DECAINDO/ESTAGNADO/DIVERGINDO). O atrito continua ESTIMADO.
- **Por API Python**: `fatigue_fea.avaliar`, `vehicle_combined.pino_mestre_3d`/`rigidez_rolagem`, `integracao.veiculo_com_cfd`, sketch com `rrect`/`slot`/`restringir`.
- **Empacotamento Windows**: `tools\empacotar_windows.bat` (NÃO testado). Envie o resultado se tentar.

## Novidades da V3.5
- **Sketch e booleanas (CAD)**: em *Solvers… → Histórico paramétrico*, adicione `sketch_extrude` (abre o editor de sketch: retângulo, círculo, polígono; um perfil dentro de outro vira furo; planos XY/XZ/YZ com deslocamento) ou `boolean` (união, corte, interseção com caixa, cilindro, esfera ou arquivo STEP). Perfis que se cruzam ou têm área zero são recusados com mensagem.
- **Pneu combinado e suspensão (VEHICLE)**: menu Analyze → *NEXUS VEHICLE — Pneu combinado e suspensão…* (e aba *Veículo* no celular). Valores iniciais são ILUSTRATIVOS; digite os do seu carro. O pneu respeita o círculo de atrito μ·Fz. A suspensão é duplo-A em vista frontal 2D (camber, Δbitola, centro de rolagem), sem elastocinemática.
- **Plasticidade, multimaterial e contato (STRUCTURAL)**: por enquanto pela API Python (`modules/calculix_nl.py`; veja `tests/test_calculix_nl.py` como exemplo): `curva_bilinear`, `write_inp_nl(... materiais, regioes, contato ...)`, `run_nl`. Os materiais são SEMPRE informados por você. Contato por penalidade: aumente K até o resultado parar de mudar e trave o movimento de corpo rígido de blocos que só se tocam.

## Resultados no visualizador 3D (V3.2)
- FEA: rode o estudo (síncrono ou isolado) e clique em *Mostrar mapa de tensões (von Mises)…*; o diálogo fecha e o mapa aparece no 3D com barra de cores. *Limpar mapa…* (menu) restaura as peças. Tet10: valor nodal suavizado; Tet4: média por elemento.
- CFD: *Solvers… → CFD — OpenFOAM*; escolha peça ou STL, ajuste malha/iterações e execute. Acompanhe o progresso, cancele se quiser; depois *Mostrar Cp no corpo*. Resultado NÃO é validado sem Cd de referência com fonte.

## CFD
Níveis 1–2 (analíticos) estão no Laboratório. O nível 3 gera um caso OpenFOAM (`gerar_caso_openfoam`), executa (`executar_openfoam`) e devolve iterações, resíduos, convergência e coeficientes. **Sem estudo de malha e sem referência o resultado nunca é VALIDADO.** Se não convergiu, o resultado diz isso.

## Veículo
- Laboratório ▸ *Dinâmica longitudinal* (RK4) e *Curva em regime (bicicleta + transferência de carga)*: dê massa, CG, bitolas, rigidez de curva e μ do pneu, rolagem e centros de rolagem. Mostra esterçamento, deriva, subesterço, limite de aderência (qual eixo satura), transferência de carga e skidpad.
- Se a curva é fisicamente impossível, o NEXUS avisa e **não** calcula esterçamento.
- A animação dos mecanismos/F1 é movimento prescrito, não simulação.

## Celular
Abra o mesmo link do visualizador; aba **Veículo** tem longitudinal + curva em regime. CalculiX/OpenFOAM/STEP só no desktop.
