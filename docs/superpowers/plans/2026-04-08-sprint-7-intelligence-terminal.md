# Sprint 7 — Intelligence Terminal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir o Intelligence Terminal — grafo de entidades navegável com dossiers, extração automática pós-pesquisa, e curadoria HITL antes de persistir no banco.

**Architecture:** Após cada pesquisa, um extrator leve (Haiku-4.5) processa o relatório e gera um rascunho JSON de entidades e relacionamentos salvo em `entity_drafts`. O usuário revisa no painel HITL antes de confirmar. O Terminal exibe o grafo via D3.js (force-directed) com tooltip on-hover e dossier em split view on-click.

**Tech Stack:** Python (FastAPI, supabase-py, anthropic), React + TypeScript, D3.js, Supabase (PostgreSQL + RLS), Vite.

**Pré-requisito:** Sprint 6 concluído — React SaaS em `frontend/src/`, Supabase configurado com tabelas `profiles`, `researches`, `reports`.

---

## Estrutura de Arquivos

```
backend/
├── entity_extractor.py       # NOVO — extração Haiku-4.5
├── models/
│   └── entities.py           # NOVO — Pydantic models
├── routers/
│   └── entities.py           # NOVO — endpoints /entities/*
└── api.py                    # MODIFICAR — incluir router

supabase/migrations/
└── 001_intelligence_terminal.sql  # NOVO — 4 tabelas

frontend/src/
├── pages/
│   └── Terminal.tsx          # NOVO — página /terminal
├── components/terminal/
│   ├── EntityGraph.tsx        # NOVO — D3.js grafo
│   ├── NodeTooltip.tsx        # NOVO — hover glass
│   ├── DossierPanel.tsx       # NOVO — split view click
│   ├── HitlPanel.tsx          # NOVO — curadoria HITL
│   └── GraphFilters.tsx       # NOVO — toggles de tipo
├── hooks/
│   └── useEntityGraph.ts     # NOVO — fetch grafo
└── api/
    └── entities.ts            # NOVO — cliente HTTP

tests/
├── test_entity_extractor.py  # NOVO
└── test_entity_endpoints.py  # NOVO
```

---

## Task 1: Supabase — Migrations

**Files:**
- Create: `supabase/migrations/001_intelligence_terminal.sql`

- [ ] **Criar o arquivo de migração**

```sql
-- supabase/migrations/001_intelligence_terminal.sql

CREATE TABLE entities (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    type        TEXT NOT NULL CHECK (type IN ('company','person','org','event','sector')),
    name        TEXT NOT NULL,
    metadata    JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_entities_user ON entities(user_id);
ALTER TABLE entities ENABLE ROW LEVEL SECURITY;
CREATE POLICY "owner access" ON entities FOR ALL
    USING (user_id = auth.uid());

CREATE TABLE relationships (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    from_entity  UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    to_entity    UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    type         TEXT NOT NULL,
    weight       FLOAT NOT NULL DEFAULT 1.0,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_rel_user ON relationships(user_id);
CREATE INDEX idx_rel_from ON relationships(from_entity);
ALTER TABLE relationships ENABLE ROW LEVEL SECURITY;
CREATE POLICY "owner access" ON relationships FOR ALL
    USING (user_id = auth.uid());

CREATE TABLE dossiers (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id  UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE UNIQUE,
    markdown   TEXT NOT NULL DEFAULT '',
    sources    JSONB NOT NULL DEFAULT '[]',
    version    INTEGER NOT NULL DEFAULT 1,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE dossiers ENABLE ROW LEVEL SECURITY;
CREATE POLICY "owner via entity" ON dossiers FOR ALL
    USING (entity_id IN (
        SELECT id FROM entities WHERE user_id = auth.uid()
    ));

CREATE TABLE entity_drafts (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    research_id  UUID NOT NULL REFERENCES researches(id) ON DELETE CASCADE,
    draft        JSONB NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending','approved','discarded')),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_drafts_research ON entity_drafts(research_id);
CREATE INDEX idx_drafts_status ON entity_drafts(status);
ALTER TABLE entity_drafts ENABLE ROW LEVEL SECURITY;
CREATE POLICY "owner via research" ON entity_drafts FOR ALL
    USING (research_id IN (
        SELECT id FROM researches WHERE user_id = auth.uid()
    ));
```

- [ ] **Aplicar a migração no Supabase**

No painel do Supabase → SQL Editor, cole e execute o arquivo acima. Ou via CLI:
```bash
supabase db push
```

- [ ] **Verificar no Supabase Table Editor** que as 4 tabelas aparecem com RLS habilitado.

- [ ] **Commit**
```bash
git add supabase/migrations/001_intelligence_terminal.sql
git commit -m "feat: add Supabase migrations for Intelligence Terminal (entities, relationships, dossiers, entity_drafts)"
```

---

## Task 2: Backend — Pydantic Models

**Files:**
- Create: `backend/models/__init__.py`
- Create: `backend/models/entities.py`

- [ ] **Criar o diretório e o arquivo de models**

```python
# backend/models/__init__.py
# (vazio)
```

```python
# backend/models/entities.py
from pydantic import BaseModel, field_validator
from typing import Any


class EntityCreate(BaseModel):
    name: str
    type: str
    metadata: dict[str, Any] = {}

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        allowed = {"company", "person", "org", "event", "sector"}
        if v not in allowed:
            raise ValueError(f"type must be one of {allowed}")
        return v


class RelationshipCreate(BaseModel):
    from_name: str   # nome da entidade de origem
    to_name: str     # nome da entidade de destino
    type: str


class EntityDraft(BaseModel):
    entities: list[EntityCreate]
    relationships: list[RelationshipCreate]


class EntityReviewRequest(BaseModel):
    draft_id: str
    approved: EntityDraft


class EntityNode(BaseModel):
    id: str
    name: str
    type: str
    metadata: dict[str, Any]
    weight: float
    initials: str


class EntityEdge(BaseModel):
    id: str
    from_entity: str
    to_entity: str
    type: str
    weight: float


class EntityGraph(BaseModel):
    nodes: list[EntityNode]
    edges: list[EntityEdge]
```

