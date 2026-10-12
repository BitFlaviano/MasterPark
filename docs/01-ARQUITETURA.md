# MasterPark — Arquitetura do Sistema

## 1. Visão Geral
MasterPark é um sistema comercial de gestão de estacionamentos, **desktop para Windows**
(10/11), **Offline-First**, modular e preparado para evolução a multiunidade e nuvem
sem reescrever as regras de negócio.

## 2. Stack Tecnológica

| Camada | Tecnologia | Justificativa |
|---|---|---|
| Frontend/Desktop | Python 3.12 + PySide6 (Qt6) | UI comercial moderna, nativa no Windows |
| Banco local | SQLite (ACID, arquivo único) | Instalação simples, 100% offline |
| Banco multiusuário (futuro) | PostgreSQL / SQL Server | Mesma interface de repositórios |
| QR Code / Código de barras | qrcode / python-barcode | Geração de tickets |
| PDF / Excel / CSV | reportlab / openpyxl / csv | Relatórios |
| Impressão térmica | ESC/POS RAW via win32print | Impressoras 58 e 80 mm |
| Empacotamento | PyInstaller + Inno Setup | .EXE + instalador e desinstalador |
| Testes | pytest | Regras críticas (tarifa, licença, auth) |

## 3. Princípios de Arquitetura

1. **Offline-First** — operação integral sem internet; externos são opcionais/assíncronos.
2. **Camadas** — UI → Services → Repositories → Database. Regras de negócio não
   conhecem SQL nem Qt.
3. **Banco trocável** — SQL parametrizado; a camada `Database` abstrai o dialeto.
   Migração para PostgreSQL/SQL Server troca conexão + migrações apenas.
4. **Integridade transacional** — saída + pagamento + liberação de vaga em uma
   transação única.
5. **Dinheiro em centavos (INTEGER)** — nunca usar FLOAT/REAL para valores.
6. **Auditoria total** — toda operação relevante grava em `audit_logs` imutável.
7. **Licenciamento criptográfico** — RSA-2048; chave pública embutida na aplicação;
   licença assinada pelo fabricante, não é um JSON editável.
8. **Senhas** — PBKDF2-HMAC-SHA256 (210.000 iterações), salt por usuário.
9. **Hardware** — interfaces + adaptadores; itens não integrados de verdade são DEMO.

## 4. Estrutura de Diretórios

    MasterPark/
      app/
        main.py               # entrada do aplicativo
        bootstrap.py          # fiação, single instance, gate de licença
        core/                 # config, banco, schema, segurança, auditoria
        domain/               # dataclasses puras + catálogo de permissões
        repositories/         # acesso a dados (implementação SQLite)
        services/             # regras de negócio (tarifa, tickets, caixa, ...)
        hardware/             # interfaces + adaptadores DEMO
        ui/                   # telas Qt (design system)
      tests/                  # pytest
      tools/                  # gerador de licenças / ativação offline
      installer/              # script Inno Setup
      scripts/                # build do EXE e do instalador
      docs/                   # documentação

## 5. Modelo Relacional (resumo)

Empresa → Estacionamento → Setor → Vaga; usuários (RBAC); clientes; veículos;
tickets; sessões de estacionamento; pagamentos; caixa; movimentações; mensalistas;
convênios; reservas; tarifas e regras; descontos; incidentes; dispositivos;
câmeras; eventos de acesso (LPR); auditoria; notificações; licenças; backups;
configurações. Schema completo em `app/core/schema.sql`, aplicado via migrações
versionadas.

## 6. Fluxo Operacional

Entrada → ticket (QR + código de barras) → ocupação da vaga → permanência →
tarifação → validação de convênio/mensalista → pagamento → recibo → saída →
liberação da vaga → movimento de caixa → auditoria.

## 7. Licenciamento

- Chave gerada pelo fabricante (RSA privada) e validada pela aplicação (RSA pública).
- Ativação associa a instalação (machine-id) à licença; registro em `license_activations`.
- Ativação online quando há internet; offline via código de ativação assinado.
- Expiração: avisos a partir de 30 dias; o sistema nunca bloqueia o acesso aos dados.

## 8. Segurança

- Autenticação local com PBKDF2 e bloqueio após tentativas (account lockout).
- RBAC granular (6 perfis + permissões individuais) e sessão com timeout configurável.
- Validação de entrada e SQL parametrizado (anti SQL Injection).
- Política de retenção e anonimização conforme LGPD.

## 9. Backup

Backup automático (diário/semanal/manual) via cópia segura do banco SQLite;
retenção configurável; nunca sobrescreve o último backup válido; restauração via
painel administrativo; verificação de integridade (`PRAGMA integrity_check`).

## 10. Módulos

Core, Estacionamento, Caixa, Financeiro, Mensalistas, Convênios, Reservas,
Relatórios, LPR, Hardware, Licenciamento, Backup, Auditoria, API, Analytics.
Cada gated feature é habilitada pela licença (STARTER/PROFESSIONAL/BUSINESS/ENTERPRISE).