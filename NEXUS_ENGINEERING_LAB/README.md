# NEXUS ENGINEERING LAB — V20.0

Laboratório digital de engenharia para Windows: importa modelos CAD, identifica a estrutura
(montagens, grupos, peças, sólidos), mostra em 3D, faz **desmontagem virtual (explosão)** e
mostra propriedades calculadas da geometria real.

## Idiomas
16 idiomas (pt, en, es, de, fr, zh + it, ja, ko, ru, tr, pl, nl, hi, ar, id) em *Tools → Idioma / Language*. Menus e diálogos: todos; relatórios PDF: pt/en/es/de/fr/zh; celular: pt/en/es/de/fr/zh. Traduções feitas por IA, não revisadas por nativos (ver `CHANGELOG.md`, V3.9).

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

**Ferramentas ▸ Biblioteca de peças** (Ctrl+L): 18 peças paramétricas (parafusos ISO, porcas, arruelas, rolamentos, engrenagens, polias, eixos, discos de freio,
flanges, chapas, tubos, vigas I/U, cantoneiras, mola helicoidal) — adicionadas à montagem atual numa posição X/Y/Z, ou criadas como projeto novo. Rosca não é modelada.

**Ferramentas ▸ Laboratório de testes** (aba, Ctrl+Shift+L) — **cálculo analítico, NÃO é CFD nem elementos finitos**:
- Atmosfera ISA; veículo (arrasto, downforce, velocidade máxima, velocidade em curva, frenagem); asa finita por linha sustentadora de Prandtl/Glauert
  (validada: asa elíptica dá e = 1,00 e a inclinação CL-α de Prandtl; α_L0 do NACA 2412 = −2,07°) com efeito solo aproximado;
- viga (5 casos), flambagem (Euler/Johnson), junta parafusada pré-tensionada, torção, vaso de pressão de parede fina, frequências naturais.
- Todos os coeficientes (CdA, ClA, μ, Crr, K de torque, E, Sy…) são digitados por você; cada resultado lista as hipóteses. Os valores iniciais são exemplos genéricos.

Testes: `tests/test_v22.py` (196 testes no total passam). Visualizador móvel atualizado (motor).

## V2.3 — F1 2026 muito mais detalhado e animação completa

**Geometria (193 peças, antes 118):** monocoque, nariz, sidepods, cobertura do motor, airbox, câmbio e estrutura traseira agora são **cascas ocas**
(o corte de seção do NEXUS mostra o interior); asa dianteira com 4 elementos, sapatas, cascatas e aletas verticais; asa traseira com beam wing e aletas;
aba lateral, cercas e 3 bargeboards por lado, aletas extras no difusor; aro do cockpit, painel, apoio de cabeça, pedais, volante com tela e botões;
V6 a 90° com **virabrequim de 3 moentes, 6 bielas e pistões com pino**, tampas de válvulas, rotores de turbo com pás, disco de embreagem, escapamentos e ponteira;
cada roda com disco furado de 72 furos, pinça em C, cubo, porca central e manga de eixo; suspensão com balancins, amortecedor de 2 peças (corpo + haste), cremalheira de direção e semi-eixos.

**Animação (aba "Animar mecanismo" e visualizador de celular), ciclo de 720° com 4 curvas alternadas:**
- chassi: arfagem (mergulho/agachamento), rolagem e afundamento por downforce — **amplitudes ilustrativas, exageradas ~3×**;
- **suspensão cinemática real**: em cada canto o duplo-A é resolvido numericamente (braços girando nos pivôs, manga rígida, barra de direção e push/pull-rod de comprimento constante,
  balancim e amortecedor telescópico); a roda é mantida no solo, então camber, bitola e convergência variam como na geometria (bump-steer incluído);
