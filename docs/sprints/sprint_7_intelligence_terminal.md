# Sprint 7 — Intelligence Terminal (Base): Guia Instrucional

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
