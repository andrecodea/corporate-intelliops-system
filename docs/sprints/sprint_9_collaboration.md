# Sprint 9 — Collaboration & Org: Guia Instrucional

## Contexto e Objetivo

O Sprint 7 transforma o produto de single-user para multi-tenant. Um usuário passa a pertencer a uma organização, e pode compartilhar relatórios internamente. Esse sprint é onde multi-tenancy é introduzido — e errar o modelo de dados aqui é caro, porque todas as queries futuras dependem dele.

**Princípio central:** o modelo de dados define os limites do que é possível. Antes de escrever uma linha de código, entenda o modelo.

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

## Tarefa 1 — Schema Multi-Tenant

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

## Tarefa 2 — Fluxo de Criação de Organização

Um novo usuário precisa de um caminho para criar ou entrar numa organização. Dois fluxos comuns:

**Fluxo A — Create on signup:** ao criar a conta, o usuário cria uma org com o mesmo nome. Simples, mas cria muitas orgs de uma pessoa só.

**Fluxo B — Invite-based:** orgs existem independentemente. Um admin convida membros por email. Mais complexo, mas o modelo certo para B2B.

Para o Sprint 7, implemente o **Fluxo A** (simples) e deixe o Fluxo B para o Sprint 7.5 ou 8:

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

## Tarefa 3 — Compartilhamento por Link

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

## Tarefa 4 — Roles: Admin vs Member

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

O Sprint 7 intencional **não** inclui:

- **Convite por email** — requer envio de email (Resend, SendGrid) e um fluxo de aceite. Adicione no Sprint 7.5.
- **SSO / SAML** — necessário para Enterprise. Deixe para Monetização (Sprint 10).
- **Audit log** — quem acessou o quê. Deixe para Enterprise tier.
- **Org settings avançados** — limites de uso por plano, billing per seat. Sprint 10.

---

## Resumo do Sprint 7

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
