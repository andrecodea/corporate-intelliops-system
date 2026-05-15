# Sprint 1 — Calibration: Guia Instrucional

## Contexto e Objetivo

O Sprint 1 tem um objetivo cirúrgico: substituir o `httpx` pela Firecrawl para busca de conteúdo completo de páginas, e validar que todos os 4 modos existentes produzem relatórios de qualidade.

Antes de implementar qualquer coisa nova, este sprint te força a **entender o estado atual** do sistema e **medir** o que está funcionando ou não. Esse é o princípio de **calibration-before-expansion**: não adianta adicionar 7 novos modos se os 4 existentes estão produzindo relatórios fracos.

---

## Task 1: `backend/tools.py` - Substituir httpx por Firecrawl

**Estimativa:** ~45min

**O que é e por que existe**

Esta task transforma o objetivo descrito abaixo em uma unidade executavel no padrao da skill `sprint-writing`. Primeiro entenda o conceito e a decisao tecnica, depois use o esqueleto para implementar, e so entao consulte a solução completa preservada no bloco colapsavel.

**Files:**
- Criar/Editar: `backend/tools.py`

---

### Conceito: Adapter — trocar extrator sem mudar interface

> A `tavily_search` tem uma interface estável: recebe URL, retorna conteúdo. O que muda é a implementação interna de `fetch_full_content`. Esse isolamento é um **Adapter**: a nova ferramenta (Firecrawl) adapta um serviço externo ao contrato existente sem que o chamador precise saber da troca.
>
> | Extrator | Limitação fatal |
> |---|---|
> | `httpx` | Não executa JavaScript; Cloudflare retorna página de desafio, não conteúdo real |
> | Firecrawl | Roda Chromium headless, passa por Cloudflare, retorna Markdown limpo |
>
> Sem essa troca, `fetch_full_content=True` entrega lixo ao agente — ele acha que pesquisou, mas recebeu um `cf-challenge`.

---

### Documentação
- https://docs.firecrawl.dev/ - referencia oficial do Firecrawl (scrape_url, formatos, erros).
- https://docs.python.org/3/reference/compound_stmts.html#try - referencia para try/except e fallback.

---

### O que você precisa fazer

1. Rode o smoke test antes de tocar no código de produção: `uv run python -c "from firecrawl import FirecrawlApp; app=FirecrawlApp(); r=app.scrape_url('https://example.com', formats=['markdown']); print((r.markdown or '')[:200])"` — valida que `FIRECRAWL_API_KEY` funciona.
2. Instale `firecrawl-py` com `uv add firecrawl-py` e adicione `_get_firecrawl_client()` em `tools.py` logo após `_get_tavily_client()`, seguindo o mesmo padrão de lazy initialization.
3. Substitua o bloco `httpx` pelo bloco Firecrawl dentro do `try/except` em `tavily_search`, preservando o fallback para snippet no `except`.
4. Remova os imports mortos `import httpx` e `from markdownify import markdownify as md`.
5. Rode `uv run python tests/run_agent.py "What is LangChain?"` para confirmar que a integração ainda funciona.

### Esqueleto

```text
# TODO: Explore - localizar arquivos, contratos e dependencias citados abaixo.
# TODO: Prototype - validar a menor versao possivel da mudanca.
# TODO: Implement - aplicar a alteracao produtiva no(s) arquivo(s) indicado(s).
# TODO: Verify - rodar teste manual, script, endpoint ou build descrito na task.
```

<details>
<summary>Ver solução completa</summary>

### Por que trocar?

O código atual em `backend/tools.py` faz isso quando `fetch_full_content=True`:

```python
# tools.py, linha 74-79 (código ATUAL — httpx)
response = httpx.get(url, follow_redirects=True, timeout=10)
content = md(response.text)  # markdownify converte HTML → Markdown
```

**O problema com httpx:**

1. **Sites com Cloudflare** — o httpx é um cliente HTTP "burro": ele só envia um request GET e recebe o HTML. Sites protegidos por Cloudflare detectam que não é um browser real e retornam uma página de desafio (`cf-challenge`), não o conteúdo real.

2. **Sites com JavaScript** — muitos sites modernos são SPAs (Single Page Applications): o HTML inicial é um esqueleto vazio. O conteúdo real é renderizado pelo JavaScript no browser. O httpx não executa JavaScript, então recebe HTML vazio.