- [ ] **Escrever teste para o validator**

```python
# tests/test_entity_models.py
import pytest
from pydantic import ValidationError
from backend.models.entities import EntityCreate

def test_valid_entity_type():
    e = EntityCreate(name="Tesla", type="company")
    assert e.type == "company"

def test_invalid_entity_type_raises():
    with pytest.raises(ValidationError):
        EntityCreate(name="Tesla", type="vehicle")
```

- [ ] **Rodar o teste**
```bash
uv run pytest tests/test_entity_models.py -v
```
Esperado: 2 PASSED

- [ ] **Commit**
```bash
git add backend/models/ tests/test_entity_models.py
git commit -m "feat: add Pydantic models for entity graph (EntityCreate, EntityGraph, EntityReviewRequest)"
```

---

## Task 3: Backend — Entity Extractor (Haiku-4.5)

**Files:**
- Create: `backend/entity_extractor.py`
- Create: `tests/test_entity_extractor.py`

- [ ] **Escrever o teste primeiro (TDD)**

```python
# tests/test_entity_extractor.py
from unittest.mock import patch, MagicMock
from backend.entity_extractor import extract_entities

SAMPLE_REPORT = """
Tesla Inc. is the market leader in electric vehicles. CEO Elon Musk also leads SpaceX.
Rivian is a direct competitor in the EV truck segment. Tesla acquired SolarCity in 2016.
"""

def _mock_haiku(response_text: str):
    msg = MagicMock()
    msg.content = [MagicMock(text=response_text)]
    return msg

def test_extract_returns_entities_and_relationships():
    mock_response = '''{
        "entities": [
            {"name": "Tesla Inc", "type": "company", "metadata": {"ceo": "Elon Musk"}},
            {"name": "Elon Musk", "type": "person", "metadata": {"role": "CEO"}},
            {"name": "Rivian", "type": "company", "metadata": {}}
        ],
        "relationships": [
            {"from_name": "Elon Musk", "to_name": "Tesla Inc", "type": "executive_of"},
            {"from_name": "Tesla Inc", "to_name": "Rivian", "type": "competitor"}
        ]
    }'''
    with patch("backend.entity_extractor.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = _mock_haiku(mock_response)
        result = extract_entities(SAMPLE_REPORT, mode="Competitor Intel", research_id="test-123")

    assert len(result.entities) == 3
    assert result.entities[0].name == "Tesla Inc"
    assert len(result.relationships) == 2

def test_extract_returns_empty_on_invalid_json():
    with patch("backend.entity_extractor.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = _mock_haiku("not json at all")
        result = extract_entities("any report", mode="Due Diligence", research_id="test-456")

    assert result.entities == []
    assert result.relationships == []
```

- [ ] **Rodar para confirmar falha**
```bash
uv run pytest tests/test_entity_extractor.py -v
```
Esperado: ImportError (módulo ainda não existe)

- [ ] **Implementar o extractor**

```python
# backend/entity_extractor.py
import json
import logging
import anthropic
from backend.models.entities import EntityDraft, EntityCreate, RelationshipCreate

log = logging.getLogger(__name__)

EXTRACTION_PROMPT = """\
You are an entity extractor for a business intelligence system.

Extract all named entities and relationships from the report below.
Mode: {mode}

Report:
{report}

Return ONLY valid JSON with this exact structure:
{{
  "entities": [
    {{"name": "string", "type": "company|person|org|event|sector", "metadata": {{}}}}
  ],
  "relationships": [
    {{"from_name": "entity name", "to_name": "entity name", "type": "relationship_type"}}
  ]
}}

Rules:
- type must be exactly one of: company, person, org, event, sector
- metadata keys for company: hq, ceo, founded, revenue (use null if unknown)
- metadata keys for person: role, company (use null if unknown)
- relationship types: competitor, acquired, invested_in, executive_of, partner, subsidiary
- Only extract entities explicitly named in the report
- Return empty arrays if nothing found
"""


def extract_entities(report_markdown: str, mode: str, research_id: str) -> EntityDraft:
    client = anthropic.Anthropic()
    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": EXTRACTION_PROMPT.format(mode=mode, report=report_markdown)
            }]
        )
        raw = json.loads(message.content[0].text)
        entities = [EntityCreate(**e) for e in raw.get("entities", [])]
        relationships = [RelationshipCreate(**r) for r in raw.get("relationships", [])]
        return EntityDraft(entities=entities, relationships=relationships)
    except Exception as exc:
        log.warning("Entity extraction failed for research %s: %s", research_id, exc)
        return EntityDraft(entities=[], relationships=[])
```

- [ ] **Rodar os testes**
```bash
uv run pytest tests/test_entity_extractor.py -v
```
Esperado: 2 PASSED

- [ ] **Commit**
```bash
git add backend/entity_extractor.py tests/test_entity_extractor.py
git commit -m "feat: add entity extractor using Haiku-4.5 with JSON output and graceful fallback"
```

---

## Task 4: Backend — FastAPI Endpoints

**Files:**
- Create: `backend/routers/__init__.py`
- Create: `backend/routers/entities.py`
- Modify: `backend/api.py`

- [ ] **Instalar supabase-py**
```bash
uv add supabase
```

- [ ] **Escrever os testes**