- direção: cremalheira ±30 mm esterça as rodas (≈15°), volante gira 110° e o capacete vira; asas ativas passam do modo curva ao modo reta; 4 rodas, virabrequim (biela-manivela exato), turbo e embreagem giram.
- Validação: restrições de comprimento verificadas em testes (manga, barra de direção, rods, amortecedor), ciclo fecha em 720°, e o celular reproduz o Python com erro máximo de ~0,17 mm.
- **Limites honestos:** é movimento prescrito (cenário), sem dinâmica de veículo, rigidez de mola/pneu ou forças; pontos de suspensão plausíveis, não de um carro real;
  as cascas ocas encostam nos componentes internos (varredura de interferência não é zero); sem compósitos no banco de materiais, a massa é parcial.
- Correção do visualizador: o plano de recorte da câmera estava curto demais para modelos longos (o F1 aparecia vazio); agora acompanha o tamanho do modelo.

## V2.4 — Treliça (MEF de barras) e relatórios rastreáveis

- **Laboratório ▸ "Treliça (MEF de barras)"**: solver espacial de barras articuladas pelo método da rigidez direta (`modules/truss_fem.py`). Entrada em texto
  (`NODE`, `BAR`, `LOAD`), saída com deslocamentos, reações, esforço axial e tensão por barra, coeficiente de segurança ao escoamento e triagem de Euler,
  além do **erro de equilíbrio global** (≈1e-15 nos testes). Detecta mecanismos/estruturas hipostáticas e recusa resolvê-los. Exemplo: Warren plana com valores genéricos.
  Validado contra fórmulas fechadas (triângulo simétrico, barra axial, reações e banzo central da Warren).
- **Exportar relatório (.md)** em todos os testes do laboratório: entradas + resultado + hipóteses, para rastreabilidade.
- **Limites honestos**: modelo linear, nós rotulados, cargas só nos nós, sem peso próprio automático, sem flambagem global/ligações/fadiga. Não é um FEA 3D de sólidos.
- **Varredura de interferência do F1 (honesta)**: 264 pares com sobreposição >1 mm³ (casca do monocoque × piloto/tanque/bateria, elementos de asa entre si etc.) — o F1 é um modelo de referência visual/cinemático, não um conjunto livre de colisões.
- **Analisar ▸ Verificação de interferência (estática)** (Ctrl+Shift+I): interseção booleana exata entre pares (filtro por caixa), lista ordenada por volume, seleção do par na cena, filtro "só selecionadas", limiar em mm³ e exportação CSV. Verificação na pose atual (não varre movimento); encaixes propositais aparecem como colisão.

## V2.5 — NEXUS Engineering Arsenal
- `modules/arsenal.py` (SQLite, sem dependências novas): IDs `NEXUS-COMP-000001`, versões 1.0/1.1/…, **nunca sobrescreve** (restaurar cria nova versão),
  comparar versões, duplicar/variantes com origem, categorias personalizadas, `instantiate` (cópia para o projeto sem alterar o original).
- Compatibilidade apenas por interfaces declaradas (eixo/furo, rosca); sem dados → `COMPATIBILIDADE NÃO VERIFICADA`. Material não informado → `PROPRIEDADE NÃO INFORMADA`.
  Propriedades do componente exigem origem (documentado/medido/calculado/estimado).
- Interface: Ferramentas → "NEXUS Engineering Arsenal…" (Ctrl+Shift+A); banco em `~/.nexus_engineering_lab/arsenal.db`.
- Limites: o componente guarda a receita paramétrica da biblioteca (ou caminho STEP); inserção de STEP guardado e juntas/restrições de montagem ainda não implementadas.

