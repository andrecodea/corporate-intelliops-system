# Sprint 9 — Collaboration & Org: Guia Instrucional

## Contexto e Objetivo

O Sprint 9 transforma o produto de single-user para multi-tenant. Um usuário passa a pertencer a uma organização, e pode compartilhar relatórios internamente. Esse sprint é onde multi-tenancy é introduzido — e errar o modelo de dados aqui é caro, porque todas as queries futuras dependem dele.

## Pré-requisitos e decisões de segurança

- Sprints 5 e 6 concluídos: relatórios persistidos, Supabase Auth funcionando e `org_id` disponível no contexto do usuário.
- Sprints 7 e 8 podem existir, mas não são obrigatórios para implementar colaboração em relatórios.
- O link compartilhado deste sprint é **público por token**: qualquer pessoa com o token consegue visualizar o relatório. Se quiser link interno restrito à org, mantenha autenticação e valide membership antes de retornar o conteúdo.
- Para evitar ambiguidade, implemente primeiro o fluxo simples: um usuário cria sua organização automaticamente no signup e vira `admin`.
- Convites por email, SSO/SAML e audit log ficam fora deste sprint.

**Princípio central:** o modelo de dados define os limites do que é possível. Antes de escrever uma linha de código, entenda o modelo.

---

## Task 0: `backend/routers/` - Modularizar API e resolver contexto auth/org

**Estimativa:** ~20min

**O que é e por que existe**

O backend atual comeca monolitico em `backend/api.py`. Antes de adicionar orgs, roles e compartilhamento, crie um padrao claro para routers e uma funcao unica que resolve usuario/organizacao a partir do JWT Supabase.

**Files:**
- Criar/Editar: `backend/routers/__init__.py`
- Criar/Editar: `backend/auth.py`
- Criar/Editar: `backend/api.py`

---

### Conceito: Multi-tenancy precisa de contexto unico
> Toda regra de org depende da mesma pergunta: quem e o usuario e a qual organizacao ele pertence? Se cada endpoint responder isso de um jeito, bugs de permissao aparecem. Um helper central de auth/org reduz duplicacao e torna as policies de acesso auditaveis.

---

### Documentação
- https://fastapi.tiangolo.com/tutorial/bigger-applications/ - referencia oficial para routers.
- https://supabase.com/docs/guides/auth - referencia oficial de Supabase Auth.
- https://supabase.com/docs/guides/auth/row-level-security - referencia oficial de RLS com Auth.

---

### O que você precisa fazer

1. Crie `backend/routers/` e registre routers no `backend/api.py`.
2. Crie `backend/auth.py` com um helper para ler `Authorization: Bearer <token>`.
3. Resolva `user_id`, `org_id` e `role` server-side.
4. Defina que endpoints publicos sao excecao explicita: `/shared/{token}`.
5. So depois implemente schema multi-tenant.

### Esqueleto

```text
# TODO: Explore - identificar endpoints atuais em backend/api.py.
# TODO: Prototype - criar router vazio e incluir no app sem quebrar /research/stream.
# TODO: Implement - criar helper auth/org reutilizavel.
# TODO: Verify - /research/stream continua respondendo e router novo aparece em /docs.
```

<details>
<summary>Ver solução completa</summary>

Estrutura alvo:

```text
backend/
  api.py
  auth.py
  routers/
    __init__.py
    orgs.py
    reports.py
```

Regra de ouro: `SUPABASE_SERVICE_KEY` pode ficar no backend, mas o backend nao deve aceitar `org_id` confiando no corpo da request. O `org_id` usado para autorizacao vem do perfil/membership encontrado a partir do usuario autenticado.

Endpoints publicos devem ser nomeados e revisados individualmente:

- `GET /shared/{token}`
- `POST /stripe/webhook` no Sprint 10

</details>

- [ ] **Step 0.1: `backend/routers/` criado sem quebrar endpoints existentes.**
- [ ] **Step 0.2: Helper de auth/org criado em um unico arquivo.**
- [ ] **Step 0.3: `/research/stream` continua funcionando.**
- [ ] **Step 0.4: Endpoints publicos foram listados explicitamente.**

