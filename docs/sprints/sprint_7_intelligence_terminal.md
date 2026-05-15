# Sprint 7 — Intelligence Terminal (Base): Guia Instrucional

## Contexto e Objetivo

Este sprint foi normalizado para seguir a skill `sprint-writing`. O conteudo original foi preservado como solução completa e deve ser usado depois das fases de exploracao e prototipo.

## Pré-requisitos para desenvolver sozinho

- Sprint 6 concluído: SPA React em `frontend/`, Supabase Auth, tabelas `profiles`, `researches` e `reports`.
- Supabase local/remoto com migrations do Sprint 5 e Sprint 6 aplicadas.
- Backend rodando em `http://localhost:8005`.
- Plano detalhado aberto ao lado: `docs/superpowers/plans/2026-04-08-sprint-7-intelligence-terminal.md`.

**Como executar sem se perder:** trate este arquivo como explicação conceitual e o plano em `docs/superpowers/plans/` como checklist operacional. Implemente uma task do plano por vez, rode o teste indicado nela e só então avance.

**Ordem mínima esperada:** migration de entidades -> models Pydantic -> extractor -> endpoints -> acionamento pós-pesquisa -> cliente React -> grafo D3 -> tooltip/dossier/HITL/filtros.

---

## Task 1: `docs/superpowers/plans/2026-04-08-sprint-7-intelligence-terminal.md` - Executar plano detalhado do sprint

**Estimativa:** ~30min

**O que é e por que existe**

Esta task transforma o sprint conceitual em uma unidade executavel. O plano detalhado em `docs/superpowers/plans/` contem o passo a passo granular; este arquivo mantem o contrato pedagogico exigido pela skill.

**Files:**
- Criar/Editar: ver plano detalhado em `docs/superpowers/plans/2026-04-08-sprint-7-intelligence-terminal.md` e os arquivos citados na solução completa.

---

### Conceito: Plano detalhado como solucao, sprint como contrato pedagogico
> O documento de sprint explica por que a arquitetura existe; o plano detalhado explica como implementar. A skill exige os dois em ordem: conceito antes do codigo, esqueleto antes da solucao. Sem essa separacao, agentes pulam direto para copiar codigo sem validar premissas.

---

### Documentação
- https://fastapi.tiangolo.com/ - referencia para endpoints backend.
- https://supabase.com/docs - referencia para banco, RLS e autenticacao.
- https://react.dev/ - referencia para componentes React planejados.

---

### O que você precisa fazer

1. Leia o conteudo conceitual preservado abaixo.
2. Abra `docs/superpowers/plans/2026-04-08-sprint-7-intelligence-terminal.md` e divida a execucao em etapas pequenas.
3. Prototipe a parte mais arriscada antes de integrar tudo.
4. Implemente task-by-task e marque os checkboxes do plano detalhado.

### Esqueleto

```text
# TODO: Explore - ler conceitos e plano detalhado.
# TODO: Prototype - validar a parte de maior risco em isolamento.
# TODO: Implement - executar o plano task-by-task.
# TODO: Verify - testar backend, frontend e persistencia conforme o plano.
```

<details>
<summary>Ver solução completa</summary>

## Contexto e Objetivo

O Sprint 7 adiciona ao IntelliOps o seu maior diferencial competitivo: um **grafo de entidades vivo**, onde cada empresa, pessoa e organização pesquisada vira um nó navegável com dossier acumulativo. Pensa no graph view do Obsidian — só que em vez de notas Markdown, os nós são entidades do mundo real extraídas automaticamente de relatórios de inteligência.

**Spec completo:** [`docs/superpowers/specs/2026-04-08-intelligence-terminal-design.md`](../superpowers/specs/2026-04-08-intelligence-terminal-design.md)
**Plano de implementação:** [`docs/superpowers/plans/2026-04-08-sprint-7-intelligence-terminal.md`](../superpowers/plans/2026-04-08-sprint-7-intelligence-terminal.md)

---

## Conceito Central: Grafo como Camada de Visualização

