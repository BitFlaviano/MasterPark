# MasterPark — Manual do Usuário

## 1. Visão Geral

O MasterPark gerencia todo o fluxo de um estacionamento: **entrada**, **saída com
tarifação automática**, **caixa**, **mensalistas**, **convênios**, **relatórios** e
**auditoria**, funcionando 100% offline.

- Todos os **valores em centavos** (sem erro de arredondamento).
- Contas de **mensalistas**: cada vencimento gera uma mensalidade; o valor do
  vencimento é cobrado no dia definido e a cobrança acumula enquanto não for paga.
- O sistema registra **auditoria** de toda operação relevante (quem, quando, o quê).

### Atalhos de teclado

| Tecla | Ação |
|---|---|
| `F2` | Nova Entrada |
| `F3` | Nova Saída |
| `F4` | Mapa de Vagas |
| `F5` | Tickets Ativos |
| `F6` | Painel (Dashboard) |
| `F7` | Mensalistas |
| `F9` | Busca |
| `Ctrl+G` | Alternar tema claro/escuro |
| `Ctrl+B` | Sair (logout) |

## 2. Login e Perfis

O MasterPark usa controle de acesso por perfis (6 perfis + permissões individuais).

| Perfil | Acessos principais |
|---|---|
| Operador | Entrada, Saída, Caixa, Mapa, Tickets |
| Visitante | Consultas (somente leitura) |
| Financeiro | Caixa, Mensalistas, Relatórios |
| Supervisor | + Cancelamentos/aprovações |
| Gerente | + Clientes, Descontos maiores |
| Administrador | Tudo, inclusive usuários e sistema |

**Conta demo (primeiro uso em modo demonstração):** `admin` / `admin123`.

O botão do caixa (canto superior direito) mostra o saldo do caixa **do operador
logado**. Para abrir/fechar caixa, clique no botão com o valor.

## 3. Entrada de Veículo (F2)

1. Digite a placa (formato `ABC-1234` ou `ABC1D23`).
2. Preencha categoria (padrão CARRO), modelo, cor e cliente (opcionais).
3. Clique em **Registrar Entrada**. O sistema:
   - gera o ticket e imprime (ou salva como arquivo em modo DEMO);
   - ocupa a vaga sugerida (primeira vaga livre do setor padrão);
   - associa à operação de caixa se houver caixa aberto.

## 4. Saída de Veículo (F3)

1. Busque por **ticket, QR, código de barras ou placa**.
2. O card mostra permanência, valor original e regra aplicada.
3. Preencha **desconto (%)**, **conveniência (gratuidade)** se houver, e o
   **valor recebido** (a vista/informado). Para **CONVÊNIO** o valor não é
   recebido na hora.
4. **Confirmar Saída e Pagamento**: fecha ticket, baixa o pagamento, libera a
   vaga, lança o movimento no caixa e imprime o recibo.

### Funcionalidades especiais

- **Ticket Perdido**: truncada via botão dedicado → aplica a tarifa e registra
  ocorrência (`incidentes`).
- **Cancelar Ticket**: exige **autorização (permissão)** e **motivo**; não gera
  pagamento nem libera valor.

## 5. Caixa (cabeçalho)

- **Abrir caixa**: informa o valor de abertura; passa a registrar entradas/saídas.
- **Sangria / Suprimento**: movimento manual motivado (ex.: reposição de troco).
- **Fechar caixa**: informa o valor conferido; se houver diferença, exige
  justificativa (fica na auditoria).
- O saldo exibido é o valor em caixa do **operador logado**.

## 6. Mensalistas (F7)

- **Cadastrar mensalista**: escolhe um cliente, uma vaga exclusiva (opcional),
  o valor mensal e o **dia de vencimento**.
- **Pendências**: o sistema cria as faturas mensais automaticamente; pagar com
  **forma de pagamento** e vincula ao **caixa**.
- **Renovar**: estende a mensalidade pelo período seguinte quando a atual expira.
- **Aplicar bloqueios**: penaliza/desbloqueia vagas quando há atraso (regras
  configuráveis).

## 7. Clientes e Veículos

Tela de clientes mantém **cadastro de pessoas/empresas (CPF/CNPJ)** e seus veículos.
Usada também no cadastro de mensalistas e convênios.

## 8. Relatórios

Disponíveis (dependem da licença): Faturamento, Mensalistas, Ocupação, Pico de
Movimento, Tickets, Caixa, Descontos, Convênios, Incidentes, Auditoria.

- Exportação: **CSV** (pasta `relatorios/`), **Excel (.xlsx)** e **PDF/A4**
  (via diálogo de salvamento).

## 9. Tickets Ativos (F5)

Lista tickets em andamento com tempo de permanência; duplo clique abre direto na
**tela de saída**.

## 10. Mapa de Vagas (F4)

Grade colorida por estado (Livre / Ocupada / Reservada / Bloqueada). Clique em uma
vaga ocupada para abrir a saída do veículo.

## 11. Painel (F6)

Indicadores em tempo real: veículos agora, entradas/saídas do dia, faturamento do
dia/mês, ticket médio, mensalistas (ativos, inadimplentes, vencendo), ocupação do
estacionamento, pagamentos por forma, pico de movimento.

## 12. Manutenção (menu Sistema)

- **Configurações**: empresa, tarifas (assistente), sistema (tema, impressora,
  backup automático), usuários, licença.
- **Saúde do Sistema**: backup manual, validação de backup, integridade do banco,
  dispositivos e licença.
- **Auditoria**: histórico completo de operações com filtros.
- **Busca (Ctrl+G / F9)**: localiza tickets e clientes rapidamente.

## 13. Backups

- Automáticos (diário/semanal) com **retenção configurável** (padrão 30 dias).
- Nunca sobrescrevem o último backup válido.
- **Restauração** e **validação** em Saúde do Sistema.
- Os dados ficam em `%LOCALAPPDATA%\MasterPark\` (banco em `data/`, backups em
  `backups/`).