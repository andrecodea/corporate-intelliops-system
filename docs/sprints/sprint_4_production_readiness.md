# Sprint 4 — Production Readiness: Guia Instrucional

## Contexto e Objetivo

Até agora o projeto roda localmente com `uv run` e variáveis de ambiente no `.env`. O Sprint 4 transforma isso num artefato deployável: uma imagem Docker que qualquer servidor consegue executar, um compose que levanta os serviços juntos, e um CI que garante que ninguém quebra a main sem perceber.

**Princípio do sprint:** produção não é um estado futuro — é uma restrição que você aplica agora. Cada decisão tomada aqui (quais portas expor, como passar segredos, qual imagem base usar) vai afetar quanto trabalho o deploy real vai custar.

## Decisões fixas para evitar ambiguidade

- Porta padrão do backend neste projeto: `8005`.
- Comando local recomendado: `uv run uvicorn backend.api:app --reload --port 8005`.
- URL consumida pelo Streamlit: `RESEARCH_API_URL=http://localhost:8005/research/stream`.
- Docker deve expor `8005` e mapear `8005:8005`, para não divergir do frontend e dos evals.
- Se algum comando antigo usar porta `8000`, trate como default do Uvicorn, não como padrão deste projeto.

---

## Task 0: `docs/sprints/INDEX.md` - Confirmar contratos de runtime

**Estimativa:** ~20min

**O que é e por que existe**

Antes de criar Dockerfile ou CI, confirme quais processos existem hoje, quais portas eles usam, e qual comando prova que o MVP ainda roda. Esta task evita congelar no Docker uma suposicao errada sobre a API, o LangGraph server ou o frontend.

**Files:**
- Criar/Editar: `docs/sprints/INDEX.md`
- Ler: `README.md`, `pyproject.toml`, `langgraph.json`, `backend/api.py`

---

### Conceito: Deploy empacota contratos existentes
> Docker nao deve inventar uma arquitetura nova; ele deve empacotar os contratos que ja funcionam localmente. Se voce nao sabe qual comando sobe a API, qual porta o frontend consome e qual env var e obrigatoria, o container so transforma a ambiguidade em erro mais dificil de debugar.

---

### Documentação
- https://docs.docker.com/build/ - referencia oficial para build de imagens Docker.
- https://fastapi.tiangolo.com/deployment/ - referencia oficial para deploy de FastAPI.
- https://docs.github.com/actions - referencia oficial para GitHub Actions.

---

### O que você precisa fazer

1. Rode a API localmente com `uv run uvicorn backend.api:app --reload --port 8005`.
2. Confirme que `POST /research/stream` continua sendo o contrato principal.
3. Confirme se o LangGraph dev server ainda usa `langgraph.json`.
4. Atualize `docs/sprints/INDEX.md` se algum comando real divergir.
5. So avance para Docker quando os comandos locais estiverem claros.

### Esqueleto

```text
# TODO: Explore - ler README, langgraph.json e backend/api.py.
# TODO: Prototype - subir API local na porta 8005.
# TODO: Implement - registrar divergencias no INDEX.md se existirem.
# TODO: Verify - abrir http://localhost:8005/docs e confirmar FastAPI vivo.
```

<details>
<summary>Ver solução completa</summary>

Comandos de verificacao antes do Docker:

```bash
uv run uvicorn backend.api:app --reload --port 8005
curl http://localhost:8005/docs
```

Se a documentacao da API abrir, a porta e o app import path estao corretos. Se falhar no import do agente por env var ausente, registre isso em `.env.example` na Task 4; nao esconda a dependencia no Dockerfile.

O resultado esperado desta task e simples: voce sabe exatamente quais comandos o Dockerfile e o `docker-compose.yml` precisam reproduzir.

</details>

- [ ] **Step 0.1: API local sobe na porta `8005`.**
- [ ] **Step 0.2: `langgraph.json` ainda aponta para `backend/agent.py:build_agent`.**
- [ ] **Step 0.3: `docs/sprints/INDEX.md` reflete os comandos reais.**
- [ ] **Step 0.4: Variaveis obrigatorias foram anotadas para `.env.example`.**

### Resumo
> *Preencher apos concluir a task: quais contratos locais foram confirmados e qual divergencia foi encontrada?*

---

## Task 1: `Dockerfile` - Dockerfile