O insight mais importante deste sprint: **o "banco de grafos" do IntelliOps são duas tabelas relacionais simples** — `entities` e `relationships`. O D3.js no frontend é que transforma isso em grafo visual. Essa é exatamente a arquitetura do Obsidian: arquivos Markdown no disco + D3.js na tela. Aqui: linhas no Supabase + D3.js no browser.

```
Supabase                          Browser (D3.js)
──────────────────────────────    ─────────────────────────
entities   (id, name, type, …)    nós coloridos por tipo
relationships (from, to, type, weight)    arestas com espessura por weight
```

Não é necessário Neo4j, ArangoDB ou qualquer graph database. PostgreSQL resolve queries de 1-2 saltos (que é tudo que o MVP precisa) com um simples JOIN.

---

## Padrão: Factory para Extração de Entidades

O extrator de entidades (`backend/entity_extractor.py`) usa **Haiku-4.5**, não Sonnet. Por quê?

A extração é uma **task estruturada**: entra um texto, sai um JSON. O modelo não precisa raciocinar — só precisa identificar nomes e classificar em categorias pré-definidas. Haiku é ~10x mais barato e rápido o suficiente para isso.

```python
# Cada chamada tem o seu próprio client — sem estado compartilhado
def extract_entities(report_markdown: str, mode: str, research_id: str) -> EntityDraft:
    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",  # não Sonnet
        ...
    )
```

Isso é o **Strategy Pattern** aplicado a modelos: a escolha do modelo é uma decisão de negócio encapsulada em um único lugar. Se quiser trocar Haiku por outro modelo leve no futuro, é uma linha.

---

## Padrão: HITL como Gate de Qualidade

HITL = Human in the Loop. O extrator gera um **rascunho** salvo em `entity_drafts`. Nenhuma entidade entra no grafo sem passar pela curadoria do usuário.

```
relatório gerado
      │
      ▼
extract_entities()  →  entity_drafts (status: 'pending')
                                │
                         usuário revisa
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
         aprova            edita nome         descarta
              │                 │
              └────────┬────────┘
                       ▼
              POST /entities/review
              entities + relationships
```

Por que isso é importante? LLMs cometem erros — extraem entidades ambíguas, confundem "Tesla" (empresa) com "Tesla" (inventor), criam duplicatas. O HITL é o filtro humano que mantém a qualidade do grafo.

---

## Padrão: Deduplicação por ILIKE

Antes de criar um nó, o backend verifica se já existe uma entidade com nome similar:

```python
existing = sb.table("entities").select("id") \
    .ilike("name", f"%{entity.name}%") \
    .eq("user_id", x_user_id).execute()
```

`ILIKE` é o `LIKE` case-insensitive do PostgreSQL. `%Tesla%` bate em "Tesla", "Tesla Inc", "TESLA". Se encontrar, reutiliza o ID em vez de criar um nó duplicado. O weight da relação é incrementado em +1 a cada run que confirma aquela relação — isso é o que faz os nós mais referenciados ficarem maiores no grafo.

---

## D3.js: Force-Directed Graph

O grafo usa um algoritmo de **força física simulada**: nós se repelem entre si (força de carga), arestas atraem nós conectados (força de link), e tudo é ancorado em torno do centro da tela (força de centro). O resultado é o layout orgânico que você conhece do Obsidian.

```typescript
const sim = d3.forceSimulation(nodes)
  .force('link',   d3.forceLink(edges).distance(120))   // arestas = molas
  .force('charge', d3.forceManyBody().strength(-300))    // nós se repelem
  .force('center', d3.forceCenter(width/2, height/2))   // ancora no centro
```

A cada "tick" da simulação, as posições dos nós são recalculadas e o SVG é atualizado. Depois de alguns segundos, o sistema encontra equilíbrio e para.

**Iniciais dentro do nó + label abaixo** resolve o problema de nomes longos: o nó fica pequeno e limpo, o texto fica fora sem colidir com arestas.

---

## Interação: Hover vs Click

