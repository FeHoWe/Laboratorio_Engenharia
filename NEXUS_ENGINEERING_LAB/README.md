# NEXUS ENGINEERING LAB — V1.8

Laboratório digital de engenharia para Windows: importa modelos CAD, identifica a estrutura
(montagens, grupos, peças, sólidos), mostra em 3D, faz **desmontagem virtual (explosão)** e
mostra propriedades calculadas da geometria real.

## Como rodar (Windows)
1. Instale Python 3.10+ (marque "Add to PATH").
2. Dê dois cliques em `run_nexus.bat` (cria o ambiente e instala as dependências na primeira vez)
   ou, manualmente:
   ```
   py -3 -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   python main\main.py [arquivo]
   ```
3. Testes: `python -m pytest tests -q`
   (no Linux sem tela: `QT_QPA_PLATFORM=offscreen python -m pytest tests -q`).

## O que funciona na V1.0
- Importar STEP/STP (hierarquia, nomes, posições), STL, OBJ (corpos separados) e FCStd (leitura direta do arquivo).
- Viewer 3D: girar, zoom, mover, clicar para selecionar (Shift soma), destacar, ocultar/mostrar/isolar,
  ajustar vista, vistas padrão, perspectiva/ortográfica.
- Árvore/lista/grupos sincronizadas com a seleção 3D.
- Explosão: montagem inteira, só um grupo, peça isolada; modos radial/eixo X,Y,Z/direção livre; distância;
  animação; restauração exata; peças separadas marcadas na árvore.
- Separação de sólidos compostos (somente quando você pedir; reversível).
- Component Inspector: dimensões, volume, área, centro de gravidade, massa (só com material), posição, rotação.
- Projetos `.nexus` (salvar, abrir, histórico), exportação STEP/FCStd/STL/OBJ.

## Novidades
- **V1.1** — Medição: menor distância exata entre duas peças (B-Rep; aproximada para malhas) com linha no 3D.
- **V1.2** — Medição de **diâmetros** (cilindros exatos) e de **ângulo** entre eixos; **corte de seção** em X/Y/Z
  (somente exibição, interior em âmbar); visual de **bancada holográfica** (ciano translúcido, grade e anéis no chão,
  HUD com leituras). A chave "Holograma" na barra de corte volta ao estilo sólido.

- **V1.3** — Modelo de exemplo realista: **motor 4 cilindros em linha DOHC 16V** (56 peças, 13 grupos): bloco com
  cilindros furados, cabeçote, tampa, cárter, virabrequim com contrapesos, bielas, pistões com canaletas, pinos,
  16 válvulas, comandos, velas, parafusos, coletores, volante, polia, filtro e alternador. Menu File ▸ Abrir exemplo.
  Gerado por `python -m samples.motor_4_cilindros` com sólidos reais; testes confirmam 1 sólido por peça e
  **nenhuma interferência** entre peças. Não é um motor de fabricante: dimensões plausíveis (a V1.7 acrescentou molas, correia e dutos; veja abaixo).

## O que NÃO existe ainda (e aparece desabilitado nos menus)
Simulação física (V2.x–V3.x: dinâmica, forças, contato), edição paramétrica, Engineering Assistant/IA (V4.0), animação de modelos que não sejam o exemplo, leitura de mates de CADs que não sejam o Assembly do FreeCAD.
Veja `docs/ARQUITETURA.md`.

## Versão de celular (teste sem o computador)
A cada evolução do NEXUS, regenere o visualizador somente leitura e publique-o:
`python mobile/build_mobile_viewer.py modelo.step` → `exports/<modelo>_mobile.html`.

## Novidades da V1.8 — animação do mecanismo e juntas gravadas do FreeCAD

- **Animar mecanismo** (*Analyze › Animar mecanismo…*, Ctrl+M) — só no motor de exemplo: controle de ângulo do virabrequim
  (0–720°, um ciclo de 4 tempos), reprodução com velocidade e repetição, leituras (curso dos pistões, válvulas abertas).
  Gira virabrequim/volante/polia/roda dentada; bielas e pistões seguem a biela-manivela exata (comprimento da biela constante,
  pistão preso ao eixo do cilindro); o comando de admissão gira a θ/2 (correia) e o de escape a −θ/2 (engrenagens); as 16 válvulas abrem quando o nariz do
  lóbulo (modelado defasado na ordem de ignição 1-3-4-2) as empurra, e as molas são comprimidas.
  É **movimento prescrito, só de exibição**: a geometria não muda; sem dinâmica, forças, contato, folgas ou atrito.
  Cenas salvas guardam a pose (e entram no PDF); explosão e animação funcionam juntas.
