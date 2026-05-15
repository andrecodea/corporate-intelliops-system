# API Contracts

Este documento registra os contratos esperados por sprint. Quando implementar um endpoint, mantenha payload, status code e comportamento compativeis com este arquivo ou atualize o contrato no mesmo PR.

## Contratos existentes no MVP

### `POST /research/stream`

Criado no MVP e preservado por todos os sprints.

Request:

```json
{
  "query": "Research Deel for due diligence...",
  "mode": "Due Diligence"
}
```

Resposta: `text/event-stream`.

Eventos SSE:

| Evento | Payload | Uso |
|---|---|---|
| `token` | texto parcial | Renderizar o relatorio em streaming |
| `tool_call` | JSON com nome/args da tool | Mostrar atividade |
| `tool_result` | JSON/texto resumido | Mostrar resultado de tool |
| `error` | mensagem de erro | Encerrar UI com falha visivel |
| `done` | objeto final ou marcador | Liberar autosave/export |

Regras:

- `mode` desconhecido nao deve quebrar a request; o backend deve rodar com query pura.
- O frontend nao deve depender de eventos fora da lista acima sem atualizar este contrato.
- A porta local padrao e `8005`.

## Sprint 5: Report History

### `POST /reports/save`

Request pre-auth temporario:

```json
{
  "user_id": "local-dev-user",
  "mode": "Due Diligence",
  "company": "Deel",
  "query": "Research Deel...",
  "markdown_content": "# Report..."
}
```

Resposta esperada:

```json
{
  "research_id": "uuid",
  "report_id": "uuid",
  "status": "saved"
}
```

Depois do Sprint 6, `user_id` deve vir do JWT Supabase no header `Authorization: Bearer <token>`.

### `GET /reports`

Query params:

| Param | Obrigatorio | Exemplo |
|---|---|---|
| `user_id` | apenas pre-auth | `local-dev-user` |
| `q` | nao | `notion` |
| `mode` | nao | `Due Diligence` |
| `company` | nao | `Deel` |

Resposta esperada:

```json
{
  "reports": [
    {
      "id": "uuid",
      "research_id": "uuid",
      "mode": "Due Diligence",
      "company": "Deel",
      "created_at": "2026-05-05T12:00:00Z",
      "snippet": "..."
    }
  ]
}
```

## Sprint 7: Intelligence Terminal

### `GET /entities/graph`

Autenticado. Retorna os nos e arestas visiveis para o usuario.

```json
{
  "nodes": [
    {"id": "uuid", "name": "Deel", "type": "company", "weight": 3}
  ],
  "edges": [
    {"source": "uuid", "target": "uuid", "type": "competitor", "weight": 2}
  ]
}
```

### `GET /entities/{entity_id}/dossier`

Autenticado. Retorna o dossier acumulado da entidade.

### `POST /entities/review`

Autenticado. Aprova, edita ou descarta drafts extraidos de um relatorio.

```json
{
  "draft_id": "uuid",
  "actions": [
    {"temp_id": "n1", "action": "approve", "name": "Deel", "type": "company"},
    {"temp_id": "n2", "action": "discard"}
  ]
}
```

## Sprint 8: Monitoring Jobs

### `POST /jobs`

Autenticado. Cria job de monitoramento.

```json
{
  "entity_id": "uuid",
  "mode": "Competitor Intel",
  "frequency": "weekly",
  "notify_slack": true,
  "notify_email": false
}
```

### `GET /jobs`

Autenticado. Lista jobs da entidade ou do usuario.

### `POST /jobs/{job_id}/runs/{run_id}/apply`

Autenticado. Aplica update aprovado ao dossier.

### `POST /jobs/{job_id}/runs/{run_id}/dismiss`

Autenticado. Descarta update sem alterar dossier.

## Sprint 9: Organizations and Sharing

### `POST /orgs/bootstrap`

Autenticado. Cria organizacao inicial do usuario quando ainda nao ha `org_id`.

### `GET /orgs/me`

Autenticado. Retorna org atual, role e membership.

### `POST /reports/{report_id}/share`

Autenticado. Gera ou retorna token publico de compartilhamento.

```json
{
  "shared_url": "http://localhost:5173/shared/token",
  "token": "opaque-token"
}
```

### `GET /shared/{token}`

Publico por decisao do Sprint 9. Retorna apenas o conteudo necessario para visualizacao do relatorio compartilhado.

## Sprint 10: Billing

### `GET /billing/status`

Autenticado. Retorna plano, saldo e proximo reset da org.

### `POST /billing/checkout`

Autenticado. Cria Stripe Checkout Session.

```json
{
  "plan": "starter"
}
```

### `POST /billing/portal`

Autenticado. Cria link para Stripe Customer Portal.

### `POST /stripe/webhook`

Publico, mas protegido por assinatura Stripe. Deve:

- verificar `stripe-signature`;
- deduplicar por `event.id`;
- atualizar plano/creditos de forma idempotente;
- nunca confiar em valores enviados pelo frontend.

## Regras de autenticacao

- Antes do Sprint 6, endpoints de relatorio podem aceitar `user_id` temporario para desenvolvimento.
- A partir do Sprint 6, endpoints privados devem ler usuario pelo JWT Supabase.
- A partir do Sprint 9, endpoints privados devem resolver `org_id` server-side.
- Apenas `/shared/{token}` e `/stripe/webhook` sao publicos por design.
