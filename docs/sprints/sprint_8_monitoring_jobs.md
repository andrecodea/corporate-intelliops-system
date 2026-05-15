# Sprint 8 — Monitoring Jobs Engine: Guia Instrucional

## Contexto e Objetivo

Este sprint foi normalizado para seguir a skill `sprint-writing`. O conteudo original foi preservado como solução completa e deve ser usado depois das fases de exploracao e prototipo.

## Pré-requisitos para desenvolver sozinho

- Sprint 7 concluído: tabelas `entities`, `dossiers`, `entity_drafts`, endpoint `/entities/graph` e aba Jobs placeholder no dossier.
- Supabase configurado com as migrations anteriores.
- Backend rodando em `http://localhost:8005`.
- Plano detalhado aberto ao lado: `docs/superpowers/plans/2026-04-08-sprint-8-monitoring-jobs.md`.

**Como testar sem esperar cron real:** depois de criar um job, force a execução chamando `run_monitoring_job(job_id)` em um script temporário local. Só use cron real depois que a execução manual criar `job_runs` corretamente.

**Risco principal:** APScheduler em memória executa dentro do processo FastAPI. Em produção com múltiplas réplicas, o mesmo job pode rodar mais de uma vez. Para este MVP, rode uma única instância e recarregue jobs ativos no startup.

---

## Task 1: `docs/superpowers/plans/2026-04-08-sprint-8-monitoring-jobs.md` - Executar plano detalhado do sprint

**Estimativa:** ~30min

**O que é e por que existe**

Esta task transforma o sprint conceitual em uma unidade executavel. O plano detalhado em `docs/superpowers/plans/` contem o passo a passo granular; este arquivo mantem o contrato pedagogico exigido pela skill.

**Files:**
- Criar/Editar: ver plano detalhado em `docs/superpowers/plans/2026-04-08-sprint-8-monitoring-jobs.md` e os arquivos citados na solução completa.

---

### Conceito: Plano detalhado como solucao, sprint como contrato pedagogico
> O documento de sprint explica por que a arquitetura existe; o plano detalhado explica como implementar. A skill exige os dois em ordem: conceito antes do codigo, esqueleto antes da solucao. Sem essa separacao, agentes pulam direto para copiar codigo sem validar premissas.

---

### Documentação
- https://fastapi.tiangolo.com/ - referencia para endpoints backend.
- https://supabase.com/docs - referencia para banco, RLS e autenticacao.
- https://react.dev/ - referencia para componentes React planejados.

---

### O que você precisa fazer

1. Leia o conteudo conceitual preservado abaixo.
2. Abra `docs/superpowers/plans/2026-04-08-sprint-8-monitoring-jobs.md` e divida a execucao em etapas pequenas.
3. Prototipe a parte mais arriscada antes de integrar tudo.
4. Implemente task-by-task e marque os checkboxes do plano detalhado.

### Esqueleto

```text
# TODO: Explore - ler conceitos e plano detalhado.
# TODO: Prototype - validar a parte de maior risco em isolamento.
# TODO: Implement - executar o plano task-by-task.
# TODO: Verify - testar backend, frontend e persistencia conforme o plano.
```

<details>
<summary>Ver solução completa</summary>

## Contexto e Objetivo

O Sprint 8 transforma o IntelliOps de uma ferramenta de consulta pontual para uma **plataforma de inteligência contínua**. O usuário configura jobs que rodam automaticamente em background, pesquisam uma entidade em intervalos definidos, e só notificam quando encontram algo novo — sem spam.

**Spec completo:** [`docs/superpowers/specs/2026-04-08-intelligence-terminal-design.md`](../superpowers/specs/2026-04-08-intelligence-terminal-design.md)
**Plano de implementação:** [`docs/superpowers/plans/2026-04-08-sprint-8-monitoring-jobs.md`](../superpowers/plans/2026-04-08-sprint-8-monitoring-jobs.md)

**Pré-requisito:** Sprint 7 concluído — tabelas `entities`, `dossiers`, e a aba Jobs no dossier (atualmente com placeholder).

---

## Conceito Central: Cron + LLM como Filtro de Relevância

Um job de monitoramento tem dois componentes independentes:

1. **Scheduler (APScheduler):** "rode isso no horário X" — sem inteligência, puramente mecânico
2. **LLM judge (Haiku-4.5):** "o que foi encontrado é novo e relevante?" — a inteligência

Separá-los é importante. O scheduler não sabe nada sobre o conteúdo — só dispara. O LLM não sabe nada sobre agendamento — só avalia. Essa separação de responsabilidades é o **Single Responsibility Principle** aplicado à arquitetura.

```
APScheduler (cron)
      │
      ▼
research-agent pesquisa entidade
      │
      ▼
Haiku-4.5 compara resultado com dossier atual
      │
      ├── had_updates = true  → gera sumário → notifica → HITL
      └── had_updates = false → registra 'skipped' → silêncio
```

---

## Padrão: APScheduler no FastAPI

APScheduler é uma biblioteca Python que gerencia jobs agendados dentro do processo FastAPI. Não precisa de Redis, Celery, ou infraestrutura separada — roda no mesmo servidor.

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

@app.on_event("startup")
async def start_scheduler():
    scheduler.start()

@app.on_event("shutdown")
async def stop_scheduler():
    scheduler.shutdown()
```

Quando um usuário cria um job, o backend adiciona dinamicamente um job ao scheduler:

```python
scheduler.add_job(
    func=run_monitoring_job,
    trigger="cron",
    id=f"job_{job_id}",
    **parse_cron(cron_expr),   # converte '0 9 * * 1' em kwargs
    args=[job_id],
)
```

**Limitação importante:** APScheduler em memória perde os jobs se o servidor reiniciar. Para produção, usar `APScheduler` com `SQLAlchemyJobStore` (persiste os jobs no banco). Para o MVP, recarregar os jobs ativos do Supabase no `startup` é suficiente.

---

## Padrão: LLM-as-Judge com Score por Dimensão

O juiz não responde "sim ou não" — responde com um score estruturado:

```json
{
  "content_score": 0.85,
  "source_score": 0.70,
  "relevance_score": 0.90,
  "summary": "Elon Musk anunciou reestruturação da liderança de engenharia...",
  "reasoning": "A informação sobre Tom Zhu assumindo operações globais não consta no dossier atual."
}
```

- **`content_score`**: os campos esperados para o modo foram cobertos?
- **`source_score`**: o agente foi às fontes certas? (SEC filings, Reuters, etc.)
- **`relevance_score`**: o resultado contém algo que não está no dossier atual?

Score geral = média ponderada. Abaixo de 0.6 → `had_updates = false`, sem notificação.

### Por que Haiku para o juiz?

O juiz recebe dois textos (dossier atual + novo resultado) e devolve um JSON com scores. É uma **comparação estruturada** — não requer raciocínio profundo. Haiku é ~10x mais barato que Sonnet e perfeitamente capaz para isso.

Sonnet só entra em escalada: se `relevance_score` ficar abaixo do threshold mas acima de um limiar de incerteza, o Sonnet faz uma segunda avaliação. Esse padrão se chama **escalada por fallback** — Haiku cobre o caminho feliz, Sonnet resolve os casos difíceis.

### Seleção de modelo: determinística, não por router

```python
JUDGE_MODEL = {
    "content_score":    "claude-haiku-4-5-20251001",
    "source_score":     "claude-haiku-4-5-20251001",
    "relevance_score":  "claude-haiku-4-5-20251001",
}
```

Um LLM router adicionaria uma chamada extra só para decidir qual modelo usar — você gastaria tokens decidindo, antes de gastar tokens avaliando. Para tasks com tipo conhecido em tempo de execução, a decisão vai no código, não num modelo.

---

## Padrão: HITL de Updates

Quando o job encontra novidade, o update **não é aplicado automaticamente ao dossier**. O usuário recebe uma notificação (Slack ou email) com o sumário e dois botões:

- **"Aplicar ao dossier"** → `POST /jobs/{job_id}/runs/{run_id}/apply`
- **"Ignorar"** → `POST /jobs/{job_id}/runs/{run_id}/dismiss`

Por que HITL aqui também? LLMs podem identificar como "novidade" algo que é irrelevante para aquele usuário específico. O HITL garante que o dossier só cresce com informação curada. O `version` do dossier é incrementado a cada aplicação aprovada — você sempre sabe quantas vezes o dossier foi atualizado.

---

## Modelo de Dados do Sprint 8

Duas tabelas novas, ambas com RLS:

### `monitoring_jobs`
```sql
id          uuid PK
user_id     uuid FK → auth.users
entity_id   uuid FK → entities
cron_expr   text    -- '0 9 * * 1' = toda segunda às 9h
mode        text    -- modo de pesquisa (Competitor Intel, etc.)
notify_slack bool
notify_email bool
active      bool
created_at  timestamptz
```

### `job_runs`
```sql
id          uuid PK
job_id      uuid FK → monitoring_jobs
status      text  -- 'running' | 'done' | 'skipped' | 'error'
had_updates bool  -- false = LLM não achou novidades
summary     text  -- sumário do update (se had_updates = true)
run_at      timestamptz
```

O `status = 'skipped'` é o registro silencioso: o job rodou, avaliou, não encontrou novidade, e não incomodou o usuário. Isso é rastreável no histórico mas invisível nas notificações.

---

## Notificações: Slack e Email

### Slack (já integrado)

O produto já tem `SLACK_BOT_TOKEN` e `SLACK_CHANNEL_ID` para exportar PDFs. O Sprint 8 reutiliza essa integração para enviar mensagens de atualização:

```python
from slack_sdk import WebClient