3. **markdownify converte lixo** — se o httpx recebeu uma página de challenge ou HTML vazio, o markdownify converte esse lixo para Markdown. O agente recebe conteúdo inútil e acha que pesquisou.

**Por que Firecrawl resolve:**

A Firecrawl roda um browser headless (Playwright/Chromium) no servidor deles. Ela:
- Executa o JavaScript da página
- Passa pelos desafios do Cloudflare
- Extrai o conteúdo limpo e retorna diretamente como Markdown

O resultado é que `fetch_full_content=True` passa a funcionar de verdade para a maioria dos sites.

### Como implementar

**Passo 1 — Instalar a dependência:**

```bash
uv add firecrawl-py
```

**Passo 2 — Adicionar o cliente Firecrawl em `tools.py`:**

O padrão já existe para o TavilyClient (linhas 8-14). Replique-o:

```python
# Adicionar após _get_tavily_client()
from firecrawl import FirecrawlApp

_firecrawl_client: FirecrawlApp | None = None

def _get_firecrawl_client() -> FirecrawlApp:
    global _firecrawl_client
    if _firecrawl_client is None:
        _firecrawl_client = FirecrawlApp()  # lê FIRECRAWL_API_KEY do ambiente
    return _firecrawl_client
```

> **Por que lazy initialization?**
> O cliente não é criado quando o módulo é importado — só quando é chamado pela primeira vez. Isso evita erros de startup se a chave não estiver configurada e torna o teste mais fácil (você pode substituir o cliente em testes sem redefinir o módulo).

**Passo 3 — Substituir o bloco httpx no `tavily_search`:**

Localize as linhas 73-79 de `tools.py` e substitua:

```python
# ANTES (httpx):
if fetch_full_content:
    try:
        response = httpx.get(url, follow_redirects=True, timeout=10)
        content = md(response.text)
    except Exception as fetch_err:
        log.warning(f"[RESEARCH AGENT] httpx fetch failed for {url}: {fetch_err}, falling back to snippet")
        content = result.get("content", "")[:1000]

# DEPOIS (Firecrawl):
if fetch_full_content:
    try:
        fc = _get_firecrawl_client()
        scraped = fc.scrape_url(url, formats=["markdown"])
        content = scraped.markdown or ""
        if not content:
            raise ValueError("Firecrawl returned empty content")
    except Exception as fetch_err:
        log.warning(f"[RESEARCH AGENT] Firecrawl fetch failed for {url}: {fetch_err}, falling back to snippet")
        content = result.get("content", "")[:1000]
```

> **Dica de design — fallback explícito:**
> O `try/except` não é defensive programming desnecessário aqui — é a fronteira do sistema. O Firecrawl é um serviço externo (pode ter timeout, rate limit, ou a URL pode estar offline). O fallback para o snippet do Tavily garante que o agente ainda recebe algum conteúdo útil em vez de travar.

**Passo 4 — Remover imports não utilizados:**

Após a troca, `httpx` e `markdownify` não são mais usados em `tools.py`:

```python
# REMOVER do topo de tools.py:
import httpx
from markdownify import markdownify as md
```

> **Por que remover?** Imports mortos enganam quem lê o código — a pessoa assume que eles são usados em algum lugar. Manter código limpo é documentação implícita.

**Passo 5 — Adicionar FIRECRAWL_API_KEY ao `.env`:**

```
FIRECRAWL_API_KEY=fc-xxxxxxxxxxxx
```

**Smoke test isolado antes de integrar:**

```bash
uv run python -c "from firecrawl import FirecrawlApp; app=FirecrawlApp(); r=app.scrape_url('https://example.com', formats=['markdown']); print((r.markdown or '')[:200])"
```

Se esse comando falhar, corrija `FIRECRAWL_API_KEY` ou a instala??o antes de editar `backend/tools.py`.

### Padrão de design aplicado: Adapter

A troca de httpx → Firecrawl é um **Adapter** de infraestrutura. A interface pública da `tavily_search` não muda (mesmos parâmetros, mesmo retorno), mas a implementação interna de `fetch_full_content` agora usa um adaptador diferente para a camada de extração.

Quem chama `tavily_search` não sabe e não precisa saber que mudou o extrator por baixo.

---

</details>