### Resumo
> *Preencher apos concluir a task: como o backend resolve usuario/org e quais endpoints ficaram publicos?*

---

## O Modelo de Dados Multi-Tenant

```
auth.users (Supabase Auth)
    │
    │ 1:1
    ▼
profiles (user_id, full_name, avatar_url, org_id, role)
    │
    │ N:1
    ▼
organizations (id, name, slug, plan, created_at)
    │
    │ 1:N
    ▼
researches (id, user_id, org_id, mode, company, ...)
    │
    │ 1:N
    ▼
reports (id, research_id, markdown_content, shared_link_token, ...)
```

O campo `org_id` em `researches` é o que habilita o compartilhamento dentro da organização: uma query pode retornar todos os relatórios `WHERE org_id = $1` em vez de `WHERE user_id = $1`.

---

## Task 1: `supabase/migrations/004_orgs.sql` - Schema Multi-Tenant

**Estimativa:** ~45min

**O que é e por que existe**

Cria as tabelas `organizations`, expande `profiles` com `org_id` e `role`, adiciona `org_id` em `researches` e `shared_link_token` em `reports`. Sem este schema, multi-tenancy e compartilhamento por link não existem no banco.

**Files:**
- Criar/Editar: `supabase/migrations/004_orgs.sql`

---

### Conceito: RLS de org vs RLS de usuário — dois níveis de visibilidade na mesma tabela
> A RLS do Sprint 5 protegia `researches` apenas por `user_id`: cada usuário via só os próprios registros. Com orgs, a visibilidade muda: `SELECT` deve retornar tudo da organização, mas `INSERT/UPDATE/DELETE` continua restrito ao próprio usuário. Isso exige duas policies separadas na mesma tabela.
>
> | Policy | Operação | Condição | Efeito |
> |---|---|---|---|
> `users see org researches` | SELECT | `user_id = auth.uid() OR org_id IN (SELECT org_id FROM profiles WHERE user_id = auth.uid())` | Membro vê todos os relatórios da org |
> `users manage own researches` | ALL (write) | `user_id = auth.uid()` | Membro só edita/deleta os próprios |
>
> Sem separar SELECT de ALL, ou o membro não vê os relatórios do colega, ou pode deletar o trabalho de outro — os dois erros são graves.

---

### Documentação
- https://supabase.com/docs/guides/auth/row-level-security - criação de policies RLS com `auth.uid()` e subqueries.
- https://www.postgresql.org/docs/current/ddl-constraints.html - `CHECK`, `UNIQUE`, `REFERENCES` e constraints em DDL.

---

### O que você precisa fazer

**Passo 1.1 — Criar tabela `organizations` com slug único**
Intent: o banco precisa de uma tabela para orgs antes de qualquer FK para ela.
Consequência: `ALTER TABLE profiles ADD COLUMN org_id` vai falhar se `organizations` não existir.
→ `CREATE TABLE organizations (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), name TEXT NOT NULL, slug TEXT NOT NULL UNIQUE, plan TEXT NOT NULL DEFAULT 'free' CHECK (plan IN ('free','pro','enterprise')), created_at TIMESTAMPTZ NOT NULL DEFAULT now());`

**Passo 1.2 — Expandir `profiles` e `researches` com `org_id` e `role`**
Intent: vincular usuário a uma org e dar-lhe um papel dentro dela.
Consequência: sem `org_id` em `profiles`, o JOIN nas policies RLS não resolve org membership.
→ `ALTER TABLE profiles ADD COLUMN org_id UUID REFERENCES organizations(id); ALTER TABLE profiles ADD COLUMN role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('admin','member'));`

**Passo 1.3 — Adicionar `shared_link_token` em `reports` com índice parcial**
Intent: habilitar lookup rápido de relatório por token público.
Consequência: sem `WHERE shared_link_token IS NOT NULL`, o índice cresce com NULLs desnecessários.
→ `ALTER TABLE reports ADD COLUMN shared_link_token TEXT UNIQUE; CREATE INDEX idx_reports_shared_token ON reports (shared_link_token) WHERE shared_link_token IS NOT NULL;`

