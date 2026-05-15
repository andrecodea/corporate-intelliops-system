# Sprint 5 — Report History & Search: Guia Instrucional

## Contexto e Objetivo

O Sprint 5 adiciona persistência: relatórios gerados passam a ser salvos no Supabase e o usuário pode recuperá-los mais tarde. A escolha deliberada deste sprint foi **não usar RAG** (busca vetorial em conteúdo de relatórios) — o caso de uso real é "encontro meu relatório sobre a Notion de março", não "encontro parágrafos semanticamente similares a uma pergunta". Full-text search via PostgreSQL resolve isso sem embedding model, pgvector, ou chunking.

Este sprint depende da infra do Sprint 6 (tabelas do Supabase), mas os endpoints FastAPI podem ser desenvolvidos e testados primeiro com dados mockados.

## Pré-requisitos e decisões temporárias

- Crie um projeto Supabase antes de começar e guarde `SUPABASE_URL` e `SUPABASE_SERVICE_KEY` no `.env`.
- Use a `service_role` key apenas no backend. Nunca exponha `SUPABASE_SERVICE_KEY` ao frontend.
- Enquanto o Sprint 6/Auth ainda não estiver pronto, aceite `user_id` no payload dos endpoints como solução temporária de desenvolvimento.
- Depois do Sprint 6, substitua `user_id` direto por JWT Supabase no header `Authorization`.
- Para testar sozinho, use um `user_id` fixo como `local-dev-user` e documente nos resultados que essa é uma fase pre-auth.

**Comandos mínimos de verificação:**

```bash
uv run uvicorn backend.api:app --reload --port 8005
curl -X POST http://localhost:8005/reports/save -H "Content-Type: application/json" -d "{\"user_id\":\"local-dev-user\",\"mode\":\"Due Diligence\",\"company\":\"Deel\",\"query\":\"test\",\"markdown_content\":\"# Test report\"}"
curl "http://localhost:8005/reports?user_id=local-dev-user"
```

---

## Task 0: `supabase/migrations/README.md` - Preparar trilha de persistencia

**Estimativa:** ~20min

**O que é e por que existe**

Este sprint e o primeiro que cria estado persistente fora do `workspace/`. Antes de escrever SQL, crie a trilha de migrations e confirme se voce vai usar Supabase remoto, Supabase local ou SQL Editor manual.

**Files:**
- Criar/Editar: `supabase/migrations/README.md`
- Criar/Editar: `supabase/migrations/001_reports.sql`

---

### Conceito: Migration e contrato, nao rascunho
> Uma migration representa uma decisao persistida. Diferente de um script solto, ela precisa ter ordem, nome, responsabilidade e verificacao. Sem isso, sprints futuros como orgs, monitoring e billing ficam sem saber qual schema ja existe.

---

### Documentação
- https://supabase.com/docs/guides/database - referencia oficial para banco Supabase.
- https://supabase.com/docs/guides/cli - referencia oficial para Supabase CLI.
- https://www.postgresql.org/docs/current/textsearch.html - referencia oficial para full-text search.

---

### O que você precisa fazer

1. Confirme se `supabase/migrations/` existe.
2. Leia `supabase/migrations/README.md` e confirme a ordem planejada.
3. Escolha uma forma de aplicar SQL: Supabase SQL Editor ou Supabase CLI.
4. Crie `001_reports.sql` somente depois de entender quais sprints dependem dela.

### Esqueleto

```text
# TODO: Explore - confirmar diretorio de migrations e ordem esperada.
# TODO: Prototype - rodar um SELECT simples no Supabase escolhido.
# TODO: Implement - criar 001_reports.sql.
# TODO: Verify - confirmar que as tabelas aparecem no Table Editor ou via SQL.
```

<details>
<summary>Ver solução completa</summary>

Verificacao minima antes da migration:

```sql
select now();
```

Se estiver usando Supabase remoto, rode o SQL no SQL Editor. Se estiver usando Supabase CLI, documente o comando local que voce usou. O importante e nao misturar ambientes sem perceber: a migration que voce valida deve ser aplicada no mesmo banco usado por `SUPABASE_URL`.

