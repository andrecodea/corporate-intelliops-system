# Sprint 6 — SaaS Frontend (React): Guia Instrucional

## Contexto e Objetivo

O Sprint 6 substitui o frontend Streamlit por uma SPA React com autenticação real, dashboard de histórico, e streaming SSE. O backend FastAPI não muda — apenas recebe endpoints novos.

Este é o sprint mais extenso do roadmap. O critério de sucesso não é ter tudo perfeito: é ter o fluxo core funcionando — login → pesquisa → relatório — antes de partir para funcionalidades secundárias.

---

## Decisões para desenvolver sem ambiguidade

- O React deve viver em `frontend/` como SPA Vite. O Streamlit atual em `frontend/app/` fica como referência até a paridade estar validada.
- Durante o desenvolvimento, use proxy do Vite para encaminhar `/api/*` para `http://localhost:8005`, evitando CORS.
- Backend local: `uv run uvicorn backend.api:app --reload --port 8005`.
- Frontend local: `cd frontend && npm run dev`.
- Variáveis do React sempre usam prefixo `VITE_`: `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `VITE_API_URL`.
- Critério de paridade: os quatro modos atuais geram a mesma query semântica do Streamlit antes de qualquer melhoria visual.

**Definition of Done do Sprint 6:** login funciona, `/research` faz stream via POST, o relatório é renderizado enquanto chega, o autosave chama `/reports/save`, e `/dashboard` lista o relatório salvo.

---

## Task 0: `frontend/package.json` - Bootstrap do Vite React

**Estimativa:** ~30min

**O que é e por que existe**

A codebase atual ainda tem o frontend Streamlit em `frontend/app/`. Antes de criar componentes React, e preciso transformar `frontend/` em uma SPA Vite real sem apagar o Streamlit que serve como referencia de paridade.

**Files:**
- Criar/Editar: `frontend/package.json`
- Criar/Editar: `frontend/vite.config.ts`
- Criar/Editar: `frontend/index.html`
- Criar/Editar: `frontend/src/main.tsx`

---

### Conceito: Bootstrap antes de componentes
> Componentes React so fazem sentido quando o runtime existe: package scripts, Vite config, entry point e proxy. Se voce comeca por `App.tsx` sem bootstrap, nao tem como testar HMR, imports, env vars ou chamadas ao backend.

---

### Documentação
- https://vite.dev/guide/ - referencia oficial do Vite.
- https://react.dev/learn - referencia oficial do React.
- https://vite.dev/config/server-options.html#server-proxy - referencia oficial para proxy local.

---

### O que você precisa fazer

1. Confirme que `frontend/app/` continua intacto.
2. Crie o projeto Vite dentro de `frontend/`, nao em uma pasta paralela.
3. Configure proxy de `/api` para `http://localhost:8005`.
4. Instale dependencias do Sprint 6.
5. Rode `npm run dev` antes de criar telas complexas.

### Esqueleto

```text
# TODO: Explore - listar conteudo atual de frontend/.
# TODO: Prototype - criar app Vite minimo e rodar npm run dev.
# TODO: Implement - configurar scripts, main.tsx e proxy.
# TODO: Verify - abrir a URL do Vite e confirmar tela React minima.
```

<details>
<summary>Ver solução completa</summary>

Comandos sugeridos:

```bash
cd frontend
npm create vite@latest . -- --template react-ts
npm install
npm install @supabase/supabase-js @tanstack/react-query react-router-dom
npm install -D tailwindcss @tailwindcss/vite
npm run dev
```

Se o Vite reclamar que a pasta nao esta vazia, crie os arquivos manualmente mantendo `frontend/app/`. O Streamlit nao deve ser apagado ate a paridade do Sprint 6 estar validada.

Proxy esperado em `vite.config.ts`:

```typescript
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:8005',
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\/api/, ''),
    },
  },
}
```

</details>

- [ ] **Step 0.1: `frontend/app/` preservado.**
- [ ] **Step 0.2: `frontend/package.json` tem scripts `dev`, `build` e `preview`.**
- [ ] **Step 0.3: `vite.config.ts` proxy `/api` para `8005`.**
- [ ] **Step 0.4: `npm run dev` abre uma tela React minima.**

### Resumo
> *Preencher apos concluir a task: como o Vite foi criado e qual URL local foi validada?*

---

## Stack e Justificativas