**Passo 1.4 — Substituir policy de SELECT em `researches` pela policy de org**
Intent: membros da mesma org devem ver os relatórios uns dos outros.
Consequência: sem dropar a policy antiga, as duas coexistem e o PostgreSQL une as condições com OR — resultado imprevisível.
→ `DROP POLICY "users see own researches" ON researches; CREATE POLICY "users see org researches" ON researches FOR SELECT USING (...);`

### Esqueleto

```sql
-- TODO: 1.1 - CREATE TABLE organizations com id, name, slug UNIQUE, plan CHECK, created_at
-- TODO: 1.2 - ALTER TABLE profiles ADD COLUMN org_id + role CHECK('admin','member')
-- TODO: 1.2 - ALTER TABLE researches ADD COLUMN org_id
-- TODO: 1.3 - ALTER TABLE reports ADD COLUMN shared_link_token UNIQUE
-- TODO: 1.3 - CREATE INDEX parcial WHERE shared_link_token IS NOT NULL
-- TODO: 1.4 - DROP POLICY antiga + CREATE POLICY "users see org researches" FOR SELECT
-- TODO: 1.4 - CREATE POLICY "users manage own researches" FOR ALL USING user_id = auth.uid()
```

<details>
<summary>Ver solução completa</summary>

```sql
-- Tabela de organizações
CREATE TABLE organizations (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name       TEXT NOT NULL,
  slug       TEXT NOT NULL UNIQUE,  -- URL-friendly: "acme-corp"
  plan       TEXT NOT NULL DEFAULT 'free'
                CHECK (plan IN ('free', 'pro', 'enterprise')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Atualizar profiles para incluir org e role
ALTER TABLE profiles ADD COLUMN org_id UUID REFERENCES organizations(id);
ALTER TABLE profiles ADD COLUMN role TEXT NOT NULL DEFAULT 'member'
  CHECK (role IN ('admin', 'member'));

-- Adicionar org_id em researches
ALTER TABLE researches ADD COLUMN org_id UUID REFERENCES organizations(id);

-- Token para compartilhamento de relatório por link
ALTER TABLE reports ADD COLUMN shared_link_token TEXT UNIQUE;

-- Índice para lookup de token (usado na rota pública /shared/:token)
CREATE INDEX idx_reports_shared_token ON reports (shared_link_token)
  WHERE shared_link_token IS NOT NULL;
```

### RLS Multi-Tenant

A RLS do Sprint 5 só protegia por `user_id`. Agora precisa incluir membros da mesma organização:

```sql
-- Substituir a policy de researches do Sprint 5
DROP POLICY "users see own researches" ON researches;

CREATE POLICY "users see org researches"
  ON researches FOR SELECT
  USING (
    user_id = auth.uid()         -- próprios relatórios
    OR
    org_id IN (                  -- ou relatórios da mesma org
      SELECT org_id FROM profiles
      WHERE user_id = auth.uid()
        AND org_id IS NOT NULL
    )
  );

-- Para INSERT/UPDATE/DELETE, o usuário só age nos próprios
CREATE POLICY "users manage own researches"
  ON researches FOR ALL
  USING (user_id = auth.uid());
```

> **Por que duas policies separadas para SELECT e ALL?** O `SELECT` é mais permissivo (vê a org toda). O `ALL` para write operations é restrito ao próprio usuário — um membro não pode deletar ou editar o relatório de outro membro. Separar as policies dá controle granular por operação.

---

</details>

- [ ] **Step 1.1: `organizations` criada com `slug UNIQUE` e `plan CHECK`.**
- [ ] **Step 1.2: `profiles` tem `org_id` e `role`; `researches` tem `org_id`.**
- [ ] **Step 1.3: `shared_link_token` adicionado em `reports` com índice parcial.**
- [ ] **Step 1.4: Policy antiga dropada; nova policy SELECT vê org toda; write restrito ao próprio `user_id`.**

