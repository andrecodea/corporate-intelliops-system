# IntelliOps — Roadmap

Each sprint is scoped to one week.

---

## Sprint 1 — Calibration

- [ ] Validate each mode prompt produces the correct deliverables
- [ ] Run all 4 modes with `tests/run_agent.py` and evaluate report quality and search coverage
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

## Sprint 5 — RAG & Conversational Agent

- [ ] Chunk and embed report content using Supabase `pgvector`
- [ ] `POST /reports/:id/chat` — retrieves relevant chunks and answers questions grounded in the report
- [ ] Chat panel in `/report/:id` — user asks questions about the report alongside the rendered markdown
- [ ] Semantic search across history — query the report collection by meaning, not just keyword

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
- [ ] Chat panel (RAG — from Sprint 5)
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

## Sprint 7 — Collaboration & Org

- [ ] Organization workspaces (multi-tenant)
- [ ] Internal report sharing (link within org)
- [ ] Multi-user orgs with roles (admin / member)

---

## Sprint 10 — Monetization

- [ ] Credit-based plans (X credits per subscription tier)
- [ ] Pay as You Go for Pro plan
- [ ] Per-seat pricing add-on
- [ ] Billing dashboard
