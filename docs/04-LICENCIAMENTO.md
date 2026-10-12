# MasterPark — Licenciamento (para o fabricante)

## 1. Modelo

- Licenças são emitidas **pelo fabricante** com a chave privada RSA
  (`tools/keys/private.pem`) e verificadas pelo app com a chave pública embutida
  (`app/core/config.py` → `DEFAULT_PUBLIC_KEY`).
- A licença não é um JSON editável: é **assinada** e validada criptograficamente.
- Cada instalação tem um `machine-id`; a ativação associa **licença ⇒ máquina**.
- Planos: `STARTER`, `PROFESSIONAL`, `BUSINESS`, `ENTERPRISE` (recursos liberados
  por licença). **Nunca bloqueia o acesso aos dados** — só avisa a validade.

> **NUNCA** commitar/compilar `tools/keys/private.pem` no produto final (já está
> no `.gitignore`). Somente a `public.pem` via `DEFAULT_PUBLIC_KEY` vai no app.

## 2. Gerar uma licença

```bash
python tools/generate_license.py \
  --plan PROFESSIONAL \
  --days 365 \
  --client "Empresa X"   # opcional
```

O script grava `tools/licencas/licenca_<CHAVE>.lic` e imprime a chave
(`PARK-XXXX-XXXX-XXXX-XXXX`) e a chave pública correspondente.

## 3. Ativação

### Online
O app submete a chave + machine-id; o fabricante assina e devolve o ativo, que
fica gravado em `license_activations`.

### Offline (sem internet no posto)
1. No app: **Ativação → chave da licença → máquina** mostra o `machine-id`.
2. Fabricante gera o código offline:
   ```bash
   python tools/generate_license.py --code-only --machine <machine-id> ...
   ```
3. Cliente cola o **código de ativação** no campo offline.

## 4. Licença DEMO (ambiente de testes)

```
Chave: PARK-KEEW-3QLY-KJL5-3SSK
Plano: PROFESSIONAL
Expira: 2027-09-20
```
Aceita sem ativação (o app reconhece a chave demo). É a usada nos testes e no
modo demonstração.

## 5. Regras de contra-pirataria

- Validade com **aviso de 30 dias** antes do vencimento; nunca trava o banco.
- Grafo de ativações registradas (auditoria) permite ver quantas máquinas ativas.
- Número de ativações por licença limitado ao plano (configurável).