| Evento | Comportamento | Por que |
|---|---|---|
| `mouseover` | Tooltip glass flutua próximo ao nó | Preview rápido sem mudar o contexto |
| `click` | Split view: grafo dimmed + dossier | Exploração profunda de uma entidade |
| `drag` | Nó segue o cursor | Permite reorganizar o layout |
| `scroll` | Zoom in/out via D3 zoom | Navegar grafos grandes |

O tooltip desaparece quando o painel do dossier abre (`if hovered && !selected`). Os dois estados são mutuamente exclusivos.

---

## RLS — Row Level Security

Todas as tabelas novas (`entities`, `relationships`, `dossiers`, `entity_drafts`) têm RLS habilitada. Isso significa que mesmo se alguém fizer uma query diretamente na API do Supabase, só verá os dados do próprio usuário. A policy é simples para o Sprint 7 (single-user):

```sql
CREATE POLICY "owner access" ON entities FOR ALL
    USING (user_id = auth.uid());
```

No Sprint 9 (Collaboration), essa policy será expandida para incluir membros da mesma organização.

---

## Critério de Conclusão

1. Após uma pesquisa, o painel HITL aparece com as entidades extraídas
2. Usuário aprova entidades → elas aparecem no grafo em `/terminal`
3. Hover sobre um nó exibe o tooltip glass
4. Click num nó abre o dossier em split view com abas
5. Filtros de tipo funcionam (desativar "person" remove nós de pessoa)

</details>

- [ ] **Step 1.1: Ler conceitos deste sprint e o plano detalhado correspondente.**
- [ ] **Step 1.2: Prototipar a integracao de maior risco antes da implementacao completa.**
- [ ] **Step 1.3: Executar as tasks do plano detalhado em ordem.**
- [ ] **Step 1.4: Verificar o criterio de conclusao do sprint.**

### Resumo
> *Preencher apos concluir a task: quais partes do plano foram implementadas, verificadas e ainda tem risco?*

---

## Task 2: `supabase/migrations/002_entities.sql` - Criar schema do grafo

**Estimativa:** ~45min

**O que é e por que existe**

Esta task cria as tabelas que transformam relatorios em entidades navegaveis. Sem esse schema, o D3 teria apenas dados temporarios no browser e nenhum dossier acumulativo.

**Files:**
- Criar/Editar: `supabase/migrations/002_entities.sql`
- Consultar: `supabase/migrations/README.md`

---

### Conceito: Grafo persistido em tabelas relacionais
> O produto nao precisa de Neo4j no MVP. `entities` sao nos, `relationships` sao arestas, e queries de um ou dois saltos cabem bem no PostgreSQL. Essa escolha reduz infra e mantem RLS no mesmo banco dos relatorios.

---

### Documentação
- https://supabase.com/docs/guides/database - referencia de banco Supabase.
- https://www.postgresql.org/docs/current/ddl-constraints.html - referencia de constraints.

---

### O que você precisa fazer

1. Crie `entities`, `relationships`, `dossiers` e `entity_drafts`.
2. Adicione `user_id` e RLS single-user nesta fase.
3. Adicione indices para `user_id`, `entity_id` e busca por nome.
4. Rode a migration no mesmo Supabase usado pelo Sprint 5/6.

### Esqueleto

```sql
-- TODO: criar entities com id, user_id, name, type, weight, timestamps
-- TODO: criar relationships com source_id, target_id, type, weight
-- TODO: criar dossiers por entity_id
-- TODO: criar entity_drafts para HITL
-- TODO: habilitar RLS e policies owner access
```

<details>
<summary>Ver solução completa</summary>

Use o plano detalhado em `docs/superpowers/plans/2026-04-08-sprint-7-intelligence-terminal.md` como fonte do SQL completo. Ao final, rode uma query simples:

```sql
select table_name
from information_schema.tables
where table_schema = 'public'
  and table_name in ('entities', 'relationships', 'dossiers', 'entity_drafts');
```

O resultado esperado sao quatro linhas.

</details>