- [ ] **Step 1.1: Smoke test Firecrawl — `scrape_url('https://example.com')` retorna Markdown não vazio.**
- [ ] **Step 1.2: `_get_firecrawl_client()` adicionado em `tools.py` após `_get_tavily_client()`.**
- [ ] **Step 1.3: Bloco `httpx` substituído; fallback para snippet preservado no `except`.**
- [ ] **Step 1.4: Imports mortos removidos; `run_agent.py "What is LangChain?"` passa.**

### Resumo
> *Preencher apos concluir a task: o que foi alterado, qual verificacao passou, e qual risco ainda merece atencao?*

---
## Task 2: `tests/run_mode_*.py` - Validar os 4 modos

**Estimativa:** ~2h

**O que é e por que existe**

Esta task transforma o objetivo descrito abaixo em uma unidade executavel no padrao da skill `sprint-writing`. Primeiro entenda o conceito e a decisao tecnica, depois use o esqueleto para implementar, e so entao consulte a solução completa preservada no bloco colapsavel.

**Files:**
- Criar/Editar: `tests/run_mode_*.py`

---

### Conceito: Calibrar antes de expandir

> Adicionar 7 modos novos sobre uma base instável replica o problema × 7. A regra é medir primeiro, expandir depois. Cada script de modo usa a infraestrutura de `tests/run_agent.py`, mas **prependa o prompt de modo ao query** — exatamente o que `_load_mode_prompt()` faz na API. Sem esse passo, o teste CLI não aplica as instruções de modo e o resultado não reflete o comportamento real do produto.
>
> | Artefato | Responsabilidade |
> |---|---|
> | `tests/run_agent.py` | Infraestrutura: mede TTFT, tokens, latência |
> | `tests/run_mode_*.py` | Especificidade: prepende prompt de modo + query alvo |
> | Checklist de avaliação | Decisão: modo passa ou precisa ajuste antes do Sprint 2 |

---

### Documentação
- https://docs.python.org/3/library/pathlib.html - referencia para leitura dos arquivos de prompt de modo.
- https://app.tavily.com/ - dashboard para monitorar uso de buscas durante os testes.

---

### O que você precisa fazer

1. Leia `tests/run_agent.py` para entender como `run()` aceita um query string e o que o script registra em `tests/runs/`.
2. Crie `tests/run_mode_due_diligence.py`: leia `backend/prompts/modes/due_diligence.md`, prependa ao query de teste, chame `run()`.
3. Replique o padrão para os outros 3 modos (`competitor_intel`, `vendor_evaluation`, `sales_intel`).
4. Execute os 4 scripts e avalie cada relatório usando o checklist da solução completa.

### Esqueleto

```text
# TODO: Explore - localizar arquivos, contratos e dependencias citados abaixo.
# TODO: Prototype - validar a menor versao possivel da mudanca.
# TODO: Implement - aplicar a alteracao produtiva no(s) arquivo(s) indicado(s).
# TODO: Verify - rodar teste manual, script, endpoint ou build descrito na task.
```

<details>
<summary>Ver solução completa</summary>

### Por que validar antes de expandir?

Antes de construir 7 novos modos no Sprint 2, você precisa saber se os 4 atuais estão funcionando como esperado. Se o prompt de "Due Diligence" está gerando relatórios genéricos sem citações, adicionar novos modos vai replicar o mesmo problema × 7.

### Como criar os scripts de teste

Crie `tests/run_mode_due_diligence.py` como modelo. Os outros 3 seguem o mesmo padrão:

```python
# tests/run_mode_due_diligence.py
"""
Script de integração para o modo Due Diligence.
Roda uma query real e salva o resultado para avaliação manual.

Uso: uv run python tests/run_mode_due_diligence.py
"""
from pathlib import Path
import sys

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from tests.run_agent import run  # reutiliza a infraestrutura existente

MODE_PROMPT = ROOT / "backend" / "prompts" / "modes" / "due_diligence.md"

TEST_QUERY = (
    "Due diligence research on Deel operating in the HR Tech / Payroll sector. "
    "Context: Investment evaluation. "
    "Deliverables: risk assessment, financial signals, reputation and legal flags, "
    "leadership background, and any red flags relevant to the deal type."
)

if __name__ == "__main__":
    mode_prompt = MODE_PROMPT.read_text(encoding="utf-8")
    run(f"{mode_prompt}\n\n---\n\n{TEST_QUERY}")
```