</details>

- [ ] **Step 0.1: Ambiente Supabase escolhido e documentado.**
- [ ] **Step 0.2: `supabase/migrations/README.md` lido antes de criar SQL.**
- [ ] **Step 0.3: `001_reports.sql` criado no lugar correto.**
- [ ] **Step 0.4: Banco responde a uma query simples antes da implementacao.**

### Resumo
> *Preencher apos concluir a task: qual ambiente Supabase foi usado e como a migration sera aplicada?*

---

## Arquitetura de Persistência

```
Frontend (Streamlit)
      │
      │ POST /research/stream  (SSE — já existe)
      │ POST /reports/save     (novo — ao fim do stream)
      │ GET  /reports          (novo — lista com filtros)
      ▼
FastAPI (backend/api.py)
      │
      │ supabase-py client
      ▼
Supabase (PostgreSQL)
  ├── researches  (metadados: empresa, modo, status, tokens)
  └── reports     (conteúdo: markdown_content + tsvector index)
```

O fluxo é intencional: o relatório é streamado ao vivo para o usuário, e só **após o stream terminar** é salvo. Isso evita salvar relatórios incompletos se o usuário fechar a aba ou a conexão cair.

---

## Task 1: `supabase/migrations/001_reports.sql` - Schema do Supabase

**Estimativa:** ~45min

**O que é e por que existe**

Esta task transforma o objetivo descrito abaixo em uma unidade executavel no padrao da skill `sprint-writing`. Primeiro entenda o conceito e a decisao tecnica, depois use o esqueleto para implementar, e so entao consulte a solução completa preservada no bloco colapsavel.

**Files:**
- Criar/Editar: `supabase/migrations/001_reports.sql`

---

### Conceito: tsvector — índice invertido vs varredura por LIKE

> `LIKE '%notion%'` faz uma *full table scan* — lê cada linha procurando o padrão. `tsvector` pré-processa o texto (remove stop words, aplica stemming) e cria um índice GIN invertido. A busca `to_tsquery('notion')` percorre esse índice em O(log n).
>
> | Técnica | Complexidade | Stemming |
> |---|---|---|
> | `LIKE '%notion%'` | O(n) — full table scan | Não — "notions" não bate |
> | `tsvector` + GIN | O(log n) — índice invertido | Sim — "running" bate "run" |
>
> O trigger `update_search_vector` garante que o índice nunca fica desatualizado: atualiza automaticamente sempre que `markdown_content` muda.

---

### Documentação
- https://www.postgresql.org/docs/current/textsearch.html - referencia oficial para full-text search no PostgreSQL.
- https://supabase.com/docs/guides/database/full-text-search - referencia Supabase para tsvector e GIN.

---

### O que você precisa fazer

1. Abra o SQL Editor do Supabase e rode `select now();` para confirmar que o banco está acessível.
2. Execute o SQL da solução completa criando `researches`, `reports`, o índice GIN e o trigger `update_search_vector`.
3. Habilite RLS em ambas as tabelas e crie as policies de acesso por `user_id`.
4. Confirme criação: `select table_name from information_schema.tables where table_schema='public' and table_name in ('researches','reports');`
5. Teste o trigger inserindo uma linha em `reports` e verificando que `search_vector` foi preenchido.

### Esqueleto

```text
# TODO: Explore - localizar arquivos, contratos e dependencias citados abaixo.
# TODO: Prototype - validar a menor versao possivel da mudanca.
# TODO: Implement - aplicar a alteracao produtiva no(s) arquivo(s) indicado(s).
# TODO: Verify - rodar teste manual, script, endpoint ou build descrito na task.
```

<details>
<summary>Ver solução completa</summary>

Execute este SQL no Supabase SQL Editor (Settings → SQL Editor):