- **Superação dos limites iniciais (ainda V1.8):**
  - *Válvulas:* o deslocamento agora é **calculado da geometria dos lóbulos modelados** (união de dois círculos) com seguidor de
    pastilha plana na haste (folga de 0,1 mm): ~5,8 mm de abertura e ~198° de manivela por evento. Testes: tabela conferida por
    força bruta, e com a pose aplicada a pastilha **toca** o lóbulo (distância < 0,35 mm) sem invadi-lo. Como sempre há uma
    válvula aberta, o modelo estático já nasce na pose de θ=0 (válvulas empurradas e molas encurtadas conforme o lóbulo).
  - *Correia:* roda do virabrequim com 20 dentes e do comando de admissão com 40 (**2:1 exato**); 96 dentes de correia são peças que
    percorrem o trajeto (o passo foi resolvido para a correia fechar com número inteiro de passos) e as rodas têm ranhuras na
    fase certa: teste confere o encaixe de todos os dentes em 7 ângulos. O comando de escape é movido por **par de
    engrenagens 1:1** e gira ao contrário (-θ/2), como em motores DOHC reais. Para isso a frente do motor foi remodelada
    (polia e alternador recuados, ponta do virabrequim mais longa).
  - O modelo passou a **173 peças**; interferência verificada em 10 ângulos com tudo em movimento (dentes, rodas, engrenagens inclusos).
- **O que ainda é simplificação:** o perfil do lóbulo é de dois círculos (não o de um motor real, e a aceleração da válvula tem
  saltos); a mola é só **comprimida por escala** na animação (e o modelo estático tem 1 variante de mola por deslocamento);
  as engrenagens e a correia **não têm perfil de dente modelado** (dentes da correia são caixas; engrenagens são discos no círculo
  primitivo); sem tensor; sem dinâmica da correia; o seguidor é suposto sempre em contato (sem flutuação de válvula). Outros
  modelos **não** ganham animação: o NEXUS não deduz movimento da geometria.
- O relatório PDF agrupa **peças iguais** (mesmo nome-base, material e volume) numa ficha só, com "×N", e anota o ângulo da animação nas cenas.
- **Descoberta ao animar:** o motor da V1.7 era uma montagem estática; ao girar o virabrequim, manivela e bielas invadiam o bloco e o
  cárter, o nariz dos comandos tocava a tampa e o filtro ficava na trajetória. O modelo foi corrigido (saia do bloco e cárter
  alargados para varredura de 80 mm, tampa mais larga por dentro, filtro de óleo remontado na saia). Teste de interferência
  com o mecanismo em 10 ângulos: nenhuma interferência entre as peças rígidas (molas ficam de fora porque são escaladas).
- **Juntas gravadas em FCStd** (*Analyze › Relações de montagem…*): ao importar um .FCStd com Assembly do FreeCAD, os objetos-junta
  (tipo, referências, sub-elementos) são lidos e listados como "Gravada (FreeCAD)", junto das juntas inferidas, e vão para o CSV/PDF.
  **Leitor escrito a partir do formato documentado e testado com `Document.xml` sintéticos — não validado com arquivos reais do
  FreeCAD.** Se o arquivo não trouxer a lista de nomes do enum, usa-se a ordem do FreeCAD 1.0 (sinalizado). Juntas lidas **não**
  viram restrições nem movimento. Referência a objeto que não está no modelo é sinalizada.
- Celular: o visualizador ganhou o controle "Ciclo" e o botão Girar (mesma matemática, validada contra o Python nos testes).

## Novidades da V1.7 — FCStd, juntas inferidas e motor mais completo

- **Gravação de FCStd** (*File › Exportar modelo…*, escolha FreeCAD): ZIP com `Document.xml` + um `.brp` por peça, grupos como
  `App::DocumentObjectGroup`, visibilidade em `GuiDocument.xml`, nomes com acento preservados. **Relido pelo importador do NEXUS
  nos testes (ida e volta: peças, volumes, grupos, visibilidade), mas NÃO validado abrindo no FreeCAD de verdade.** Não leva
  histórico paramétrico, materiais nem cenas.