> **Por que ler o prompt manualmente aqui?** `tests/run_agent.py` chama `build_agent()` direto e não passa pela API FastAPI, então ele não aplica `_load_mode_prompt()`. Para testar um modo via CLI, o script precisa prependar o arquivo de prompt do modo à query, igual a API faz em `/research/stream`.

**Comandos de verificação:**

```bash
uv run python tests/run_mode_due_diligence.py
uv run python tests/run_mode_competitor_intel.py
uv run python tests/run_mode_vendor_evaluation.py
uv run python tests/run_mode_sales_intel.py
```

> **Dica:** Use empresas reais e conhecidas para os testes de modo (Deel, Notion, Figma) — elas têm cobertura de imprensa ampla, então é fácil verificar se o relatório gerado é factualmente coerente.

### O que avaliar em cada relatório

Crie um checklist de avaliação manual para cada modo:

**Due Diligence:**
- [ ] Tem seção de Risco com nível explícito (Low/Medium/High)?
- [ ] Cita pelo menos 3 fontes verificáveis?
- [ ] Menciona dados financeiros específicos (rodada de funding, receita estimada)?
- [ ] Sinaliza riscos legais ou reputacionais com evidência, ou declara explicitamente que não encontrou?

**Competitor Intel:**
- [ ] Compara funcionalidades concretas (não apenas categorias genéricas)?
- [ ] Tem dados de precificação, mesmo que estimados?
- [ ] Identifica pelo menos uma fraqueza explorável do competidor?

**Vendor Evaluation:**
- [ ] Gera tabela comparativa com trade-offs?
- [ ] Menciona complexidade de integração com o stack fornecido?
- [ ] Recomenda um vencedor com justificativa?

**Sales Intel:**
- [ ] Identifica pain points específicos da empresa-alvo?
- [ ] Traz sinais de tech stack?
- [ ] Sugere hooks de conversa concretos?

### Ajustando o search cap por modo

Após rodar os testes, se "Competitor Intel" ou "Vendor Evaluation" produzirem relatórios rasos (poucas fontes, comparações genéricas), o problema provavelmente é a quantidade de buscas disponível.

O ajuste é em `agent.py` na função `_init_subagents`. O cap atual é 5 buscas por sub-agente:

```python
tools=[create_tavily_search(max_calls=5)],  # agent.py, linha 160
```

Para modos comparativos, considere aumentar para 8:

```python
# Versão futura: cap por modo
tools=[create_tavily_search(max_calls=mode_search_cap)],
```

> **Por que não simplesmente aumentar para 10 para todos?** Tokens e latência. Cada busca adicional custa tempo (15-20s) e tokens de contexto. Você quer o mínimo que produce qualidade aceitável, não o máximo possível.

---

</details>

- [ ] **Step 2.1: `tests/run_mode_due_diligence.py` criado — lê o arquivo de modo e prependa ao query antes de chamar `run()`.**
- [ ] **Step 2.2: Scripts dos outros 3 modos criados com o mesmo padrão.**
- [ ] **Step 2.3: Todos os 4 scripts executam sem erros de API ou timeout.**
- [ ] **Step 2.4: Cada relatório foi avaliado pelo checklist manual da solução completa.**

### Resumo
> *Preencher apos concluir a task: o que foi alterado, qual verificacao passou, e qual risco ainda merece atencao?*

---

## Resumo do Sprint 1

| Tarefa | Arquivo | Padrão |
|---|---|---|
| Substituir httpx por Firecrawl | `backend/tools.py` | Adapter |
| Remover imports mortos | `backend/tools.py` | — |
| Scripts de teste por modo | `tests/run_mode_*.py` | Observer (reutiliza UsageTracker) |
| Avaliar e ajustar prompts | `backend/prompts/modes/` | Template Method |

**Critério de conclusão do Sprint:** todos os 4 modos produzem relatórios que passam no checklist de avaliação manual acima, e o `fetch_full_content=True` funciona corretamente via Firecrawl.

## Solo Developer Ready

- [ ] Consigo rodar `uv run python tests/run_mode_due_diligence.py`.
- [ ] Tenho `FIRECRAWL_API_KEY` configurada ou documentei o fallback.
- [ ] Sei comparar os quatro relatorios pelo checklist manual.
- [ ] Sei qual arquivo mudou para busca (`backend/tools.py`) e qual arquivo mudou para validacao (`tests/run_mode_*.py`).
- [ ] Registrei no resumo quais modos ainda parecem fracos.
