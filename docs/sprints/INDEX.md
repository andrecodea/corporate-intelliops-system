# Sprint Execution Index

Este arquivo e o mapa operacional dos sprints. Use-o antes de abrir um sprint especifico para saber quais pre-requisitos, artefatos e verificacoes devem existir.

## Ordem e dependencias

| Sprint | Objetivo | Depende de | Artefatos principais | Prova de conclusao |
|---|---|---|---|---|
| 1 | Calibrar busca e modos atuais | MVP atual rodando | Firecrawl em `backend/tools.py`, scripts `tests/run_mode_*.py` | 4 modos atuais geram relatorios aceitaveis e `fetch_full_content=True` funciona |
| 2 | Adicionar 7 modos novos | Sprint 1 validado | Novos prompts em `backend/prompts/modes/`, `MODE_FILES`, UI Streamlit | Cada modo aparece no frontend, envia `mode` correto e gera secoes esperadas |
| 3 | Criar evals de qualidade | Sprints 1 e 2 | `tests/evals/test_set.json`, `judge.py`, `run_evals.py`, baseline | Baseline salva e nenhum modo abaixo de 70/100 |
| 4 | Preparar deploy e CI | Sprints 1 a 3 | `Dockerfile`, `.dockerignore`, `docker-compose.yml`, `.github/workflows/ci.yml`, `.env.example` | `docker-compose up --build` sobe API e LangGraph, CI passa |
| 5 | Persistir historico de relatorios | Sprint 4 recomendado | `supabase/migrations/001_reports.sql`, `backend/db.py`, endpoints `/reports` | Salvar, listar e buscar relatorios por texto funciona |
| 6 | Trocar Streamlit por React SaaS | Sprint 5 | Vite React em `frontend/`, Supabase Auth, dashboard, streaming SSE | Login -> pesquisa -> stream -> autosave -> dashboard funcionando |
| 7 | Criar Intelligence Terminal | Sprint 6 | `002_entities.sql`, extractor, endpoints de entidades, grafo D3, HITL | Entidades extraidas, aprovadas e visiveis no grafo/dossier |
| 8 | Criar monitoring jobs | Sprint 7 | `003_monitoring.sql`, scheduler, judge, endpoints/jobs UI | Job manual cria `job_runs`; apply/dismiss funciona |
| 9 | Introduzir orgs e compartilhamento | Sprints 5 e 6 | `004_orgs.sql`, routers de org/report, link publico por token | Admin compartilha relatorio; visitante ve via token |
| 10 | Monetizacao e creditos | Sprint 9 | `005_billing.sql`, `backend/billing.py`, Stripe webhook, billing UI | Checkout test atualiza creditos uma vez e pesquisa debita saldo |

## Portas, processos e URLs

| Processo | Comando local | URL |
|---|---|---|
| FastAPI | `uv run uvicorn backend.api:app --reload --port 8005` | `http://localhost:8005` |
| Streamlit MVP | `uv run streamlit run frontend/app/app.py` | URL impressa pelo Streamlit |
| React Sprint 6+ | `cd frontend && npm run dev` | URL impressa pelo Vite |
| LangGraph dev server | `PYTHONUTF8=1 uv run langgraph dev --no-reload --allow-blocking` | `http://127.0.0.1:2024` |

Porta padrao do projeto: `8005`. Se algum trecho antigo citar `8000`, trate como default do Uvicorn, nao como decisao do projeto.

## Variaveis por fase

| Fase | Variaveis obrigatorias |
|---|---|
| MVP/Sprints 1-4 | `ANTHROPIC_API_KEY` ou `OPENAI_API_KEY`, `TAVILY_API_KEY` |
| Sprint 1 | `FIRECRAWL_API_KEY` para `fetch_full_content=True` |
| Sprint 5+ | `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` no backend |
| Sprint 6+ | `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `VITE_API_URL` no React |
| Sprint 8 | `SLACK_BOT_TOKEN`, `SLACK_CHANNEL_ID` e/ou `RESEND_API_KEY` se notificacoes forem testadas |
| Sprint 10 | `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_STARTER`, `STRIPE_PRICE_PRO`, `APP_URL` |

## Migrations planejadas

| Migration | Sprint | Responsabilidade |
|---|---|---|
| `001_reports.sql` | 5 | `researches`, `reports`, busca textual e RLS single-user |
| `002_entities.sql` | 7 | `entities`, `relationships`, `dossiers`, `entity_drafts` |
| `003_monitoring.sql` | 8 | `monitoring_jobs`, `job_runs` |
| `004_orgs.sql` | 9 | `organizations`, `profiles.org_id`, roles, compartilhamento |
| `005_billing.sql` | 10 | creditos, billing, ledger e eventos Stripe processados |

## Checklist antes de iniciar qualquer sprint

- [ ] Li o sprint anterior e confirmei que os artefatos dele existem na codebase.
- [ ] Rodei o comando local minimo do backend na porta `8005`.
- [ ] Conferi no `docs/api_contracts.md` quais endpoints este sprint cria ou altera.
- [ ] Conferi no `supabase/migrations/README.md` se ha migrations anteriores obrigatorias.
- [ ] Separei env vars reais em `.env` e exemplos seguros em `.env.example`.
- [ ] Sei qual comando prova que o sprint terminou.