| Tecnologia | Por que |
|---|---|
| **Vite + React** | Vite tem HMR instantâneo e build ultrarrápido. React é o padrão da indústria para SPAs com estado complexo. |
| **Supabase Auth** | Auth + banco + storage num só serviço. Elimina a necessidade de implementar JWT, refresh tokens, e sessões do zero. |
| **TanStack Query** | Cache de requisições, loading/error states, refetch automático. Resolve 90% dos problemas de estado assíncrono sem Redux. |
| **Tailwind CSS** | Utility-first: estilos ficam no JSX, sem arquivos CSS separados, sem naming de classes. |

---

## Estrutura de Arquivos

```
frontend/
├── src/
│   ├── main.tsx              # entry point — monta o App com providers
│   ├── App.tsx               # router raiz com rotas protegidas
│   ├── lib/
│   │   ├── supabase.ts       # cliente Supabase (singleton)
│   │   └── api.ts            # funções para chamar o FastAPI
│   ├── components/
│   │   ├── AuthGuard.tsx     # wrapper de rota protegida
│   │   ├── ResearchCard.tsx  # card de pesquisa no dashboard
│   │   ├── FilterSidebar.tsx # filtros do dashboard
│   │   ├── ResearchForm.tsx  # formulário de input por modo
│   │   ├── StreamViewer.tsx  # painel Activity + Report com SSE
│   │   └── ReportView.tsx    # relatório salvo em markdown
│   └── pages/
│       ├── Login.tsx
│       ├── Dashboard.tsx
│       ├── Research.tsx
│       ├── Report.tsx        # /report/:id
│       └── Settings.tsx
├── index.html
├── vite.config.ts
└── package.json
```

---

## Task 1: `frontend/src/App.tsx` - Setup do Projeto

**Estimativa:** ~30min

**O que é e por que existe**

Esta task configura o router React com proteção de rotas via AuthGuard. Sem um router centralizado, cada página precisaria verificar autenticação individualmente.

**Files:**
- Criar/Editar: `frontend/src/App.tsx`

---

### Conceito: Router como ponto único de proteção de acesso
> Em uma SPA React, nenhuma rota deve verificar auth individualmente. O router é o único lugar onde isso acontece: cada rota protegida é envolvida em `<AuthGuard>`. Adicionar uma rota nova significa envolvê-la — não reescrever lógica de auth.
>
> | Abordagem | Consequência |
> |---|---|
> | Verificar auth em cada página | Duplicação; fácil esquecer em uma página nova |
> | AuthGuard no router | Um único ponto de controle; nova rota = `<AuthGuard><Pagina /></AuthGuard>` |

---

### Documentação
- https://reactrouter.com/en/main/components/routes - referencia para Routes e Route.
- https://reactrouter.com/en/main/components/navigate - referencia para redirect com Navigate.

---

### O que você precisa fazer

1. Crie `App.tsx` com `BrowserRouter` e `Routes`.
2. Mapeie as 5 rotas: `/login`, `/dashboard`, `/research`, `/report/:id`, `/settings`.
3. Envolva rotas protegidas em `<AuthGuard>`.
4. Rode `npm run dev` e confirme que `/login` carrega sem erros de import.

### Esqueleto

```tsx
export function App() {
  // TODO: importar BrowserRouter, Routes, Route, Navigate, AuthGuard
  // TODO: rota /login sem AuthGuard
  // TODO: rotas /dashboard, /research, /report/:id, /settings dentro de <AuthGuard>
  // TODO: redirecionar / para /dashboard
}
```

<details>
<summary>Ver solução completa</summary>

```bash
cd frontend
npm create vite@latest . -- --template react-ts
npm install @supabase/supabase-js @tanstack/react-query react-router-dom
npm install -D tailwindcss @tailwindcss/vite
```