### Resumo
> *Preencher apos concluir a task: o que foi alterado, qual verificacao passou, e qual risco ainda merece atencao?*

---
## Task 2: `backend/routers/orgs.py` - Fluxo de Criação de Organização

**Estimativa:** ~30min

**O que é e por que existe**

Implementa o endpoint `POST /orgs` que cria uma organização e vincula o usuário criador como `admin`. É o Fluxo A (create-on-signup): simples, um usuário cria sua org e vira admin imediatamente. Fluxo B (invite-based) fica para sprint futuro.

**Files:**
- Criar/Editar: `backend/routers/orgs.py`

---

### Conceito: Create-on-signup — uma org por usuário vs org compartilhada
> Existem dois modelos para B2B multi-tenant. No Fluxo A, a org nasce junto com o usuário: simples de implementar, mas cria muitas orgs de uma pessoa só. No Fluxo B, a org existe independentemente e membros são convidados: modelo correto para B2B real, mas exige email + fluxo de aceite. O Sprint 9 usa Fluxo A intencionalmente para não bloquear o restante da feature.
>
> | Fluxo | Como a org nasce | Quem é admin | Quando usar |
> |---|---|---|---|
> | A — Create-on-signup | Junto com o usuário, no mesmo request | O próprio criador | MVP, Sprint 9 |
> | B — Invite-based | Org criada separadamente; membros convidados | Quem criou a org | Colaboração avançada |
>
> Sem escolher explicitamente Fluxo A, o desenvolvedor pode tentar implementar o Fluxo B e travar no sprint por falta de email service.

---

### Documentação
- https://fastapi.tiangolo.com/tutorial/bigger-applications/ - como criar e registrar routers modulares no FastAPI.
- https://supabase.com/docs/reference/python/insert - `supabase.table().insert().select().single()` para criar registro e retornar o objeto criado.

---

### O que você precisa fazer

**Passo 2.1 — Criar o router `orgs.py` com `POST /orgs`**
Intent: o endpoint recebe `org_name` no body e cria a organização no banco.
Consequência: sem o router registrado em `api.py`, a rota não aparece em `/docs` e o frontend não consegue chamar.
→ `router = APIRouter(prefix="/orgs", tags=["orgs"])` + `@router.post("")`

**Passo 2.2 — Gerar `slug` a partir do nome da org**
Intent: o slug é o identificador URL-friendly da org (ex: "Acme Corp" → "acme-corp").
Consequência: sem `UNIQUE` no slug (definido na Task 1), dois usuários com nomes parecidos criam conflito de slug.
→ `slug = name.lower().replace(" ", "-")` com regex para remover caracteres não alfanuméricos.

**Passo 2.3 — Vincular o usuário como `admin` após criar a org**
Intent: o criador da org deve ser `admin` imediatamente — sem esta etapa, nenhum usuário tem `role='admin'`.
Consequência: sem o UPDATE em `profiles`, o usuário fica com `org_id=NULL` e `role='member'` (default) — invisível para a RLS da Task 1.
→ `supabase.table("profiles").update({"org_id": org.id, "role": "admin"}).eq("user_id", user_id)`

**Passo 2.4 — Registrar o router em `backend/api.py`**
Intent: FastAPI só reconhece a rota quando o router é incluído no app.
Consequência: sem `app.include_router(orgs_router)`, `POST /orgs` retorna 404.
→ `from backend.routers import orgs; app.include_router(orgs.router)`

### Esqueleto

```python
# backend/routers/orgs.py
from fastapi import APIRouter, Depends
import re

router = APIRouter(prefix="/orgs", tags=["orgs"])

@router.post("")
async def create_org(name: str, user_id: str):
    # TODO: 2.2 - gerar slug: lower + replace spaces + regex [^a-z0-9-]
    # TODO: 2.1 - insert em organizations com name e slug
    # TODO: 2.3 - update profiles com org_id e role='admin' WHERE user_id
    # TODO: retornar org criada
    pass
```

