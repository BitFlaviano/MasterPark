# MasterPark — Guia de Instalação

## 1. Requisitos

- Windows 10 ou 11 (64 bits).
- Para **impressão térmica real**: driver da impressora (58/80 mm) + comando
  `printer` no Windows; o app envia ESC/POS RAW pela impressora configurada.
- Não precisa de internet para operar.

## 2. Instalação via Instalador

1. Execute `MasterParkSetup.exe` (conceda o UAC quando solicitado).
2. Siga o assistente (idioma: Português do Brasil).
3. Atalhos: menu Iniciar (obrigatório) e opcional na área de trabalho.
4. O desinstalador remove o programa. **Os dados em `%LOCALAPPDATA%\MasterPark`
   são preservados** (faça backup antes se desejar reverter).

## 3. Versão Portátil

A pasta `dist\MasterPark\` contém a versão portátil:
Execute **`MasterPark.exe`** diretamente — sem instalação, sem registro no Windows.

> Se a pasta portátil for gravável, o app passa a usar uma pasta **local** para
> os dados (defina a variável de ambiente `MASTERPARK_PORTABLE` para forçar esse
> comportamento).

## 4. Primeira Execução (Assistente)

Ao iniciar pela primeira vez o app pergunta:

- **Assistente de configuração**: preenche empresa, unidade (estacionamento),
  setores e vagas, tarifas, impressora, administrador e backup.
- **Modo demonstração**: cria dados de exemplo (empresa demo, setores/vagas,
  tarifas, operador `admin`/`admin123`) para você conhecer o sistema.

> A conta criada no assistente é a de **Administrador** (acesso total).

## 5. Ativação da Licença

Se a licença demo/avulsa não estiver válida, aparece a **Ativação**:

1. **Chave de licença** (`PARK-XXXX-XXXX-XXXX-XXXX`): salva a chave; com internet
   ativa automaticamente.
2. **Arquivo .lic** do fabricante: funcional mesmo sem internet.
3. **Código offline**: cole o código de ativação gerado pelo fabricante com a
   chave desta instalação (ver `docs/04-LICENCIAMENTO.md`).

A instalação é identificada por um **machine-id** (GUID do Windows → hash da placa
de rede). Cada licença ativa **uma** instalação.

## 6. Configuração da Impressora

Em **Sistema → Configurações → Imprimindo**:
- Nome da impressora (aparece no app), largura do papel (58/80 mm).
- Marque **Imprimir ticket na entrada** e **Imprimir recibo na saída**.
- Sem impressora, o app usa o **adaptador DEMO**: salva o ticket/recibo em
  `%LOCALAPPDATA%\MasterPark\data\printed\demo\` e **mostra [IMPRESSÃO DEMO]**.

## 7. Upgrade / Movendo de máquina

1. Faça backup em **Sistema → Saúde do Sistema → Backup**.
2. Instale o MasterPark na nova máquina.
3. Mova o arquivo `.bak` para `%LOCALAPPDATA%\MasterPark\backups\`.
4. **Valide** o backup na nova instalação e ative novamente a licença (código
   offline com o novo machine-id).