Configure `vite.config.ts`:

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      // Redireciona /api/* para o FastAPI em desenvolvimento
      // Evita problemas de CORS sem precisar configurar o backend
      '/api': {
        target: 'http://localhost:8005',
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
```

---

</details>

- [ ] **Step 1.1: `BrowserRouter` e `Routes` importados sem erro de TypeScript.**
- [ ] **Step 1.2: `/login` carrega sem redirect para outra rota.**
- [ ] **Step 1.3: Acessar `/dashboard` sem sessão redireciona para `/login`.**
- [ ] **Step 1.4: `npm run dev` abre sem erros no console do browser.**

### Resumo
> *Preencher apos concluir a task: o que foi alterado, qual verificacao passou, e qual risco ainda merece atencao?*

---
## Task 2: `frontend/src/lib/supabase.ts` - Cliente Supabase

**Estimativa:** ~20min

**O que é e por que existe**

Esta task cria o cliente Supabase compartilhado por toda a aplicação. Centralizar aqui evita recriar clientes e garante que a anon key não seja hardcoded em múltiplos arquivos.

**Files:**
- Criar/Editar: `frontend/src/lib/supabase.ts`

---

### Conceito: anon key no frontend — RLS é a barreira real
> A chave `anon` é segura para expor no navegador porque o Supabase injeta o JWT do usuário autenticado em cada requisição. A RLS usa esse JWT para filtrar dados por `user_id`. A `service_role` bypassa RLS completamente — jamais no frontend.
>
> | Chave | Quem usa | Bypassa RLS? |
> |---|---|---|
> | `anon` | Browser / frontend | Não — RLS filtra por JWT do usuário |
> | `service_role` | Backend / servidor | Sim — acesso irrestrito ao banco |

---

### Documentação
- https://supabase.com/docs/reference/javascript/initializing - referencia para `createClient`.
- https://vitejs.dev/guide/env-and-mode.html - referencia para variáveis `VITE_` expostas ao browser.

---

### O que você precisa fazer

1. Crie `frontend/.env.local` com `VITE_SUPABASE_URL` e `VITE_SUPABASE_ANON_KEY`.
2. Crie `frontend/src/lib/supabase.ts` usando `createClient(url, anonKey)`.
3. Exporte o cliente como `supabase` (singleton de módulo — importado em qualquer arquivo).
4. Importe em `App.tsx` e confirme que não há erro de TypeScript.

### Esqueleto

```typescript
import { createClient } from '@supabase/supabase-js'

// TODO: ler VITE_SUPABASE_URL e VITE_SUPABASE_ANON_KEY de import.meta.env
// TODO: criar e exportar: export const supabase = createClient(url, key)
```

<details>
<summary>Ver solução completa</summary>

Crie `src/lib/supabase.ts`:

```typescript
import { createClient } from '@supabase/supabase-js'

// Variáveis de ambiente expostas ao frontend (prefixo VITE_ é obrigatório no Vite)
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

// Nota: usa a anon key (não a service_role).
// No frontend, o Supabase Auth injeta o JWT do usuário automaticamente em cada
// requisição. A RLS do banco usa esse JWT para filtrar os dados.
export const supabase = createClient(supabaseUrl, supabaseAnonKey)
```

Crie `.env.local` na pasta `frontend/`:

```
VITE_SUPABASE_URL=https://xxxxxxxxxx.supabase.co
VITE_SUPABASE_ANON_KEY=eyJ...
VITE_API_URL=http://localhost:8005
```

> **`anon` vs `service_role` no frontend:** a `anon` key é segura para expor no navegador porque a RLS do banco garante que o usuário só acessa os próprios dados. A `service_role` bypassa RLS — jamais no frontend.

---

</details>

- [ ] **Step 2.1: `.env.local` criado com `VITE_SUPABASE_URL` e `VITE_SUPABASE_ANON_KEY`.**
- [ ] **Step 2.2: `import { supabase } from '../lib/supabase'` resolve sem erro de TypeScript.**
- [ ] **Step 2.3: `supabase.auth.getSession()` retorna objeto sem lançar exceção.**
- [ ] **Step 2.4: `service_role` key não aparece em nenhum arquivo do diretório `frontend/`.**

### Resumo
> *Preencher apos concluir a task: o que foi alterado, qual verificacao passou, e qual risco ainda merece atencao?*

---
## Task 3: `frontend/src/components/AuthGuard.tsx` - AuthGuard

**Estimativa:** ~30min

**O que é e por que existe**

Esta task cria o componente que protege rotas. O AuthGuard verifica a sessão Supabase antes de renderizar qualquer rota privada, redirecionando para `/login` se não houver sessão.

**Files:**
- Criar/Editar: `frontend/src/components/AuthGuard.tsx`

---

### Conceito: Decorator Pattern — injetar auth sem modificar o componente filho
> `<AuthGuard><Dashboard /></AuthGuard>` adiciona verificação de sessão sem que `Dashboard` saiba que existe auth. É o Decorator Pattern: um componente envolve outro e adiciona comportamento sem alterar o envolvido.
>
> | Alternativa | Problema |
> |---|---|
> | Verificar sessão dentro de `Dashboard` | Dashboard conhece detalhes de auth; difícil testar em isolamento |
> | `<AuthGuard>` no router | Dashboard é puro; auth centralizado em um único lugar |

---

### Documentação
- https://supabase.com/docs/reference/javascript/auth-onauthstatechange - referencia para ouvir mudanças de sessão.
- https://react.dev/reference/react/useEffect - referencia para cleanup de subscription no unmount.

---

### O que você precisa fazer

1. Crie estado `'loading' | 'authenticated' | 'unauthenticated'`.
2. Chame `getSession()` no mount para estado inicial.
3. Assine `onAuthStateChange` para reagir a login, logout e refresh de token.
4. Retorne spinner durante loading, `<Navigate to="/login">` se não autenticado, ou `<>{children}</>`.

### Esqueleto

```tsx
export function AuthGuard({ children }: { children: React.ReactNode }) {
  // TODO: useState para 'loading' | 'authenticated' | 'unauthenticated'
  // TODO: useEffect: getSession() no mount
  // TODO: useEffect: onAuthStateChange — atualiza estado em cada mudança
  // TODO: cleanup: listener.subscription.unsubscribe() no return do useEffect
  // TODO: if loading → spinner; if unauthenticated → <Navigate to="/login">; else → children
}
```

<details>
<summary>Ver solução completa</summary>

`AuthGuard` é um **wrapper de rota** que verifica se o usuário está autenticado. Se não estiver, redireciona para `/login`. Padrão central de segurança no frontend.

```typescript
// src/components/AuthGuard.tsx
import { useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { supabase } from '../lib/supabase'

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<'loading' | 'authenticated' | 'unauthenticated'>('loading')

  useEffect(() => {
    // Verifica a sessão atual ao montar
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session ? 'authenticated' : 'unauthenticated')
    })

    // Escuta mudanças de sessão (login, logout, token refresh)
    const { data: listener } = supabase.auth.onAuthStateChange((_, session) => {
      setSession(session ? 'authenticated' : 'unauthenticated')
    })

    return () => listener.subscription.unsubscribe()
  }, [])

  if (session === 'loading') return <div>Loading...</div>
  if (session === 'unauthenticated') return <Navigate to="/login" replace />
  return <>{children}</>
}
```

Use no router:

```typescript
// src/App.tsx
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AuthGuard } from './components/AuthGuard'

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/dashboard" element={<AuthGuard><Dashboard /></AuthGuard>} />
        <Route path="/research" element={<AuthGuard><Research /></AuthGuard>} />
        <Route path="/report/:id" element={<AuthGuard><Report /></AuthGuard>} />
        <Route path="/settings" element={<AuthGuard><Settings /></AuthGuard>} />
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
```

> **Padrão de design: Decorator.** `AuthGuard` adiciona comportamento (verificação de auth) a uma rota sem modificar a rota em si. Qualquer componente pode ser "decorado" com `AuthGuard` apenas envolvendo-o.

---

</details>

- [ ] **Step 3.1: AuthGuard exibe loading enquanto `getSession()` resolve (sem flash de conteúdo).**
- [ ] **Step 3.2: Usuário sem sessão é redirecionado para `/login`.**
- [ ] **Step 3.3: Usuário autenticado vê o componente filho sem redirect.**
- [ ] **Step 3.4: Listener `onAuthStateChange` é cancelado no unmount (sem memory leak).**

### Resumo
> *Preencher apos concluir a task: o que foi alterado, qual verificacao passou, e qual risco ainda merece atencao?*

---
## Task 4: `frontend/src/pages/Login.tsx` - Página de Login

**Estimativa:** ~45min

**O que é e por que existe**

Esta task cria a única porta de entrada da aplicação. Login por email/senha e OAuth produzem o mesmo artefato: uma sessão Supabase que o AuthGuard verifica da mesma forma.

**Files:**
- Criar/Editar: `frontend/src/pages/Login.tsx`

---

### Conceito: Dois caminhos de auth, mesma sessão resultante
> `signInWithPassword` e `signInWithOAuth` produzem resultados idênticos para o `AuthGuard`: uma sessão válida ou ausência de sessão. O `AuthGuard` não sabe qual método foi usado — só checa se a sessão existe.
>
> | Método | Fluxo | Quando usar |
> |---|---|---|
> | `signInWithPassword` | Form → API Supabase → sessão local | Email/senha cadastrada |
> | `signInWithOAuth(google)` | Redirect → Google → callback → sessão | Login social |

---

### Documentação
- https://supabase.com/docs/reference/javascript/auth-signinwithpassword - referencia para login com email/senha.
- https://supabase.com/docs/reference/javascript/auth-signinwithoauth - referencia para login OAuth.

---

### O que você precisa fazer

1. Crie form controlado com estados `email`, `password`, `error`.
2. Implemente `handleLogin` com `signInWithPassword` — navigate para `/dashboard` no sucesso.
3. Implemente `handleGoogleLogin` com `signInWithOAuth({ provider: 'google', options: { redirectTo } })`.
4. Exiba mensagem de erro na tela se `signInWithPassword` retornar `error`.

### Esqueleto

```tsx
export function Login() {
  // TODO: estado email, password, error
  // TODO: handleLogin → signInWithPassword → navigate('/dashboard') ou setError(error.message)
  // TODO: handleGoogleLogin → signInWithOAuth({ provider: 'google' })
  return (
    <form>
      {/* TODO: campos email e password */}
      {/* TODO: exibir error se existir */}
      {/* TODO: botão Sign in */}
      {/* TODO: botão Sign in with Google */}
    </form>
  )
}
```

<details>
<summary>Ver solução completa</summary>

```typescript
// src/pages/Login.tsx
import { useState } from 'react'
import { supabase } from '../lib/supabase'
import { useNavigate } from 'react-router-dom'

