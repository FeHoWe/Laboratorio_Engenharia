# NEXUS — Guia do usuário (V3.0)

## Antes de tudo
1. Abra *Ferramentas ▸ Solvers…* e leia o **Diagnóstico completo**: ele mostra quais motores existem na sua máquina.
2. Nenhum material, coeficiente ou parâmetro de pneu é atribuído sozinho. Valores iniciais das calculadoras são **exemplos ILUSTRATIVOS**.

## Fluxo CAD → Arsenal → projeto → FEA → versão → comparação
1. Crie/edite uma peça na biblioteca (Ctrl+L) ou no editor paramétrico com histórico (undo/redo). STL é malha triangulada: **não** é editável parametricamente.
2. Salve no Arsenal (Ctrl+Shift+A); cada alteração cria uma nova versão e o histórico é preservado.
3. Defina o material (você escolhe) e insira a peça num projeto.
4. FEA: *Estudo FEA 3D…* (Tet10 + malha Gmsh). Com `ccx` instalado, o mesmo caso pode ser exportado/executado no CalculiX e os deslocamentos são comparados (`calculix_io.compare`).
5. Anexe o resultado ao projeto **com a impressão digital da geometria**. Se alterar a peça, o resultado antigo fica **OBSOLETO** (preservado) e o novo é vigente. `result_store.compare` mostra a diferença entre versões.

## CFD
Níveis 1–2 (analíticos) estão no Laboratório. O nível 3 gera um caso OpenFOAM (`gerar_caso_openfoam`), executa (`executar_openfoam`) e devolve iterações, resíduos, convergência e coeficientes. **Sem estudo de malha e sem referência o resultado nunca é VALIDADO.** Se não convergiu, o resultado diz isso.

## Veículo
- Laboratório ▸ *Dinâmica longitudinal* (RK4) e *Curva em regime (bicicleta + transferência de carga)*: dê massa, CG, bitolas, rigidez de curva e μ do pneu, rolagem e centros de rolagem. Mostra esterçamento, deriva, subesterço, limite de aderência (qual eixo satura), transferência de carga e skidpad.
- Se a curva é fisicamente impossível, o NEXUS avisa e **não** calcula esterçamento.
- A animação dos mecanismos/F1 é movimento prescrito, não simulação.

## Celular
Abra o mesmo link do visualizador; aba **Veículo** tem longitudinal + curva em regime. CalculiX/OpenFOAM/STEP só no desktop.