```sql
-- Tabela de pesquisas (metadados)
CREATE TABLE researches (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  mode        TEXT NOT NULL,
  company     TEXT,          -- nome da empresa pesquisada (extraído da query)
  query       TEXT NOT NULL,
  status      TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'completed', 'failed')),
  token_count INTEGER,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Tabela de relatórios (conteúdo)
CREATE TABLE reports (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  research_id      UUID NOT NULL REFERENCES researches(id) ON DELETE CASCADE,
  markdown_content TEXT NOT NULL,
  pdf_url          TEXT,               -- URL do PDF no Supabase Storage (opcional)
  search_vector    TSVECTOR,           -- índice full-text gerado automaticamente
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Índice full-text no conteúdo do relatório
-- gin = Generalized Inverted Index: otimizado para buscas em texto
CREATE INDEX idx_reports_search ON reports USING GIN (search_vector);

-- Trigger: atualiza search_vector automaticamente quando markdown_content muda
-- Isso garante que o índice nunca fica desatualizado sem precisar atualizar manualmente
CREATE OR REPLACE FUNCTION update_search_vector()
RETURNS TRIGGER AS $$
BEGIN
  NEW.search_vector := to_tsvector('english', NEW.markdown_content);
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER reports_search_vector_update
  BEFORE INSERT OR UPDATE ON reports
  FOR EACH ROW EXECUTE FUNCTION update_search_vector();

-- Row Level Security: cada usuário só vê seus próprios dados
ALTER TABLE researches ENABLE ROW LEVEL SECURITY;
ALTER TABLE reports ENABLE ROW LEVEL SECURITY;

CREATE POLICY "users see own researches"
  ON researches FOR ALL
  USING (auth.uid() = user_id);

CREATE POLICY "users see own reports via research"
  ON reports FOR ALL
  USING (
    research_id IN (
      SELECT id FROM researches WHERE user_id = auth.uid()
    )
  );
```

> **O que é `tsvector`?** É a representação interna do PostgreSQL para busca full-text. Ele pré-processa o texto: remove stop words ("the", "a", "of"), aplica stemming ("running" → "run"), e cria um índice invertido. A busca `to_tsquery('notion & funding')` percorre esse índice em O(log n) — muito mais rápido que `LIKE '%notion%'`.

> **Por que RLS (Row Level Security)?** RLS é uma política que roda dentro do banco, não no servidor da aplicação. Mesmo que um bug no código Python tente ler registros de outro usuário, o banco recusa. É a camada de segurança que você não precisa lembrar de aplicar em cada query — ela é automática.

---

</details>

- [ ] **Step 1.1: `researches` e `reports` criadas — query de confirmação retorna 2 linhas.**
- [ ] **Step 1.2: Índice GIN `idx_reports_search` existe em `reports`.**
- [ ] **Step 1.3: Trigger `update_search_vector` ativo — INSERT preenche `search_vector` automaticamente.**
- [ ] **Step 1.4: RLS habilitado e policy de acesso por `user_id` criada.**

### Resumo
> *Preencher apos concluir a task: o que foi alterado, qual verificacao passou, e qual risco ainda merece atencao?*

---
## Task 2: `backend/db.py` - Cliente Supabase no Backend

**Estimativa:** ~20min

**O que é e por que existe**

Esta task transforma o objetivo descrito abaixo em uma unidade executavel no padrao da skill `sprint-writing`. Primeiro entenda o conceito e a decisao tecnica, depois use o esqueleto para implementar, e so entao consulte a solução completa preservada no bloco colapsavel.

**Files:**
- Criar/Editar: `backend/db.py`

---

### Conceito: Singleton lazy — client criado na primeira chamada, não no import

> Se o client fosse criado no módulo (fora de função), qualquer `import backend.db` falharia sem `SUPABASE_URL` — inclusive em testes e no CI sem credenciais. O padrão *lazy singleton* adia a criação para a primeira chamada de `get_supabase()`: se as variáveis não existirem, o erro acontece em runtime com contexto claro.
>
> | Inicialização | Quando falha sem credenciais |
> |---|---|
> | `_client = create_client(...)` no módulo | Import time — stack trace difícil de rastrear |
> | Lazy em `get_supabase()` | Runtime — erro claro com mensagem descritiva |

---