export function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const navigate = useNavigate()

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault()
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) setError(error.message)
    else navigate('/dashboard')
  }

  async function handleGoogleLogin() {
    await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: `${window.location.origin}/dashboard` }
    })
    // O Supabase redireciona para o Google e depois de volta para /dashboard
    // com o token na URL. O AuthGuard pega o token automaticamente.
  }

  return (
    <div className="min-h-screen flex items-center justify-center">
      <form onSubmit={handleLogin} className="flex flex-col gap-4 w-80">
        <h1 className="text-2xl font-bold">IntelliOps</h1>
        {error && <p className="text-red-500 text-sm">{error}</p>}
        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={e => setEmail(e.target.value)}
          className="border rounded p-2"
        />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          className="border rounded p-2"
        />
        <button type="submit" className="bg-blue-600 text-white rounded p-2">
          Sign in
        </button>
        <button type="button" onClick={handleGoogleLogin} className="border rounded p-2">
          Sign in with Google
        </button>
      </form>
    </div>
  )
}
```

---

</details>

- [ ] **Step 4.1: Login com credenciais válidas navega para `/dashboard`.**
- [ ] **Step 4.2: Credenciais inválidas exibem mensagem de erro na tela (sem page crash).**
- [ ] **Step 4.3: Botão Google dispara redirect OAuth sem erro de console.**
- [ ] **Step 4.4: Usuário já autenticado ao acessar `/login` é redirecionado para `/dashboard`.**

### Resumo
> *Preencher apos concluir a task: o que foi alterado, qual verificacao passou, e qual risco ainda merece atencao?*

---
## Task 5: `frontend/src/components/StreamViewer.tsx` - StreamViewer (SSE no React)

**Estimativa:** ~1.5h

**O que é e por que existe**

Esta task é o componente mais complexo do sprint. Ela consome o stream SSE do FastAPI via `fetch + ReadableStream` e atualiza a UI em tempo real conforme tokens e chamadas de tools chegam.

**Files:**
- Criar/Editar: `frontend/src/components/StreamViewer.tsx`

---

### Conceito: fetch + ReadableStream em vez de EventSource — SSE via POST
> A Web API `EventSource` só faz GET. `/research/stream` é POST (query e mode vão no body). `fetch` expõe `ReadableStream` no `response.body` e resolve o mesmo protocolo SSE com suporte a qualquer método HTTP.
>
> | API | Método HTTP | Corpo no request | Uso no IntelliOps |
> |---|---|---|---|
> | `EventSource` | GET apenas | Impossível | Não serve para POST |
> | `fetch` + `ReadableStream` | Qualquer | JSON body | Correto |

---

### Documentação
- https://developer.mozilla.org/en-US/docs/Web/API/ReadableStream - referencia para consumir streams de response.
- https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events - protocolo SSE (eventos separados por `\n\n`).

---

### O que você precisa fazer

1. Faça `fetch POST /api/research/stream` com `query` e `mode` no body.
2. Pegue `response.body.getReader()` e execute loop `reader.read()`.
3. Acumule chunks em `buffer`, divida por `\n\n`, e parse cada evento (`event:` + `data:`).
4. Atualize estado: `token` → acumula relatório; `tool_call` → adiciona atividade; `done` → chama `onComplete`.

### Esqueleto

```tsx
export function StreamViewer({ onComplete }: { onComplete: (r: string) => void }) {
  const [report, setReport] = useState('')
  const [activity, setActivity] = useState<ActivityItem[]>([])

  const runResearch = useCallback(async (query: string, mode: string) => {
    // TODO: fetch POST /api/research/stream com { query, mode }
    // TODO: const reader = response.body.getReader()
    // TODO: loop: { done, value } = await reader.read(); if (done) break
    // TODO: buffer += decode(value); parts = buffer.split('\n\n')
    // TODO: parse cada part: event token → setReport; tool_call → setActivity; done → onComplete
  }, [onComplete])

  return { report, activity, runResearch }
}
```

<details>
<summary>Ver solução completa</summary>

Este é o componente mais complexo do sprint — ele consome o stream SSE do FastAPI e atualiza a UI em tempo real.

```typescript
// src/components/StreamViewer.tsx
import { useState, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'

interface ActivityItem {
  tool: string
  input: Record<string, unknown>
  done: boolean
}

interface StreamViewerProps {
  onComplete: (report: string) => void  // callback quando o stream termina
}

export function StreamViewer({ onComplete }: StreamViewerProps) {
  const [report, setReport] = useState('')
  const [activity, setActivity] = useState<ActivityItem[]>([])
  const [status, setStatus] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)

  const runResearch = useCallback(async (query: string, mode: string) => {
    setReport('')
    setActivity([])
    setIsStreaming(true)
    setStatus('Planning research...')

    // EventSource não suporta POST — usamos fetch com ReadableStream
    const response = await fetch('/api/research/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, mode }),
    })

    if (!response.body) return

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let fullReport = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      // SSE: eventos separados por \n\n
      const parts = buffer.split('\n\n')
      buffer = parts.pop() ?? ''  // último fragmento incompleto fica no buffer

      for (const part of parts) {
        const lines = part.split('\n')
        const eventLine = lines.find(l => l.startsWith('event:'))
        const dataLine = lines.find(l => l.startsWith('data:'))

        if (!eventLine || !dataLine) continue

        const eventType = eventLine.replace('event:', '').trim()
        const data = JSON.parse(dataLine.replace('data:', '').trim())

        if (eventType === 'token') {
          fullReport += data.content
          setReport(fullReport)
        } else if (eventType === 'tool_call') {
          setActivity(prev => [...prev, { tool: data.tool, input: data.input, done: false }])
          setStatus(getStatusLabel(data.tool))
        } else if (eventType === 'tool_result') {
          setActivity(prev => prev.map((item, i) =>
            i === prev.length - 1 ? { ...item, done: true } : item
          ))
        } else if (eventType === 'done') {
          setStatus('')
          setIsStreaming(false)
          onComplete(fullReport)
        }
      }
    }
  }, [onComplete])

  return { report, activity, status, isStreaming, runResearch }
  // Retorna como hook-like object para o componente pai controlar quando iniciar
}