def notify_slack(summary: str, entity_name: str, run_id: str):
    client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])
    client.chat_postMessage(
        channel=os.environ["SLACK_CHANNEL_ID"],
        text=f"*{entity_name}* — nova atualização detectada",
        blocks=[...]  # sumário + botões Apply/Dismiss
    )
```

### Email (Resend)

Resend é uma API de email moderna com SDK Python. O free tier cobre 3.000 emails/mês — suficiente para o MVP.

```python
import resend

resend.api_key = os.environ["RESEND_API_KEY"]

resend.Emails.send({
    "from": "updates@yourdomain.com",
    "to": user_email,
    "subject": f"{entity_name} — nova atualização",
    "html": render_update_email(entity_name, summary, run_id),
})
```

---

## Frequências Disponíveis e Cron Expressions

| UI | cron_expr | Significado |
|---|---|---|
| Diário (9h) | `0 9 * * *` | Todo dia às 9h |
| Semanal (seg 9h) | `0 9 * * 1` | Toda segunda às 9h |
| Quinzenal | `0 9 1,15 * *` | Dias 1 e 15 do mês às 9h |
| Mensal | `0 9 1 * *` | Todo dia 1 do mês às 9h |

O frontend exibe um dropdown com essas opções — o usuário nunca precisa escrever cron manualmente. O backend converte a opção selecionada para a `cron_expr` correspondente.

---

## Critério de Conclusão

1. Usuário cria um job de monitoramento na aba Jobs do dossier
2. Job aparece como ativo com frequência e próximo run
3. Job roda no horário configurado (testar com `0 * * * *` = a cada hora)
4. Se encontrar novidade: sumário aparece na aba Jobs + notificação Slack/email
5. Botões "Aplicar ao dossier" e "Ignorar" funcionam
6. Se não encontrar novidade: `job_runs` registra `had_updates=false`, sem notificação

</details>

- [ ] **Step 1.1: Ler conceitos deste sprint e o plano detalhado correspondente.**
- [ ] **Step 1.2: Prototipar a integracao de maior risco antes da implementacao completa.**
- [ ] **Step 1.3: Executar as tasks do plano detalhado em ordem.**
- [ ] **Step 1.4: Verificar o criterio de conclusao do sprint.**

### Resumo
> *Preencher apos concluir a task: quais partes do plano foram implementadas, verificadas e ainda tem risco?*

---

## Task 2: `supabase/migrations/003_monitoring.sql` - Criar schema de jobs

**Estimativa:** ~30min

**O que é e por que existe**

Esta task cria as tabelas que permitem monitoramento continuo. Jobs definem o que deve rodar; runs registram cada execucao, inclusive quando nada relevante foi encontrado.

**Files:**
- Criar/Editar: `supabase/migrations/003_monitoring.sql`
- Consultar: `supabase/migrations/README.md`

---

### Conceito: agendamento e historico sao dados diferentes
> `monitoring_jobs` guarda a configuracao atual; `job_runs` guarda fatos historicos. Separar os dois evita sobrescrever evidencia e permite auditar quando um job rodou, falhou ou decidiu ficar silencioso.

---

### Documentação
- https://supabase.com/docs/guides/database - referencia de banco Supabase.
- https://www.postgresql.org/docs/current/ddl-constraints.html - referencia de constraints.

---

### O que você precisa fazer

1. Crie `monitoring_jobs` com `entity_id`, `mode`, `cron_expr`, notificacoes e `active`.
2. Crie `job_runs` com `status`, `had_updates`, `summary`, erro e timestamps.
3. Adicione RLS por usuario.
4. Rode query de verificacao no Supabase.

### Esqueleto

```sql
-- TODO: criar monitoring_jobs
-- TODO: criar job_runs
-- TODO: adicionar FK para entities
-- TODO: habilitar RLS
-- TODO: criar indices por user_id, entity_id e job_id
```

<details>
<summary>Ver solução completa</summary>

Verificacao minima:

```sql
select table_name
from information_schema.tables
where table_schema = 'public'
  and table_name in ('monitoring_jobs', 'job_runs');