- **Relações de montagem (juntas) inferidas** (*Analyze › Relações de montagem…*, Ctrl+J): deduz da geometria exata
  (a) eixo/furo concêntricos (folga radial até 1 mm, ajuste justo quando coincidem) e (b) faces planas coplanares em contato.
  Mostra o resumo, as peças sem junta e os conjuntos ligados; duplo clique seleciona as duas peças; exporta CSV; entra no PDF.
  **Tudo rotulado "inferido"**: coincidência geométrica não prova intenção de projeto. Juntas gravadas por CADs
  (mates, Assembly do FreeCAD) **não são lidas**; não há restrições cinemáticas nem simulação de movimento.
- **Motor de exemplo com 76 peças** (era 56; continua 1 sólido por peça e **0 interferências**): 16 molas helicoidais de válvula
  (fio varrido em hélice, volume conferido com a fórmula), 3 rodas dentadas, correia dentada fechada, dutos de admissão/escape
  no cabeçote e 2 galerias de óleo cegas no bloco. Para dar espaço às molas, as hastes das válvulas ficaram mais longas, o
  comando subiu e a tampa de válvulas ficou mais alta. **Simplificações:** proporções da correia ilustrativas (rodas dos comandos
  não têm o dobro do diâmetro da do virabrequim), sem dentes modelados, sem tensor, molas de passo constante.
- `PlaneFace` agora traz a normal para fora do sólido e a caixa da face (corrige faces invertidas na leitura de planos).

## Novidades da V1.6 — cenas salvas e relatório PDF

- **Cenas salvas** (menu *Scenes*; Ctrl+K salva a atual, Ctrl+Shift+K gerencia): guardam com um nome a câmera, a explosão,
  a visibilidade, o corte de seção, o estilo (holograma/sólido) e a seleção. Aplicar uma cena leva a montagem até lá
  (com animação, se "Animar" estiver ligado). As cenas ficam dentro do `.nexus`. Ids que não existem mais
  (peça dividida/apagada) são ignorados e o console avisa quantos. Cenas **não alteram a geometria**.
- **Relatório PDF** (*File › Relatório PDF do projeto…*, Ctrl+Shift+R): capa com vista geral e resumo de massa,
  BOM, massa por material e por grupo, pendências, uma página para cada cena salva (imagem reproduzida da cena) e,
  opcionalmente, **uma ficha por componente** (peça isolada + destacada no conjunto + dimensões, volume, área, material,
  massa, diâmetros). As imagens são renderizadas offscreen e não mexem no estado do projeto.
  Exemplo do motor com 56 fichas: 32 páginas, ~5 MB, ~20 s. Fonte DejaVu embutida (`assets/fonts`, licença incluída).
- Mesmas regras de honestidade: massa só com material escolhido; total "PARCIAL" enquanto houver pendências.
- API: `modules/scene_manager.py`, `modules/snapshot.py`, `modules/report.py`.

## Novidades da V1.5 — lista de materiais (BOM) e massa

- **Analyze › Lista de materiais (BOM) e massa… (Ctrl+B)**: tabela por componente com quantidade (peças iguais agrupadas),
  material, densidade, volume, massa unitária/total e % da massa; totais por material e por grupo; **centro de massa** da montagem.
- **Exportação CSV** (`;`, UTF-8) e **XLSX** com fórmulas vivas (`SOMA`, `qtd × massa`) e abas *Por material*, *Por grupo* e *Pendências*.
- **Honestidade:** peça sem material ou sem volume **não entra no total**; o total aparece como **PARCIAL** e as pendências são listadas.
- **Components › Aplicar materiais típicos ao exemplo do motor**: sugestão didática (bloco em ferro fundido, pistão em alumínio…),
  só quando você pede; vela e junta ficam sem material de propósito. No exemplo: ~81,9 kg parciais (51 de 56 peças).
- Celular: `python mobile/build_mobile_viewer.py modelo.step saida.html --typical` embute material/massa por peça e a massa total no HUD.
- Dependência nova: `openpyxl`.

## Novidades da V1.4 — banco SQL de densidades