<details>
<summary>Ver solução completa</summary>

Um novo usuário precisa de um caminho para criar ou entrar numa organização. Dois fluxos comuns:

**Fluxo A — Create on signup:** ao criar a conta, o usuário cria uma org com o mesmo nome. Simples, mas cria muitas orgs de uma pessoa só.

**Fluxo B — Invite-based:** orgs existem independentemente. Um admin convida membros por email. Mais complexo, mas o modelo certo para B2B.

Para o Sprint 9, implemente o **Fluxo A** (simples) e deixe o Fluxo B para um sprint futuro:

```typescript
// src/lib/org.ts

export async function createOrganizationForUser(userId: string, orgName: string) {
  const slug = orgName.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '')

  // 1. Cria a organização
  const { data: org } = await supabase
    .from('organizations')
    .insert({ name: orgName, slug })
    .select()
    .single()

  // 2. Vincula o usuário como admin da org
  await supabase
    .from('profiles')
    .update({ org_id: org.id, role: 'admin' })
    .eq('user_id', userId)

  return org
}
```

---

</details>

- [ ] **Step 2.1: `POST /orgs` aparece em `/docs` sem erro 422.**
- [ ] **Step 2.2: Slug gerado sem espaços ou caracteres especiais.**
- [ ] **Step 2.3: Após criar org, `profiles.org_id` e `role='admin'` atualizados para o `user_id` do criador.**
- [ ] **Step 2.4: Router registrado em `api.py`; `/docs` lista `/orgs`.**

### Resumo
> *Preencher apos concluir a task: o que foi alterado, qual verificacao passou, e qual risco ainda merece atencao?*

---
## Task 3: `backend/routers/reports.py` - Compartilhamento por Link

**Estimativa:** ~30min

**O que é e por que existe**

Implementa `POST /reports/{report_id}/share` (gera token) e `GET /shared/{token}` (rota pública sem auth). A rota pública é a exceção explícita ao AuthGuard: qualquer pessoa com o token consegue ver o relatório.

**Files:**
- Criar/Editar: `backend/routers/reports.py`

---

### Conceito: Token de alta entropia vs UUID — previsibilidade importa em links públicos
> Um link de compartilhamento funciona como uma senha de uso único: quem tem o token, acessa o relatório. UUID v4 tem 122 bits de aleatoriedade e é amplamente usado como PK — mas não foi projetado para ser um token de segurança. `secrets.token_urlsafe(32)` gera 256 bits de entropia em base64url, é menor em caracteres e é a recomendação explícita da stdlib Python para tokens de segurança.
>
> | Gerador | Entropia | Uso pretendido | Previsível? |
> |---|---|---|---|
> | `uuid.uuid4()` | 122 bits | Primary key | Não, mas não é token de segurança |
> | `secrets.token_urlsafe(32)` | 256 bits | Token de auth/compartilhamento | Não — projetado para segurança |
>
> Sem entropia suficiente, um atacante pode enumerar tokens e acessar relatórios de outros usuários.

---

### Documentação
- https://docs.python.org/3/library/secrets.html - `secrets.token_urlsafe(nbytes)` — módulo oficial para tokens criptograficamente seguros.
- https://fastapi.tiangolo.com/tutorial/path-params/ - parâmetros de path como `{report_id}` e `{token}`.

---

### O que você precisa fazer

**Passo 3.1 — Criar `POST /reports/{report_id}/share` que gera e persiste o token**
Intent: o endpoint gera um token único e salva em `reports.shared_link_token`.
Consequência: sem persistir, o token é descartado e o link nunca funciona.
→ `token = secrets.token_urlsafe(32)` + `supabase.table("reports").update({"shared_link_token": token}).eq("id", report_id)`

**Passo 3.2 — Criar `GET /shared/{token}` sem dependência de auth**
Intent: qualquer pessoa (incluindo não autenticada) deve conseguir acessar este endpoint.
Consequência: se o endpoint herdar o `Depends(get_current_user)` do router, retorna 401 para quem não tem login.
→ Não adicionar `Depends` de auth; usar `supabase_service_client` (não o client do usuário) para buscar pelo token.