- [ ] **Step 2.1: Migration `002_entities.sql` criada.**
- [ ] **Step 2.2: Quatro tabelas principais existem.**
- [ ] **Step 2.3: RLS habilitada nas tabelas novas.**
- [ ] **Step 2.4: Indices de lookup criados.**

### Resumo
> *Preencher apos concluir a task: qual schema foi criado e qual query confirmou as tabelas?*

---

## Task 3: `backend/entity_extractor.py` - Extrair entidades para draft

**Estimativa:** ~1h

**O que é e por que existe**

Esta task cria a camada que le um relatorio e produz um JSON revisavel. Ela nao deve inserir entidades finais direto no grafo; primeiro salva drafts para aprovacao humana.

**Files:**
- Criar/Editar: `backend/entity_extractor.py`
- Criar/Editar: `backend/models/entities.py`

---

### Conceito: HITL antes de persistencia final
> LLMs extraem entidades com ruido: duplicatas, nomes ambiguos e relacoes fracas. Salvar tudo direto no grafo contaminaria o produto. Drafts permitem revisao humana antes de criar nos definitivos.

---

### Documentação
- https://docs.pydantic.dev/latest/ - referencia para modelos Pydantic.
- https://docs.anthropic.com/ - referencia para chamadas estruturadas ao modelo, se Anthropic for usado.

---

### O que você precisa fazer

1. Defina modelos Pydantic para entidade, relacao e draft.
2. Crie `extract_entities(report_markdown, mode, research_id)`.
3. Retorne JSON estruturado validado por Pydantic.
4. Salve o resultado em `entity_drafts` com status `pending`.

### Esqueleto

```python
class ExtractedEntity(BaseModel):
    # TODO: name, type, confidence, evidence
    pass

def extract_entities(report_markdown: str, mode: str, research_id: str):
    # TODO: chamar modelo leve
    # TODO: validar JSON
    # TODO: salvar draft pending
    pass
```

<details>
<summary>Ver solução completa</summary>

Use um modelo barato para esta task estruturada e mantenha o client encapsulado no extractor. A saida minima precisa separar entidades e relacoes, com evidencia textual suficiente para o usuario decidir se aprova.

Verificacao manual:

```bash
uv run python -c "from backend.entity_extractor import extract_entities; print(extract_entities('# Deel competes with Rippling', 'Competitor Intel', 'local-test'))"
```

</details>

- [ ] **Step 3.1: Modelos Pydantic criados.**
- [ ] **Step 3.2: Extractor retorna JSON validado.**
- [ ] **Step 3.3: Draft salvo como `pending`.**
- [ ] **Step 3.4: Teste manual com markdown pequeno funciona.**

### Resumo
> *Preencher apos concluir a task: qual formato de draft foi produzido e como voce validou?*

---

## Task 4: `backend/routers/entities.py` - Criar endpoints do grafo

**Estimativa:** ~1h

**O que é e por que existe**

Esta task expoe o grafo para o frontend sem vazar detalhes do Supabase. O React deve consumir um contrato estavel de `nodes` e `edges`.

**Files:**
- Criar/Editar: `backend/routers/entities.py`
- Criar/Editar: `backend/api.py`
- Consultar: `docs/api_contracts.md`

---

### Conceito: API como anti-corruption layer
> O frontend nao deve conhecer nomes internos de tabelas, policies ou joins. O endpoint converte dados relacionais em contrato visual: `nodes` e `edges`. Isso permite mudar o schema sem reescrever o grafo.

---

### Documentação
- https://fastapi.tiangolo.com/tutorial/bigger-applications/ - referencia para routers.
- https://fastapi.tiangolo.com/tutorial/response-model/ - referencia para response models.

---

### O que você precisa fazer

1. Crie `GET /entities/graph`.
2. Crie `GET /entities/{entity_id}/dossier`.
3. Crie `POST /entities/review`.
4. Registre o router no app FastAPI.

### Esqueleto

```python
router = APIRouter(prefix="/entities", tags=["entities"])

@router.get("/graph")
def get_graph():
    # TODO: carregar entities e relationships do usuario
    # TODO: retornar {"nodes": [...], "edges": [...]}
    pass
```