**Estimativa:** ~45min

**O que é e por que existe**

Esta task transforma o objetivo descrito abaixo em uma unidade executavel no padrao da skill `sprint-writing`. Primeiro entenda o conceito e a decisao tecnica, depois use o esqueleto para implementar, e so entao consulte a solução completa preservada no bloco colapsavel.

**Files:**
- Criar/Editar: `Dockerfile`

---

### Conceito: Docker layer caching — dependências antes do código

> Cada instrução `COPY` + `RUN` cria uma layer. O Docker reutiliza layers em cache enquanto o input não muda. Se você copia o código junto com `pyproject.toml`, qualquer mudança de código invalida o cache das dependências — e você reinstala tudo desnecessariamente a cada build.
>
> | Ordem de COPY | Comportamento no cache |
> |---|---|
> | Código + pyproject.toml juntos | Mudança de código → reinstala dependências |
> | pyproject.toml primeiro, código depois | Mudança de código reutiliza cache de dependências |
>
> O `CMD` usa `--host 0.0.0.0` porque dentro de um container `localhost` é o próprio container — sem isso, nada externo acessa a API.

---

### Documentação
- https://docs.docker.com/build/cache/ - referencia oficial para Docker layer caching.
- https://docs.docker.com/reference/dockerfile/ - referencia para sintaxe do Dockerfile.

---

### O que você precisa fazer

1. Crie `Dockerfile` na raiz com a sequência correta: base image → instalar uv → `COPY pyproject.toml` → `uv sync` → `COPY backend/` → `EXPOSE 8005` → `CMD`.
2. Crie `.dockerignore` excluindo `.env`, `.venv/`, `workspace/`, `tests/`, `__pycache__/`, `*.pyc`, `.git/`.
3. Crie `Dockerfile.langgraph` para o LangGraph server com `EXPOSE 2024` e `CMD langgraph dev`.
4. Rode `docker build -t intelliops-api .` e confirme que o build passa.
5. Teste com `docker run --env-file .env -p 8005:8005 intelliops-api` e abra `http://localhost:8005/docs`.

### Esqueleto

```text
# TODO: Explore - localizar arquivos, contratos e dependencias citados abaixo.
# TODO: Prototype - validar a menor versao possivel da mudanca.
# TODO: Implement - aplicar a alteracao produtiva no(s) arquivo(s) indicado(s).
# TODO: Verify - rodar teste manual, script, endpoint ou build descrito na task.
```

<details>
<summary>Ver solução completa</summary>

O projeto tem dois processos: a API FastAPI (via Uvicorn) e o LangGraph dev server. Em produção, eles rodam como serviços separados — não num mesmo processo.

### Por que separar em dois Dockerfiles?

O LangGraph server é usado para desenvolvimento (Studio UI) e para o runtime do agente em produção via seu próprio servidor ASGI. A API FastAPI é a camada REST que o frontend consome. Eles têm dependências em comum mas ciclos de vida independentes.

Crie `Dockerfile` na raiz:

```dockerfile
# Dockerfile
# Imagem base: Python 3.13 slim (menor que full, sem ferramentas de build desnecessárias)
FROM python:3.13-slim

# Define o diretório de trabalho dentro do container
WORKDIR /app

# Instala o uv (gerenciador de pacotes do projeto) direto do binário oficial
# Isso é mais rápido e reproduzível do que pip install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copia os arquivos de dependências primeiro (antes do código)
# Por quê? Docker cacheia cada instrução como uma layer. Se você copiar o código
# junto com o pyproject.toml, qualquer mudança de código invalida o cache
# das dependências — e você reinstala tudo desnecessariamente.
COPY pyproject.toml uv.lock* ./

# Instala as dependências no sistema (não em venv isolado dentro do container)
# --no-dev exclui dependências de desenvolvimento
# --frozen garante que usa exatamente as versões do uv.lock
RUN uv sync --frozen --no-dev

# Copia o restante do código
COPY backend/ ./backend/
COPY workspace/ ./workspace/

# Expõe a porta da API FastAPI
EXPOSE 8005

# Comando padrão: sobe a API
CMD ["uv", "run", "uvicorn", "backend.api:app", "--host", "0.0.0.0", "--port", "8005"]
```

