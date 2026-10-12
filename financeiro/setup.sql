-- =====================================================================
-- FINANCEIRO - CRIACAO DO BANCO (SQL Server / T-SQL)
-- Ajustado ao ambiente real desta maquina (apenas unidades C: e D:).
-- Regras de ouro preservadas do exemplo original:
--   * PRIMARY no disco do sistema (dados atuais, acesso rapido)
--   * FG_HISTORICO em volume E/F/G = aqui condensado numa pasta D:\Data
--     (como so existem C: e D:, mantemos filegroup separado para
--     arquivamento, mas sem exigir unidades fisicas que nao existem)
--   * LOGON em volume proprio (D:), contracao minima
-- =====================================================================

USE [master];
GO

IF DB_ID(N'Financeiro') IS NOT NULL
BEGIN
    ALTER DATABASE [Financeiro] SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE [Financeiro];
END
GO

CREATE DATABASE [Financeiro]
ON
PRIMARY
(
    NAME = N'Financeiro_Primary',
    FILENAME = N'C:\Financeiro\Financeiro_Primary.mdf',
    SIZE = 100MB,
    MAXSIZE = 10GB,
    FILEGROWTH = 100MB
),
FILEGROUP [FG_HISTORICO]
(
    NAME = N'Financeiro_Hist1',
    FILENAME = N'D:\Financeiro\Financeiro_Hist1.ndf',
    SIZE = 500MB,
    MAXSIZE = 50GB,
    FILEGROWTH = 500MB
),
(
    NAME = N'Financeiro_Hist2',
    FILENAME = N'D:\Financeiro\Financeiro_Hist2.ndf',
    SIZE = 500MB,
    MAXSIZE = 50GB,
    FILEGROWTH = 500MB
)
LOG ON
(
    NAME = N'Financeiro_Log',
    FILENAME = N'D:\Financeiro\Financeiro_Log.ldf',
    SIZE = 200MB,
    MAXSIZE = 5GB,
    FILEGROWTH = 200MB
);
GO

-- =====================================================================
-- TABELA DEMONSTRATIVA: provar que FG_HISTORICO existe e aponta os dados
-- (rows da tabela irao para o filegroup secundario por DECLARACAO)
-- =====================================================================
USE [Financeiro];
GO

CREATE TABLE dbo.MovimentoFinanceiro
(
    MovimentoID  BIGINT IDENTITY(1,1) NOT NULL,
    DataMov      DATETIME2(0)    NOT NULL,
    ValorCentavos BIGINT         NOT NULL,
    Historico    NVARCHAR(200)   NULL,

    CONSTRAINT PK_MovimentoFinanceiro PRIMARY KEY (MovimentoID)
) ON [FG_HISTORICO];
GO

PRINT N'>>> Banco Financeiro criado.';
PRINT N'>>> Filegroup FG_HISTORICO verificar com:';
PRINT N'>>>   SELECT name, type_desc FROM sys.filegroups;';
GO