```

O resultado esperado sao duas linhas.

</details>

- [ ] **Step 2.1: Migration `003_monitoring.sql` criada.**
- [ ] **Step 2.2: `monitoring_jobs` e `job_runs` existem.**
- [ ] **Step 2.3: RLS habilitada.**
- [ ] **Step 2.4: Indices principais criados.**

### Resumo
> *Preencher apos concluir a task: qual schema de jobs foi criado e como foi verificado?*

---

## Task 3: `backend/scheduler.py` - Inicializar APScheduler

**Estimativa:** ~30min

**O que é e por que existe**

Esta task cria o mecanismo que dispara jobs em horario configurado. O scheduler nao decide relevancia; ele apenas chama o runner no momento certo.

**Files:**
- Criar/Editar: `backend/scheduler.py`
- Criar/Editar: `backend/api.py`

---

### Conceito: scheduler mecanico, inteligencia separada
> APScheduler deve saber quando rodar, nao o que e importante. A avaliacao de novidade fica no judge. Essa separacao evita acoplar cron, pesquisa e LLM em uma funcao impossivel de testar.

---

### Documentação
- https://apscheduler.readthedocs.io/ - referencia oficial do APScheduler.
- https://fastapi.tiangolo.com/advanced/events/ - referencia para startup/shutdown.

---

### O que você precisa fazer

1. Crie `AsyncIOScheduler`.
2. Inicie no startup do FastAPI e desligue no shutdown.
3. Recarregue jobs ativos do banco ao subir.
4. Garanta que o MVP rode com uma unica instancia FastAPI.

### Esqueleto

```python
scheduler = AsyncIOScheduler()

def load_active_jobs():
    # TODO: buscar jobs ativos no Supabase
    # TODO: registrar scheduler.add_job(...)
    pass
```

<details>
<summary>Ver solução completa</summary>

Teste sem esperar cron real:

```bash
uv run python -c "from backend.scheduler import scheduler; print(scheduler.running)"
```

Depois de subir a API, o scheduler deve estar iniciado. Em desenvolvimento com `--reload`, cuidado com execucao duplicada; documente se notar dois processos.

</details>

- [ ] **Step 3.1: Scheduler criado em modulo proprio.**
- [ ] **Step 3.2: Startup/shutdown registrados.**
- [ ] **Step 3.3: Jobs ativos recarregam no startup.**
- [ ] **Step 3.4: Risco de multiplas instancias documentado.**

### Resumo
> *Preencher apos concluir a task: como o scheduler inicia e como evita surpresa em dev?*

---

## Task 4: `backend/monitoring.py` - Executar job e julgar relevancia

**Estimativa:** ~1h

**O que é e por que existe**

Esta task implementa o coracao do Sprint 8: pesquisar uma entidade, comparar com dossier atual e decidir se ha novidade relevante.

**Files:**
- Criar/Editar: `backend/monitoring.py`
- Criar/Editar: `backend/monitoring_judge.py`

---

### Conceito: LLM-as-judge com registro silencioso
> Um job que nao encontra novidade ainda e uma execucao valida. Registrar `skipped` evita spam ao usuario e preserva auditoria. O judge deve retornar score estruturado, nao texto livre.

---

### Documentação
- https://docs.pydantic.dev/latest/ - referencia para validar saida estruturada.
- https://docs.anthropic.com/ - referencia para chamadas LLM, se Anthropic for usado.

---

### O que você precisa fazer

1. Crie `run_monitoring_job(job_id)`.
2. Carregue entidade, dossier e configuracao do job.
3. Rode pesquisa usando o modo configurado.
4. Julgue novidade com scores.
5. Salve `job_runs` como `done`, `skipped` ou `error`.

### Esqueleto

```python
def run_monitoring_job(job_id: str):
    # TODO: criar job_run running
    # TODO: pesquisar entidade
    # TODO: comparar com dossier
    # TODO: atualizar status e had_updates
    pass
