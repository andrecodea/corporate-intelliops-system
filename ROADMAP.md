# IntelliOps — Roadmap

Each sprint is scoped to one week.

Planos instrucionais detalhados (código, padrões, dicas) estão em `docs/sprints/`:
- [Sprint 1 — Calibration](docs/sprints/sprint_1_calibration.md)
- [Sprint 2 — New Intelligence Modes](docs/sprints/sprint_2_new_modes.md)
- [Sprint 3 — Evals](docs/sprints/sprint_3_evals.md)
- [Sprint 4 — Production Readiness](docs/sprints/sprint_4_production_readiness.md)
- [Sprint 5 — Report History & Search](docs/sprints/sprint_5_report_history.md)
- [Sprint 6 — SaaS Frontend (React)](docs/sprints/sprint_6_saas_frontend.md)
- [Sprint 7 — Collaboration & Org](docs/sprints/sprint_7_collaboration.md)
- [Sprint 10 — Monetization](docs/sprints/sprint_10_monetization.md)

---

## Sprint 1 — Calibration

- [ ] Replace `httpx` full-page fetch with Firecrawl — handles Cloudflare, JS-rendered pages, and blocked sites; falls back to Tavily snippet on failure
- [ ] Validate each mode prompt produces the correct deliverables
- [ ] Run all 4 modes with `tests/run_mode_{mode}.py` and evaluate report quality and search coverage
- [ ] Adjust search cap per mode if comparative modes (Competitor Intel, Vendor Evaluation) show thin findings
- [ ] Re-run after adjustments and compare token usage and output quality against baseline

---

## Sprint 2 — New Intelligence Modes

Each mode = new file in `backend/prompts/modes/` + structured form inputs + entry in `MODE_FILES`.

- [ ] **Market Mapping** — map players, segments, and positioning across a sector
- [ ] **Leadership Intel** — executive background, track record, and professional connections
- [ ] **Funding & Deal Intelligence** — investment rounds, M&A activity, and capital movements
- [ ] **Risk Assessment** — multi-dimensional scorecard: reputational, financial, regulatory, geopolitical
- [ ] **Regulatory Watch** — regulatory changes by sector and jurisdiction
- [ ] **Talent Signal** — hiring patterns as a proxy for undisclosed strategic direction
- [ ] **Partnership & Ecosystem Mapping** — alliances, integrations, and partner ecosystem

---

## Sprint 3 — Evals

- [ ] LLM-as-judge eval script — runs a fixed set of queries per mode and scores response quality
- [ ] Eval criteria per mode (e.g. coverage of required sections, citation density, factual specificity)
- [ ] Eval results saved to `tests/evals/` for tracking quality over time
- [ ] Baseline established for all modes before any further prompt changes

---

## Sprint 4 — Production Readiness

- [ ] `Dockerfile` for FastAPI + LangGraph stack
- [ ] `docker-compose.yml` — brings up backend + LangGraph server together
- [ ] CI pipeline — runs integration tests and evals on push
- [ ] `.env.example` review — ensure all required and optional vars are documented

---

## Sprint 5 — Report History & Search

**Motivação:** relatórios de inteligência são gerados ao vivo via web search — o valor está na frescura dos dados, não no histórico. RAG (busca vetorial em relatórios antigos) introduz complexidade de infraestrutura (pgvector, embedding model, chunking strategy) por benefício marginal: o usuário que quer informação atualizada vai re-rodar o agente, não perguntar para um relatório de 3 meses atrás. Busca por metadados é suficiente para o caso de uso.

- [ ] Armazenar relatórios no Supabase após stream (`researches` + `reports` tables do Sprint 6)
- [ ] `GET /reports` — lista relatórios com filtros: modo, empresa, data
- [ ] Full-text search nos relatórios via PostgreSQL `tsvector` (sem embedding, sem pgvector)
- [ ] Dashboard de histórico no frontend: card grid com filtro por modo, empresa, data
- [ ] `/report/:id` — visualização do relatório salvo com export (PDF, Obsidian, Slack)

---

## Sprint 6 — SaaS Frontend (React)

**Stack:** Vite + React SPA · Supabase (Auth + PostgreSQL + Storage)

### Auth
- [ ] Email/password login (Supabase Auth)
- [ ] Google OAuth login (Supabase Auth)
- [ ] AuthGuard — protected route wrapper
- [ ] User profile (`/settings`)

### Dashboard
- [ ] Card grid per research (company, mode, date, status)
- [ ] Filter sidebar: mode, date presets (today / week / month), company search
- [ ] Card click opens `/report/:id`

### Research
- [ ] Mode-specific form (`ResearchForm`) replicating current `build_query()` logic
- [ ] Real-time SSE streaming (`StreamViewer`) — Activity + Report panels
- [ ] Auto-save report on `done` event

### Saved Report
- [ ] Rendered markdown view at `/report/:id`
- [ ] Export: PDF, Obsidian, Slack

### Backend (FastAPI)
- [ ] `POST /reports/save` — persists research + report to Supabase after stream ends

### Database (Supabase)
- [ ] `profiles` table (id = auth.uid, full_name, avatar, org_id)
- [ ] `researches` table (id, user_id, mode, company, query, status, token_count, created_at)
- [ ] `reports` table (id, research_id, markdown_content, pdf_url, updated_at)
- [ ] Row Level Security by user_id on all tables
- [ ] Supabase Storage — PDFs per research

---

## Sprint 7 — Intelligence Terminal (Base)

Spec: [`docs/superpowers/specs/2026-04-08-intelligence-terminal-design.md`](docs/superpowers/specs/2026-04-08-intelligence-terminal-design.md)

- [ ] Tabelas Supabase: `entities`, `relationships`, `dossiers`, `entity_drafts`
- [ ] Extrator de entidades pós-run (Haiku-4.5) — processa relatório e gera rascunho JSON
- [ ] Endpoint `POST /entities/review` — HITL gate antes de persistir no grafo
- [ ] Endpoint `GET /entities/graph` — carrega nós e arestas para o frontend
- [ ] Painel HITL de curadoria no frontend (aprovar / descartar / editar entidades)
- [ ] Grafo D3.js: force-directed, iniciais dentro do nó, label abaixo, cor por tipo, tamanho por weight
- [ ] Hover sobre nó → tooltip glass flutuante próximo ao nó
- [ ] Click no nó → split view (grafo dimmed + dossier com abas: Perfil / Conexões / Histórico / Jobs)
- [ ] Filtros por tipo de entidade (company, person, org, event)

---

## Sprint 8 — Monitoring Jobs Engine

Spec: [`docs/superpowers/specs/2026-04-08-intelligence-terminal-design.md`](docs/superpowers/specs/2026-04-08-intelligence-terminal-design.md)

- [ ] APScheduler integrado ao FastAPI
- [ ] Tabelas: `monitoring_jobs`, `job_runs`
- [ ] Aba Jobs no dossier: criar, pausar, remover jobs de monitoramento
- [ ] Filtro LLM de relevância pré-notificação (compara resultado novo com dossier atual)
- [ ] Notificações via Slack (existente) + email via Resend
- [ ] HITL de updates: "Aplicar ao dossier" / "Ignorar" antes de persistir mudanças

---

## Sprint 9 — Collaboration & Org

- [ ] Organization workspaces (multi-tenant)
- [ ] Internal report sharing (link within org)
- [ ] Multi-user orgs with roles (admin / member)

---

## Sprint 10 — Monetization

- [ ] Credit-based plans (X credits per subscription tier)
- [ ] Pay as You Go for Pro plan
- [ ] Per-seat pricing add-on
- [ ] Billing dashboard