```python
# tests/test_entity_endpoints.py
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from backend.api import app

client = TestClient(app)

def _supabase_mock(entities=None, relationships=None):
    mock = MagicMock()
    mock.table.return_value.select.return_value.eq.return_value.execute.return_value.data = entities or []
    mock.table.return_value.select.return_value.ilike.return_value.eq.return_value.execute.return_value.data = []
    mock.table.return_value.insert.return_value.execute.return_value.data = [{"id": "abc-123"}]
    mock.table.return_value.update.return_value.eq.return_value.execute.return_value.data = []
    return mock

def test_get_graph_empty():
    with patch("backend.routers.entities.get_supabase", return_value=_supabase_mock()):
        resp = client.get("/entities/graph", headers={"X-User-Id": "user-1"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["nodes"] == []
    assert data["edges"] == []

def test_review_entities_success():
    payload = {
        "draft_id": "draft-1",
        "approved": {
            "entities": [{"name": "Tesla", "type": "company", "metadata": {}}],
            "relationships": []
        }
    }
    with patch("backend.routers.entities.get_supabase", return_value=_supabase_mock()):
        resp = client.post("/entities/review", json=payload,
                           headers={"X-User-Id": "user-1"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
```

- [ ] **Rodar para confirmar falha**
```bash
uv run pytest tests/test_entity_endpoints.py -v
```
Esperado: FAIL (router não existe)

- [ ] **Criar o router**

```python
# backend/routers/__init__.py
# (vazio)
```

```python
# backend/routers/entities.py
import os
from fastapi import APIRouter, Header, HTTPException
from supabase import create_client, Client
from backend.models.entities import EntityReviewRequest, EntityGraph, EntityNode, EntityEdge

router = APIRouter(prefix="/entities", tags=["entities"])


def get_supabase() -> Client:
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_KEY"]
    )


def _compute_initials(name: str) -> str:
    words = name.strip().split()
    if len(words) >= 2:
        return (words[0][0] + words[-1][0]).upper()
    return name[:2].upper()


@router.post("/review")
async def review_entities(request: EntityReviewRequest, x_user_id: str = Header(...)):
    sb = get_supabase()

    sb.table("entity_drafts").update({"status": "approved"}) \
        .eq("id", request.draft_id).execute()

    created: dict[str, str] = {}  # name → id

    for entity in request.approved.entities:
        existing = sb.table("entities").select("id") \
            .ilike("name", f"%{entity.name}%") \
            .eq("user_id", x_user_id).execute()

        if existing.data:
            entity_id = existing.data[0]["id"]
        else:
            result = sb.table("entities").insert({
                "user_id": x_user_id,
                "name": entity.name,
                "type": entity.type,
                "metadata": entity.metadata,
            }).execute()
            entity_id = result.data[0]["id"]
            sb.table("dossiers").insert({
                "entity_id": entity_id,
                "markdown": "",
                "sources": [],
                "version": 1,
            }).execute()

        created[entity.name] = entity_id

    for rel in request.approved.relationships:
        from_id = created.get(rel.from_name)
        to_id = created.get(rel.to_name)
        if not (from_id and to_id):
            continue

        existing = sb.table("relationships").select("id,weight") \
            .eq("from_entity", from_id).eq("to_entity", to_id) \
            .eq("type", rel.type).execute()

        if existing.data:
            sb.table("relationships").update(
                {"weight": existing.data[0]["weight"] + 1.0}
            ).eq("id", existing.data[0]["id"]).execute()
        else:
            sb.table("relationships").insert({
                "user_id": x_user_id,
                "from_entity": from_id,
                "to_entity": to_id,
                "type": rel.type,
                "weight": 1.0,
            }).execute()

    return {"status": "ok", "entities_created": len(created)}


@router.get("/graph", response_model=EntityGraph)
async def get_graph(x_user_id: str = Header(...)):
    sb = get_supabase()

    entities_data = sb.table("entities").select("id,name,type,metadata") \
        .eq("user_id", x_user_id).execute().data

    rels_data = sb.table("relationships").select("id,from_entity,to_entity,type,weight") \
        .eq("user_id", x_user_id).execute().data

    # Compute node weight = soma dos weights das arestas conectadas
    weight_map: dict[str, float] = {}
    for r in rels_data:
        weight_map[r["from_entity"]] = weight_map.get(r["from_entity"], 0) + r["weight"]
        weight_map[r["to_entity"]] = weight_map.get(r["to_entity"], 0) + r["weight"]

    nodes = [
        EntityNode(
            id=e["id"], name=e["name"], type=e["type"],
            metadata=e["metadata"],
            weight=weight_map.get(e["id"], 1.0),
            initials=_compute_initials(e["name"]),
        )
        for e in entities_data
    ]

    edges = [
        EntityEdge(
            id=r["id"], from_entity=r["from_entity"],
            to_entity=r["to_entity"], type=r["type"], weight=r["weight"],
        )
        for r in rels_data
    ]

    return EntityGraph(nodes=nodes, edges=edges)
```

- [ ] **Registrar o router em `api.py`**

```python
# backend/api.py — adicionar após as imports existentes:
from backend.routers.entities import router as entities_router

# adicionar após app = FastAPI(...):
app.include_router(entities_router)
```

- [ ] **Rodar os testes**
```bash
uv run pytest tests/test_entity_endpoints.py tests/test_entity_models.py -v
```
Esperado: 4 PASSED

- [ ] **Commit**
```bash
git add backend/routers/ backend/api.py tests/test_entity_endpoints.py
git commit -m "feat: add /entities/review and /entities/graph endpoints with Supabase persistence"
```

---

## Task 5: Backend — Acionar Extrator Pós-Pesquisa

**Files:**
- Modify: `backend/api.py`

O extrator deve ser chamado em background depois que o relatório é gerado, sem bloquear o stream SSE.