## V2.6 — Infraestrutura honesta (rastreabilidade, solvers, dinâmica veicular)
- `modules/result_trace.py`: classe de cada resultado (ANALITICO / SIMULACAO_NUMERICA / VALIDADO / NAO_EXECUTADO / ANIMACAO_PRESCRITA); VALIDADO exige referência; NAO_EXECUTADO não carrega números.
- `modules/solver_registry.py`: detecta CalculiX, OpenFOAM e Gmsh; ausente => "NÃO INSTALADO" (nunca resultado falso). Neste ambiente CalculiX e OpenFOAM NÃO estão instalados.
- `modules/vehicle_dynamics.py`: dinâmica longitudinal 1D (RK4) separada da animação prescrita; validada contra velocidade terminal analítica.
- `modules/interference_sweep.py`: varredura de interferência sobre poses do mecanismo.
- `modules/fea3d.py`: FEA 3D linear-elástico Tet4 próprio (NEXUS-Tet4), malhas de caixa, carga de superfície consistente, escritor de .inp CalculiX. Validado: teste de patch (tração exata, erro <1e-6) e viga engastada (converge por baixo; Tet4 trava em flexão — malha 40×4×4 ≈ 79% do Euler-Bernoulli). Material (E, ν) sempre informado.
- `modules/cfd_case.py`: aerodinâmica nível 1 e 2 (analíticos) e gerador de caso OpenFOAM (simpleFoam k-ω SST, snappyHexMesh). Só executa com OpenFOAM instalado; senão NAO_EXECUTADO, sem números.
- `modules/workspace.py`: projetos (.nexus.json), histórico paramétrico com undo/redo, vitrine da biblioteca no Arsenal, uso por projeto, exclusão confirmada (bloqueada se em uso); Arsenal ganhou `export_component` e `delete_component`.
- Menu "Solvers, vitrine e projetos…" (Ctrl+Shift+S). Celular: aba Veículo (RK4) validada JS×Python.
- NÃO implementado: edição CAD paramétrica sobre B-rep importado, malhador para geometria arbitrária (Gmsh exige libGLU, indisponível aqui), CFD/CalculiX executados.
- `modules/fea_voxel.py`: malha de voxels→tetraedros de QUALQUER sólido OCP (peça da biblioteca ou STEP); reporta erro de volume da malha (geometria em escada).
- `modules/fea_study.py`: estudo completo peça→malha→NEXUS-Tet4→resultado rastreado; estudo de convergência de malha; FS só se o usuário informar o escoamento.
- `modules/fea3d.py`: + análise modal (massa consistente; densidade informada) e exportação VTK (ParaView). Validado: f1 de viga engastada ≈ +8% vs Euler-Bernoulli (Tet4 é rígido).
- Diálogo "Estudo FEA 3D de peça" (via Solvers…): estático, convergência, modal, salvar em projeto, exportar .vtk.
- Laboratório: nova calculadora "Dinâmica longitudinal (RK4)". Celular v25: abas "FEA 3D" (viga maciça, validada JS×Python 3e-12) e "Veículo".

## V2.6.1 — limites superados
- **Travamento (Tet4)** → `modules/fea_tet10.py`: Tet10 quadrático isoparamétrico; viga: <5% vs Timoshenko em malha grossa; modal ≈ +3% (Tet4: +8%).
- **Tensão local em escada** → `modules/fea_gmsh.py`: malha conforme via Gmsh/OpenCASCADE (erro de volume <0,1%); recuperação nodal de tensões; placa com furo vs Peterson: σmax −1%. Voxel continua disponível (marcado como não confiável localmente).
- **Edição paramétrica de STEP** → `modules/cad_history.py` + diálogo: base STEP/peça + operações (mover, girar, escalar, furo, caixa±, filete, chanfro), editar parâmetro antigo reconstrói, suprimir, desfazer/refazer. Sem nomeação topológica persistente (seletores geométricos).
- **CalculiX** → `modules/calculix_io.py`: escreve .inp (C3D4/C3D10), executa `ccx` se instalado, lê .dat (U, S) e compara com o NEXUS. O leitor é testado com amostras sintéticas do formato; a execução com `ccx` real NÃO foi testada aqui.
- Celular v26: Tet10 na aba FEA 3D (JS×Python 1e-11).
- Dica Linux/sandbox: o wheel do Gmsh exige libGLU/libXft; no Windows funciona direto com `pip install gmsh`.