### Documentação
- https://supabase.com/docs/reference/python/introduction - referencia oficial do supabase-py.
- https://docs.python.org/3/faq/programming.html#how-do-i-share-global-variables-across-modules - referencia para singleton em Python.

---

### O que você precisa fazer

1. Instale a dependência: `uv add supabase`.
2. Adicione `SUPABASE_URL` e `SUPABASE_SERVICE_KEY` ao `.env` e ao `.env.example`.
3. Crie `backend/db.py` com `get_supabase()` usando o padrão lazy singleton (`global _client = None`).
4. Teste o módulo isolado: `uv run python -c "from backend.db import get_supabase; print(get_supabase())"`.

### Esqueleto

```text
# TODO: Explore - localizar arquivos, contratos e dependencias citados abaixo.
# TODO: Prototype - validar a menor versao possivel da mudanca.
# TODO: Implement - aplicar a alteracao produtiva no(s) arquivo(s) indicado(s).
# TODO: Verify - rodar teste manual, script, endpoint ou build descrito na task.
```

<details>
<summary>Ver solução completa</summary>

Instale a dependência:

```bash
uv add supabase
```

Adicione ao `.env`:

```
SUPABASE_URL=https://xxxxxxxxxx.supabase.co
SUPABASE_SERVICE_KEY=eyJ...  # service_role key — bypassa RLS para operações server-side
```

> **Por que `service_role` no backend?** A `anon` key respeita RLS mas precisa de um token de usuário autenticado. O backend não age em nome de um usuário específico quando salva relatórios — ele age como serviço. A `service_role` key bypassa RLS e é segura para uso server-side porque nunca é exposta ao frontend.

Crie `backend/db.py`:

```python
"""Cliente Supabase para persistência de relatórios."""
import os
from supabase import create_client, Client

_client: Client | None = None

def get_supabase() -> Client:
    """Retorna cliente Supabase (singleton lazy)."""
    global _client
    if _client is None:
        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_SERVICE_KEY", "")
        if not url or not key:
            raise EnvironmentError("SUPABASE_URL e SUPABASE_SERVICE_KEY são obrigatórios")
        _client = create_client(url, key)
    return _client
```

---

</details>

- [ ] **Step 2.1: `uv add supabase` instalado sem conflito de dependências.**
- [ ] **Step 2.2: `SUPABASE_URL` e `SUPABASE_SERVICE_KEY` documentados no `.env.example`.**
- [ ] **Step 2.3: `get_supabase()` usa lazy singleton — `_client` é None no módulo, criado na primeira chamada.**
- [ ] **Step 2.4: `from backend.db import get_supabase; print(get_supabase())` imprime o client sem erro.**

### Resumo
> *Preencher apos concluir a task: o que foi alterado, qual verificacao passou, e qual risco ainda merece atencao?*

---
## Task 3: `backend/api.py` - Endpoint `POST /reports/save`

**Estimativa:** ~30min

**O que é e por que existe**

Esta task transforma o objetivo descrito abaixo em uma unidade executavel no padrao da skill `sprint-writing`. Primeiro entenda o conceito e a decisao tecnica, depois use o esqueleto para implementar, e so entao consulte a solução completa preservada no bloco colapsavel.

**Files:**
- Criar/Editar: `backend/api.py`

---

### Conceito: Salvar depois do stream — não durante

> O relatório é streamado token a token para o usuário. Salvar durante o stream significa salvar conteúdo incompleto se o usuário fechar a aba ou a conexão cair. O frontend chama `POST /reports/save` somente após receber o evento `done`. O backend faz dois inserts em ordem: `researches` (metadados) primeiro, depois `reports` com o conteúdo — a ordem importa porque `reports.research_id` é FK para `researches.id`.

---

### Documentação
- https://fastapi.tiangolo.com/tutorial/body/ - referencia para request body com Pydantic.
- https://supabase.com/docs/reference/python/insert - referencia para insert no supabase-py.

---

### O que você precisa fazer

1. Adicione `SaveReportRequest` (Pydantic model) com os campos: `mode`, `company`, `query`, `markdown_content`, `token_count`, `user_id`.
2. Implemente `POST /reports/save`: insira em `researches` primeiro, use o `research_id` retornado para inserir em `reports`.
3. Teste com curl após subir a API na porta 8005.
4. Confirme que as linhas aparecem no Supabase Table Editor.