> **Por que `--host 0.0.0.0`?** Por padrão, Uvicorn escuta em `127.0.0.1` (localhost). Dentro de um container, `localhost` é o próprio container. Para que o host (ou outro container) consiga acessar, precisa escutar em todas as interfaces: `0.0.0.0`.

> **Por que não incluir o `.env` na imagem?** Segredos não entram em imagens Docker. A imagem é um artefato versionado — qualquer pessoa com acesso ao registry poderia extraí-la e ler suas chaves. Segredos são injetados em runtime via variáveis de ambiente.

### `.dockerignore`

Crie `.dockerignore` na raiz para evitar copiar lixo para a imagem:

```
.env
.venv/
workspace/
tests/
__pycache__/
*.pyc
.git/
```

> **Por que ignorar `workspace/`?** É gerado em runtime pelo agente. Não faz sentido fazer parte da imagem. O container vai recriar a pasta ao iniciar (o código já tem `WORKSPACE_DIR.mkdir(exist_ok=True)` em `agent.py:29`).

### Verificação

```bash
docker build -t intelliops-api .
docker run --env-file .env -p 8005:8005 intelliops-api
# Teste: curl -X POST http://localhost:8005/research/stream ...
```

---

</details>

- [ ] **Step 1.1: `pyproject.toml` copiado ANTES do código no Dockerfile — cache de dependências funciona.**
- [ ] **Step 1.2: `.dockerignore` criado — `.env` e `.venv/` excluídos da imagem.**
- [ ] **Step 1.3: `docker build -t intelliops-api .` passa sem erros.**
- [ ] **Step 1.4: Container sobe e `http://localhost:8005/docs` abre.**

### Resumo
> *Preencher apos concluir a task: o que foi alterado, qual verificacao passou, e qual risco ainda merece atencao?*

---
## Task 2: `docker-compose.yml` - docker-compose.yml

**Estimativa:** ~30min

**O que é e por que existe**

Esta task transforma o objetivo descrito abaixo em uma unidade executavel no padrao da skill `sprint-writing`. Primeiro entenda o conceito e a decisao tecnica, depois use o esqueleto para implementar, e so entao consulte a solução completa preservada no bloco colapsavel.

**Files:**
- Criar/Editar: `docker-compose.yml`

---

### Conceito: Startup order com healthcheck

> `depends_on` sem condição garante que o container B *inicia* depois do A, mas não que o A está *pronto*. O LangGraph server consome a API — se ele subir antes da API responder, as primeiras requisições falham. O `healthcheck` + `condition: service_healthy` resolve: o LangGraph só sobe quando a API responde `200` no endpoint configurado.
>
> | `depends_on` | Garantia |
> |---|---|
> | Sem condição | Container A iniciou (processo existe) |
> | `condition: service_healthy` | Container A respondeu ao healthcheck |

---

### Documentação
- https://docs.docker.com/compose/how-tos/startup-order/ - referencia para depends_on e healthcheck.
- https://docs.docker.com/compose/compose-file/05-services/#healthcheck - sintaxe de healthcheck.

---

### O que você precisa fazer

1. Crie `docker-compose.yml` com dois serviços: `api` (porta 8005) e `langgraph` (porta 2024).
2. Adicione `healthcheck` no serviço `api` testando `http://localhost:8005/docs`.
3. Configure `depends_on` no `langgraph` com `condition: service_healthy`.
4. Monte `./workspace:/app/workspace` como volume em ambos os serviços.
5. Rode `docker-compose up --build` e confirme que ambos os serviços sobem.

### Esqueleto

```text
# TODO: Explore - localizar arquivos, contratos e dependencias citados abaixo.
# TODO: Prototype - validar a menor versao possivel da mudanca.
# TODO: Implement - aplicar a alteracao produtiva no(s) arquivo(s) indicado(s).
# TODO: Verify - rodar teste manual, script, endpoint ou build descrito na task.
```

<details>
<summary>Ver solução completa</summary>

O compose define como os serviços se relacionam. Neste projeto: a API FastAPI (que serve o frontend) e o LangGraph server (que roda o agente).

```yaml
# docker-compose.yml
services:
  api:
    build: .
    ports:
      - "8005:8005"
    env_file:
      - .env
    volumes:
      # workspace montado como volume para que os arquivos gerados
      # persistam entre restarts do container
      - ./workspace:/app/workspace
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8005/docs"]
      interval: 30s
      timeout: 10s
      retries: 3

  langgraph:
    build:
      context: .
      dockerfile: Dockerfile.langgraph  # segundo Dockerfile para o server LangGraph
    ports:
      - "2024:2024"
    env_file:
      - .env
    environment:
      - PYTHONUTF8=1
    volumes:
      - ./workspace:/app/workspace
    depends_on:
      api:
        condition: service_healthy
```

