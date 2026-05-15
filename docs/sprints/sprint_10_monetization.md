# Sprint 10 — Monetization: Guia Instrucional

## Contexto e Objetivo

O Sprint 10 adiciona créditos, planos, e billing. Este é o sprint onde o produto passa a ter receita — e onde erros de implementação têm consequências financeiras reais.

**Princípio do sprint:** nunca confie em dados do cliente para autorizar consumo. A fonte da verdade de créditos disponíveis é sempre o banco, verificado server-side antes de iniciar qualquer operação cara.

---

## Pre-requisitos e regras de seguranca

- Sprint 9 concluido: `organizations` existem e cada request consegue descobrir `org_id`.
- Stripe em modo test configurado antes de qualquer teste real.
- Variaveis obrigatorias: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_STARTER`, `STRIPE_PRICE_PRO`, `APP_URL`.
- Nunca use `sk_live_...` durante desenvolvimento. Use `sk_test_...`.
- Webhook deve ser idempotente: antes de creditar uma organizacao, registre ou verifique o `event.id` da Stripe para nao processar o mesmo evento duas vezes.
- Debito de credito deve ser atomico no banco; nao faca `SELECT balance` seguido de `UPDATE` em Python para saldo financeiro.

**Teste local obrigatorio com Stripe CLI:**

```bash
stripe listen --forward-to localhost:8005/stripe/webhook
stripe trigger checkout.session.completed
```

So considere o sprint concluido quando um evento de webhook em modo test atualizar plano/creditos uma unica vez, mesmo que o mesmo evento seja reenviado.

---

## Task 0: `backend/billing.py` - Confirmar fundacoes de seguranca financeira

**Estimativa:** ~20min

**O que é e por que existe**

Billing nao deve ser adicionado em cima de autenticacao ambigua. Antes de criar checkout ou debitar credito, confirme que cada request autenticada resolve `org_id` server-side, que eventos Stripe serao deduplicados e que debito de saldo sera atomico no banco.

**Files:**
- Criar/Editar: `backend/billing.py`
- Criar/Editar: `supabase/migrations/005_billing.sql`
- Ler: `backend/auth.py`, `docs/api_contracts.md`

---

### Conceito: dinheiro exige idempotencia e atomicidade
> Sistemas de billing recebem eventos repetidos, requests concorrentes e falhas parciais. Idempotencia impede cobrar ou creditar duas vezes; atomicidade impede saldo negativo quando duas pesquisas rodam ao mesmo tempo. Sem esses dois conceitos, o produto pode perder dinheiro ou bloquear usuarios incorretamente.

---

### Documentação
- https://docs.stripe.com/webhooks - referencia oficial de webhooks Stripe.
- https://docs.stripe.com/api/idempotent_requests - referencia oficial de idempotencia.
- https://www.postgresql.org/docs/current/transaction-iso.html - referencia oficial de transacoes PostgreSQL.

---

### O que você precisa fazer

1. Confirme que Sprint 9 resolve `org_id` no backend.
2. Planeje tabela `stripe_events` com `event_id unique`.
3. Planeje funcao SQL/RPC para debitar credito de forma atomica.
4. Confirme que nenhuma secret Stripe sera exposta em `VITE_*`.
5. So depois implemente Checkout, Portal e webhook.

### Esqueleto

```text
# TODO: Explore - revisar auth/org do Sprint 9 e contrato de billing.
# TODO: Prototype - desenhar fluxo idempotente para um evento Stripe repetido.
# TODO: Implement - adicionar tabelas/funcoes necessarias em 005_billing.sql.
# TODO: Verify - reenviar o mesmo evento Stripe e confirmar uma unica transacao.
```

<details>
<summary>Ver solução completa</summary>

Checklist minimo antes do codigo:

```text
org_id vem do backend, nao do frontend
stripe_events.event_id tem UNIQUE
credit_transactions registra todo movimento
debito usa UPDATE condicional ou RPC transacional
STRIPE_SECRET_KEY fica somente no backend
```

Exemplo de regra atomica em SQL:

```sql
update org_credits
set credits_balance = credits_balance - requested_credits
where org_id = target_org_id
  and credits_balance >= requested_credits
