# AGENT.md

Guia interno para agentes trabalhando nesta codebase.

## Produto

Corporate IntelliOps Agent e uma plataforma de inteligencia B2B baseada em `deepagents` + LangGraph. O usuario escolhe um modo de pesquisa, preenche contexto estruturado no frontend, e o backend executa uma pesquisa web com sub-agentes para produzir um relatorio citado em Markdown, exportavel para PDF, Obsidian ou Slack.

Modos ativos hoje:

- `Due Diligence`
- `Competitor Intel`
- `Vendor Evaluation`
- `Sales Intel`

Nao assuma que os sprints do roadmap ja foram implementados. A implementacao atual ainda e o MVP Streamlit + FastAPI; muitos documentos em `docs/sprints/` descrevem trabalho futuro.

## Comandos

Instalar dependencias:

```bash
uv sync
```

Rodar teste manual do agente:

```bash
uv run python tests/run_agent.py "your query here"
```

Subir o LangGraph dev server no Windows:

```bash
PYTHONUTF8=1 uv run langgraph dev --no-reload --allow-blocking
```

Subir a API FastAPI:

```bash
uv run uvicorn backend.api:app --reload
```

Subir o frontend Streamlit:

```bash
uv run streamlit run frontend/app/app.py
```

## Variaveis de ambiente

Obrigatorias para uma pesquisa real:

- `ANTHROPIC_API_KEY`: provider principal, usado por `ChatAnthropic`.
- `OPENAI_API_KEY`: fallback, usado por `ChatOpenAI` se Anthropic nao estiver configurado.
- `TAVILY_API_KEY`: busca web.

Opcionais:

- `MODEL_NAME`: default `claude-sonnet-4-6`.
- `FALLBACK_MODEL`: default `gpt-5.2`.
- `SUBAGENT_MODEL_NAME`: default `claude-sonnet-4-6`.
- `SUBAGENT_BASE_URL` e `SUBAGENT_API_KEY`: provider OpenAI-compatible dedicado aos sub-agentes.
- `MAX_SUBAGENTS_ITERATIONS`: default `1`; atualmente e instrucional no prompt.
- `MAX_CONCURRENT_RESEARCH_UNITS`: default `2`; atualmente e instrucional no prompt.
- `RECURSION_LIMIT`: default `50`.
- `SLACK_BOT_TOKEN` e `SLACK_CHANNEL_ID`: upload de PDF para Slack.
- `LANGSMITH_API_KEY`: observabilidade.
- `LANGGRAPH_DATABASE_URL`: planejado para checkpoint persistente; o codigo atual usa `InMemorySaver`.
- `FIRECRAWL_API_KEY`: planejado no Sprint 1, mas o codigo atual ainda usa `httpx` + `markdownify` em `backend/tools.py`.

## Estrutura

```text
backend/
  agent.py                 # build_agent(), LLM config, sub-agente, prompts, middleware
  api.py                   # FastAPI, endpoint SSE /research/stream, prompt por modo
  tools.py                 # tavily_search factory, think_tool
  prompts/
    modes/                 # prompts dos quatro modos ativos

frontend/app/
  app.py                   # entrada Streamlit multipagina
  pages/research.py        # formulario, build_query(), SSE, PDF, Slack
  pages/home.py            # pagina inicial
  pages/info.py            # diagramas e benchmark

tests/
  run_agent.py             # teste manual com metricas de tokens e latencia

docs/sprints/              # guias instrucionais de roadmap
docs/sprints/INDEX.md      # mapa operacional dos sprints, dependencias e artefatos
docs/api_contracts.md      # contratos de endpoints por sprint
docs/superpowers/          # planos detalhados para sprints 7 e 8
skills/                    # skills locais de escrita de sprint/aula
supabase/migrations/       # plano e migrations futuras de persistencia
workspace/                 # saida runtime do agente
```

## Arquitetura atual

`langgraph.json` aponta o grafo `research` para `backend/agent.py:build_agent`.

`backend/agent.py` constroi um deep agent com:

- Orquestrador principal.
- Um sub-agente chamado `research-agent`.
- `think_tool` no orquestrador.
- `create_tavily_search(max_calls=5)` no sub-agente.
- `ToolRetryMiddleware` no orquestrador.
- `FilesystemBackend(root_dir=workspace/, virtual_mode=True)`.
- `InMemorySaver` como checkpointer.

`backend/api.py` cria o agente uma vez em import time:

```python
agent = build_agent()
```

O endpoint ativo e:

```text
POST /research/stream
```

Ele recebe:

```json
{"query": "...", "mode": "Due Diligence"}
```

E retorna eventos SSE:

- `token`
- `tool_call`
- `tool_result`
- `error`
- `done`

Os prompts de modo sao carregados por request via `_load_mode_prompt()`, concatenados antes da query, e enviados como mensagem de usuario. Nao coloque todos os prompts de modo no system prompt.

## Padroes importantes

- Factory: `backend/tools.py::create_tavily_search(max_calls)` retorna uma tool nova com contador proprio em closure. Preserve isso para evitar que sub-agentes compartilhem limite de busca.
- Strategy: `backend/agent.py::_init_llm()` escolhe Anthropic primeiro e OpenAI como fallback.
- Adapter: `backend/api.py::event_stream()` traduz mensagens LangGraph para eventos SSE estaveis.
- Facade: `frontend/app/pages/research.py::stream_events()` esconde detalhes de `httpx_sse` do restante da UI.
- Observer: `tests/run_agent.py::UsageTracker` mede tokens sem alterar o codigo produtivo.
- Dependency injection: `InjectedToolArg` em `tavily_search.max_results` oculta parametro fixo do schema visto pelo LLM.
- Per-request prompt injection: modos sao adicionados por request, nao na construcao do agente.