## V2.6.2 — desempenho e robustez
- Abertura do programa 2,1 s → 0,9 s (import preguiçoso do trimesh, `core/lazy.py`).
- Solver Tet4 vetorizado (52 mil tetraedros: 10,7 s → 4,0 s); Tet10 vetorizado.
- FEA no diálogo roda em thread (interface não congela, botões bloqueados durante o cálculo).
- Solvers verificam o resíduo: mecanismo/apoio insuficiente vira erro explícito, nunca número absurdo; limite de GDL do solver direto.
- Celular v27: cópia para a área de transferência com fallback; limite antecipado de malha; auditoria automatizada de todas as abas sem erros.
- `tests/test_robustness.py`: entradas inválidas/extremas viram erro explícito.

## V2.7 — Sete novos projetos predefinidos (além de motores)

Menu **Projetos** (e viewer de celular): todos com STEP gerado por OpenCascade, mecanismo animado e **0 interferências não intencionais** (peças só encostam).

| Projeto | Peças | Animação (prescrita) |
|---|---|---|
| Motor rotativo **Wankel** (1 rotor) | 17 | eixo excêntrico θ; rotor a θ/3 sobre o excêntrico (vértices ficam na epitrocoide); ciclo 1080° |
| Motor **V12 a 60°** | 71 | virabrequim, 12 bielas e 12 pistões (biela-manivela exata por banco, 720°) |
| **Braço robótico** 6 eixos | 12 | ângulos senoidais por junta, cinemática direta (produto de exponenciais) |
| **Bomba centrífuga** com voluta | 13 | rotação do eixo/rotor |
| **Aerogerador** 3 pás (60 m) | 10 | rotação do rotor |
| **Turbojato** axial (4 est. compressor, 2 turbina) | 29 | rotação do spool |
| **Guindaste torre** treliçado | 146 | giro ±100° e carrinho/gancho |

**Honestidade:** são modelos de referência geométricos, ilustrativos — não foram dimensionados nem analisados (sem termodinâmica, BEM, CFD, norma de guindaste etc.); materiais NÃO são atribuídos automaticamente (você escolhe). Animações são cenários prescritos, não dinâmica. No Wankel/V12 não há válvulas, vedações reais, óleo ou refrigeração; o punho 2 do robô é uma esfera simplificada; a verificação de colisão cobre a pose inicial (não varre o movimento).
Celular: novos descritores de pose (`orb`, `rsn`, `tsn`, `vr`/`vs`), conferidos contra o Python (diferença ≤ 1e-10). Testes: `tests/test_new_projects.py` (`NEXUS_SLOW=1` inclui a checagem de interferência de V12 e guindaste).


## V2.8 — F1 (2027, clássicos), aeronaves e Engenharia/Telemetria F1

**Novos projetos predefinidos** (todos com animação prescrita; `has_mechanism=True`):
- **Protótipo de F1 2027** (`samples/f1_2027.py`): o modelo 2026 com as mudanças públicas de 2027 — asa traseira ~20 mm mais rasa, estai da asa traseira, piso/prancha 300 mm mais curtos (prancha 10 mm), tanque maior (ilustrativo). Massa mínima 2027 e volume do tanque **não verificados**.
- **F1 clássicos** (`samples/f1_classicos.py`): Ferrari 312T (1975), McLaren MP4/4 (1988), Lotus 72 (1970–75). Entre-eixos e bitolas de fontes públicas; largura/altura da cabine do MP4/4 e quase tudo do Lotus 72 são **ESTIMADOS**; internos e suspensão plausíveis. Rodas giram (mesmo nº de voltas nas 4 — não é rolagem exata com raios diferentes) e as dianteiras esterçam ±20° (ilustrativo).
- **Aeronaves** (`samples/aeronaves.py`): Cessna 172S, Supermarine Spitfire, Airbus A320-200. Hélice/fan giram; flapes, ailerons, profundor e leme oscilam. Sem aerodinâmica/CFD, sem estrutura interna.
- Todos conferidos **sem interferência na pose inicial** (OpenCascade). Lição do A320: o loft "suave" da fuselagem gerava sólido inválido para booleanos (volume negativo) — usa-se loft reto.