- `data/materials.db` (SQLite) e `data/materials.sql` (dump): **882 materiais em 25 categorias**, metais e ligas
  (aços AISI/ASTM, inox, alumínio, titânio, níquel, cobre, ferros fundidos), polímeros, borrachas, cerâmicas técnicas,
  compósitos, madeiras, pedras/minerais, construção civil, líquidos, combustíveis e fluidos automotivos
  (freio DOT 3/4/5/5.1, ATF, óleos, graxas).
- Cada linha guarda o valor **como publicado** (`orig_text`, na unidade original), a conversão para g/cm³
  (mín./máx./típico = ponto médio) e a **fonte com URL** (11 fontes na tabela `sources`).
- Regenerar: `python data/build_materials_db.py` (dados brutos em `data/raw_sources.py`).
- No NEXUS: *Definir material…* e a opção "Buscar no banco de materiais…" abrem um seletor com busca e categorias,
  mostrando faixa e fonte. Os 11 materiais nativos continuam; o projeto `.nexus` guarda a densidade dos materiais
  do banco usados, então abre igual mesmo sem o banco.
- Consulta exemplo: `SELECT display_name, density_typ FROM v_materials WHERE category='Madeiras' ORDER BY 2;`

**Limites honestos:** densidades de ligas variam por têmpera/processo; o banco traz valores nominais de tabelas
publicadas (faixas usam o ponto médio) — para peso exato use *Material personalizado*. Alguns nomes estão em inglês
(só ~120 têm tradução). Há pequenas divergências entre fontes (marcadas na coluna `note`). Gases não foram incluídos.

## V1.9 — Realismo do motor de exemplo

- **Comando de válvulas**: lóbulo com perfil suave (lei de levantamento polinomial H·(1−u²)³, aceleração contínua), ~7,7 mm de levantamento, ~217° de manivela de abertura, folga de 0,1 mm; **seguidor de rolete** (contato calculado entre a curva de passo e o lóbulo).
- **Engrenagens dos comandos**: dentes de **evolvente** reais (módulo 2, 26 dentes, 20°, folga 0,1 mm), engrenadas sem interferência (verificado em 20 ângulos).
- **Correia e rodas dentadas**: dentes trapezoidais tipo HTD (96 dentes) com flanges; correia animada 2:1.
- Validação: 151 testes, varredura de interferência estática e em movimento, visualizador móvel × Python (diferença máx. ~2e-4 mm).
- **Limites honestos**: perfil do lóbulo é uma lei didática, não de fabricante; seguidor sempre em contato (sem flutuação/dinâmica); mola comprimida por escala (ilustração); dentes sem raio de pé; sem tensionador; animação só no motor de exemplo; leitura de juntas FCStd ainda não validada com arquivos reais do FreeCAD.
- **Diagrama de válvulas** (janela de animação e celular): levantamento, velocidade e aceleração × ângulo, com seletor de rpm (v ∝ rpm, a ∝ rpm²). É cinemática do movimento prescrito; não inclui mola, massa nem flutuação.
- **Lóbulo com "pé" de ataque**: rampa de folga que elimina o pico de aceleração ao sair da folga de 0,1 mm (aceleração entre ≈ −129 e +135 m/s² a 1000 rpm).

## V2.0 — Aba "Simulação de fadiga"

Nova aba ao lado da "Bancada 3D" (menu Ferramentas › *Simulação de fadiga*, Ctrl+Shift+F), para qualquer projeto que você construir:

- **Peça (S-N / vida)**: material (Su, Sy, Se' digitados), fatores de Marin (acabamento, tamanho, carga, temperatura, confiabilidade), seção (círculo, tubo, retângulo, personalizada), cargas por ciclo (axial, flexão, torção), Kt/q → Kf, tensão equivalente de von Mises, coeficientes de segurança (Goodman, Gerber, Soderberg, ASME-elíptico, Langer), curva S-N (Basquin) com ponto de operação, vida em ciclos e horas.
- **Espectro de cargas (Miner)**: dano acumulado linear por blocos e vida em repetições.
- **Mola helicoidal**: taxa, forças, cisalhamento (Bergsträsser), coeficiente de segurança em cisalhamento, altura sólida, surto (regra 13×) e botão que preenche a geometria da mola do motor de exemplo.
- Exporta relatório .txt. Testes: `tests/test_fatigue.py`.
- **Honestidade**: análise analítica de tensão nominal — NÃO é elementos finitos e não lê a geometria do CAD. O banco SQL só tem densidades; as resistências são sempre digitadas por você (a única estimativa opcional, Se' = 0,5·Su para aço, aparece marcada). Marin/S-N seguem o Shigley (aço). Miner linear, sem efeito de sequência; sem baixo ciclo, entalhe local, tensões residuais, corrosão nem propagação de trincas.
- Motor de exemplo: dentes das engrenagens agora com concordância de 0,3 mm no pé.
- Ainda não feito: tensionador/folga dinâmica da correia; dinâmica de válvula (flutuação).

### V2.1 — Tensionador e dinâmica de válvula

- **Roda tensora dentada** (18 dentes, apoio fixo, lado +y) com eixo e suporte aparafusado na face frontal: a correia agora percorre 3 rodas e tem 100 dentes (passo recalculado para fechar o trajeto). Roda na velocidade tangencial da correia; sem colisões em 10 ângulos. É geometria e movimento: SEM mola, excêntrico, amortecedor nem cálculo de tensão da correia.
- **Dinâmica de válvula (corpo rígido, 1 g.d.l.)** na aba de mola: força de contato came–seguidor `m·y'' + c·y' + k·y + F0` e rotação de flutuação (força mínima = 0). Massa equivalente, pré-carga e amortecimento são digitados por você; k vem da mola calculada. Sem elasticidade do trem, surto da mola, pressão de gás nem folga dinâmica. `modules/valvetrain.py`.

## V2.2 — Projetos predefinidos, biblioteca de peças e Laboratório de testes

**Arquivo ▸ Projetos predefinidos** gera (B-rep real, OpenCascade) e importa:

| Projeto | Conteúdo | Observação honesta |
|---|---|---|
| Motor 4 cilindros | DOHC, correia, válvulas animadas | didático |
| Carro de F1 2026 | monocoque, asas com elementos ativos, V6 híbrido (PU), Halo, suspensão push/pull, rodas, freios (118 peças) | referência pelo regulamento, **não** é CAD de equipe; larguras de pneu, asas e internos não verificados; flaps com aberturas ilustrativas; sem compósitos no banco → carbono fica sem material |
| Redutor 2 estágios (6:1) | carcaça, 3 eixos, 4 engrenagens evolventes engrazadas, rolamentos, parafusos | 0 interferências (varredura booleana) |
| Suspensão duplo A | pneu 225/45 R17, roda, cubo, disco, pinça, manga, braços, mola/amortecedor, travessa | 0 interferências; sem buchas/curso |
| Ponte treliçada | 6 painéis, banzos, diagonais, tabuleiro (266 peças) | 0 interferências; não dimensionada por norma |

*Materiais típicos* (menu Material) só são aplicados a pedido e só às peças que o banco cobre.

**Ferramentas ▸ Biblioteca de peças** (Ctrl+L): 19 peças paramétricas (parafusos ISO, porcas, arruelas, rolamentos, engrenagens, polias, eixos, discos de freio,
flanges, chapas, tubos, vigas I/U, cantoneiras, mola helicoidal) — adicionadas à montagem atual numa posição X/Y/Z, ou criadas como projeto novo. Rosca não é modelada.

**Ferramentas ▸ Laboratório de testes** (aba, Ctrl+Shift+L) — **cálculo analítico, NÃO é CFD nem elementos finitos**:
- Atmosfera ISA; veículo (arrasto, downforce, velocidade máxima, velocidade em curva, frenagem); asa finita por linha sustentadora de Prandtl/Glauert
  (validada: asa elíptica dá e = 1,00 e a inclinação CL-α de Prandtl; α_L0 do NACA 2412 = −2,07°) com efeito solo aproximado;
- viga (5 casos), flambagem (Euler/Johnson), junta parafusada pré-tensionada, torção, vaso de pressão de parede fina, frequências naturais.
- Todos os coeficientes (CdA, ClA, μ, Crr, K de torque, E, Sy…) são digitados por você; cada resultado lista as hipóteses. Os valores iniciais são exemplos genéricos.

Testes: `tests/test_v22.py` (196 testes no total passam). Visualizador móvel atualizado (motor).