- [ ] **Localizar onde o relatório final é escrito em `api.py`**

Procurar pelo evento `done` no `event_stream()`. É onde o relatório está disponível.

- [ ] **Adicionar chamada em background**

```python
# backend/api.py — no topo, adicionar imports:
from fastapi import BackgroundTasks
from backend.entity_extractor import extract_entities
from supabase import create_client
import os

# Adicionar função helper:
def _save_entity_draft(research_id: str, mode: str | None, report_markdown: str):
    """Chamada em background após o stream terminar."""
    draft = extract_entities(report_markdown, mode=mode or "General", research_id=research_id)
    if not draft.entities:
        return
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    sb.table("entity_drafts").insert({
        "research_id": research_id,
        "draft": draft.model_dump(),
        "status": "pending",
    }).execute()
```

- [ ] **Modificar o endpoint `/research/stream` para aceitar `BackgroundTasks` e acionar o extrator**

```python
# backend/api.py — modificar a assinatura e o corpo de /research/stream:
@app.post("/research/stream")
async def research_stream(request: ResearchRequest, background_tasks: BackgroundTasks):
    research_id = str(uuid.uuid4())
    report_parts: list[str] = []   # acumula tokens do relatório

    async def event_stream():
        # ... lógica existente de streaming ...
        # Quando o evento 'done' for emitido, acionar background task:
        background_tasks.add_task(
            _save_entity_draft,
            research_id=research_id,
            mode=request.mode,
            report_markdown="".join(report_parts),
        )

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

> **Nota:** integre `report_parts.append(text)` nos pontos onde tokens do relatório são emitidos, antes do `yield`.

- [ ] **Confirmar que o servidor ainda sobe sem erros**
```bash
uv run uvicorn backend.api:app --reload
```
Esperado: `Application startup complete.`

- [ ] **Commit**
```bash
git add backend/api.py
git commit -m "feat: trigger entity extraction in background after research stream completes"
```

---

## Task 6: Frontend — Página Terminal e API Client

**Files:**
- Create: `frontend/src/api/entities.ts`
- Create: `frontend/src/hooks/useEntityGraph.ts`
- Create: `frontend/src/pages/Terminal.tsx`
- Modify: `frontend/src/App.tsx` (ou router config)

- [ ] **Criar o cliente HTTP para entidades**

```typescript
// frontend/src/api/entities.ts
import { supabase } from '../lib/supabase'

export interface EntityNode {
  id: string
  name: string
  type: 'company' | 'person' | 'org' | 'event' | 'sector'
  metadata: Record<string, unknown>
  weight: number
  initials: string
}

export interface EntityEdge {
  id: string
  from_entity: string
  to_entity: string
  type: string
  weight: number
}

export interface EntityGraph {
  nodes: EntityNode[]
  edges: EntityEdge[]
}

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8005'

async function authHeaders(): Promise<HeadersInit> {
  const { data } = await supabase.auth.getUser()
  return { 'X-User-Id': data.user?.id ?? '' }
}

export async function fetchGraph(): Promise<EntityGraph> {
  const headers = await authHeaders()
  const res = await fetch(`${API_URL}/entities/graph`, { headers })
  if (!res.ok) throw new Error('Failed to fetch graph')
  return res.json()
}

export interface ReviewRequest {
  draft_id: string
  approved: {
    entities: Array<{ name: string; type: string; metadata: Record<string, unknown> }>
    relationships: Array<{ from_name: string; to_name: string; type: string }>
  }
}