**Engenharia F1** (menu Analisar → *Engenharia F1…*, Ctrl+Alt+F; aba **F1** no celular), ferramentas de **estudo** com SEUS parâmetros:
- **Regulamento** (`modules/f1_regs.py`): conferência geométrica 2026/2027 (meia-largura, entre-eixos, prancha, massa) com fonte e status; limites não lidos aparecem como `LIMITE_NAO_VERIFICADO`.
- **Massa e CG** (`modules/f1_mass.py`): massa, CG, distribuição, altura do CG e inércia (massas pontuais), só com peças de material escolhido por você; lastro para alvo.
- **Volta** (`modules/lapsim.py`): ponto material quase-estacionário, elipse de atrito, ERS por volta — `SIMULACAO_NUMERICA` (NEXUS-LapSim 1.0); pista de exemplo **sintética**.
- **Telemetria** (`modules/telemetria.py`, NEXUS-Telemetria 1.0): canais sintéticos por distância — velocidade, tempo, g longitudinal/lateral, acelerador/freio (**estimados**), marcha/rotação (**ilustrativas**), arrasto, downforce, ERS, setores; faixas empilhadas e exportação CSV (cabeçalho avisa que são dados sintéticos). No celular: mesma matemática em JS (diferença JS×Python ≈ 5e-15) e CSV para baixar.
- **Limites**: não é telemetria real nem de equipe; sem pneus reais, transferência de carga, combustível, temperaturas, DRS ou mapas de motor; não substitui os sistemas de uma equipe nem a homologação da FIA.

**Fontes**: FIA 2027 Section C (iss.04) e The Race (regras 2027), RaceTeq (unidade de potência 2027), ultimatecarpage, f1technical, Wikipedia, AOPA e aerocorner (aeronaves).


## V2.9 — NEXUS F1 completo, análise estilo equipe, visual realista e vidros

**NEXUS F1 integrado** (`nexus_f1/`, menu Analisar → *Simulador F1 completo…*, Ctrl+Alt+S): trazido da conversa "Simulador de Telemetria da F1". Simulador quase-estático por circuito (15 circuitos configuráveis, passes de frenagem/tração, pneus com janela térmica e desgaste, ERS, pista molhada), temporadas independentes em JSON com `status`/`src` por parâmetro (modo regulamentar × experimental, `create_season` nunca sobrescreve), estratégia de pit stop, comparação A/B/C, relatórios CSV/JSON/Markdown, telemetria com cursor, e **áudio procedural do motor** (síntese harmônica ligada ao RPM, Doppler, trocas de marcha, ambiente). Todos os parâmetros dos pneus/carro são **estimativas** e os tempos **resultam da simulação** (não são fixos). 52 testes originais passam.

**Análise no estilo MoTeC i2 / ATLAS / OptimumLap** (`nexus_f1/core/analysis.py`, aba *Análise*): Δ-tempo entre voltas por distância (como o canal *time delta* do i2) e por segmento; canais matemáticos com avaliador seguro (AST, sem atributos/índices/imports); diagrama g-g com envelope; histogramas ponderados pelo tempo; uso de marchas e pedais; varredura de parâmetro; sensibilidade (s por +1 %); otimização de nível de asa (Monza × Mônaco dão resultados opostos) e de relação final (seção áurea). Varreduras rodam em modo experimental. São **tendências** com parâmetros estimados, não dados de equipe.

**Celular**: abas *F1 Sim* (visualizador do NEXUS F1: pista animada, telemetria e som sintetizado, 15 circuitos; `f1sim.html`) e *F1 Análise* (`analise_f1.json`: sensibilidade, nível ótimo de asa, marchas e histograma por circuito).