**Passo 3.3 — Retornar 404 quando token não existe ou foi revogado**
Intent: não vazar informação sobre existência de relatórios.
Consequência: retornar 200 com dados vazios revela que o relatório existe mas o token expirou.
→ `if not result.data: raise HTTPException(status_code=404, detail="Report not found")`

**Passo 3.4 — Adicionar rota `/shared/{token}` no frontend sem AuthGuard**
Intent: a rota pública não pode estar dentro do bloco protegido pelo AuthGuard.
Consequência: usuário não autenticado recebe redirect para `/login` em vez de ver o relatório.
→ `<Route path="/shared/:token" element={<SharedReport />} />` fora do `<AuthGuard>`.

### Esqueleto

```python
# backend/routers/reports.py
import secrets
from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["reports"])

@router.post("/reports/{report_id}/share")
async def create_share_link(report_id: str):
    # TODO: 3.1 - secrets.token_urlsafe(32)
    # TODO: 3.1 - update reports SET shared_link_token WHERE id = report_id
    # TODO: retornar {"token": token, "url": f"/shared/{token}"}
    pass

@router.get("/shared/{token}")
async def get_shared_report(token: str):
    # TODO: 3.2 - buscar reports WHERE shared_link_token = token (sem auth)
    # TODO: 3.3 - se result.data vazio: raise HTTPException 404
    # TODO: retornar result.data[0]
    pass
```

<details>
<summary>Ver solução completa</summary>

Um relatório pode ser compartilhado por link dentro da org (ou externamente, dependendo da regra de negócio). O padrão é gerar um token aleatório e criar uma rota pública `/shared/:token`.

### Backend — gerar token

```python
# backend/api.py
import secrets

@app.post("/reports/{report_id}/share")
async def create_share_link(report_id: str):
    """Gera um token de compartilhamento único para o relatório."""
    token = secrets.token_urlsafe(32)  # 256 bits de entropia — não é adivinável

    db = get_supabase()
    db.table("reports").update({"shared_link_token": token}).eq("id", report_id).execute()

    return {"token": token, "url": f"/shared/{token}"}

@app.get("/shared/{token}")
async def get_shared_report(token: str):
    """Retorna o relatório pelo token público. Não requer autenticação."""
    db = get_supabase()
    result = db.table("reports").select("*").eq("shared_link_token", token).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Report not found or link expired")

    return result.data[0]
```

> **Por que `secrets.token_urlsafe(32)` e não UUID?** UUIDs são sequenciais e previsíveis (v4 tem 122 bits de aleatoriedade). `token_urlsafe(32)` gera 256 bits de entropia base64url — menor chance de colisão e adequado para tokens de segurança.

### Frontend — rota pública

```typescript
// src/pages/SharedReport.tsx
// Esta rota NÃO é protegida pelo AuthGuard — é pública
import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import ReactMarkdown from 'react-markdown'

export function SharedReport() {
  const { token } = useParams()

  const { data, isLoading, error } = useQuery({
    queryKey: ['shared-report', token],
    queryFn: () => fetch(`/api/shared/${token}`).then(r => r.json()),
  })

  if (isLoading) return <div>Loading...</div>
  if (error) return <div>Report not found.</div>

  return (
    <div className="max-w-3xl mx-auto py-8 px-4">
      <div className="text-sm text-gray-500 mb-4">
        Shared report — IntelliOps
      </div>
      <ReactMarkdown>{data.markdown_content}</ReactMarkdown>
    </div>
  )
}
```

Adicione no router (sem AuthGuard):

```typescript
<Route path="/shared/:token" element={<SharedReport />} />
```

---

</details>