<details>
<summary>Ver solução completa</summary>

Compare o payload com `docs/api_contracts.md`. A verificacao minima e abrir `/docs` e confirmar que os tres endpoints aparecem.

```bash
uv run uvicorn backend.api:app --reload --port 8005
curl http://localhost:8005/entities/graph
```

Em pre-auth, use um header temporario ou user local documentado. Depois do Sprint 9, o endpoint deve resolver org/membership.

</details>

- [ ] **Step 4.1: Router de entidades registrado.**
- [ ] **Step 4.2: `/entities/graph` retorna `nodes` e `edges`.**
- [ ] **Step 4.3: `/entities/{id}/dossier` retorna dossier.**
- [ ] **Step 4.4: `/entities/review` aplica aprovacao HITL.**

### Resumo
> *Preencher apos concluir a task: quais endpoints foram criados e qual payload retornaram?*

---

## Task 5: `backend/api.py` - Acionar extracao apos salvar relatorio

**Estimativa:** ~30min

**O que é e por que existe**

O grafo so cresce se cada relatorio salvo virar um draft de entidades. Esta task conecta o fim da pesquisa ao pipeline de extracao sem bloquear a experiencia principal.

**Files:**
- Criar/Editar: `backend/api.py`
- Criar/Editar: `backend/entity_extractor.py`

---

### Conceito: side effect controlado apos persistencia
> A pesquisa e o salvamento do relatorio continuam sendo o fluxo principal. Extrair entidades e um side effect posterior: se falhar, o relatorio nao deve sumir. Essa separacao deixa o produto tolerante a falhas do extractor.

---

### Documentação
- https://fastapi.tiangolo.com/tutorial/background-tasks/ - referencia para background tasks.
- https://fastapi.tiangolo.com/tutorial/handling-errors/ - referencia para erros controlados.

---

### O que você precisa fazer

1. Encontre o ponto onde `/reports/save` confirma persistencia.
2. Dispare `extract_entities()` apos o report existir.
3. Registre erro sem quebrar a resposta de save.
4. Retorne `entity_draft_id` quando disponivel.

### Esqueleto

```python
# TODO: apos salvar report
# try:
#     draft = extract_entities(markdown_content, mode, research_id)
# except Exception:
#     log.exception("entity extraction failed")
```

<details>
<summary>Ver solução completa</summary>

Para o MVP, pode ser sincrono com tratamento de erro. Se a latencia ficar ruim, mova para `BackgroundTasks`. O contrato importante: relatorio salvo nao deve ser perdido por falha de extracao.

Verificacao:

```bash
curl -X POST http://localhost:8005/reports/save -H "Content-Type: application/json" -d "{\"user_id\":\"local-dev-user\",\"mode\":\"Competitor Intel\",\"company\":\"Deel\",\"query\":\"test\",\"markdown_content\":\"# Deel vs Rippling\"}"
```

Depois confira se `entity_drafts` recebeu uma linha.

</details>

- [ ] **Step 5.1: Save de relatorio continua funcionando.**
- [ ] **Step 5.2: Draft e criado apos save.**
- [ ] **Step 5.3: Falha do extractor nao derruba `/reports/save`.**
- [ ] **Step 5.4: Resultado documenta `entity_draft_id` ou erro.**

### Resumo
> *Preencher apos concluir a task: como a extracao foi acionada e como falhas sao tratadas?*

---

## Task 6: `frontend/src/pages/Terminal.tsx` - Renderizar grafo D3

**Estimativa:** ~1.5h

**O que é e por que existe**

Esta task cria a tela principal do Intelligence Terminal. Ela transforma o contrato `/entities/graph` em visualizacao navegavel.

**Files:**
- Criar/Editar: `frontend/src/pages/Terminal.tsx`
- Criar/Editar: `frontend/src/components/EntityGraph.tsx`
- Criar/Editar: `frontend/src/lib/api.ts`

---

### Conceito: visualizacao e estado de exploracao
> O D3 calcula posicoes e interacoes do grafo; o React controla estado de aplicacao como filtros, entidade selecionada e carregamento. Misturar tudo torna a tela fragil. Separe fetch/state em React e simulacao/render em um componente isolado.