returning credits_balance;
```

Se `returning` nao trouxer linha, o saldo era insuficiente ou a org nao existe. Nao faca `SELECT` separado seguido de `UPDATE` em Python.

</details>

- [ ] **Step 0.1: `org_id` e resolvido server-side.**
- [ ] **Step 0.2: `stripe_events` planejada com `event_id unique`.**
- [ ] **Step 0.3: Debito atomico definido antes do endpoint.**
- [ ] **Step 0.4: Secrets Stripe ausentes do frontend.**

### Resumo
> *Preencher apos concluir a task: quais garantias de billing foram confirmadas antes da implementacao?*

---

## Modelo de Monetização

O IntelliOps usa **créditos** como unidade de consumo:
- Cada pesquisa consome créditos proporcionalmente ao número de tokens usados
- Planos incluem um pacote mensal de créditos
- Pro tem Pay as You Go além dos créditos inclusos
- Enterprise tem per-seat add-on

| Plano | Créditos/mês | PAYG | Price |
|---|---|---|---|
| Free | 10 | ❌ | $0 |
| Starter | 100 | ❌ | $29/mês |
| Pro | 500 | ✅ ($0.10/crédito extra) | $99/mês |
| Enterprise | Custom | ✅ (negociado) | Custom |

**Conversão de tokens para créditos:** 1 crédito = 10.000 tokens. Uma pesquisa simples (~18k tokens) custa ~2 créditos. Uma comparação profunda (~90k tokens) custa ~9 créditos.

---

## Stack de Billing

| Tecnologia | Por que |
|---|---|
| **Stripe** | Padrão da indústria para SaaS billing. Webhooks confiáveis, SDKs bem mantidos, compliance PCI out-of-the-box. |
| **Stripe Checkout** | UI de pagamento hospedada pelo Stripe. Você não toca em dados de cartão — compliance PCI fica com eles. |
| **Stripe Customer Portal** | UI de gerenciamento de assinatura hospedada pelo Stripe. O cliente altera plano, cancela, e baixa faturas sem você construir essa UI. |
| **Stripe Webhooks** | Notificações de eventos assíncronos (pagamento confirmado, assinatura cancelada, etc). |

---

## Task 1: `supabase/migrations/005_billing.sql` - Schema de Billing

**Estimativa:** ~45min

**O que é e por que existe**

Cria `org_credits` (saldo atual), `credit_transactions` (ledger imutável de cada operação) e `org_billing` (vínculo com Stripe). Sem este schema, nenhum débito, crédito ou webhook pode ser persistido.

**Files:**
- Criar/Editar: `supabase/migrations/005_billing.sql`

---

### Conceito: Ledger de transações — saldo atual + histórico imutável
> Sistemas financeiros têm dois registros distintos: o saldo (quanto sobrou agora) e o ledger (o que aconteceu em cada operação). Guardar só o saldo torna impossível auditar double charges, disputas de billing ou bugs de débito. O ledger é append-only — nunca se atualiza uma linha existente, só se insere uma nova.
>
> | Tabela | O que armazena | Mutável? |
> |---|---|---|
> | `org_credits` | Saldo corrente da org | Sim — atualizado a cada débito/crédito |
> | `credit_transactions` | Cada operação com `balance_after` | Não — append-only |
> | `org_billing` | Dados Stripe da org (customer_id, plan, status) | Sim — atualizado via webhook |
>
> Sem o `CHECK (credits_balance >= 0)` em `org_credits`, um bug no Python pode deixar o saldo negativo silenciosamente — o constraint é a última linha de defesa.

---

### Documentação
- https://www.postgresql.org/docs/current/ddl-constraints.html - `CHECK`, `REFERENCES`, `UNIQUE` e constraints de integridade no DDL.
- https://supabase.com/docs/guides/database/migrations - como criar e aplicar migrations no Supabase.

---

### O que você precisa fazer

**Passo 1.1 — Criar `org_credits` com `CHECK (credits_balance >= 0)`**
Intent: o banco precisa garantir que o saldo nunca fique negativo, mesmo se o código Python tiver bug.
Consequência: sem o constraint, `UPDATE SET credits_balance = -3` seria aceito silenciosamente.
→ `CREATE TABLE org_credits (org_id UUID PRIMARY KEY REFERENCES organizations(id), credits_balance INTEGER NOT NULL DEFAULT 0 CHECK (credits_balance >= 0), ...)`

**Passo 1.2 — Criar `credit_transactions` com `type CHECK` e `balance_after`**
Intent: cada débito/crédito deve ser registrado com o saldo resultante para auditoria.
Consequência: sem `balance_after`, não é possível reconstruir o saldo em qualquer ponto do tempo nem auditar double charges.
→ `type TEXT NOT NULL CHECK (type IN ('consume', 'purchase', 'refund', 'reset'))` + coluna `balance_after INTEGER NOT NULL`

**Passo 1.3 — Criar `org_billing` com `stripe_customer_id UNIQUE` e índice para lookup**
Intent: o webhook do Stripe identifica a org pelo `stripe_customer_id` — o índice acelera este lookup.
Consequência: sem o índice, cada webhook faz full scan em `org_billing` para encontrar a org.
→ `CREATE INDEX idx_org_billing_customer ON org_billing (stripe_customer_id);`

**Passo 1.4 — Criar função SQL `debit_credits_atomic`**
Intent: o débito precisa ser atômico — `UPDATE WHERE credits_balance >= p_credits` numa única query.
Consequência: sem a função, o Python fará SELECT → check → UPDATE em passos separados, criando race condition.
→ `CREATE OR REPLACE FUNCTION debit_credits_atomic(p_org_id UUID, p_credits INTEGER) RETURNS JSON AS $$ ... $$`

### Esqueleto

```sql
-- TODO: 1.1 - CREATE TABLE org_credits com credits_balance CHECK >= 0, credits_included, reset_at
-- TODO: 1.2 - CREATE TABLE credit_transactions com type CHECK, amount, balance_after, description
-- TODO: 1.3 - CREATE TABLE org_billing com stripe_customer_id UNIQUE, plan, status CHECK
-- TODO: 1.3 - CREATE INDEX idx_org_billing_customer ON org_billing (stripe_customer_id)
-- TODO: 1.4 - CREATE OR REPLACE FUNCTION debit_credits_atomic(p_org_id, p_credits) RETURNS JSON
--             UPDATE WHERE credits_balance >= p_credits RETURNING credits_balance
--             IF NOT FOUND: RAISE EXCEPTION 'Insufficient credits'
```

<details>
<summary>Ver solução completa</summary>

```sql
-- Créditos por organização
CREATE TABLE org_credits (
  org_id          UUID PRIMARY KEY REFERENCES organizations(id),
  credits_balance INTEGER NOT NULL DEFAULT 0 CHECK (credits_balance >= 0),
  credits_included INTEGER NOT NULL DEFAULT 0,  -- créditos do plano atual
  reset_at        TIMESTAMPTZ,  -- próximo reset mensal
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Histórico de consumo de créditos
CREATE TABLE credit_transactions (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          UUID NOT NULL REFERENCES organizations(id),
  research_id     UUID REFERENCES researches(id),
  type            TEXT NOT NULL CHECK (type IN ('consume', 'purchase', 'refund', 'reset')),
  amount          INTEGER NOT NULL,   -- positivo = crédito, negativo = débito
  balance_after   INTEGER NOT NULL,
  description     TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Dados de billing do Stripe por organização
CREATE TABLE org_billing (
  org_id              UUID PRIMARY KEY REFERENCES organizations(id),
  stripe_customer_id  TEXT UNIQUE,
  stripe_subscription_id TEXT UNIQUE,
  plan                TEXT NOT NULL DEFAULT 'free',
  status              TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'past_due', 'canceled', 'trialing')),
  current_period_end  TIMESTAMPTZ,
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Índice para lookup por stripe_customer_id (usado nos webhooks)
CREATE INDEX idx_org_billing_customer ON org_billing (stripe_customer_id);
```

> **Por que `credit_transactions` além de `org_credits`?** O saldo em `org_credits` é o valor atual. O histórico em `credit_transactions` é o ledger — o registro imutável de cada operação. Se algo der errado (bug, double charge, disputa de billing), você precisa do ledger para auditar. Nunca dependa só do saldo atual.

> **Por que `CHECK (credits_balance >= 0)`?** Constraints de banco são a última linha de defesa. Mesmo que o código Python tenha um bug e tente debitar mais créditos do que existem, o banco rejeita. Sempre use constraints para invariantes de negócio críticos.

---

</details>

- [ ] **Step 1.1: `org_credits` criada com `CHECK (credits_balance >= 0)`; INSERT com valor negativo é rejeitado.**
- [ ] **Step 1.2: `credit_transactions` aceita `type IN ('consume','purchase','refund','reset')` e rejeita outros.**
- [ ] **Step 1.3: `org_billing` tem `stripe_customer_id UNIQUE`; índice de lookup criado.**
- [ ] **Step 1.4: `debit_credits_atomic` executada via `supabase.rpc()`; retorna `new_balance`; falha com `INSUFFICIENT_CREDITS` quando saldo < créditos pedidos.**

### Resumo
> *Preencher apos concluir a task: o que foi alterado, qual verificacao passou, e qual risco ainda merece atencao?*

---
## Task 2: `backend/billing.py` - Verificação de Créditos antes de Pesquisar

**Estimativa:** ~30min

**O que é e por que existe**

Implementa `check_credits(org_id)` e o gate na rota `POST /research/stream`. O objetivo é rejeitar a pesquisa com HTTP 402 antes de qualquer chamada ao LLM — créditos insuficientes não devem consumir tokens.

**Files:**
- Criar/Editar: `backend/billing.py`

---

### Conceito: Gate antes da operação cara — 402 antes de consumir tokens
> O stream de pesquisa consome tokens do LLM assim que inicia. Se a verificação de créditos acontecer depois ou não existir, a org pode consumir tokens sem ter créditos — o produto perde dinheiro. O gate deve ser a primeira coisa que acontece no endpoint, antes de qualquer `yield` do stream.
>
> | Momento da verificação | Custo se crédito insuficiente | Código HTTP correto |
> |---|---|---|
> | Antes de iniciar o stream (correto) | Zero tokens consumidos | 402 Payment Required |
> | Após o stream terminar (errado) | Tokens já consumidos | 402 — mas tarde demais |
> | Nunca (ausente) | Tokens consumidos sem débito | N/A — vazamento de receita |
>
> 402 "Payment Required" é o código correto para "você não pode acessar por falta de pagamento" — diferente de 403 "Forbidden" que significa falta de permissão independente de pagamento.

---

### Documentação
- https://fastapi.tiangolo.com/tutorial/dependencies/ - `Depends()` para injetar verificação de créditos antes do handler.
- https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/402 - definição do HTTP 402 Payment Required.

---

### O que você precisa fazer

**Passo 2.1 — Criar `check_credits(org_id)` em `billing.py`**
Intent: a função deve retornar `True` se o saldo for suficiente para uma pesquisa estimada.
Consequência: sem isolamento em `billing.py`, a lógica de créditos fica espalhada em `api.py` e fica difícil de testar.
→ `SELECT credits_balance FROM org_credits WHERE org_id = $1` → `return balance >= CREDITS_PER_RESEARCH_ESTIMATE`

**Passo 2.2 — Inserir o gate no início de `POST /research/stream`**
Intent: a pesquisa só começa se `check_credits()` retornar `True`.
Consequência: inserir o gate depois do primeiro `yield` do stream não funciona — o stream já iniciou e o HTTP 402 não pode mais ser enviado.
→ `if org_id and not check_credits(org_id): raise HTTPException(status_code=402, detail="Insufficient credits")`

**Passo 2.3 — Definir `CREDITS_PER_RESEARCH_ESTIMATE` como constante nomeada**
Intent: a estimativa conservadora (ex: 5 créditos) deve ser visível e editável em um lugar.
Consequência: número mágico inline (ex: `>= 5`) é invisível para quem ajusta o modelo de créditos depois.
→ `CREDITS_PER_RESEARCH_ESTIMATE = 5` no topo de `billing.py`

**Passo 2.4 — Testar o gate com org sem créditos**
Intent: confirmar que a pesquisa não inicia quando o saldo é 0.
Consequência: sem testar o caminho negativo, o gate pode existir no código mas estar comentado ou com bug lógico.
→ Zerar `org_credits.credits_balance` para a org de teste; chamar `POST /research/stream`; confirmar HTTP 402.

### Esqueleto

```python
# backend/billing.py
CREDITS_PER_RESEARCH_ESTIMATE = 5  # TODO: 2.3 - ajustar conforme benchmark de tokens

async def check_credits(org_id: str) -> bool:
    # TODO: 2.1 - SELECT credits_balance FROM org_credits WHERE org_id = org_id
    # TODO: 2.1 - return balance >= CREDITS_PER_RESEARCH_ESTIMATE (False se org não encontrada)
    pass

# backend/api.py (modificar o endpoint existente)
@app.post("/research/stream")
async def research_stream(request: ResearchRequest):
    # TODO: 2.2 - if request.org_id: checar créditos; raise HTTPException(402) se insuficiente
    # ... stream existente continua
    pass
```

<details>
<summary>Ver solução completa</summary>

Antes de iniciar qualquer pesquisa, o backend verifica se a organização tem créditos suficientes:

```python
# backend/api.py

CREDITS_PER_RESEARCH_ESTIMATE = 5  # estimativa conservadora para verificação prévia
# O custo real é calculado após a pesquisa e debitado no /reports/save

async def check_credits(org_id: str) -> bool:
    """Verifica se a org tem créditos suficientes para uma pesquisa."""
    db = get_supabase()
    result = db.table("org_credits").select("credits_balance").eq("org_id", org_id).execute()

    if not result.data:
        return False

    return result.data[0]["credits_balance"] >= CREDITS_PER_RESEARCH_ESTIMATE


@app.post("/research/stream")
async def research_stream(request: ResearchRequest):
    # Verificar créditos antes de iniciar (se org_id for fornecido)
    if request.org_id:
        has_credits = await check_credits(request.org_id)
        if not has_credits:
            raise HTTPException(
                status_code=402,  # 402 Payment Required
                detail="Insufficient credits. Please upgrade your plan."
            )

    async def event_stream():
        # ... código existente do stream
        pass

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

> **Por que 402 e não 403?** HTTP 402 "Payment Required" foi definido para exatamente este caso — acesso negado por falta de pagamento, não por falta de autorização. 403 significa "você não tem permissão independente de pagar".

---

</details>

- [ ] **Step 2.1: `check_credits()` retorna `False` quando `credits_balance = 0`.**
- [ ] **Step 2.2: `POST /research/stream` com org sem créditos retorna HTTP 402 sem iniciar stream.**
- [ ] **Step 2.3: `CREDITS_PER_RESEARCH_ESTIMATE` é constante nomeada visível no topo de `billing.py`.**
- [ ] **Step 2.4: `POST /research/stream` com org com créditos suficientes continua funcionando normalmente.**

### Resumo
> *Preencher apos concluir a task: o que foi alterado, qual verificacao passou, e qual risco ainda merece atencao?*

---
## Task 3: `backend/billing.py` - Débito de Créditos após Pesquisa

**Estimativa:** ~1h

**O que é e por que existe**

Implementa `debit_credits(org_id, research_id, token_count)` que chama a função SQL atômica da Task 1 e registra a transação no ledger. O débito ocorre após a pesquisa terminar, quando o token count real é conhecido.

**Files:**
- Criar/Editar: `backend/billing.py`

---

### Conceito: SELECT + UPDATE em Python ≠ atômico — race condition em requests concorrentes
> Fazer `SELECT balance → check → UPDATE` em dois roundtrips Python cria uma janela de tempo entre o SELECT e o UPDATE. Se duas pesquisas terminarem ao mesmo tempo para a mesma org, ambas leem o mesmo saldo suficiente e ambas debitam — resultado: saldo negativo e duas pesquisas foram feitas com crédito de uma. A função SQL da Task 1 resolve isso executando o `UPDATE WHERE balance >= credits` como operação única.
>
> | Abordagem | Passos | Race condition possível? |
> |---|---|---|
> | SELECT → check → UPDATE em Python | 3 roundtrips separados | Sim — janela entre SELECT e UPDATE |
> | `UPDATE WHERE balance >= p_credits` em SQL | 1 roundtrip atômico | Não — banco trava a linha |
>
> O `math.ceil` no cálculo de créditos garante que pesquisas que consomem fração de crédito são arredondadas para cima — não para baixo.

---

### Documentação
- https://supabase.com/docs/reference/python/rpc - `supabase.rpc("function_name", params)` para chamar funções SQL.
- https://docs.python.org/3/library/math.html#math.ceil - `math.ceil()` para arredondamento para cima.

---

### O que você precisa fazer

**Passo 3.1 — Calcular créditos a debitar com `math.ceil(token_count / 10_000)`**
Intent: 1 crédito = 10.000 tokens; pesquisa que usa 18.001 tokens custa 2 créditos (não 1).
Consequência: usar `//` (divisão inteira) truncaria para baixo — o produto perderia receita.
→ `credits_to_debit = math.ceil(token_count / 10_000)`

**Passo 3.2 — Chamar `debit_credits_atomic` via `supabase.rpc()`**
Intent: o débito deve ser atômico — uma única operação SQL.
Consequência: chamar SELECT + UPDATE em Python separadamente cria race condition (ver conceito).
→ `result = db.rpc("debit_credits_atomic", {"p_org_id": org_id, "p_credits": credits_to_debit}).execute()`

**Passo 3.3 — Registrar a transação no ledger `credit_transactions`**
Intent: cada débito deve ter registro imutável com `balance_after` para auditoria.
Consequência: sem o ledger, é impossível responder "quando esse crédito foi consumido?" em disputas de billing.
→ `supabase.table("credit_transactions").insert({..., "type": "consume", "amount": -credits_to_debit, "balance_after": new_balance})`

**Passo 3.4 — Chamar `debit_credits` a partir de `POST /reports/save` após o stream terminar**
Intent: o débito deve acontecer só após `done` — quando o token count real está disponível.
Consequência: debitar na estimativa prévia (Task 2) cobra sempre 5 créditos mesmo para pesquisas mais baratas.
→ No handler de `/reports/save`, após salvar o relatório, chamar `debit_credits(org_id, research_id, token_count)`.

### Esqueleto

```python
# backend/billing.py
import math

def debit_credits(org_id: str, research_id: str, token_count: int) -> int:
    # TODO: 3.1 - credits_to_debit = math.ceil(token_count / 10_000)
    # TODO: 3.2 - db.rpc("debit_credits_atomic", {p_org_id, p_credits}).execute()
    # TODO: 3.2 - extrair new_balance de result.data
    # TODO: 3.3 - INSERT em credit_transactions com type='consume', amount=-credits_to_debit, balance_after
    # TODO: retornar new_balance
    pass
```

<details>
<summary>Ver solução completa</summary>

O débito acontece **após** a pesquisa terminar, quando o token count real é conhecido:

```python
# backend/api.py

def debit_credits(org_id: str, research_id: str, token_count: int) -> int:
    """Debita créditos proporcionais ao uso de tokens.

    Returns:
        Saldo restante após o débito.
    """
    # Arredonda para cima: 18.001 tokens = 2 créditos (não 1)
    credits_to_debit = math.ceil(token_count / 10_000)

    db = get_supabase()

    # UPDATE atômico: debita e retorna o novo saldo numa única query
    # Isso evita race conditions se duas pesquisas terminarem ao mesmo tempo
    result = db.rpc("debit_credits_atomic", {
        "p_org_id": org_id,
        "p_credits": credits_to_debit,
    }).execute()

    new_balance = result.data["new_balance"]

    # Registra no ledger
    db.table("credit_transactions").insert({
        "org_id": org_id,
        "research_id": research_id,
        "type": "consume",
        "amount": -credits_to_debit,
        "balance_after": new_balance,
        "description": f"{token_count} tokens consumed",
    }).execute()

    return new_balance
```

Crie a função atômica no Supabase:

```sql
-- Função SQL para débito atômico (evita race conditions)
CREATE OR REPLACE FUNCTION debit_credits_atomic(p_org_id UUID, p_credits INTEGER)
RETURNS JSON AS $$
DECLARE
  v_new_balance INTEGER;
BEGIN
  UPDATE org_credits
  SET
    credits_balance = credits_balance - p_credits,
    updated_at = now()
  WHERE org_id = p_org_id
    AND credits_balance >= p_credits  -- só atualiza se tiver saldo
  RETURNING credits_balance INTO v_new_balance;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'Insufficient credits';
  END IF;

  RETURN json_build_object('new_balance', v_new_balance);
END;
$$ LANGUAGE plpgsql;
```

> **Por que uma função SQL para o débito?** O débito de créditos é uma operação crítica — precisa ser atômica. Se você fizer `SELECT balance → check → UPDATE` em Python, há uma janela de tempo entre o SELECT e o UPDATE onde outra requisição pode debitar o mesmo saldo (race condition). A função SQL executa como uma transação atômica, eliminando esse risco.

---

</details>

- [ ] **Step 3.1: Pesquisa com 18.001 tokens debita 2 créditos (não 1).**
- [ ] **Step 3.2: `debit_credits_atomic` chamada via RPC; retorna `new_balance` correto.**
- [ ] **Step 3.3: `credit_transactions` tem linha com `type='consume'` e `balance_after` igual ao saldo resultante.**
- [ ] **Step 3.4: Débito acontece em `/reports/save`, não no stream; token count real (não estimativa) é usado.**

### Resumo
> *Preencher apos concluir a task: o que foi alterado, qual verificacao passou, e qual risco ainda merece atencao?*

---
## Task 4: `backend/billing.py` - Integração com Stripe

**Estimativa:** ~1.5h

**O que é e por que existe**

Implementa `create_checkout_session()`, o handler `POST /stripe/webhook` com verificação de assinatura e deduplicação por `event_id`. O webhook é onde créditos são adicionados — não a `success_url`.

**Files:**
- Criar/Editar: `backend/billing.py`

---

### Conceito: Webhook como fonte confiável — não a success_url do checkout
> O Stripe Checkout redireciona para a `success_url` quando o usuário clica em "Pay". Mas o redirecionamento acontece antes da confirmação do pagamento — pode ser interceptado ou disparado acidentalmente. O webhook `checkout.session.completed` é disparado pelo Stripe somente depois que o pagamento é processado e confirmado. Nunca credite a org na `success_url`.
>
> | Evento | Quando dispara | Confiável para creditar? |
> |---|---|---|
> | `success_url` redirect | Após clique do usuário | Não — antes da confirmação |
> | `checkout.session.completed` webhook | Após pagamento confirmado pelo Stripe | Sim — fonte autoritativa |
> | `customer.subscription.deleted` webhook | Após cancelamento | Sim — para revogar acesso |
>
> Antes de processar qualquer webhook, verificar a assinatura com `stripe.Webhook.construct_event()` garante que o evento veio do Stripe, não de um atacante.

---

### Documentação
- https://docs.stripe.com/webhooks - eventos, assinatura e deduplicação por `event["id"]`.
- https://docs.stripe.com/api/checkout/sessions/create - parâmetros de `stripe.checkout.Session.create()`.

---

### O que você precisa fazer

**Passo 4.1 — Criar `create_checkout_session()` com `metadata` contendo `org_id` e `plan`**
Intent: o webhook precisa saber qual org e qual plano creditar — isso vem do `metadata`.
Consequência: sem `metadata`, o webhook recebe `checkout.session.completed` mas não sabe qual org promover.
→ `session = stripe.checkout.Session.create(..., metadata={"org_id": org_id, "plan": plan})`

**Passo 4.2 — Verificar assinatura do webhook com `stripe.Webhook.construct_event()`**
Intent: garantir que o payload veio do Stripe, não de um atacante enviando eventos falsos.
Consequência: sem verificação, qualquer pessoa pode enviar um POST para `/stripe/webhook` com `event_id` falso e ganhar créditos.
→ `event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)`

**Passo 4.3 — Deduplicar por `event["id"]` antes de processar**
Intent: o Stripe pode reenviar o mesmo evento em caso de falha de entrega — processar duas vezes cobra créditos duplos.
Consequência: sem deduplicação, `stripe trigger checkout.session.completed` reenviado credita a org duas vezes.
→ Verificar se `event["id"]` já existe em `stripe_events` antes de processar; inserir após processar.

**Passo 4.4 — Processar `checkout.session.completed` creditando org e atualizando `org_billing`**
Intent: após pagamento confirmado, atualizar plano em `organizations`, créditos em `org_credits` e dados Stripe em `org_billing`.
Consequência: atualizar só `org_billing` sem atualizar `org_credits` deixa a org sem créditos mesmo após pagar.
→ `upsert` em `org_billing` + `upsert` em `org_credits` + `update` em `organizations`; tudo na mesma função.

### Esqueleto

```python
# backend/billing.py
import stripe, os

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
PLAN_PRICES = {"starter": os.getenv("STRIPE_PRICE_STARTER"), "pro": os.getenv("STRIPE_PRICE_PRO")}
CREDITS_BY_PLAN = {"starter": 100, "pro": 500}

def create_checkout_session(org_id: str, plan: str, success_url: str, cancel_url: str) -> str:
    # TODO: 4.1 - stripe.checkout.Session.create com mode="subscription", metadata={org_id, plan}
    # TODO: 4.1 - buscar stripe_customer_id existente de org_billing e passar como customer=
    # TODO: retornar session.url
    pass

# backend/api.py
@app.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    # TODO: 4.2 - stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)
    # TODO: 4.3 - checar se event["id"] já em stripe_events; se sim, return {"received": True}
    # TODO: 4.4 - se checkout.session.completed: upsert org_billing + org_credits + organizations
    # TODO: 4.4 - se customer.subscription.deleted: update org_billing status="canceled"
    # TODO: inserir event["id"] em stripe_events após processar
    pass
```

<details>
<summary>Ver solução completa</summary>

### Setup

```bash
pip install stripe
# Adicionar ao pyproject.toml: stripe>=11.0.0
```

```bash
STRIPE_SECRET_KEY=sk_test_...       # use sk_test em desenvolvimento; nunca exponha ao frontend
STRIPE_WEBHOOK_SECRET=whsec_...     # para verificar assinatura dos webhooks
STRIPE_PRICE_STARTER=price_xxx      # ID do price no Stripe Dashboard
STRIPE_PRICE_PRO=price_yyy
```

### Criar sessão de checkout

```python
# backend/billing.py
import stripe
import os

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

PLAN_PRICES = {
    "starter": os.getenv("STRIPE_PRICE_STARTER"),
    "pro": os.getenv("STRIPE_PRICE_PRO"),
}

def create_checkout_session(org_id: str, plan: str, success_url: str, cancel_url: str) -> str:
    """Cria uma sessão de checkout no Stripe.

    Returns:
        URL da página de checkout hospedada pelo Stripe.
    """
    db = get_supabase()

    # Busca ou cria o customer Stripe para esta org
    billing = db.table("org_billing").select("stripe_customer_id").eq("org_id", org_id).execute()
    customer_id = billing.data[0].get("stripe_customer_id") if billing.data else None

    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": PLAN_PRICES[plan], "quantity": 1}],
        success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=cancel_url,
        metadata={"org_id": org_id, "plan": plan},
    )

    return session.url
```

### Webhook — processar eventos do Stripe

O Stripe envia eventos assincronos (pagamento confirmado, assinatura cancelada). O webhook e onde voce reage a esses eventos.

Antes de escrever o codigo abaixo, crie uma coluna ou tabela para registrar `stripe_event_id` processado. Webhooks podem ser reenviados pela Stripe; se voce nao deduplicar por `event["id"]`, pode creditar a mesma organizacao duas vezes.

```python
# backend/api.py
from fastapi import Request

@app.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        # Verifica a assinatura do webhook — garante que veio do Stripe, não de um atacante
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.getenv("STRIPE_WEBHOOK_SECRET")
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    db = get_supabase()

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        org_id = session["metadata"]["org_id"]
        plan = session["metadata"]["plan"]
        customer_id = session["customer"]
        subscription_id = session["subscription"]

        # Atualiza o plano e vincula o customer Stripe
        db.table("org_billing").upsert({
            "org_id": org_id,
            "stripe_customer_id": customer_id,
            "stripe_subscription_id": subscription_id,
            "plan": plan,
            "status": "active",
        }).execute()

        # Atualiza o plano na tabela organizations
        db.table("organizations").update({"plan": plan}).eq("id", org_id).execute()

        # Adiciona os créditos do plano
        credits_by_plan = {"starter": 100, "pro": 500}
        credits = credits_by_plan.get(plan, 0)
        db.table("org_credits").upsert({
            "org_id": org_id,
            "credits_balance": credits,
            "credits_included": credits,
        }).execute()

    elif event["type"] == "customer.subscription.deleted":
        # Assinatura cancelada — reverte para free
        customer_id = event["data"]["object"]["customer"]
        db.table("org_billing").update({"plan": "free", "status": "canceled"}).eq(
            "stripe_customer_id", customer_id
        ).execute()

    return {"received": True}
```

> **Por que processar billing via webhook e não na resposta do checkout?** A sessão de checkout retorna uma `success_url` imediatamente quando o usuário clica em "Pay". Mas o pagamento pode ainda não ter sido processado. O webhook é disparado só quando o Stripe confirma que o pagamento foi recebido — é a fonte confiável.

---

</details>

- [ ] **Step 4.1: `create_checkout_session()` retorna URL do Stripe Checkout com `metadata.org_id` e `metadata.plan`.**
- [ ] **Step 4.2: Webhook com assinatura inválida retorna HTTP 400 sem processar.**
- [ ] **Step 4.3: `stripe trigger checkout.session.completed` reenviado duas vezes credita a org apenas uma vez.**
- [ ] **Step 4.4: Após `checkout.session.completed`: `org_billing.plan` atualizado + `org_credits.credits_balance` correto + `organizations.plan` atualizado.**

### Resumo
> *Preencher apos concluir a task: o que foi alterado, qual verificacao passou, e qual risco ainda merece atencao?*

---
## Task 5: `frontend/src/pages/Billing.tsx` - Dashboard de Billing no Frontend

**Estimativa:** ~45min

**O que é e por que existe**

Cria a página de billing com saldo de créditos, plano atual e botão de upgrade. O upgrade faz `POST /billing/checkout` e redireciona para a URL do Stripe Checkout — o frontend nunca toca dados de cartão.

**Files:**
- Criar/Editar: `frontend/src/pages/Billing.tsx`

---

### Conceito: Redirect para Stripe Checkout — não construir UI de cartão
> Construir um formulário de cartão de crédito próprio exige PCI DSS compliance — auditorias anuais, rede segmentada, criptografia de dados de cartão. O Stripe Checkout é uma UI hospedada pelo Stripe que já tem compliance PCI. O frontend faz um POST para o backend, recebe a URL do Checkout, e faz `window.location.href = url` — isso é tudo.
>
> | Abordagem | Responsabilidade de PCI | Tempo de implementação |
> |---|---|---|
> | UI de cartão própria | Da sua empresa — auditorias anuais | Semanas + compliance |
> | Redirect para Stripe Checkout | Do Stripe — você não toca dados de cartão | Horas |
>
> Nunca passe dados de cartão pelo seu backend. Se o frontend receber número de cartão, o servidor processa dados de pagamento — isso ativa PCI DSS.

---

### Documentação
- https://docs.stripe.com/checkout/quickstart - fluxo de redirect para Stripe Checkout com `session.url`.
- https://react.dev/reference/react/useState - `useState` + loading state para botão de upgrade.

---

### O que você precisa fazer

**Passo 5.1 — Buscar `plan` e `credits_balance` da org ao carregar a página**
Intent: o componente precisa saber o plano atual e o saldo para mostrar os cards corretos.
Consequência: sem buscar do banco, o componente mostra dados estáticos ou desatualizados após upgrade.
→ `useEffect` + `supabase.from('org_billing').select('plan').eq('org_id', ...)` + `supabase.from('org_credits').select('credits_balance')`

**Passo 5.2 — Implementar `handleUpgrade(plan)` que faz POST e redireciona**
Intent: o clique em "Upgrade" deve chamar o backend, receber a URL do Checkout, e redirecionar.
Consequência: redirecionar para uma URL hardcoded do Stripe sem sessão autenticada resulta em sessão inválida.
→ `fetch('/api/billing/checkout', {method: 'POST', ...})` → `const {url} = await response.json()` → `window.location.href = url`

**Passo 5.3 — Mostrar "Manage billing" para orgs já assinantes (plano não-free)**
Intent: orgs no Starter/Pro devem acessar o Customer Portal para cancelar ou mudar plano.
Consequência: sem o botão de manage, o usuário não consegue cancelar e fica preso no plano.
→ `{plan !== 'free' && <button onClick={handleManageBilling}>Manage billing</button>}`

**Passo 5.4 — Adicionar rota `/settings/billing` protegida pelo AuthGuard**
Intent: a página de billing é privada — somente usuários autenticados podem ver.
Consequência: rota fora do AuthGuard expõe dados de plano e créditos sem autenticação.
→ Adicionar `<Route path="/settings/billing" element={<Billing />} />` dentro do bloco do AuthGuard em `App.tsx`.

### Esqueleto

```typescript
// frontend/src/pages/Billing.tsx
import { useState, useEffect } from 'react'

export function Billing() {
  const [plan, setPlan] = useState<string>('free')
  const [credits, setCredits] = useState<number>(0)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    // TODO: 5.1 - buscar org_billing.plan e org_credits.credits_balance
  }, [])

  async function handleUpgrade(targetPlan: string) {
    setLoading(true)
    // TODO: 5.2 - POST /api/billing/checkout com {org_id, plan, success_url, cancel_url}
    // TODO: 5.2 - window.location.href = url
  }

  async function handleManageBilling() {
    // TODO: 5.3 - POST /api/billing/portal; window.location.href = url
  }

  return (
    <div>
      {/* TODO: 5.1 - mostrar plan e credits */}
      {/* TODO: 5.3 - {plan !== 'free' && <button>Manage billing</button>} */}
      {/* TODO: 5.2 - {plan === 'free' && cards de Starter e Pro com handleUpgrade} */}
    </div>
  )
}
```

<details>
<summary>Ver solução completa</summary>

```typescript
// src/pages/Settings.tsx (seção de billing)
import { useState } from 'react'

export function BillingSection({ orgId, plan, creditsBalance }: BillingProps) {
  const [loading, setLoading] = useState(false)

  async function handleUpgrade(targetPlan: string) {
    setLoading(true)
    const response = await fetch('/api/billing/checkout', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        org_id: orgId,
        plan: targetPlan,
        success_url: `${window.location.origin}/settings?upgraded=true`,
        cancel_url: `${window.location.origin}/settings`,
      }),
    })
    const { url } = await response.json()
    window.location.href = url  // redireciona para o Stripe Checkout
  }

  async function handleManageBilling() {
    // Abre o Stripe Customer Portal — o usuário gerencia assinatura e faturas lá
    const response = await fetch('/api/billing/portal', {
      method: 'POST',
      body: JSON.stringify({ org_id: orgId }),
    })
    const { url } = await response.json()
    window.location.href = url
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <div>
          <p className="font-medium">Current plan: {plan}</p>
          <p className="text-sm text-gray-500">{creditsBalance} credits remaining</p>
        </div>
        {plan !== 'free' && (
          <button onClick={handleManageBilling} className="text-sm underline">
            Manage billing
          </button>
        )}
      </div>

      {plan === 'free' && (
        <div className="grid grid-cols-2 gap-4">
          <PlanCard
            name="Starter"
            price="$29/mo"
            credits="100 credits/mo"
            onUpgrade={() => handleUpgrade('starter')}
            loading={loading}
          />
          <PlanCard
            name="Pro"
            price="$99/mo"
            credits="500 credits/mo + PAYG"
            onUpgrade={() => handleUpgrade('pro')}
            loading={loading}
          />
        </div>
      )}
    </div>
  )
}
```

---

</details>

- [ ] **Step 5.1: Página carrega `plan` e `credits_balance` reais do banco sem valores hardcoded.**
- [ ] **Step 5.2: Clicar em "Upgrade to Starter" redireciona para página do Stripe Checkout (URL `checkout.stripe.com/...`).**
- [ ] **Step 5.3: Org com `plan !== 'free'` vê botão "Manage billing"; org free não vê.**
- [ ] **Step 5.4: Rota `/settings/billing` sem login redireciona para `/login`.**

### Resumo
> *Preencher apos concluir a task: o que foi alterado, qual verificacao passou, e qual risco ainda merece atencao?*

---

## Resumo do Sprint 10

| Artefato | Responsabilidade | Risco crítico |
|---|---|---|
| Schema (`org_credits`, `credit_transactions`, `org_billing`) | Persistência de billing | CHECK constraint em `credits_balance >= 0` |
| `debit_credits_atomic` (SQL function) | Débito sem race condition | Transação atômica |
| `check_credits` antes do stream | Gate de créditos | HTTP 402 antes de consumir |
| Stripe Checkout | UI de pagamento | Nunca processar cartão diretamente |
| Webhook `checkout.session.completed` | Creditar após pagamento confirmado | Verificar assinatura do webhook |
| Customer Portal | Gerenciamento de assinatura | Usar portal Stripe — não construir do zero |

**Critério de conclusão:** um usuário Free consegue fazer upgrade para Starter via Stripe Checkout, os créditos aparecem no dashboard, e uma pesquisa debita créditos corretamente com registro no ledger de transações.

## Solo Developer Ready

- [ ] Stripe esta em test mode e nenhuma `sk_live_` foi usada.
- [ ] `stripe_events.event_id` impede processar webhook duplicado.
- [ ] Debito de creditos e atomico no banco.
- [ ] `STRIPE_SECRET_KEY` e `STRIPE_WEBHOOK_SECRET` ficam somente no backend.
- [ ] Stripe CLI reenviou evento e os creditos foram atualizados uma unica vez.