- [ ] **Step 3.1: `POST /reports/{id}/share` retorna `{"token": "...", "url": "/shared/..."}`.**
- [ ] **Step 3.2: `GET /shared/{token}` retorna 200 sem `Authorization` header.**
- [ ] **Step 3.3: Token inexistente retorna 404 (não 200 com lista vazia).**
- [ ] **Step 3.4: Rota `/shared/:token` no frontend fora do `<AuthGuard>` — usuário sem login consegue acessar.**

### Resumo
> *Preencher apos concluir a task: o que foi alterado, qual verificacao passou, e qual risco ainda merece atencao?*

---
## Task 4: `backend/routers/orgs.py` - Roles: Admin vs Member

**Estimativa:** ~30min

**O que é e por que existe**

Implementa a função utilitária `getCurrentUserRole()` no frontend e o helper de verificação de role no backend. Ambos consultam `profiles.role` para condicionar ações restritas a admins (ex: convidar membros, mudar plano).

**Files:**
- Criar/Editar: `backend/routers/orgs.py`
- Criar/Editar: `frontend/src/lib/auth.ts`

---

### Conceito: Roles como enum, não como permissões granulares — V1 não precisa de RBAC completo
> RBAC (Role-Based Access Control) completo tem permissões atômicas (`can_invite`, `can_delete_any`, `can_change_plan`) que se combinam em roles. É o modelo correto para Enterprise, mas para V1 B2B basta dois papéis fixos: `admin` e `member`. A diferença entre eles cabe numa tabela de 6 linhas. Adicionar RBAC agora seria over-engineering que atrasa o sprint sem benefício real.
>
> | Ação | member | admin |
> |---|---|---|
> | Criar pesquisa | ✅ | ✅ |
> | Ver relatórios da org | ✅ | ✅ |
> | Deletar relatório próprio | ✅ | ✅ |
> | Deletar relatório de outro membro | ❌ | ✅ |
> | Convidar membros | ❌ | ✅ |
> | Mudar plano da org | ❌ | ✅ |
>
> Sem um enum explícito no `CHECK` da Task 1, valores inválidos como `"owner"` ou `"superadmin"` entrariam no banco silenciosamente.

---

### Documentação
- https://supabase.com/docs/reference/python/select - `supabase.table().select("role").eq().single()` para buscar role do usuário.
- https://react.dev/reference/react/useState - `useState` + `useEffect` para carregar role assincronamente no componente.

---

### O que você precisa fazer

**Passo 4.1 — Criar helper de verificação de role no backend**
Intent: o backend precisa checar `role='admin'` antes de executar ações restritas.
Consequência: sem o helper, cada endpoint repete a query `SELECT role FROM profiles` — duplicação que facilita bugs de inconsistência.
→ `async def require_admin(user_id: str, db) -> None: ... raise HTTPException(403)` se role não for admin.

**Passo 4.2 — Criar `getCurrentUserRole()` no frontend**
Intent: o frontend precisa saber o role para mostrar ou esconder botões de admin.
Consequência: sem checar role, o botão "Invite Members" aparece para todos — e o backend rejeita a chamada com 403, gerando UX confusa.
→ `supabase.from("profiles").select("role").eq("user_id", user.id).single()`

**Passo 4.3 — Usar role para condicionar UI no componente Settings ou Dashboard**
Intent: o botão "Invite Members" só deve aparecer para admins.
Consequência: renderizar o botão para todos e só bloquear no backend cria UX confusa — o usuário clica e recebe 403 sem entender por quê.
→ `{role === 'admin' && <button>Invite Members</button>}`

**Passo 4.4 — Testar os dois roles manualmente**
Intent: confirmar que um `member` não consegue acessar ação de admin nem via UI nem via curl.
Consequência: sem teste dos dois caminhos, a proteção pode existir só na UI (bypassável) ou só no backend (confuso).
→ Criar dois usuários, um admin e um member; confirmar que o member não vê o botão e recebe 403 se chamar direto.

### Esqueleto

```python
# backend/routers/orgs.py (adicionar ao arquivo da Task 2)
from fastapi import HTTPException

async def require_admin(user_id: str, db) -> None:
    # TODO: 4.1 - buscar profiles.role WHERE user_id
    # TODO: 4.1 - se role != 'admin': raise HTTPException(status_code=403, detail="Admin only")
    pass
```