**Visual realista** (`modules/appearance.py`): cor/metal/rugosidade/opacidade por tipo de peça (pneu = borracha, vidro translúcido, rodas de liga, pintura por projeto — vermelho Ferrari 312T, preto/ouro Lotus 72, branco/azul A320, verde Spitfire…), no celular (botão *Visual: Realista/Holograma* + sombras) e no desktop (desligar *Holograma*). É **só estética**: não é material de engenharia e nunca alimenta massa/BOM. Nota técnica: o mapeamento de tons ACES foi retirado por renderizar preto em alguns drivers/GL por software.

**Vidros** nos aviões, recortados da pele da fuselagem (encaixam no rebaixo, sem interferência): janelas da cabine do Cessna, canopy do Spitfire, parabrisa e janelas do A320. Correção: o loft *suave* da fuselagem do A320 gerava sólido inválido para booleanos (invisível no viewer); usa-se loft reto.

**Estudo gratuito de F1 / engenharia de corrida** (base das ferramentas acima): Monlau Repsol (módulos *Introduction to Motorsport* e *Racing Team* gratuitos ao se matricular em outro), SimScale (série de workshops de F1 com CFD/modal/térmica/estática — encerrada, gravação no YouTube), HP Academy (análise de dados, canal de ganho/perda), MathWorks Racing Lounge (dinâmica veicular em Simulink), School of Race Engineering (módulo de simulação veicular). Softwares de referência: ATLAS (McLaren/Motion Applied), MoTeC i2, Ansys (CFD), MATLAB/Simulink, OptimumLap/OpenLAP.

**Limites**: NEXUS F1 e análises usam dados sintéticos e parâmetros estimados; não substituem sistemas de equipe nem a homologação da FIA.

## V3.0 — NEXUS CORE, solvers reais, resultados ligados à geometria e dinâmica lateral
Resumo (detalhes em `CHANGELOG.md`, `NEXUS_TECHNICAL_AUDIT.md`, `NEXUS_ARCHITECTURE.md`, `NEXUS_ROADMAP.md`):
- **Fila de processos isolados** (`core/jobs.py`) e **diagnóstico de ambiente** (`core/doctor.py`, botão em *Solvers…*).
- **CalculiX e OpenFOAM executados de verdade** (antes só gerávamos os arquivos). Bugs reais do gerador de casos corrigidos. Cd da esfera **não é validado** (malha grosseira, sem referência).
- **Resultados amarrados à versão da geometria**: mudou a peça → resultado antigo fica OBSOLETO (preservado).
- **Dinâmica lateral**: bicicleta + pneu de escova + transferência de carga; calculadora "Curva em regime" (desktop e celular).
- Status honesto por fase: ver `NEXUS_ROADMAP.md` (nem tudo do Master Prompt está concluído).

## V3.3 — cinco produtos e NEXUS INTELLIGENCE
CAD · STRUCTURAL · AERODYNAMICS · VEHICLE · INTELLIGENCE (assistente por regras). Importação de Arsenal, Cp em mm sobre as peças, atrito viscoso estimado, caminho WSL2/GPU e script de verificação para Windows. Ver `CHANGELOG.md`.

## V3.2 — resultados dentro do NEXUS
Mapa de von Mises no visualizador 3D, diálogo de CFD (OpenFOAM isolado, progresso, cancelar, Cp no corpo) e backup automático do Arsenal. Detalhes e limites em `CHANGELOG.md`.

## V3.1 — estabilidade e integração
FEA em **processo isolado** na interface (progresso + Cancelar + comparação com CalculiX), leitura do campo **.frd** (U e von Mises nodal → VTK), **log central** e **backup** de projetos ao salvar. Detalhes e esclarecimentos em `CHANGELOG.md`. Ainda não validado em Windows 11.