## Como adicionar um novo modo

Siga o padrao existente, sem criar arquitetura paralela.

1. Crie `backend/prompts/modes/<mode_name>.md`.
2. Registre o modo em `MODE_FILES` em `backend/api.py`.
3. Adicione entrada em `MODES` em `frontend/app/pages/research.py`.
4. Adicione os campos de input na branch correspondente da UI.
5. Adicione a branch em `build_query()`.
6. Atualize `OPTIONAL_FIELDS` se houver campos opcionais.
7. Rode um teste manual real pelo frontend ou pelo endpoint.

Cada prompt de modo deve conter, no minimo:

- `Research Priorities`
- `Search Strategy`
- `Report Structure`

## Como mexer em busca web

O contrato publico de `tavily_search` deve permanecer estavel:

```python
tavily_search(query, topic="general", search_depth="fast", fetch_full_content=False)
```

O codigo atual usa Tavily para resultados e, se `fetch_full_content=True`, usa `httpx` + `markdownify` para buscar e converter pagina inteira. O Sprint 1 propoe substituir essa camada por Firecrawl, mantendo fallback para snippet Tavily. Se implementar isso, atualize tambem:

- `pyproject.toml`
- `README.md`
- `frontend/app/pages/info.py`
- este `AGENT.md`

## Frontend

O frontend atual e Streamlit. Nao introduza React/Vite salvo se estiver implementando explicitamente o Sprint 6.

Arquivo principal: `frontend/app/pages/research.py`.

Areas sensiveis:

- `build_query()`: monta a query final de cada modo. Mudancas aqui alteram a qualidade de pesquisa.
- `stream_events()`: consome SSE do backend.
- `format_activity_item()`: traduz tool calls para a coluna de atividade.
- `report_to_pdf()`: converte Markdown para PDF com `xhtml2pdf`.
- `send_pdf_to_slack()`: usa Slack `files.upload`; precisa de bot token com `files:write`.

## Testes e verificacao

Nao ha suite unitaria ampla ainda. Para mudancas no agente ou prompts, use:

```bash
uv run python tests/run_agent.py "what is context engineering for AI agents?"
```

Para mudancas em modo, rode uma query representativa e salve a avaliacao manual. `tests/run_agent.py` grava JSON em `tests/runs/` com:

- latencia
- TTFT
- tokens de entrada
- tokens de saida
- total de chamadas LLM

Evite commitar arquivos gerados em `workspace/` ou runs locais se nao forem parte explicita da tarefa.

## Padrao para sprints

As skills locais relevantes sao:

- `skills/sprint-writing/SKILL.md`: padrao geral para planos de sprint.
- `skills/ml-sprint-writing/SKILL.md`: extensao para ML/data science.
- `skills/aula-writing/SKILL.md`: aulas em notebook, nao e o padrao primario dos sprints desta codebase.

Para novos sprints ou reescritas, siga `sprint-writing`:

~~~markdown
## Task N: `path/to/file` - short description

**O que e e por que existe**

**Files:**
- Criar/Editar: `exact/path`

---

### Conceito: Nome
> Explicar por que a decisao importa e qual consequencia pratica ela tem.

---

### Documentacao
- Link oficial - descricao curta

---

### O que voce precisa fazer

### Esqueleto

```python
# TODOs primeiro
```

<details>
<summary>Ver solucao completa</summary>

```python
# implementacao completa
```

</details>

- [ ] **Step N.M: verbo + acao concreta**

### Resumo
> *Preencher apos concluir a task.*
~~~

Ordem pedagogica esperada:

1. Explore: investigar o material bruto e validar premissas.
2. Prototype: provar a decisao em ambiente isolado.
3. Implement: levar a decisao validada ao codigo produtivo.

## Validacao dos sprints atuais

Estado atual:

- `docs/sprints/*.md` foi normalizado para o template da skill `sprint-writing`.
- `docs/sprints/INDEX.md` agora e o ponto de entrada para ordem, dependencias, env vars, migrations e criterios de conclusao.
- `docs/api_contracts.md` registra os contratos de API que cada sprint cria ou altera.
- `supabase/migrations/README.md` registra a ordem planejada de migrations antes de qualquer SQL real.
- Cada task deve ter `Task`, `O que e e por que existe`, `Files`, `Conceito`, `Documentacao`, `O que voce precisa fazer`, `Esqueleto`, `<details>` com solucao completa, checklist e `Resumo`.
- Sprints 7 e 8 foram quebrados em tasks operacionais granulares dentro de `docs/sprints/`, mantendo os planos detalhados em `docs/superpowers/plans/` como referencia de implementacao.
- Varios sprints descrevem features futuras, como Supabase, React, Stripe, APScheduler e Firecrawl. Nao trate essas features como existentes antes de checar a codebase.

Conclusao operacional: ao executar um sprint, leia primeiro `docs/sprints/INDEX.md`, depois o sprint especifico, depois `docs/api_contracts.md` se houver endpoint envolvido. Confirme se os sprints anteriores realmente foram implementados e so entao siga as tasks na ordem.

## Regras de trabalho

- Leia a codebase antes de implementar; os documentos de sprint podem estar a frente do codigo.
- Preserve a API publica de `/research/stream` e os nomes dos eventos SSE, salvo pedido explicito.
- Nao mova a injecao de prompt por modo para o startup do agente.
- Nao compartilhe instancia de `tavily_search` entre sub-agentes.
- Ao adicionar env vars, documente em README/guia relevante e mantenha defaults seguros.
- Ao alterar prompts, rode pelo menos um teste manual com fonte real.
- Ao editar docs de sprint, priorize explicacoes de "por que" e mantenha checkboxes acionaveis.