function getStatusLabel(tool: string): string {
  const labels: Record<string, string> = {
    task: 'Delegating to research agent...',
    tavily_search: 'Searching the web...',
    think_tool: 'Assessing findings...',
    write_file: 'Writing report...',
  }
  return labels[tool] ?? 'Working...'
}
```

> **Por que `fetch` com `ReadableStream` e não `EventSource`?** O `EventSource` da Web API só suporta GET. O endpoint `/research/stream` é POST (precisa enviar `query` e `mode` no body). `fetch` suporta qualquer método e expõe o `ReadableStream` do response body — o mesmo mecanismo, mas com controle total.

---

</details>

- [ ] **Step 5.1: Eventos `token` acumulam o relatório sem perder caracteres.**
- [ ] **Step 5.2: Evento `tool_call` adiciona item à lista de atividade.**
- [ ] **Step 5.3: Evento `done` encerra o stream e chama `onComplete` com o relatório completo.**
- [ ] **Step 5.4: Buffer não perde fragmentos SSE quando um chunk é dividido entre dois `read()`.**

### Resumo
> *Preencher apos concluir a task: o que foi alterado, qual verificacao passou, e qual risco ainda merece atencao?*

---
## Task 6: `frontend/src/components/ResearchForm.tsx` - ResearchForm com `build_query()` portado

**Estimativa:** ~1h

**O que é e por que existe**

Esta task porta o `build_query()` Python para TypeScript e cria o formulário com campos dinâmicos por modo. É a ponte entre a entrada do usuário e o stream do backend.

**Files:**
- Criar/Editar: `frontend/src/components/ResearchForm.tsx`
- Criar/Editar: `frontend/src/lib/buildQuery.ts`

---

### Conceito: Strategy Pattern — cada modo é um `case`, não um `if` encadeado
> `buildQuery` em TypeScript espelha o Python de `research.py`: um `switch (mode)`. Adicionar um modo novo = novo `case` isolado. Com `if/else`, cada novo modo exige modificar o bloco existente e arriscaria quebrar outro modo.
>
> | Padrão | Como adicionar modo | Risco |
> |---|---|---|
> | `if/else` encadeado | Modificar bloco existente | Pode quebrar lógica de outro modo |
> | `switch` (Strategy) | Novo `case` isolado | Sem risco de regressão nos demais |

---

### Documentação
- https://react.dev/reference/react/useState - referencia para campos de formulário controlados.
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/switch - referencia para switch/case em TypeScript.

---

### O que você precisa fazer

1. Crie `src/lib/buildQuery.ts` com `switch (mode)` — porte o Python de `frontend/app/pages/research.py`.
2. Crie `ResearchForm` com campos dinâmicos por modo controlados por `useState`.
3. Conecte submit: chame `buildQuery(mode, fields)` e passe a query para `runResearch`.
4. Verifique que Due Diligence gera uma query com `company`, `sector`, e `deal_type`.

### Esqueleto

```typescript
// buildQuery.ts
export function buildQuery(mode: Mode, fields: Fields): string {
  switch (mode) {
    case 'Due Diligence':
      // TODO: montar string com company, sector, deal_type, company_url, focus
      return ''
    case 'Competitor Intel':
      // TODO: montar string com company, competitors, focus
      return ''
    default:
      return ''
  }
}
```

<details>
<summary>Ver solução completa</summary>

O `build_query()` existe em Python no Streamlit. Ele precisa ser portado para TypeScript. A lógica é idêntica — só muda a sintaxe.

```typescript
// src/lib/buildQuery.ts

