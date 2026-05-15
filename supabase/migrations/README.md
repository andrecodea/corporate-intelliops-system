# Supabase Migrations Plan

Este diretorio e criado pelos sprints que introduzem persistencia. A codebase atual pode ainda nao conter as migrations; este README define a ordem e os contratos esperados para quando elas forem implementadas.

## Ordem obrigatoria

1. `001_reports.sql` - Sprint 5
2. `002_entities.sql` - Sprint 7
3. `003_monitoring.sql` - Sprint 8
4. `004_orgs.sql` - Sprint 9
5. `005_billing.sql` - Sprint 10

Nunca aplique uma migration posterior se a anterior ainda nao existe ou nao foi aplicada no mesmo banco.

## `001_reports.sql`

Responsavel por historico de pesquisas e relatorios.

Tabelas esperadas:

- `researches`
- `reports`

Requisitos:

- `reports.markdown_content` guarda o relatorio completo.
- Busca textual usa PostgreSQL full-text search.
- Durante desenvolvimento pre-auth, `user_id` pode ser texto/uuid local conforme definido no sprint.
- Depois do Sprint 6, acesso deve ser derivado de Supabase Auth.

## `002_entities.sql`

Responsavel pelo Intelligence Terminal.

Tabelas esperadas:

- `entities`
- `relationships`
- `dossiers`
- `entity_drafts`

Requisitos:

- RLS habilitada.
- Entidades pertencem ao usuario no MVP.
- Duplicatas devem ser evitadas por normalizacao ou busca case-insensitive.
- `entity_drafts` guarda saida do LLM antes de aprovacao humana.

## `003_monitoring.sql`

Responsavel por jobs recorrentes.

Tabelas esperadas:

- `monitoring_jobs`
- `job_runs`

Requisitos:

- `monitoring_jobs.active` controla se o scheduler deve carregar o job.
- `job_runs.status` deve diferenciar `running`, `done`, `skipped` e `error`.
- `had_updates=false` nao deve gerar notificacao.

## `004_orgs.sql`

Responsavel por multi-tenancy.

Tabelas/alteracoes esperadas:

- `organizations`
- `profiles.org_id`
- `profiles.role`
- `researches.org_id`
- `reports.shared_link_token`

Requisitos:

- Toda query privada deve ser limitada por membership da org.
- Link compartilhado publico usa token opaco e unico.
- Admin pode convidar/gerenciar membros; member nao pode alterar billing ou roles.

## `005_billing.sql`

Responsavel por planos, creditos e ledger financeiro.

Tabelas esperadas:

- `org_credits`
- `org_billing`
- `credit_transactions`
- `stripe_events`

Requisitos:

- `stripe_events.event_id` deve ser unico para idempotencia.
- Debito de creditos deve ser atomico no banco.
- Ledger deve registrar todo credito/debito com motivo e referencia.
- Nenhuma secret Stripe fica no frontend.

## Checklist ao adicionar uma migration

- [ ] Nome segue a ordem acima.
- [ ] A migration pode rodar uma vez sem erro.
- [ ] RLS esta habilitada nas tabelas acessadas pelo frontend.
- [ ] Policies refletem a fase atual: single-user antes do Sprint 9, org-based depois.
- [ ] `docs/sprints/INDEX.md` e `docs/api_contracts.md` continuam coerentes.
