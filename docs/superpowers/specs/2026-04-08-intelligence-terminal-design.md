# Intelligence Terminal — Design Spec

**Data:** 2026-04-08  
**Sprints:** 7 (Terminal Base) e 8 (Monitoring Jobs)  
**Pré-requisito:** Sprint 6 (SaaS Frontend React + Supabase) concluído

---

## Visão

Transformar o IntelliOps de uma ferramenta de pesquisa pontual numa **plataforma de inteligência contínua**. O Intelligence Terminal é o fator WOW do produto: um grafo de entidades vivo, estilo Obsidian, onde cada nó é uma empresa, pessoa, ou organização pesquisada — com dossier acumulativo, conexões navegáveis, e jobs de monitoramento que mantêm tudo atualizado automaticamente.

O produto passa a ter três módulos distintos:

1. **Research** (atual) — entrada estruturada → relatório. Não muda.
2. **Intelligence Terminal** (novo, Sprint 7) — grafo de entidades + dossiers.
3. **Monitoring Engine** (novo, Sprint 8) — jobs cron que atualizam dossiers e notificam.

---

## Arquitetura Geral

```
┌─────────────────────────────────────────────────────┐
│                   React SaaS (Sprint 6)              │
│                                                      │
│  /research   →  Research Module (atual)              │
│  /terminal   →  Intelligence Terminal (novo)         │
│  /settings   →  Monitoring Jobs config (novo)        │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP / SSE
┌──────────────────────▼──────────────────────────────┐
│                   FastAPI Backend                    │
│                                                      │
│  POST /research/stream     (existente)               │
│  POST /entities/review     (novo — HITL gate)        │
│  GET  /entities/graph      (novo — carrega o grafo)  │
│  POST /jobs                (novo — cria job)         │
│  GET  /jobs                (novo — lista jobs)       │
└──────────────────────┬──────────────────────────────┘
                       │
         ┌─────────────┴──────────────┐
         │                            │
┌────────▼────────┐        ┌──────────▼──────────┐
│  LangGraph      │        │  APScheduler        │
│  Agent Pipeline │        │  Monitoring Engine  │
│                 │        │                     │
│  research-agent │        │  cron job runner    │
│  + extrator de  │        │  + LLM relevance    │
│    entidades    │        │    filter           │
└────────┬────────┘        └──────────┬──────────┘
         │                            │
         └─────────────┬──────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│                   Supabase                           │
│                                                      │
│  entities · relationships · dossiers                 │
│  monitoring_jobs · job_runs · entity_drafts          │
│  (+ tabelas existentes: researches, reports)         │
└─────────────────────────────────────────────────────┘
```

**Fluxo principal (Research → Terminal):**
1. Usuário roda uma pesquisa → relatório gerado normalmente
2. Em paralelo, extrator de entidades (Haiku-4.5) processa o relatório e gera rascunho JSON de nós + arestas
3. Frontend exibe rascunho para curadoria HITL — usuário confirma, edita ou descarta
4. Entidades aprovadas entram no grafo do Terminal

**Fluxo de monitoramento:**
1. APScheduler dispara job no horário configurado
2. Agente roda pesquisa sobre a entidade monitorada
3. LLM compara resultado com dossier atual — se relevante, gera sumário e notifica
4. Se sem novidade: registra como `skipped`, sem notificação

---

## Modelo de Dados (Supabase)

Todas as tabelas têm RLS por `org_id` ou `user_id`.

### `entities` — nós do grafo
```sql
id          uuid PK
org_id      uuid FK → orgs
type        text       -- 'company' | 'person' | 'event' | 'sector' | ...
name        text
metadata    jsonb      -- campos livres: founded, hq, ceo, revenue, etc.
created_at  timestamptz
updated_at  timestamptz
```

> `metadata` é `jsonb` livre — o LLM preenche os campos disponíveis sem schema rígido.
> Tipos de entidade são abertos: o agente classifica o que encontrar, filtros de UI controlam a visualização.

### `relationships` — arestas do grafo
```sql
id            uuid PK
org_id        uuid FK → orgs
from_entity   uuid FK → entities
to_entity     uuid FK → entities
type          text       -- 'competitor', 'acquired', 'invested_in', 'executive_of', ...
weight        float      -- força da relação (acumula a cada run que confirma)
metadata      jsonb
created_at    timestamptz
```