```typescript
// frontend/src/lib/auth.ts
export async function getCurrentUserRole(): Promise<'admin' | 'member' | null> {
  // TODO: 4.2 - supabase.auth.getUser()
  // TODO: 4.2 - supabase.from('profiles').select('role').eq('user_id', user.id).single()
  // TODO: 4.2 - return data?.role ?? null
}
```

<details>
<summary>Ver solução completa</summary>

A diferença entre admin e member em V1 é simples:

| Ação | Member | Admin |
|---|---|---|
| Criar pesquisa | ✅ | ✅ |
| Ver relatórios da org | ✅ | ✅ |
| Deletar relatório próprio | ✅ | ✅ |
| Deletar relatório de outro membro | ❌ | ✅ |
| Convidar membros | ❌ | ✅ |
| Mudar plano da org | ❌ | ✅ |

Implemente a verificação de role como uma função utilitária:

```typescript
// src/lib/auth.ts
import { supabase } from './supabase'

export async function getCurrentUserRole(): Promise<'admin' | 'member' | null> {
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) return null

  const { data } = await supabase
    .from('profiles')
    .select('role')
    .eq('user_id', user.id)
    .single()

  return data?.role ?? null
}
```

Use para condicionar UI:

```typescript
// Mostra botão "Invite Members" só para admins
const [role, setRole] = useState<string | null>(null)

useEffect(() => {
  getCurrentUserRole().then(setRole)
}, [])

{role === 'admin' && (
  <button onClick={() => navigate('/settings/invite')}>
    Invite Members
  </button>
)}
```

---

## O que Deixar para Depois

O Sprint 9 intencionalmente **não** inclui:

- **Convite por email** — requer envio de email (Resend, SendGrid) e um fluxo de aceite. Adicione em um sprint futuro de colaboração avançada.
- **SSO / SAML** — necessário para Enterprise. Deixe para Monetização (Sprint 10).
- **Audit log** — quem acessou o quê. Deixe para Enterprise tier.
- **Org settings avançados** — limites de uso por plano, billing per seat. Sprint 10.

---

</details>

- [ ] **Step 4.1: `require_admin()` levanta 403 quando role é `member`.**
- [ ] **Step 4.2: `getCurrentUserRole()` retorna `'admin'` ou `'member'` — nunca `undefined`.**
- [ ] **Step 4.3: Botão "Invite Members" visível para admin e ausente para member.**
- [ ] **Step 4.4: curl direto ao endpoint de admin com token de member retorna 403.**

### Resumo
> *Preencher apos concluir a task: o que foi alterado, qual verificacao passou, e qual risco ainda merece atencao?*

---

## Resumo do Sprint 9

| Artefato | O que faz | Padrão |
|---|---|---|
| Schema SQL (organizations, slug, shared_link_token) | Multi-tenancy no banco | — |
| RLS policies atualizadas | SELECT vê org toda; write restrito ao próprio | — |
| `createOrganizationForUser()` | Fluxo de criação de org no signup | — |
| `POST /reports/:id/share` | Gera token de compartilhamento | — |
| `GET /shared/:token` | Rota pública sem auth | — |
| `SharedReport.tsx` | Frontend da rota pública | — |
| `getCurrentUserRole()` | Verifica role para condicionar UI | — |

**Critério de conclusão:** um usuário admin consegue compartilhar um relatório por link, e um usuário não autenticado consegue visualizar o relatório pelo link sem fazer login.

## Solo Developer Ready

- [ ] Backend tem helper unico para resolver `user_id`, `org_id` e `role`.
- [ ] `004_orgs.sql` foi aplicado depois das migrations anteriores.
- [ ] Endpoints privados nao aceitam `org_id` confiando no frontend.
- [ ] Link publico por token foi testado sem login.
- [ ] Roles admin/member foram testadas em pelo menos uma acao restrita.