export type Mode =
  | 'Due Diligence'
  | 'Competitor Intel'
  | 'Vendor Evaluation'
  | 'Sales Intel'
  | 'Market Mapping'   // Sprint 2

type Fields = Record<string, string>

function urlHint(url: string, label = 'company'): string {
  return `The official website for this ${label} is ${url} — use it to confirm the correct entity before searching.`
}

export function buildQuery(mode: Mode, fields: Fields): string {
  switch (mode) {
    case 'Due Diligence': {
      const lines = [
        `Due diligence research on ${fields.company} operating in the ${fields.sector} sector.`,
        `Context: ${fields.deal_type} evaluation.`,
      ]
      if (fields.company_url) lines.push(urlHint(fields.company_url))
      if (fields.focus) lines.push(`Additional focus: ${fields.focus}.`)
      lines.push(
        'Deliverables: risk assessment, financial signals, reputation and legal flags, ' +
        'leadership background, and any red flags relevant to the deal type.'
      )
      return lines.join(' ')
    }
    // ... demais modos seguem o mesmo padrão
    default:
      return ''
  }
}
```

> **Padrão de design: Strategy.** `buildQuery` é uma Strategy — cada `case` é uma estratégia diferente para montar a query. Quando você adiciona um novo modo no Sprint 2, adiciona um novo `case` aqui e em `ResearchForm.tsx`. Não mexe no resto.

---

</details>

- [ ] **Step 6.1: `buildQuery('Due Diligence', {...})` retorna string com `company`, `sector` e `deal_type`.**
- [ ] **Step 6.2: Modo selecionado altera os campos exibidos no formulário.**
- [ ] **Step 6.3: Campo `company_url` opcional aparece em todos os modos.**
- [ ] **Step 6.4: Submit chama `runResearch` com a query montada por `buildQuery`.**

### Resumo
> *Preencher apos concluir a task: o que foi alterado, qual verificacao passou, e qual risco ainda merece atencao?*

---
## Task 7: `frontend/src/pages/Research.tsx` - Salvar relatório via FastAPI após stream

**Estimativa:** ~45min

**O que é e por que existe**

Esta task conecta o fim do stream à persistência. Quando o evento `done` chega, o relatório completo é salvo via `POST /reports/save` com JWT no header, preparando o contrato para o Sprint 9.

**Files:**
- Criar/Editar: `frontend/src/pages/Research.tsx`
- Criar/Editar: `frontend/src/lib/api.ts`

---

### Conceito: JWT no header desde o primeiro commit — o backend exigirá depois
> Sprint 6 aceita `user_id` direto no body. O Sprint 9 vai validar o JWT. Enviar `Authorization: Bearer <token>` agora significa que o frontend não muda quando o backend endurecer o contrato de auth.
>
> | Sprint | Backend aceita | Frontend envia |
> |---|---|---|
> | 6 | `user_id` no body | JWT no header + user_id no body (ambos) |
> | 9 | Apenas JWT validado | JWT no header (sem mudança no frontend) |

---

### Documentação
- https://supabase.com/docs/reference/javascript/auth-getsession - referencia para pegar o JWT do usuário autenticado.
- https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/ - referencia para validação de Bearer token (Sprint 9).

---

### O que você precisa fazer

1. Crie `saveReport(payload)` em `api.ts` — pega sessão com `getSession()` e envia POST com `Authorization: Bearer`.
2. Em `Research.tsx`, chame `saveReport()` apenas no callback `onComplete` do `StreamViewer`.
3. Envolva em `try/catch` — falha de save não deve apagar o relatório exibido.
4. Confirme que `/dashboard` lista o relatório após reload da página.

### Esqueleto

```typescript
// api.ts
export async function saveReport(payload: SaveReportPayload) {
  // TODO: const { data: { session } } = await supabase.auth.getSession()
  // TODO: if (!session) throw new Error('Not authenticated')
  // TODO: fetch POST /api/reports/save com Authorization: Bearer session.access_token
  // TODO: return response.json()
}
```

<details>
<summary>Ver solução completa</summary>

Quando o stream termina (evento `done`), o frontend chama `POST /reports/save`:

```typescript
// src/lib/api.ts
import { supabase } from './supabase'