```

<details>
<summary>Ver solução completa</summary>

Para testar sozinho, chame o runner manualmente:

```bash
uv run python -c "from backend.monitoring import run_monitoring_job; run_monitoring_job('JOB_ID_AQUI')"
```

Antes de usar cron real, confirme que essa chamada cria uma linha em `job_runs`.

</details>

- [ ] **Step 4.1: Runner cria `job_runs`.**
- [ ] **Step 4.2: Judge retorna scores estruturados.**
- [ ] **Step 4.3: `had_updates=false` vira `skipped`.**
- [ ] **Step 4.4: Erros sao registrados como `error`.**

### Resumo
> *Preencher apos concluir a task: qual job manual rodou e qual linha foi criada em `job_runs`?*

---

## Task 5: `backend/routers/jobs.py` - Criar endpoints de jobs

**Estimativa:** ~30min

**O que é e por que existe**

Esta task expoe criacao, listagem e acoes de jobs para o frontend. O contrato deve bater com `docs/api_contracts.md`.

**Files:**
- Criar/Editar: `backend/routers/jobs.py`
- Criar/Editar: `backend/api.py`
- Consultar: `docs/api_contracts.md`

---

### Conceito: comandos separados de leitura
> Criar/listar jobs e aplicar/descartar updates sao operacoes diferentes. Separar endpoints deixa permissao, payload e erro mais simples de entender e testar.

---

### Documentação
- https://fastapi.tiangolo.com/tutorial/bigger-applications/ - referencia para routers.
- https://fastapi.tiangolo.com/tutorial/path-params/ - referencia para path params.

---

### O que você precisa fazer

1. Crie `POST /jobs`.
2. Crie `GET /jobs`.
3. Crie `POST /jobs/{job_id}/runs/{run_id}/apply`.
4. Crie `POST /jobs/{job_id}/runs/{run_id}/dismiss`.
5. Registre o router no app.

### Esqueleto

```python
router = APIRouter(prefix="/jobs", tags=["jobs"])

@router.post("")
def create_job(payload: CreateJobRequest):
    # TODO: salvar job e registrar no scheduler
    pass
