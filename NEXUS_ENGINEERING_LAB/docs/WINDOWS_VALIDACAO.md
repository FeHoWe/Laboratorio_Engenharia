# Roteiro de validação em Windows 11 real

**Estado atual: NÃO VALIDADO.** Nada abaixo foi executado em Windows 11 pelo desenvolvimento do NEXUS (o ambiente de desenvolvimento é Linux, sem tela). O `nexus.spec` foi auditado só de forma estática. Marque cada item SOMENTE depois de fazer na sua máquina; quando todos estiverem marcados, registre data, versão do Windows e do NEXUS no fim deste arquivo.

## 1. Preparação
- [ ] Windows 11 atualizado, usuário comum (não administrador) e uma pasta com espaço e acento no caminho (ex.: `C:\Users\Seu Nome\Área de Trabalho\NEXUS`).
- [ ] `tools\verificar_windows.bat` roda e o relatório não aponta dependência obrigatória ausente.
- [ ] `python nexus_cli.py doctor` lista as ferramentas externas (CalculiX, Gmsh, OpenFOAM/WSL2) e diz o que falta.

## 2. Execução a partir do código
- [ ] `run_nexus.bat` abre a janela principal sem erro e sem internet.
- [ ] Importar um STEP e um STL de `samples\`, salvar `.nexus` em caminho com acento, fechar e reabrir.
- [ ] Menu Estudos avançados (Ctrl+Alt+E) abre e calcula com os valores de exemplo.
- [ ] Trocar o idioma e conferir que os menus mudam (as traduções são de IA, sem revisão nativa).

## 3. Empacotamento
- [ ] `tools\empacotar_windows.bat` termina sem erro.
- [ ] `dist\NEXUS\NEXUS.exe` abre em outra pasta/máquina sem Python instalado.
- [ ] No executável: idiomas aparecem traduzidos (confirma que `locales\` foi empacotado), F1 (nexus_f1) abre, exportar PDF funciona.
- [ ] Log de erros: provocar um erro (arquivo inválido) e conferir que a janela mostra mensagem compreensível e nada fecha sozinho.

## 4. Instalador
- [ ] Compilar `tools\nexus_instalador.iss` com Inno Setup; instalar em `C:\Program Files` e em pasta do usuário.
- [ ] Atalho do menu Iniciar abre o programa; desinstalar remove o programa e NÃO apaga seus projetos `.nexus`.

## 5. Dados e recuperação
- [ ] Autosave: matar o processo no Gerenciador de Tarefas com projeto não salvo e reabrir → oferece recuperação.
- [ ] Backup/versões: registrar versão do projeto e restaurar.
- [ ] Histórico de atividade em `%USERPROFILE%\.nexus_lab\atividade.jsonl` é criado e pode ser apagado sem efeito colateral.

## 6. Tela
- [ ] Escalonamento 100 %, 125 % e 150 %: janelas legíveis, nada cortado.
- [ ] Duas resoluções (ex.: 1366×768 e 1920×1080).

## Registro (preencher por quem testou)
Data: ____  Windows (build): ____  NEXUS: ____  Resultado: ____  Observações: ____