export async function saveReport(payload: {
  mode: string
  company?: string
  query: string
  markdown_content: string
}) {
  // Pega o JWT do usuário autenticado
  const { data: { session } } = await supabase.auth.getSession()
  if (!session) throw new Error('Not authenticated')

  const response = await fetch('/api/reports/save', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${session.access_token}`,
    },
    body: JSON.stringify({
      ...payload,
      user_id: session.user.id,
    }),
  })

  return response.json()
}
```

> **Por que mandar o JWT no header?** No Sprint 6, o backend ainda não valida JWT (aceita `user_id` direto). Mas o padrão correto é mandar o token JWT — assim quando você adicionar validação no backend, o frontend não muda. Comece certo.

---

</details>

- [ ] **Step 7.1: Autosave ocorre apenas após evento `done` (relatório completo, não parcial).**
- [ ] **Step 7.2: Header `Authorization: Bearer` está presente na requisição (verificar Network tab).**
- [ ] **Step 7.3: Falha de save exibe aviso mas não apaga o relatório exibido na tela.**
- [ ] **Step 7.4: `/dashboard` lista o relatório após reload da página.**

### Resumo
> *Preencher apos concluir a task: o que foi alterado, qual verificacao passou, e qual risco ainda merece atencao?*

---

## Resumo do Sprint 6

| Componente | Responsabilidade | Padrão |
|---|---|---|
| `AuthGuard` | Protege rotas para usuários autenticados | Decorator |
| `supabase.ts` | Cliente Supabase singleton (anon key) | Singleton |
| `StreamViewer` | Consome SSE com fetch + ReadableStream | Observer |
| `buildQuery.ts` | Porta o `build_query()` Python para TypeScript | Strategy |
| `api.ts` | Calls ao FastAPI com JWT | Facade |
| `ResearchForm` | Formulário por modo com campos específicos | Template Method |

**Critério de conclusão:** fluxo core funcionando — login → preencher formulário → ver stream → relatório salvo → aparecer no dashboard ao recarregar.

## Solo Developer Ready

- [ ] `frontend/app/` Streamlit foi preservado ate validar paridade.
- [ ] `frontend/package.json` existe e `npm run dev` funciona.
- [ ] Vite proxy encaminha `/api/*` para `http://localhost:8005`.
- [ ] Os quatro modos atuais geram query semanticamente equivalente ao Streamlit.
- [ ] Fluxo login -> pesquisa -> stream -> autosave -> dashboard foi testado.