Crie `Dockerfile.langgraph`:

```dockerfile
FROM python:3.13-slim
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock* langgraph.json ./
RUN uv sync --frozen --no-dev
COPY backend/ ./backend/
COPY workspace/ ./workspace/
EXPOSE 2024
CMD ["uv", "run", "langgraph", "dev", "--no-reload", "--allow-blocking", "--host", "0.0.0.0"]
```

> **Por que `depends_on` com `condition: service_healthy`?** O LangGraph server consome a API. Se o LangGraph subir antes da API estar pronta, as primeiras requisições vão falhar. O `healthcheck` garante que a API está respondendo antes do LangGraph iniciar.

> **Por que montar `workspace/` como volume?** Sem volume, os arquivos gerados pelo agente (`research_request.md`, `final_report.md`) ficam dentro do container e somem ao reiniciar. Com o bind mount, eles persistem no host — útil para debug.

### Rodar tudo:

```bash
docker-compose up --build   # primeira vez
docker-compose up           # depois
docker-compose down         # parar
```

---

</details>

- [ ] **Step 2.1: `docker-compose.yml` tem dois serviços: `api` e `langgraph`.**
- [ ] **Step 2.2: `healthcheck` configurado no serviço `api`.**
- [ ] **Step 2.3: `langgraph` usa `condition: service_healthy` no `depends_on`.**
- [ ] **Step 2.4: `docker-compose up --build` sobe ambos sem erros.**

### Resumo
> *Preencher apos concluir a task: o que foi alterado, qual verificacao passou, e qual risco ainda merece atencao?*

---
## Task 3: `.github/workflows/ci.yml` - CI Pipeline (GitHub Actions)

**Estimativa:** ~30min

**O que é e por que existe**

Esta task transforma o objetivo descrito abaixo em uma unidade executavel no padrao da skill `sprint-writing`. Primeiro entenda o conceito e a decisao tecnica, depois use o esqueleto para implementar, e so entao consulte a solução completa preservada no bloco colapsavel.

**Files:**
- Criar/Editar: `.github/workflows/ci.yml`

---

### Conceito: Pipeline gates — cada etapa é uma barreira de qualidade

> Um CI é sequencial com *gates*: se o lint falha, o build não roda; se o build falha, o teste não roda. Isso evita gastar tokens de API em testes de integração quando há erros de sintaxe triviais. O teste de integração é condicionado à presença do secret — sem `ANTHROPIC_API_KEY` no repo, o job não roda.
>
> | Gate | O que detecta |
> |---|---|
> | `ruff check` | Erros de sintaxe, imports mortos |
> | `pyright` | Erros de tipo que o Python mostraria só em runtime |
> | `docker build` | Dockerfile quebrado |
> | `run_agent.py` | Pipeline end-to-end funcionando |

---

### Documentação
- https://docs.github.com/en/actions/writing-workflows - referencia oficial para GitHub Actions.
- https://astral-sh.github.io/setup-uv/ - action oficial para instalar uv no CI.

---

### O que você precisa fazer

1. Crie `.github/workflows/ci.yml` com trigger em push/PR para `main`.
2. Job `lint-and-build`: checkout → instalar uv → `uv sync` → `ruff check` → `pyright` → `docker build`.
3. Job `integration-test` condicional: só roda se `secrets.ANTHROPIC_API_KEY != ''`.
4. Adicione `uv add --dev ruff pyright` ao `pyproject.toml` se ainda não existirem.
5. Faça um push para `main` e confirme que o CI passa no GitHub Actions.

### Esqueleto

```text
# TODO: Explore - localizar arquivos, contratos e dependencias citados abaixo.
# TODO: Prototype - validar a menor versao possivel da mudanca.
# TODO: Implement - aplicar a alteracao produtiva no(s) arquivo(s) indicado(s).
# TODO: Verify - rodar teste manual, script, endpoint ou build descrito na task.
```

<details>
<summary>Ver solução completa</summary>