### Esqueleto

```text
# TODO: Explore - localizar arquivos, contratos e dependencias citados abaixo.
# TODO: Prototype - validar a menor versao possivel da mudanca.
# TODO: Implement - aplicar a alteracao produtiva no(s) arquivo(s) indicado(s).
# TODO: Verify - rodar teste manual, script, endpoint ou build descrito na task.
```

<details>
<summary>Ver solução completa</summary>

Adicione em `backend/api.py`:

```python
from backend.db import get_supabase

class SaveReportRequest(BaseModel):
    mode: str
    company: str | None = None   # nome da empresa (opcional — extraído do frontend)
    query: str
    markdown_content: str
    token_count: int | None = None
    user_id: str                 # vem do token Supabase Auth (Sprint 6)
    # Por ora (antes do Sprint 6), pode ser um ID fixo para testes

@app.post("/reports/save")
async def save_report(request: SaveReportRequest):
    """Salva pesquisa e relatório no Supabase após o stream terminar."""
    db = get_supabase()

    # 1. Cria o registro de pesquisa
    research = db.table("researches").insert({
        "user_id": request.user_id,
        "mode": request.mode,
        "company": request.company,
        "query": request.query,
        "status": "completed",
        "token_count": request.token_count,
    }).execute()

    research_id = research.data[0]["id"]

    # 2. Salva o relatório (search_vector é atualizado automaticamente pelo trigger)
    db.table("reports").insert({
        "research_id": research_id,
        "markdown_content": request.markdown_content,
    }).execute()

    return {"research_id": research_id}
```

> **Por que o frontend manda `user_id` ao invés do backend inferir?** No Sprint 6, o frontend vai mandar o JWT do Supabase Auth no header `Authorization`. O backend vai decodificar esse token e extrair o `user_id`. Por enquanto (antes do Auth estar implementado), aceitar `user_id` diretamente simplifica o desenvolvimento.

---

</details>

- [ ] **Step 3.1: `SaveReportRequest` criado com todos os campos.**
- [ ] **Step 3.2: Endpoint insere em `researches` primeiro, depois em `reports` com FK.**
- [ ] **Step 3.3: `curl -X POST http://localhost:8005/reports/save ...` retorna `research_id`.**
- [ ] **Step 3.4: Linha aparece no Supabase Table Editor em `researches` e `reports`.**

### Resumo
> *Preencher apos concluir a task: o que foi alterado, qual verificacao passou, e qual risco ainda merece atencao?*

---
## Task 4: `backend/api.py` - Endpoint `GET /reports`

**Estimativa:** ~45min

**O que é e por que existe**

Esta task transforma o objetivo descrito abaixo em uma unidade executavel no padrao da skill `sprint-writing`. Primeiro entenda o conceito e a decisao tecnica, depois use o esqueleto para implementar, e so entao consulte a solução completa preservada no bloco colapsavel.

**Files:**
- Criar/Editar: `backend/api.py`

---

### Conceito: Dois filtros com índices diferentes — B-tree para metadata, GIN para conteúdo

> Filtros de `mode` e `company` usam índices B-tree padrão — rápidos e simples. A busca por conteúdo usa o índice GIN com `tsvector`. O `supabase-py` não suporta joins com full-text search em uma query só, então a busca por texto é feita em separado: primeiro obtém os `research_id` que batem, depois filtra a query principal por esses IDs.
>
> | Filtro | Índice | Estratégia |
> |---|---|---|
> | `mode`, `company` | B-tree (`.eq`, `.ilike`) | Join direto na query principal |
> | `search` (conteúdo) | GIN tsvector | Query separada → filtra por IDs |

---

### Documentação
- https://supabase.com/docs/reference/python/select - referencia para select e filtros no supabase-py.
- https://supabase.com/docs/reference/python/textsearch - referencia para full-text search no supabase-py.

---

### O que você precisa fazer