### `dossiers` — conteúdo acumulado por entidade
```sql
id            uuid PK
entity_id     uuid FK → entities
markdown      text       -- sumário acumulado gerado pelo LLM
sources       jsonb      -- lista de research_ids que contribuíram
version       int        -- incrementado a cada atualização
updated_at    timestamptz
```

### `entity_drafts` — rascunhos aguardando curadoria HITL
```sql
id            uuid PK
research_id   uuid FK → researches
draft         jsonb      -- { entities: [...], relationships: [...] }
status        text       -- 'pending' | 'approved' | 'discarded'
created_at    timestamptz
```

### `monitoring_jobs` — configuração dos jobs
```sql
id            uuid PK
user_id       uuid FK → auth.users
entity_id     uuid FK → entities
cron_expr     text       -- ex: '0 9 * * 1' (toda segunda às 9h)
mode          text       -- modo de pesquisa usado no job
notify_slack  bool
notify_email  bool
active        bool
created_at    timestamptz
```

### `job_runs` — histórico de execuções
```sql
id            uuid PK
job_id        uuid FK → monitoring_jobs
status        text       -- 'running' | 'done' | 'skipped' | 'error'
had_updates   bool       -- false = LLM não achou novidades relevantes
summary       text       -- sumário do que mudou (se had_updates = true)
run_at        timestamptz
```

---

## Pipeline de Extração de Entidades (HITL)

```
Relatório gerado (Markdown)
         │
         ▼
  Extrator de Entidades — Haiku-4.5
  Prompt estruturado → JSON
         │
         ▼
  entity_drafts (status: 'pending')
  {
    entities: [
      { name: "Tesla", type: "company", metadata: { ceo: "Elon Musk" } },
      { name: "Elon Musk", type: "person", metadata: { role: "CEO" } }
    ],
    relationships: [
      { from: "Elon Musk", to: "Tesla", type: "executive_of" }
    ]
  }
         │
         ▼
  Painel HITL no Frontend
  Usuário pode: ✓ Aprovar · ✗ Descartar · ✎ Editar · + Adicionar relação
         │
         ▼
  POST /entities/review
  Backend persiste aprovados em entities + relationships
```

**Decisões de design:**
- **Haiku-4.5 para extração** — task estruturada (JSON in, JSON out), não precisa do Sonnet. Mais barato e rápido.
- **Deduplicação automática** — antes de criar nó, backend verifica entidade com nome similar (`ilike '%name%'`). Se existir, sugere merge.
- **HITL não bloqueia o relatório** — curadoria aparece como badge/notificação: "3 entidades encontradas — revisar". O usuário lê o relatório normalmente.
- **Modo da pesquisa como contexto** — o extrator recebe o modo (ex: Leadership Intel) para classificar entidades com mais precisão.

---

## Intelligence Terminal — UI

### Interação

**Hover sobre nó → tooltip glass próximo ao nó**
- Painel semitransparente flutua adjacente ao nó (não fixo na tela)
- Linha tracejada conecta tooltip ao nó
- Conteúdo: nome, tags de tipo, sumário curto, nº de conexões e runs
- Rodapé: "clique para abrir dossier"

**Click no nó → split view**
- Grafo fica dimmed à esquerda (fundo)
- Painel dossier desliza da direita com abas: **Perfil / Conexões / Histórico / Jobs**
- Botão "✕" fecha o painel, grafo volta ao estado normal
- Botão "↗ Pesquisar" dispara nova pesquisa sobre aquela entidade

### Nós do grafo

- **Iniciais da entidade dentro do nó** (ex: "TI" para Tesla Inc, "EM" para Elon Musk)
- **Nome completo como label abaixo do nó** — resolve o problema de nomes longos
- **Cor do nó por tipo de entidade** — company (azul), person (roxo), org (verde), event (laranja)
- **Tamanho do nó proporcional ao `weight` acumulado** — entidades mais referenciadas ficam maiores
- **Espessura da aresta proporcional ao `weight` da relação**

### Filtros

Barra de filtros no canto inferior esquerdo (glass), toggles por tipo de entidade: `company`, `person`, `org`, `event`, etc.

### Dossier — abas

| Aba | Conteúdo |
|---|---|
| Perfil | Sumário acumulado, metadata estruturado, botões Monitorar / Pesquisar |
| Conexões | Lista de entidades relacionadas com tipo de relação e weight |
| Histórico | Timeline de runs que contribuíram para o dossier |
| Jobs | Jobs de monitoramento ativos, histórico de runs, criar novo job |