O CI tem uma responsabilidade simples: garantir que nenhum push quebra a main. Para isso, roda o lint, o build da imagem Docker, e o teste de integração (se a chave Tavily estiver disponível).

Crie `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint-and-build:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Install dependencies
        run: uv sync --frozen

      - name: Lint (ruff)
        run: uv run ruff check backend/ tests/
        # ruff é o linter mais rápido do ecossistema Python.
        # Adicione: uv add --dev ruff

      - name: Type check (pyright)
        run: uv run pyright backend/
        # Pyright detecta erros de tipo que o Python só mostraria em runtime.
        # Adicione: uv add --dev pyright

      - name: Build Docker image
        run: docker build -t intelliops-api .
        # Verifica que o Dockerfile não está quebrado.
        # Não faz push — apenas valida o build.

  integration-test:
    runs-on: ubuntu-latest
    # Só roda se os segredos estiverem configurados no repositório
    if: ${{ secrets.ANTHROPIC_API_KEY != '' }}

    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv sync --frozen

      - name: Run integration test
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          TAVILY_API_KEY: ${{ secrets.TAVILY_API_KEY }}
        run: |
          uv run python tests/run_agent.py "What is LangChain?"
          # Query simples: barata, rápida, verifica que o pipeline end-to-end funciona
```

> **Como adicionar segredos no GitHub:** Settings → Secrets and variables → Actions → New repository secret. Nunca coloque chaves direto no YAML.

> **Por que testar com uma query simples no CI?** Queries simples ("What is LangChain?") são classificadas pelo orquestrador como triviais — respondem sem busca, em segundos, com poucos tokens. Suficiente para verificar que o pipeline end-to-end não está quebrado, sem gastar tokens em pesquisa real.

### Padrão de design: Pipeline

O CI é um pipeline sequencial com gates: lint → build → test. Cada etapa é um gate — se falha, a próxima não roda. Isso garante que problemas simples (erro de sintaxe, import quebrado) não desperdiçam tempo rodando testes caros.

---

</details>

- [ ] **Step 3.1: CI dispara em push e PR para `main`.**
- [ ] **Step 3.2: `ruff check` e `pyright` rodam no job `lint-and-build`.**
- [ ] **Step 3.3: `docker build` faz parte do job `lint-and-build`.**
- [ ] **Step 3.4: Job `integration-test` condicionado à presença do secret.**

### Resumo
> *Preencher apos concluir a task: o que foi alterado, qual verificacao passou, e qual risco ainda merece atencao?*

---
## Task 4: `.env.example` - `.env.example` revisado

**Estimativa:** ~15min

**O que é e por que existe**

Esta task transforma o objetivo descrito abaixo em uma unidade executavel no padrao da skill `sprint-writing`. Primeiro entenda o conceito e a decisao tecnica, depois use o esqueleto para implementar, e so entao consulte a solução completa preservada no bloco colapsavel.

**Files:**
- Criar/Editar: `.env.example`

---

### Conceito: `.env.example` como contrato de secrets

> Segredos não entram em imagens Docker nem no git. O `.env.example` é o *contrato documentado*: lista todas as variáveis com placeholders e comentários explicando onde obter cada chave. Qualquer novo deploy ou colaborador lê este arquivo e sabe exatamente o que configurar.
>
> | Arquivo | Finalidade |
> |---|---|
> | `.env` | Valores reais — nunca versionar (`.gitignore`) |
> | `.env.example` | Template com placeholders — sempre versionar |

---

### Documentação
- https://12factor.net/config - princípio de configuração via variáveis de ambiente.

---

### O que você precisa fazer

1. Crie `.env.example` com todas as variáveis organizadas por seção (Obrigatórias / Recomendadas / Opcionais).
2. Use placeholders reais (`sk-ant-...`, `tvly-...`, `fc-...`) — não `XXXXXX`.
3. Adicione um comentário por variável explicando propósito e onde obter a chave.
4. Confirme que `.env.example` está no git e `.env` está no `.gitignore`.

### Esqueleto

```text
# TODO: Explore - localizar arquivos, contratos e dependencias citados abaixo.
# TODO: Prototype - validar a menor versao possivel da mudanca.
# TODO: Implement - aplicar a alteracao produtiva no(s) arquivo(s) indicado(s).
# TODO: Verify - rodar teste manual, script, endpoint ou build descrito na task.
```

