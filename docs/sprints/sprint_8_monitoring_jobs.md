# Sprint 8 — Monitoring Jobs Engine: Guia Instrucional

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