---

## Monitoring Jobs Engine

### Configuração (aba Jobs no dossier)

- Selecionar modo de pesquisa (dropdown)
- Selecionar frequência: Diário / Semanal / Quinzenal / Mensal (mapeia para cron expression)
- Canais de notificação: Email · Slack (ambos já integrados)
- Toggle "Só notificar se houver novidade" — ativa filtro LLM (recomendado por padrão)

### Filtro LLM de relevância

```
1. Job roda → agente pesquisa entidade com modo configurado
2. LLM recebe: dossier atual + resultado novo
   Prompt: "Há informação relevante que não está no dossier? Responda sim/não e justifique."
3a. Se relevante → gera sumário do update → notifica via Slack/email
3b. Se sem novidade → registra job_run com had_updates=false → silêncio
```

### HITL de updates

Quando o job encontra novidade, o update não é aplicado automaticamente ao dossier. O usuário recebe notificação com o sumário e decide:
- **"Aplicar ao dossier"** — dossier é atualizado, versão incrementada
- **"Ignorar"** — job_run registrado como descartado

---

## Revisão do Roadmap

| Sprint | Tema | Mudança |
|---|---|---|
| 1 | Calibration | sem mudança |
| 2 | New Intelligence Modes | sem mudança |
| 3 | Evals | sem mudança |
| 4 | Production Readiness | sem mudança |
| 5 | Report History & Search | sem mudança |
| 6 | SaaS Frontend (React) | sem mudança |
| **7** | **Intelligence Terminal — Base** | **novo** |
| **8** | **Monitoring Jobs Engine** | **novo** |
| 9 | Collaboration & Org | era Sprint 7 |
| 10 | Monetization | sem mudança |

### Sprint 7 — Intelligence Terminal Base
- Tabelas Supabase: `entities`, `relationships`, `dossiers`, `entity_drafts`
- Extrator de entidades pós-run (Haiku-4.5) + endpoint `POST /entities/review`
- Painel HITL de curadoria no frontend
- Endpoint `GET /entities/graph`
- Grafo D3.js: force-directed, iniciais + label abaixo, cor por tipo, tamanho por weight
- Hover → tooltip glass próximo ao nó
- Click → split view com dossier tabelado

### Sprint 8 — Monitoring Jobs Engine
- APScheduler integrado ao FastAPI
- Tabelas: `monitoring_jobs`, `job_runs`
- Aba Jobs no dossier: criar, pausar, remover jobs
- Filtro LLM de relevância pré-notificação
- Notificações Slack (existente) + email via Resend
- HITL de updates: "Aplicar ao dossier" / "Ignorar"

---

## Padrão de Avaliação — LLM-as-Judge