<details>
<summary>Ver solução completa</summary>

O `.env.example` é a documentação viva das variáveis de ambiente. Deve ter todas as vars, valores de exemplo realistas, e comentários explicando o que cada uma faz.

```bash
# .env.example

# === OBRIGATÓRIAS ===

# Chave da API Anthropic (LLM principal)
# Obtenha em: https://console.anthropic.com
ANTHROPIC_API_KEY=sk-ant-...

# Chave da API Tavily (busca web)
# Obtenha em: https://tavily.com
TAVILY_API_KEY=tvly-...


# === RECOMENDADAS ===

# Chave da API Firecrawl (fetch completo de páginas, Sprint 1)
# Necessário para fetch_full_content=True. Sem ela, o agente faz fallback para snippets.
# Obtenha em: https://firecrawl.dev
FIRECRAWL_API_KEY=fc-...

# Chave LangSmith (observabilidade de LLM — ver traces, latência, tokens por chamada)
# Obtenha em: https://smith.langchain.com
LANGSMITH_API_KEY=lsv2_...
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=intelliops


# === OPCIONAIS — TUNAGEM ===

# Modelo LLM principal (padrão: claude-sonnet-4-6)
MODEL_NAME=claude-sonnet-4-6

# Modelo de fallback se ANTHROPIC_API_KEY não estiver presente (padrão: gpt-5.2)
FALLBACK_MODEL=gpt-5.2

# Limite de iterações por sub-agente (padrão: 1)
MAX_SUBAGENTS_ITERATIONS=1

# Limite de sub-agentes concorrentes (padrão: 2)
MAX_CONCURRENT_RESEARCH_UNITS=2

# Limite de recursão do grafo LangGraph (padrão: 50)
RECURSION_LIMIT=50


# === OPCIONAIS — PROVIDER CUSTOM PARA SUB-AGENTE ===

# Usar um provider diferente para sub-agentes (ex: Mercury da Inception Labs)
# Se não definido, usa o mesmo provider do orquestrador
SUBAGENT_MODEL_NAME=mercury-coder-small
SUBAGENT_BASE_URL=https://api.inceptionlabs.ai/v1
SUBAGENT_API_KEY=...


# === OPCIONAIS — INTEGRAÇÕES ===

# Slack: necessário para o botão "Send PDF to Slack" no frontend
# O bot precisa do scope files:write
SLACK_BOT_TOKEN=xoxb-...
SLACK_CHANNEL_ID=C0XXXXXXXXXX

# PostgreSQL para checkpoints persistentes (padrão: in-memory)
# Formato: postgresql://user:password@host:5432/dbname
LANGGRAPH_DATABASE_URL=postgresql://...
```

---

</details>

- [ ] **Step 4.1: `.env.example` cobre todas as variáveis obrigatórias com placeholders.**
- [ ] **Step 4.2: Cada variável tem comentário explicando propósito e onde obter.**
- [ ] **Step 4.3: `.env` está no `.gitignore` — confirmado com `git check-ignore .env`.**
- [ ] **Step 4.4: `.env.example` foi commitado no repositório.**

### Resumo
> *Preencher apos concluir a task: o que foi alterado, qual verificacao passou, e qual risco ainda merece atencao?*

---

## Resumo do Sprint 4

| Artefato | O que faz | Padrão envolvido |
|---|---|---|
| `Dockerfile` | Empacota a API FastAPI | — |
| `Dockerfile.langgraph` | Empacota o LangGraph server | — |
| `.dockerignore` | Exclui segredos e lixo da imagem | — |
| `docker-compose.yml` | Orquestra os dois serviços com healthcheck | Pipeline |
| `.github/workflows/ci.yml` | Lint → build → teste em cada push | Pipeline |
| `.env.example` revisado | Documenta todas as variáveis com contexto | — |

**Critério de conclusão:** `docker-compose up --build` sobe ambos os serviços sem erros, e um push para a main dispara o CI e passa.

## Solo Developer Ready

- [ ] Confirmei comandos locais antes de escrever Docker.
- [ ] `Dockerfile` expoe e roda a API na porta `8005`.
- [ ] `.env.example` documenta env vars obrigatorias e opcionais sem secrets reais.
- [ ] `docker-compose up --build` sobe os servicos esperados.
- [ ] CI roda lint/type/build/test sem depender de secrets de producao.