1. Implemente `GET /reports` com parâmetros opcionais: `user_id`, `mode`, `company`, `search`, `limit`, `offset`.
2. Construa a query base com join entre `researches` e `reports`.
3. Aplique filtros B-tree (`mode`, `company`) diretamente na query principal.
4. Se `search` estiver presente, faça a query separada com `text_search` e filtre por IDs.
5. Teste: salve dois relatórios, busque por texto presente em apenas um.

### Esqueleto

```text
# TODO: Explore - localizar arquivos, contratos e dependencias citados abaixo.
# TODO: Prototype - validar a menor versao possivel da mudanca.
# TODO: Implement - aplicar a alteracao produtiva no(s) arquivo(s) indicado(s).
# TODO: Verify - rodar teste manual, script, endpoint ou build descrito na task.
```

<details>
<summary>Ver solução completa</summary>

```python
from fastapi import Query as QueryParam

@app.get("/reports")
async def list_reports(
    user_id: str,
    mode: str | None = QueryParam(default=None),
    company: str | None = QueryParam(default=None),
    search: str | None = QueryParam(default=None),
    limit: int = QueryParam(default=20, ge=1, le=100),
    offset: int = QueryParam(default=0, ge=0),
):
    """Lista relatórios com filtros opcionais.

    Suporta filtro por modo, empresa, e full-text search no conteúdo.
    """
    db = get_supabase()

    # Monta a query base: join entre researches e reports
    query = (
        db.table("researches")
        .select("id, mode, company, created_at, status, reports(id, markdown_content)")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
    )

    # Filtros opcionais de metadados (rápidos — usam índices B-tree)
    if mode:
        query = query.eq("mode", mode)
    if company:
        query = query.ilike("company", f"%{company}%")

    # Full-text search no conteúdo do relatório
    # Isso é feito como query separada por limitação do supabase-py com joins + FTS
    if search:
        matching_report_ids = (
            db.table("reports")
            .select("research_id")
            .text_search("search_vector", search, config="english")
            .execute()
            .data
        )
        ids = [r["research_id"] for r in matching_report_ids]
        if not ids:
            return {"data": [], "total": 0}
        query = query.in_("id", ids)

    result = query.execute()
    return {"data": result.data, "total": len(result.data)}
```

> **Por que dois tipos de filtro?** Filtros por `mode` e `company` usam índices B-tree padrão — são rápidos e simples. A busca por conteúdo usa o índice GIN com `tsvector` — é full-text search real, não `LIKE`. A diferença: `LIKE '%notion%'` faz full table scan; `to_tsquery('notion')` usa o índice invertido em O(log n).

---

</details>

- [ ] **Step 4.1: `GET /reports?user_id=X` retorna lista paginada.**
- [ ] **Step 4.2: Filtros `mode` e `company` funcionam individualmente.**
- [ ] **Step 4.3: `search=notion` retorna apenas relatórios com "notion" no conteúdo.**
- [ ] **Step 4.4: `search` que não existe retorna `{"data": [], "total": 0}`.**

### Resumo
> *Preencher apos concluir a task: o que foi alterado, qual verificacao passou, e qual risco ainda merece atencao?*

---
## Task 5: `frontend/app/pages/research.py` - Integração no Frontend Streamlit

**Estimativa:** ~30min

**O que é e por que existe**

Esta task transforma o objetivo descrito abaixo em uma unidade executavel no padrao da skill `sprint-writing`. Primeiro entenda o conceito e a decisao tecnica, depois use o esqueleto para implementar, e so entao consulte a solução completa preservada no bloco colapsavel.

**Files:**
- Criar/Editar: `frontend/app/pages/research.py`

---

### Conceito: Operações secundárias devem falhar silenciosamente

> O save é secundário — o usuário veio buscar um relatório, não salvar. Se o Supabase estiver fora do ar ou a conexão cair, o `try/except` com `pass` garante que o usuário ainda vê o relatório na tela e pode exportar manualmente. Exibir um erro de save quebraria uma experiência que tecnicamente funcionou. A mesma lógica se aplica a analytics, logs e webhooks: o caminho crítico não deve depender de infra de suporte.