Inspirado no projeto [operation-public-notice](https://github.com/andrecodea/operation-public-notice). Aplicável em dois contextos: **Sprint 3 (Evals)** e **Sprint 8 (Monitoring Jobs)**.

### Dimensões de score

O juiz avalia 3 dimensões independentes, retornando um JSON estruturado:

```json
{
  "content_score": 0.85,
  "source_score": 0.70,
  "relevance_score": 0.90
}
```

| Dimensão | O que avalia | Quando é usado |
|---|---|---|
| `content_score` | Cobertura dos campos esperados para o modo (seções, citações, especificidade factual) | Evals (Sprint 3) + Monitoring Jobs |
| `source_score` | Autoridade e adequação das fontes ao modo — o agente foi às fontes certas? | Evals (Sprint 3) + Monitoring Jobs |
| `relevance_score` | Novidade do update em relação ao dossier existente | Só Monitoring Jobs |

**Score geral** = média ponderada das dimensões ativas. Threshold padrão: **0.6**. Abaixo disso:
- Em evals: aciona uma única tentativa de correção com feedback dos campos problemáticos
- Em monitoring jobs: descarta o update (registra como `skipped`)

### Validação de fontes (`source_score`)

O agente retorna as URLs consultadas (Tavily + Firecrawl). O juiz classifica cada URL por categoria e verifica se as categorias esperadas para o modo foram cobertas:

| Modo | Fontes esperadas |
|---|---|
| Competitor Intel | Relatórios anuais, SEC filings, earnings calls, Reuters/Bloomberg |
| Leadership Intel | Perfis profissionais, entrevistas, bios oficiais, LinkedIn |
| Funding & Deal | Crunchbase, PitchBook, SEC EDGAR, press releases de investimento |
| Due Diligence | Múltiplas das acima + regulatórias + reputacionais |
| Vendor Evaluation | Documentação técnica, G2/Gartner, casos de uso publicados |

Se `source_score` for baixo, o relatório é sinalizado mesmo que `content_score` seja alto — conteúdo bom baseado em fontes fracas é um falso positivo que o usuário precisa ver.

### Modelo por task (controle de custo)

| Task | Modelo | Motivo |
|---|---|---|
| Validar campos extraídos (`content_score`) | Haiku-4.5 | JSON in/out, critério objetivo |
| Classificar e validar fontes (`source_score`) | Haiku-4.5 | Lista de URLs → classificação por categoria |
| Julgar relevância de update (`relevance_score`) | Haiku-4.5 | Comparação texto vs dossier, critério claro |
| Julgar qualidade narrativa do relatório | Sonnet 4.6 | Requer compreensão contextual e nuance |

Haiku custa ~10x menos que Sonnet. As 3 dimensões de score rodam em Haiku — Sonnet só é acionado para julgamento qualitativo subjetivo, que é opcional e desligado por padrão nos evals automatizados.

### Seleção de modelo — determinístico com escalada por fallback

**Não usar LLM router.** Router resolve o problema de task type desconhecido em tempo de roteamento — não é o caso aqui. Cada chamada ao juiz é disparada por um evento de sistema com tipo conhecido. Um router adicionaria uma chamada LLM extra só para decidir qual modelo usar, aumentando custo e latência sem benefício.

O padrão adotado é **determinístico com escalada por fallback**:

```python
JUDGE_MODEL = {
    "content_score":     "claude-haiku-4-5-20251001",
    "source_score":      "claude-haiku-4-5-20251001",
    "relevance_score":   "claude-haiku-4-5-20251001",
    "narrative_quality": "claude-sonnet-4-6",   # opcional, off por padrão
}

def get_judge_model(task: str) -> str:
    return JUDGE_MODEL[task]
```

Fluxo de escalada:
```
Haiku avalia → score < threshold → escalada pontual para Sonnet
```

Haiku cobre o caminho feliz (maioria dos casos). Sonnet entra só quando Haiku retorna score abaixo do threshold — uma única tentativa de correção, sem loops. Isso mantém custo baixo sem abrir mão de qualidade nos casos difíceis.

**Quando um router faria sentido:** se o Terminal ganhar interface conversacional no futuro ("compare Tesla e Rivian", "explique esse dossier") — aí o tipo de query é imprevisível e roteamento dinâmico se justifica. Para o juiz estruturado atual, determinístico é a escolha correta.

### Princípios herdados do operation-public-notice

- **Correção única, sem loops** — uma tentativa de correção com feedback dos campos problemáticos. Se ainda falhar, registra como falha e segue.
- **Campos não encontrados retornam `null`**, nunca score forçado
- **Score por campo individual** disponível no output além do score agregado — permite diagnóstico preciso de onde o agente falhou

---

## Decisões de Arquitetura

| Decisão | Escolha | Alternativa descartada | Motivo |
|---|---|---|---|
| Storage do grafo | Supabase (PostgreSQL) | Neo4j, ArangoDB | Zero dependência nova; SQL resolve traversals de 1-2 saltos que o MVP precisa; mesma abordagem do Obsidian |
| Renderização do grafo | D3.js | Biblioteca proprietária | Ecossistema React maduro, controle total sobre estética |
| Extrator de entidades | Haiku-4.5 | Sonnet 4.6 | Task estruturada simples; Haiku é 10x mais barato e suficiente para JSON extraction |
| Orquestração de jobs | APScheduler (FastAPI) | Celery + Redis | Sem nova infraestrutura; adequado para o volume do MVP |
| Email de notificação | Resend | SendGrid, SMTP próprio | API moderna com SDK Python, deliverability gerenciada, free tier generoso |
| Labels dos nós | Iniciais dentro + nome abaixo | Nome dentro do nó | Nomes longos cabem, nós ficam limpos, identificação rápida sem hover |
| LLM judge — modelo | Haiku-4.5 (scores) + Sonnet opcional (narrativa) | Sonnet para tudo | Haiku é 10x mais barato e suficiente para avaliação estruturada; Sonnet reservado para julgamento subjetivo |
