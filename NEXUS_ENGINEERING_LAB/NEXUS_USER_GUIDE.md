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

## Novidades da V5.0
- **NEXUS HOME** (primeira aba): vê o estado do projeto e abre cada ambiente. **Verificar consistência do projeto** mostra o que falta (materiais, massa parcial, interferência não verificada, alterações não salvas) — sem inventar números.
- **Ferramentas F1 → Comparar A/B:** edite a configuração B, compare com a aba Volta e veja em que ponto da pista B ganha ou perde tempo; a *varredura de parâmetro* mostra o tempo de volta para vários valores de um parâmetro (ex.: `p_ice`: 400, 500, 600 kW).
- **Editor paramétrico:** *Varrer* (perfil ao longo de um caminho x,y,z; …) e a operação *filete variável* (raio muda de uma ponta à outra da aresta). O loft entre perfis é feito pela API.

## Novidades da V4.1b — nomes, revolução e restrições
No editor paramétrico: **Nomear face/aresta…** dá um nome a uma face ou aresta (a face de cima, uma aresta perto de um ponto…). O nome *acompanha* a peça pelas operações seguintes — mover, escalar, furar, editar um parâmetro antigo — e pode ser usado em filetes, chanfros e na casca (`nome:borda`). Se uma operação destrói aquela face ou aresta, o NEXUS avisa “referência perdida” em vez de escolher outra. **Revolucionar** (no diálogo de esboço) gira o perfil em torno de um eixo. **Variável…** e **Restrição…** permitem escrever parâmetros como `=D*2` ou `=op[0].diameter`, e regras como `volume > 1000`; uma edição que quebre uma regra é desfeita. As regras só *verificam* — o NEXUS não reajusta sozinho.

## Novidades da V4.1 — CAD avançado
No *Editor paramétrico com histórico* (Solvers → Editor paramétrico) há novas operações: **furo escareado**, **padrão linear** e **padrão circular** (repete furos/saliências), **espelhar** e **casca** (esvazia o sólido deixando uma face aberta). Filete e chanfro aceitam arestas do **topo** ou da **base** de um eixo. Tudo entra no histórico: dá para editar parâmetros, suprimir e desfazer. Se uma operação não cabe na geometria (ex.: casca mais grossa que a peça), o NEXUS recusa e mantém o histórico como estava. A *volta do veículo* agora roda em segundo plano, com cancelamento.

## Novidades da V4.0 — proteção do seu trabalho
- **Recuperação automática**: se o NEXUS fechar de forma inesperada com alterações não salvas, ao abrir de novo ele pergunta se você quer recuperar o projeto. O instantâneo é gravado a cada 60 s só quando há alterações e nunca substitui o seu arquivo.
- **Backup ao salvar**: o arquivo anterior fica em `backups/` (últimos 10).
- **Versões**: *Arquivo → Registrar versão…* guarda uma cópia nomeada em `versions/`. *Arquivo → Versões do projeto…* lista, compara com o arquivo atual (peças adicionadas, removidas, renomeadas, material, geometria, posição) e restaura uma versão (o estado atual vai antes para `backups/`).
- **Casos não lineares (plástico, série, contato)** rodam em segundo plano: a janela não trava e há botão **Cancelar**. São verificações em malha grosseira, **não** validação de peça real.

## Novidades da V3.9
- **Relatórios PDF no seu idioma**: o PDF do projeto e o laudo de resultados saem em inglês, espanhol, alemão, francês ou chinês, conforme *Tools → Idioma / Language*. Classes de resultado, números e unidades não mudam. Chinês/japonês/coreano precisam de fonte CJK no leitor de PDF (não vai embutida). O parecer automático e as premissas dos módulos continuam em português.
- **Celular**: calculadoras e telas principais traduzidas (en, es, de, fr, zh); nomes de peças, circuitos e modelos continuam em português.
- **Italiano, japonês, coreano, russo, turco, polonês, holandês, hindi, árabe e indonésio** agora traduzem também os diálogos (não só os menus). Traduções feitas por IA e não revisadas por nativos: revise antes de usar em documento crítico.

## Novidades da V3.8
- **VEHICLE → aba Suspensão 3D**: digite os hardpoints (x à frente, y para fora, z acima) dos dois braços, barra de direção, roda e contato; veja caster, KPI, trail, scrub, camber gain, bump steer, razão de esterçamento e a tabela por heave. Os campos de Fy/Fx e °/kN aplicam elastocinemática LINEAR com os coeficientes que VOCÊ medir (zeros = desligado). Valores iniciais são ILUSTRATIVOS.
- **VEHICLE → Aderência g-g**: campos *sens. do μ à carga* (0 = μ constante, comportamento antigo). Com valor > 0, a transferência de carga passa a reduzir o limite lateral; use o valor de ensaio do seu pneu. No celular: campos *Sensib. do μ* na aba Veículo.
- **STRUCTURAL → Contato (2 peças)**: escolha caixa, cilindro ou arquivo STEP para a peça inferior e a superior (a superior é apoiada sobre a inferior em z), digite E e ν de cada uma, a força e o tamanho de elemento. O resultado traz o equilíbrio das reações (deve dar ~0 %) e a rigidez; aumente K até o resultado parar de mudar.
- **Idiomas**: *Tools → Idioma / Language* (reinicie para aplicar). Traduzidos (inglês, espanhol, alemão, francês, chinês): menus, dicas e os textos fixos dos diálogos; no celular, abas, controles do visualizador e a aba Veículo (seletor no cabeçalho). Resultados calculados, relatórios PDF e o restante do celular seguem em português. Há ainda 10 idiomas só com o núcleo (menus e botões comuns; o resto em inglês): italiano, japonês, coreano, russo, turco, polonês, holandês, hindi, árabe e indonésio. Para contribuir com um idioma, copie `locales/en.json` para `locales/<código>.json` e traduza os valores.
- Correção: o sinal do trail mecânico (`pino_mestre_3d`) estava invertido na V3.6.

## Novidades da V3.7
- **VEHICLE → abas**: *CFD → Veículo* (usa o Cd do último resultado de CFD do projeto + a ÁREA REAL que você digita) e, em *Aderência g-g*, o botão de **volta com modelo de veículo** no circuito de exemplo SINTÉTICO.
- **INTELLIGENCE → Fadiga do último resultado FEA…**: pede R, Su, Sy e Se corrigido (seus); usa o pico de von Mises do resultado. Cuidado com singularidades de malha.
- **Por API**: `sketch.resolver([...])` (solver de restrições), `calculix_nl.contato_automatico(malha, regioes, mestre, escravo, folga, K)`.
- **CFD**: `y_mais_alvo` (ex.: 40) com camadas dimensiona a 1ª camada para a lei da parede. Veja `NEXUS_CFD_PLATE_STUDY.md`.
- Correção: carga do eixo com roda levantando (modelo lateral).

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


## Novidades da V6.0
- **Ajustar variável (CAD):** no histórico, *Ajustar…* — escolha a variável, a métrica (ex.: volume), o alvo e o intervalo; o NEXUS busca o valor por bisseção. Só funciona se a métrica crescer ou decrescer de forma monótona no intervalo; caso contrário avisa.
- **Relatório PDF:** inclui a consistência do projeto.
- **Celular → Engenharia F1 → Comparar A/B:** preencha só os campos de B que mudam; campo vazio = igual a A. Resultado vale para o modelo simplificado, não para o carro real.