---

### Documentação
- https://docs.streamlit.io/library/api-reference/session-state - referencia para `st.session_state` no Streamlit.
- https://www.python-httpx.org/ - referencia para httpx.post no frontend.

---

### O que você precisa fazer

1. Localize o evento `done` no loop de `stream_events()` em `frontend/app/pages/research.py`.
2. Após o relatório estar completo em `st.session_state.report_content`, chame `httpx.post` para `/reports/save`.
3. Envolva o save em `try/except Exception: pass` para não quebrar o fluxo se falhar.
4. Rode uma pesquisa e confirme que o relatório aparece no `GET /reports` depois.

### Esqueleto

```text
# TODO: Explore - localizar arquivos, contratos e dependencias citados abaixo.
# TODO: Prototype - validar a menor versao possivel da mudanca.
# TODO: Implement - aplicar a alteracao produtiva no(s) arquivo(s) indicado(s).
# TODO: Verify - rodar teste manual, script, endpoint ou build descrito na task.
```

<details>
<summary>Ver solução completa</summary>

Após o evento `done` do stream, o frontend faz a chamada de save:

```python
# Em frontend/app/pages/research.py
# Adicionar após o loop de stream_events, dentro do bloco elif event_type == "done":

elif event_type == "done":
    if token_buffer:
        report_placeholder.markdown(fix_latex(st.session_state.report_content))
    status_placeholder.empty()
    render_activity()

    # Salva o relatório no backend (se configurado)
    api_save_url = os.getenv("RESEARCH_API_URL", "").replace("/stream", "").replace("/research", "") + "/reports/save"
    if st.session_state.report_content and api_save_url:
        try:
            httpx.post(api_save_url, json={
                "mode": mode,
                "company": fields.get("company") or fields.get("target_company") or fields.get("competitor"),
                "query": query,
                "markdown_content": st.session_state.report_content,
                "user_id": "dev-user-001",  # substituído pelo JWT no Sprint 6
            }, timeout=10)
        except Exception:
            pass  # save failure não deve quebrar a experiência do usuário
```

> **Por que `pass` no except?** O save é uma operação secundária. Se o Supabase estiver fora do ar ou a conexão cair, o usuário ainda tem o relatório na tela e pode exportar manualmente. Não deve aparecer uma tela de erro por causa de uma operação de persistência.

---

</details>

- [ ] **Step 5.1: Save chamado apenas depois do evento `done` (relatório completo).**
- [ ] **Step 5.2: `try/except Exception: pass` envolve o save — falha não quebra a UI.**
- [ ] **Step 5.3: Após uma pesquisa, `GET /reports?user_id=dev-user-001` lista o relatório.**
- [ ] **Step 5.4: Fechar a aba durante o stream não gera erros visíveis no relançamento.**

### Resumo
> *Preencher apos concluir a task: o que foi alterado, qual verificacao passou, e qual risco ainda merece atencao?*

---

## Resumo do Sprint 5

| Artefato | Localização | O que faz |
|---|---|---|
| Schema SQL | Supabase SQL Editor | Tabelas + RLS + trigger de tsvector |
| `backend/db.py` | Novo arquivo | Cliente Supabase singleton |
| `POST /reports/save` | `backend/api.py` | Persiste pesquisa + relatório |
| `GET /reports` | `backend/api.py` | Lista com filtros + full-text search |
| Save pós-stream | `frontend/app/pages/research.py` | Chama save após evento `done` |

**Critério de conclusão:** após rodar uma pesquisa no Streamlit, o relatório aparece listado em `GET /reports`, e a busca por texto no conteúdo retorna o relatório correto.

## Solo Developer Ready

- [ ] Ambiente Supabase escolhido e documentado.
- [ ] `supabase/migrations/001_reports.sql` foi aplicado no banco certo.
- [ ] `SUPABASE_SERVICE_KEY` esta somente no backend.
- [ ] `POST /reports/save` funciona com `local-dev-user` na fase pre-auth.
- [ ] `GET /reports` lista e filtra relatorios salvos.