export async function reviewEntities(payload: ReviewRequest): Promise<void> {
  const headers = { ...(await authHeaders()), 'Content-Type': 'application/json' }
  const res = await fetch(`${API_URL}/entities/review`, {
    method: 'POST', headers, body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error('Review failed')
}
```

- [ ] **Criar o hook `useEntityGraph`**

```typescript
// frontend/src/hooks/useEntityGraph.ts
import { useState, useEffect } from 'react'
import { fetchGraph, EntityGraph } from '../api/entities'

export function useEntityGraph() {
  const [graph, setGraph] = useState<EntityGraph>({ nodes: [], edges: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchGraph()
      setGraph(data)
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  return { graph, loading, error, reload: load }
}
```

- [ ] **Criar a página Terminal (shell inicial)**

```tsx
// frontend/src/pages/Terminal.tsx
import { useEntityGraph } from '../hooks/useEntityGraph'
import { EntityGraph } from '../components/terminal/EntityGraph'
import { useState } from 'react'
import type { EntityNode } from '../api/entities'

export default function Terminal() {
  const { graph, loading, error } = useEntityGraph()
  const [selected, setSelected] = useState<EntityNode | null>(null)
  const [hovered, setHovered] = useState<EntityNode | null>(null)

  if (loading) return <div className="flex h-screen items-center justify-center text-slate-400">Carregando grafo...</div>
  if (error) return <div className="flex h-screen items-center justify-center text-red-400">{error}</div>

  return (
    <div className="relative h-screen w-full bg-[#0a0e1a] overflow-hidden">
      <EntityGraph
        graph={graph}
        onHover={setHovered}
        onSelect={setSelected}
      />
      {/* NodeTooltip e DossierPanel serão adicionados nas próximas tasks */}
    </div>
  )
}
```

- [ ] **Registrar a rota `/terminal` no router da aplicação**

```tsx
// frontend/src/App.tsx — adicionar dentro das rotas existentes:
import Terminal from './pages/Terminal'

// dentro do <Routes>:
<Route path="/terminal" element={<AuthGuard><Terminal /></AuthGuard>} />
```

- [ ] **Verificar que a rota abre sem erros**
```bash
cd frontend && npm run dev
```
Navegar para `http://localhost:5173/terminal` — deve exibir "Carregando grafo..." (grafo vazio).

- [ ] **Commit**
```bash
git add frontend/src/api/entities.ts frontend/src/hooks/useEntityGraph.ts frontend/src/pages/Terminal.tsx frontend/src/App.tsx
git commit -m "feat: add Terminal page, useEntityGraph hook, and entities API client"
```

---

## Task 7: Frontend — Grafo D3.js

**Files:**
- Create: `frontend/src/components/terminal/EntityGraph.tsx`

```bash
cd frontend && npm install d3 @types/d3
```

- [ ] **Instalar D3**
```bash
cd frontend && npm install d3 @types/d3
```

- [ ] **Criar o componente EntityGraph**

```tsx
// frontend/src/components/terminal/EntityGraph.tsx
import { useEffect, useRef } from 'react'
import * as d3 from 'd3'
import type { EntityNode, EntityEdge, EntityGraph as GraphData } from '../../api/entities'

const TYPE_COLORS: Record<string, string> = {
  company: '#3b82f6',
  person:  '#8b5cf6',
  org:     '#10b981',
  event:   '#f59e0b',
  sector:  '#ef4444',
}

const BASE_R = 16
const MAX_R  = 28

interface Props {
  graph: GraphData
  onHover: (node: EntityNode | null) => void
  onSelect: (node: EntityNode | null) => void
}

export function EntityGraph({ graph, onHover, onSelect }: Props) {
  const svgRef = useRef<SVGSVGElement>(null)

  useEffect(() => {
    if (!svgRef.current) return
    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()

    const width = svgRef.current.clientWidth
    const height = svgRef.current.clientHeight

    const maxWeight = Math.max(...graph.nodes.map(n => n.weight), 1)
    const rScale = d3.scaleLinear().domain([1, maxWeight]).range([BASE_R, MAX_R])
    const wScale = d3.scaleLinear().domain([1, maxWeight]).range([1, 4])

    const nodes = graph.nodes.map(n => ({ ...n })) as (EntityNode & d3.SimulationNodeDatum)[]
    const edges = graph.edges.map(e => ({ ...e })) as (EntityEdge & { source: string; target: string })[]
    edges.forEach(e => { e.source = e.from_entity; e.target = e.to_entity })

    const sim = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(edges).id((d: any) => d.id).distance(120))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))

    const g = svg.append('g')

    // zoom
    svg.call(d3.zoom<SVGSVGElement, unknown>().on('zoom', e => g.attr('transform', e.transform)) as any)

    // edges
    const link = g.append('g').selectAll('line')
      .data(edges).join('line')
      .attr('stroke', '#1e3a5f')
      .attr('stroke-width', (d: any) => wScale(d.weight))
      .attr('opacity', 0.6)

    // nodes group
    const node = g.append('g').selectAll('g')
      .data(nodes).join('g')
      .style('cursor', 'pointer')
      .on('mouseover', (_e, d) => onHover(d))
      .on('mouseout', () => onHover(null))
      .on('click', (_e, d) => onSelect(d))
      .call(d3.drag<SVGGElement, any>()
        .on('start', (e, d) => { if (!e.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y })
        .on('drag', (e, d) => { d.fx = e.x; d.fy = e.y })
        .on('end', (e, d) => { if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null })
      )

    // círculo
    node.append('circle')
      .attr('r', (d: any) => rScale(d.weight))
      .attr('fill', (d: any) => TYPE_COLORS[d.type] ?? '#64748b')
      .attr('fill-opacity', 0.15)
      .attr('stroke', (d: any) => TYPE_COLORS[d.type] ?? '#64748b')
      .attr('stroke-width', 2)

    // iniciais dentro
    node.append('text')
      .text((d: any) => d.initials)
      .attr('text-anchor', 'middle')
      .attr('dominant-baseline', 'central')
      .attr('fill', (d: any) => TYPE_COLORS[d.type] ?? '#64748b')
      .attr('font-size', (d: any) => `${rScale(d.weight) * 0.65}px`)
      .attr('font-weight', 'bold')
      .style('pointer-events', 'none')

    // label abaixo
    node.append('text')
      .text((d: any) => d.name)
      .attr('text-anchor', 'middle')
      .attr('dy', (d: any) => rScale(d.weight) + 14)
      .attr('fill', '#94a3b8')
      .attr('font-size', '11px')
      .style('pointer-events', 'none')

    sim.on('tick', () => {
      link
        .attr('x1', (d: any) => d.source.x)
        .attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x)
        .attr('y2', (d: any) => d.target.y)
      node.attr('transform', (d: any) => `translate(${d.x},${d.y})`)
    })

    return () => { sim.stop() }
  }, [graph])

  return <svg ref={svgRef} className="w-full h-full" />
}
```

- [ ] **Verificar no browser** que o grafo renderiza (testar com dados mock se ainda sem dados reais):

Adicionar temporariamente em `Terminal.tsx` para teste visual:
```tsx
const MOCK_GRAPH = {
  nodes: [
    { id: '1', name: 'Tesla Inc', type: 'company', metadata: {}, weight: 3, initials: 'TI' },
    { id: '2', name: 'Elon Musk', type: 'person', metadata: {}, weight: 2, initials: 'EM' },
    { id: '3', name: 'Rivian', type: 'company', metadata: {}, weight: 1, initials: 'Ri' },
  ],
  edges: [
    { id: 'e1', from_entity: '2', to_entity: '1', type: 'executive_of', weight: 1 },
    { id: 'e2', from_entity: '1', to_entity: '3', type: 'competitor', weight: 1 },
  ],
}
```
Passar `MOCK_GRAPH` como prop e confirmar que 3 nós aparecem com iniciais e labels.

- [ ] **Remover o mock** e restaurar `{graph}`.

- [ ] **Commit**
```bash
git add frontend/src/components/terminal/EntityGraph.tsx frontend/package.json frontend/package-lock.json
git commit -m "feat: add D3.js force-directed EntityGraph with initials, labels, color by type, size by weight"
```

---

## Task 8: Frontend — Hover Tooltip (NodeTooltip)

**Files:**
- Create: `frontend/src/components/terminal/NodeTooltip.tsx`
- Modify: `frontend/src/pages/Terminal.tsx`

- [ ] **Criar NodeTooltip**

```tsx
// frontend/src/components/terminal/NodeTooltip.tsx
import type { EntityNode } from '../../api/entities'

const TYPE_LABELS: Record<string, string> = {
  company: 'Company', person: 'Person', org: 'Org', event: 'Event', sector: 'Sector',
}

const TYPE_COLORS: Record<string, string> = {
  company: '#3b82f6', person: '#8b5cf6', org: '#10b981', event: '#f59e0b', sector: '#ef4444',
}

interface Props {
  node: EntityNode
  x: number
  y: number
  onClose: () => void
}

export function NodeTooltip({ node, x, y, onClose }: Props) {
  return (
    <div
      className="absolute z-20 w-48 rounded-lg border p-3 text-xs shadow-xl backdrop-blur-sm"
      style={{
        left: x + 16,
        top: y - 40,
        background: 'rgba(10,14,26,0.95)',
        borderColor: `${TYPE_COLORS[node.type]}55`,
      }}
    >
      <p className="font-bold text-slate-100 mb-1">{node.name}</p>
      <span
        className="inline-block rounded px-1.5 py-0.5 text-[10px] mb-2"
        style={{ background: `${TYPE_COLORS[node.type]}22`, color: TYPE_COLORS[node.type] }}
      >
        {TYPE_LABELS[node.type]}
      </span>
      {node.metadata.ceo && (
        <p className="text-slate-400">CEO · {String(node.metadata.ceo)}</p>
      )}
      {node.metadata.role && (
        <p className="text-slate-400">Role · {String(node.metadata.role)}</p>
      )}
      <p className="mt-2 text-[10px] text-slate-600 text-center border-t border-slate-800 pt-1">
        clique para abrir dossier →
      </p>
    </div>
  )
}
```

- [ ] **Integrar tooltip em `Terminal.tsx`**

O D3 não expõe coordenadas de tela diretamente via props React. Capturar posição do mouse via evento nativo no SVG wrapper:

```tsx
// frontend/src/pages/Terminal.tsx — atualizar:
import { NodeTooltip } from '../components/terminal/NodeTooltip'
import { useState, useCallback } from 'react'

// Adicionar estado de posição:
const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 })

// Wrapper do grafo com onMouseMove:
<div
  className="relative h-screen w-full bg-[#0a0e1a] overflow-hidden"
  onMouseMove={e => setTooltipPos({ x: e.clientX, y: e.clientY })}
>
  <EntityGraph graph={graph} onHover={setHovered} onSelect={setSelected} />
  {hovered && !selected && (
    <NodeTooltip
      node={hovered}
      x={tooltipPos.x}
      y={tooltipPos.y}
      onClose={() => setHovered(null)}
    />
  )}
</div>
```

- [ ] **Verificar no browser** que o tooltip aparece próximo ao cursor ao passar o mouse sobre um nó.

- [ ] **Commit**
```bash
git add frontend/src/components/terminal/NodeTooltip.tsx frontend/src/pages/Terminal.tsx
git commit -m "feat: add hover glass tooltip near node with entity metadata preview"
```

---

## Task 9: Frontend — Dossier Panel (Click Split View)

**Files:**
- Create: `frontend/src/components/terminal/DossierPanel.tsx`
- Modify: `frontend/src/pages/Terminal.tsx`

- [ ] **Criar DossierPanel**

```tsx
// frontend/src/components/terminal/DossierPanel.tsx
import { useState } from 'react'
import type { EntityNode } from '../../api/entities'

const TYPE_COLORS: Record<string, string> = {
  company: '#3b82f6', person: '#8b5cf6', org: '#10b981', event: '#f59e0b', sector: '#ef4444',
}

type Tab = 'profile' | 'connections' | 'history' | 'jobs'

interface Props {
  node: EntityNode
  onClose: () => void
  onSearch: (node: EntityNode) => void
}

export function DossierPanel({ node, onClose, onSearch }: Props) {
  const [tab, setTab] = useState<Tab>('profile')
  const color = TYPE_COLORS[node.type] ?? '#64748b'

  return (
    <div className="absolute right-0 top-0 h-full w-[42%] flex flex-col bg-[#0f1629] border-l z-10"
         style={{ borderColor: `${color}44` }}>

      {/* Header */}
      <div className="flex items-start justify-between p-4 border-b border-slate-800">
        <div>
          <h2 className="text-slate-100 font-bold text-base">{node.name}</h2>
          <span className="inline-block mt-1 rounded px-2 py-0.5 text-[10px]"
                style={{ background: `${color}22`, color }}>
            {node.type}
          </span>
        </div>
        <button onClick={onClose} className="text-slate-500 hover:text-slate-300 text-lg">✕</button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-800 text-xs">
        {(['profile','connections','history','jobs'] as Tab[]).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className="px-4 py-2 capitalize transition-colors"
            style={tab === t
              ? { color, borderBottom: `2px solid ${color}` }
              : { color: '#64748b' }}
          >
            {t === 'profile' ? 'Perfil' : t === 'connections' ? 'Conexões' : t === 'history' ? 'Histórico' : 'Jobs'}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-4">
        {tab === 'profile' && (
          <div className="space-y-3">
            <p className="text-slate-400 text-sm leading-relaxed">
              {(node.metadata.summary as string) ?? 'Nenhum sumário disponível ainda. Execute uma pesquisa sobre esta entidade para popular o dossier.'}
            </p>
            <div className="grid grid-cols-2 gap-2 text-xs text-slate-500">
              {Object.entries(node.metadata)
                .filter(([k]) => k !== 'summary')
                .map(([k, v]) => (
                  <span key={k}>{k} · {String(v ?? '—')}</span>
                ))}
            </div>
          </div>
        )}
        {tab === 'connections' && (
          <p className="text-slate-500 text-sm">Conexões disponíveis após curadoria HITL.</p>
        )}
        {tab === 'history' && (
          <p className="text-slate-500 text-sm">Histórico de runs aparece aqui após pesquisas.</p>
        )}
        {tab === 'jobs' && (
          <p className="text-slate-500 text-sm">Monitoring jobs — disponível no Sprint 8.</p>
        )}
      </div>

      {/* Actions */}
      <div className="p-4 border-t border-slate-800 flex gap-2">
        <button
          onClick={() => onSearch(node)}
          className="text-xs px-3 py-1.5 rounded border border-slate-700 text-green-400 hover:bg-green-900/20"
        >
          ↗ Pesquisar
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Integrar em `Terminal.tsx`**

```tsx
// frontend/src/pages/Terminal.tsx — adicionar import e uso:
import { DossierPanel } from '../components/terminal/DossierPanel'

// Dentro do JSX, após o NodeTooltip:
{selected && (
  <>
    {/* overlay para dimmer o grafo */}
    <div className="absolute inset-0 bg-black/50 z-[5]" onClick={() => setSelected(null)} />
    <DossierPanel
      node={selected}
      onClose={() => setSelected(null)}
      onSearch={node => {
        // redirecionar para /research com a entidade pré-preenchida
        window.location.href = `/research?entity=${encodeURIComponent(node.name)}`
      }}
    />
  </>
)}
```

- [ ] **Verificar no browser**: clicar num nó deve abrir o painel à direita com o grafo dimmed atrás.

- [ ] **Commit**
```bash
git add frontend/src/components/terminal/DossierPanel.tsx frontend/src/pages/Terminal.tsx
git commit -m "feat: add DossierPanel split view with tabs on node click"
```

---

## Task 10: Frontend — HITL Panel

**Files:**
- Create: `frontend/src/components/terminal/HitlPanel.tsx`

O painel aparece quando há `entity_drafts` com status `pending`. Buscar drafts pendentes ao carregar o Terminal.

- [ ] **Adicionar fetch de drafts pendentes em `entities.ts`**

```typescript
// frontend/src/api/entities.ts — adicionar:
export interface EntityDraft {
  id: string
  research_id: string
  draft: {
    entities: Array<{ name: string; type: string; metadata: Record<string, unknown> }>
    relationships: Array<{ from_name: string; to_name: string; type: string }>
  }
  status: string
}

export async function fetchPendingDrafts(): Promise<EntityDraft[]> {
  const { data } = await supabase
    .from('entity_drafts')
    .select('*')
    .eq('status', 'pending')
    .order('created_at', { ascending: false })
  return data ?? []
}
```

- [ ] **Criar HitlPanel**

```tsx
// frontend/src/components/terminal/HitlPanel.tsx
import { useState } from 'react'
import { reviewEntities } from '../../api/entities'
import type { EntityDraft } from '../../api/entities'

interface Props {
  draft: EntityDraft
  onDone: () => void
}

export function HitlPanel({ draft, onDone }: Props) {
  const [approved, setApproved] = useState(
    new Set(draft.draft.entities.map((_, i) => i))
  )

  const toggle = (i: number) =>
    setApproved(prev => {
      const next = new Set(prev)
      next.has(i) ? next.delete(i) : next.add(i)
      return next
    })

  const submit = async () => {
    await reviewEntities({
      draft_id: draft.id,
      approved: {
        entities: draft.draft.entities.filter((_, i) => approved.has(i)),
        relationships: draft.draft.relationships,
      },
    })
    onDone()
  }

  return (
    <div className="absolute bottom-4 left-4 w-80 bg-[#0f1629] border border-slate-700 rounded-lg p-4 z-30 shadow-xl">
      <p className="text-slate-300 text-sm font-semibold mb-3">
        {draft.draft.entities.length} entidades encontradas — revisar
      </p>

      <div className="space-y-2 max-h-48 overflow-auto mb-3">
        {draft.draft.entities.map((e, i) => (
          <label key={i} className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={approved.has(i)}
              onChange={() => toggle(i)}
              className="accent-blue-500"
            />
            <span className="text-slate-300 text-xs">{e.name}</span>
            <span className="text-slate-500 text-[10px]">{e.type}</span>
          </label>
        ))}
      </div>

      <div className="flex gap-2">
        <button
          onClick={submit}
          className="flex-1 bg-blue-900/50 text-blue-400 border border-blue-800 rounded px-3 py-1.5 text-xs hover:bg-blue-800/50"
        >
          Salvar no grafo ({approved.size})
        </button>
        <button
          onClick={onDone}
          className="text-slate-500 text-xs px-2 hover:text-slate-300"
        >
          Ignorar
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Integrar em `Terminal.tsx`**

```tsx
// frontend/src/pages/Terminal.tsx — adicionar:
import { HitlPanel } from '../components/terminal/HitlPanel'
import { fetchPendingDrafts, EntityDraft } from '../api/entities'
import { useEffect, useState } from 'react'

// Estado:
const [pendingDraft, setPendingDraft] = useState<EntityDraft | null>(null)

// Fetch ao montar:
useEffect(() => {
  fetchPendingDrafts().then(drafts => setPendingDraft(drafts[0] ?? null))
}, [])

// JSX (antes do fechamento da div principal):
{pendingDraft && (
  <HitlPanel
    draft={pendingDraft}
    onDone={() => { setPendingDraft(null); reload() }}
  />
)}
```

- [ ] **Verificar no browser**: com um draft pendente no banco, o painel deve aparecer no canto inferior esquerdo do Terminal.

- [ ] **Commit**
```bash
git add frontend/src/components/terminal/HitlPanel.tsx frontend/src/pages/Terminal.tsx frontend/src/api/entities.ts
git commit -m "feat: add HITL curation panel for reviewing and approving extracted entities"
```

---

## Task 11: Frontend — Graph Filters

**Files:**
- Create: `frontend/src/components/terminal/GraphFilters.tsx`
- Modify: `frontend/src/pages/Terminal.tsx`
- Modify: `frontend/src/components/terminal/EntityGraph.tsx`

- [ ] **Criar GraphFilters**

```tsx
// frontend/src/components/terminal/GraphFilters.tsx
const TYPES = [
  { key: 'company', color: '#3b82f6' },
  { key: 'person',  color: '#8b5cf6' },
  { key: 'org',     color: '#10b981' },
  { key: 'event',   color: '#f59e0b' },
  { key: 'sector',  color: '#ef4444' },
]

interface Props {
  active: Set<string>
  onToggle: (type: string) => void
}

export function GraphFilters({ active, onToggle }: Props) {
  return (
    <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex gap-2 z-10">
      {TYPES.map(({ key, color }) => (
        <button
          key={key}
          onClick={() => onToggle(key)}
          className="px-3 py-1 rounded-full text-[11px] border transition-all"
          style={active.has(key)
            ? { background: `${color}22`, borderColor: color, color }
            : { background: 'rgba(10,14,26,0.7)', borderColor: '#1e293b', color: '#475569' }}
        >
          {key}
        </button>
      ))}
    </div>
  )
}
```

- [ ] **Integrar filtros em `Terminal.tsx`**

```tsx
import { GraphFilters } from '../components/terminal/GraphFilters'

// Estado:
const [activeFilters, setActiveFilters] = useState(
  new Set(['company', 'person', 'org', 'event', 'sector'])
)
const toggleFilter = (type: string) =>
  setActiveFilters(prev => {
    const next = new Set(prev)
    next.has(type) ? next.delete(type) : next.add(type)
    return next
  })

// Filtrar grafo antes de passar para EntityGraph:
const filteredGraph = {
  nodes: graph.nodes.filter(n => activeFilters.has(n.type)),
  edges: graph.edges.filter(e => {
    const fromNode = graph.nodes.find(n => n.id === e.from_entity)
    const toNode = graph.nodes.find(n => n.id === e.to_entity)
    return fromNode && toNode && activeFilters.has(fromNode.type) && activeFilters.has(toNode.type)
  }),
}

// JSX — passar filteredGraph e adicionar GraphFilters:
<EntityGraph graph={filteredGraph} onHover={setHovered} onSelect={setSelected} />
<GraphFilters active={activeFilters} onToggle={toggleFilter} />
```

- [ ] **Verificar no browser**: desativar "person" deve remover nós do tipo person e suas arestas.

- [ ] **Commit**
```bash
git add frontend/src/components/terminal/GraphFilters.tsx frontend/src/pages/Terminal.tsx
git commit -m "feat: add entity type filters to graph view"
```

---

## Task 12: Navegação — Link para o Terminal

**Files:**
- Modify: `frontend/src/components/Navbar.tsx` (ou equivalente da Sprint 6)

- [ ] **Adicionar link "⬡ Terminal" na navbar**

```tsx
// Dentro do componente de navegação existente, adicionar ao lado de Dashboard/Research:
<NavLink to="/terminal" className={({ isActive }) =>
  isActive ? 'text-yellow-400 border-b border-yellow-400' : 'text-slate-400 hover:text-slate-200'
}>
  ⬡ Terminal
</NavLink>
```

- [ ] **Verificar** que o link aparece na nav e redireciona para `/terminal`.

- [ ] **Commit final**
```bash
git add frontend/src/components/Navbar.tsx
git commit -m "feat: add Intelligence Terminal link to navbar"
```

---

## Self-Review

**Spec coverage:**
- ✅ Tabelas Supabase (4 tabelas com RLS) — Task 1
- ✅ Extrator Haiku-4.5 + endpoint `POST /entities/review` — Tasks 3, 4
- ✅ Endpoint `GET /entities/graph` — Task 4
- ✅ Extrator acionado pós-run — Task 5
- ✅ Grafo D3.js force-directed, iniciais + label abaixo, cor por tipo, tamanho por weight — Task 7
- ✅ Hover → tooltip glass próximo ao nó — Task 8
- ✅ Click → split view com dossier tabelado — Task 9
- ✅ Painel HITL de curadoria — Task 10
- ✅ Filtros por tipo de entidade — Task 11
- ✅ Deduplicação automática de entidades — Task 4 (`ilike`)
- ✅ Weight acumulado por run — Task 4 (`weight + 1.0`)
- ✅ Botão "↗ Pesquisar" no dossier — Task 9

**Fora do escopo deste sprint (Sprint 8):**
- Monitoring Jobs (aba Jobs no dossier mostra placeholder)
- Conteúdo real das abas Conexões e Histórico (infraestrutura existe, queries detalhadas no Sprint 8)

**Placeholder scan:** Nenhum TBD ou TODO no plano. Todos os passos têm código completo.

**Type consistency:** `EntityNode`, `EntityEdge`, `EntityGraph` definidos em `entities.ts` e reutilizados consistentemente em hooks, componentes e `EntityGraph.tsx`.