```

<details>
<summary>Ver solução completa</summary>

Verificacao minima:

```bash
uv run uvicorn backend.api:app --reload --port 8005
curl http://localhost:8005/docs
```

Confirme que os endpoints de jobs aparecem em `/docs` e que `POST /jobs` cria uma linha em `monitoring_jobs`.

</details>

- [ ] **Step 5.1: Router de jobs registrado.**
- [ ] **Step 5.2: `POST /jobs` cria job e agenda execucao.**
- [ ] **Step 5.3: `GET /jobs` lista jobs.**
- [ ] **Step 5.4: Apply/dismiss alteram run corretamente.**

### Resumo
> *Preencher apos concluir a task: quais endpoints foram criados e como foram testados?*

---

## Task 6: `frontend/src/components/JobsPanel.tsx` - UI de jobs no dossier

**Estimativa:** ~45min

**O que é e por que existe**

Esta task coloca monitoring dentro do fluxo natural do usuario: abrir um dossier, criar job, ver historico e aplicar ou ignorar novidades.

**Files:**
- Criar/Editar: `frontend/src/components/JobsPanel.tsx`
- Criar/Editar: `frontend/src/lib/api.ts`

---

### Conceito: configuracao simples, cron escondido
> O usuario nao deve escrever cron. A UI oferece frequencias humanas e o backend recebe uma escolha controlada. Isso reduz erro e evita jobs em horarios inesperados.

---

### Documentação
- https://react.dev/learn/managing-state - referencia para estado React.
- https://tanstack.com/query/latest - referencia para cache e mutations, se usado.

---

### O que você precisa fazer

1. Adicione aba Jobs ao dossier.
2. Mostre formulario com frequencia, modo e notificacoes.
3. Liste jobs ativos e historico de runs.
4. Ligue botoes apply/dismiss aos endpoints.

### Esqueleto

```tsx
function JobsPanel({ entityId }) {
  // TODO: carregar jobs
  // TODO: formulario de novo job
  // TODO: listar runs recentes
}
```

<details>
<summary>Ver solução completa</summary>

Comece com frequencias fixas:

```text
daily -> 0 9 * * *
weekly -> 0 9 * * 1
biweekly -> 0 9 1,15 * *
monthly -> 0 9 1 * *
```

O frontend pode mandar `frequency`; o backend traduz para cron.

</details>

- [ ] **Step 6.1: Aba Jobs aparece no dossier.**
- [ ] **Step 6.2: Criar job pela UI funciona.**
- [ ] **Step 6.3: Historico de runs aparece.**
- [ ] **Step 6.4: Apply/dismiss funcionam na UI.**

### Resumo
> *Preencher apos concluir a task: qual fluxo de jobs foi testado na interface?*

---

## Task 7: `backend/notifications.py` - Notificar sem spam

**Estimativa:** ~30min

**O que é e por que existe**

Esta task envia notificacoes somente quando o judge encontrou novidade relevante. Ela completa o loop de inteligencia continua sem transformar o produto em spam.

**Files:**
- Criar/Editar: `backend/notifications.py`
- Criar/Editar: `backend/monitoring.py`

---

### Conceito: notificacao e consequencia, nao log
> Todo job deve gerar registro em `job_runs`, mas nem todo registro deve virar notificacao. Notifique apenas `had_updates=true`, com resumo e acoes claras para aplicar ou descartar.

---

### Documentação
- https://api.slack.com/messaging/webhooks - referencia de mensagens Slack.
- https://resend.com/docs - referencia de envio de email via Resend.

---

### O que você precisa fazer

1. Crie funcoes `notify_slack` e/ou `notify_email`.
2. Chame notificacao apenas quando `had_updates=true`.
3. Inclua links ou ids para apply/dismiss.
4. Registre falha de notificacao sem perder `job_run`.

### Esqueleto

```python
def notify_update(run_id: str, summary: str):
    # TODO: se Slack habilitado, enviar mensagem
    # TODO: se email habilitado, enviar email
    # TODO: logar falhas sem quebrar run
    pass
```

<details>
<summary>Ver solução completa</summary>

Teste primeiro com Slack desabilitado e confirme que o job ainda termina. Depois habilite uma integracao por vez.

Resultado esperado:

```text
had_updates=false -> sem notificacao
had_updates=true -> resumo enviado + run continua salvo
falha Slack/email -> erro logado, run nao desaparece
```

</details>

- [ ] **Step 7.1: Notificacao so ocorre com `had_updates=true`.**
- [ ] **Step 7.2: Falha de notificacao nao apaga run.**
- [ ] **Step 7.3: Slack ou email testado em modo dev.**
- [ ] **Step 7.4: Apply/dismiss referenciam o run correto.**

### Resumo
> *Preencher apos concluir a task: qual canal foi testado e como voce evitou spam?*

## Solo Developer Ready

- [ ] Sprint 7 esta concluido e existe ao menos uma entidade com dossier.
- [ ] `003_monitoring.sql` foi aplicado no banco certo.
- [ ] Consigo chamar `run_monitoring_job(job_id)` manualmente.
- [ ] Uma execucao cria `job_runs` como `done`, `skipped` ou `error`.
- [ ] Notificacoes so disparam quando `had_updates=true`.