---

### Documentação
- https://d3js.org/ - referencia oficial do D3.
- https://react.dev/learn/synchronizing-with-effects - referencia para integrar libs imperativas.

---

### O que você precisa fazer

1. Crie client `getEntityGraph()`.
2. Crie componente `EntityGraph`.
3. Renderize nos por tipo e arestas por peso.
4. Adicione hover, click, drag e zoom basicos.

### Esqueleto

```tsx
export function EntityGraph({ nodes, edges, onSelect }) {
  // TODO: criar svg ref
  // TODO: inicializar d3.forceSimulation
  // TODO: atualizar posicoes no tick
  return <svg />
}
```

<details>
<summary>Ver solução completa</summary>

Comece com dados mockados antes de chamar a API. Depois substitua por `GET /entities/graph`. O teste visual minimo: dois nos conectados aparecem, podem ser arrastados e click seleciona uma entidade.

</details>

- [ ] **Step 6.1: Grafo renderiza dados mockados.**
- [ ] **Step 6.2: Grafo consome `/entities/graph`.**
- [ ] **Step 6.3: Drag/zoom/hover funcionam.**
- [ ] **Step 6.4: Click define entidade selecionada.**

### Resumo
> *Preencher apos concluir a task: quais interacoes do grafo foram validadas?*

---

## Task 7: `frontend/src/components/EntityReviewPanel.tsx` - Revisar drafts e abrir dossier

**Estimativa:** ~1h

**O que é e por que existe**

Esta task fecha o ciclo HITL: o usuario aprova entidades extraidas, ve os nos no grafo e abre o dossier da entidade selecionada.

**Files:**
- Criar/Editar: `frontend/src/components/EntityReviewPanel.tsx`
- Criar/Editar: `frontend/src/components/EntityDossier.tsx`
- Criar/Editar: `frontend/src/lib/api.ts`

---

### Conceito: curadoria como parte do produto
> O diferencial nao e apenas extrair nomes; e permitir que o usuario transforme pesquisa bruta em memoria confiavel. A interface de revisao precisa deixar claro o que sera aprovado, editado ou descartado.

---

### Documentação
- https://react.dev/learn/managing-state - referencia para estado de formularios.
- https://fastapi.tiangolo.com/tutorial/body/ - referencia para payloads POST.

---

### O que você precisa fazer

1. Liste drafts pendentes depois de uma pesquisa.
2. Permita aprovar, editar nome/tipo ou descartar.
3. Chame `POST /entities/review`.
4. Atualize grafo e dossier apos aprovacao.

### Esqueleto

```tsx
function EntityReviewPanel({ draft }) {
  // TODO: renderizar entidades extraidas
  // TODO: permitir approve/edit/discard
  // TODO: enviar POST /entities/review
}
```

<details>
<summary>Ver solução completa</summary>

O caminho feliz do sprint deve terminar assim:

```text
pesquisa -> report salvo -> draft criado -> usuario aprova -> grafo atualiza -> dossier abre
```

Se esse fluxo funcionar com uma entidade e uma relacao, o MVP do Sprint 7 esta vivo.

</details>

- [ ] **Step 7.1: Draft pendente aparece na UI.**
- [ ] **Step 7.2: Approve/edit/discard funcionam.**
- [ ] **Step 7.3: Grafo atualiza apos revisao.**
- [ ] **Step 7.4: Dossier abre com dados da entidade.**

### Resumo
> *Preencher apos concluir a task: qual fluxo HITL foi validado de ponta a ponta?*

## Solo Developer Ready

- [ ] Migrations anteriores foram aplicadas antes de `002_entities.sql`.
- [ ] Consigo salvar um relatorio e ver um draft pendente.
- [ ] Consigo aprovar uma entidade e ver o no no grafo.
- [ ] `GET /entities/graph` segue o contrato de `docs/api_contracts.md`.
- [ ] O dossier abre a partir do click em uma entidade.
