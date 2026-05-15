# Sprint 3 — Evals: Guia Instrucional

## Contexto e Objetivo

O Sprint 3 responde a uma pergunta que a maioria dos projetos de IA ignora até ser tarde: **"como sei que o agente está performando bem?"**

Sem evals, cada mudança de prompt é uma aposta no escuro. Com evals, você tem uma linha de base — um número que sobe ou desce quando você muda algo. Esse número é o que transforma "acho que melhorou" em "melhorou 18%".

O padrão usado aqui é **LLM-as-Judge**: em vez de humanos avaliarem cada relatório (lento, caro, subjetivo), você usa um LLM separado como avaliador. Esse avaliador lê o relatório gerado e pontua contra critérios objetivos.

---

## Pré-requisitos para rodar sozinho

- API FastAPI rodando em `http://localhost:8005`: `uv run uvicorn backend.api:app --reload --port 8005`.
- `RESEARCH_API_URL=http://localhost:8005/research/stream` definido no ambiente quando usar o runner SSE.
- Pelo menos uma chave LLM configurada: `ANTHROPIC_API_KEY` ou `OPENAI_API_KEY`.
- `TAVILY_API_KEY` configurada, porque os evals devem medir pesquisa real.
- Baseline do Sprint 1 salva em `tests/runs/` ou uma rodada manual recente para comparação.

**Critério de autonomia:** se o runner falhar, você deve conseguir saber se a falha veio de API desligada, env var ausente, judge inválido ou relatório ruim. Por isso cada resultado salvo precisa incluir `case_id`, `mode`, `query`, `report`, `scores`, `error` e timestamp.

---

## Arquitetura do Sistema de Evals

```
tests/evals/
├── run_evals.py          # Script principal — roda todas as queries e coleta scores
├── judge.py              # Lógica do LLM-as-Judge
├── queries/              # Queries fixas por modo (o "test set")
│   ├── due_diligence.json
│   ├── competitor_intel.json
│   └── ...
└── results/              # Resultados salvos por data
    ├── 2026-04-01/
    │   └── due_diligence_score.json
    └── ...
```

---

## Task 1: `tests/evals/test_set.json` - Definir o Test Set (queries fixas)

**Estimativa:** ~30min

**O que é e por que existe**

O test set é o que torna a avaliação reproduzível. Queries fixas para empresas conhecidas permitem comparar scores diretamente antes e depois de mudanças de prompt.

**Files:**
- Criar/Editar: `tests/evals/queries/{modo}.json` (um arquivo por modo)

---

### Conceito: Test set com empresas conhecidas — cobertura ampla elimina ruído de dados
> Com empresas obscuras, um score baixo pode ser "o agente não sabe pesquisar" OU "não há dados públicos sobre essa empresa". Impossível distinguir. Com Notion ou Brex, qualquer score baixo é culpa do agente.
>
> | Tipo de empresa no test set | O que um score baixo significa |
> |---|---|
> | Empresa obscura (startup XYZ) | Agente fraco OU ausência de dados — ambíguo |
> | Empresa conhecida (Notion, Brex) | Agente fraco — conclusão inequívoca |

---

### Documentação
- https://docs.python.org/3/library/json.html - referencia para `json.dumps` e `json.loads`.
- `tests/run_agent.py` — ver como as queries são enviadas para o agente (formato de referência).

---

### O que você precisa fazer

1. Crie o diretório `tests/evals/queries/`.
2. Para cada modo do Sprint 1, crie um arquivo JSON com 2 queries (empresas diferentes).
3. Inclua: `id`, `query` (gerada por `build_query()` para uma empresa conhecida), `mode`, `expected_sections`.
4. `expected_sections` deve corresponder às seções definidas no `Report Structure` do prompt do modo.

### Esqueleto

```json
[
  {
    "id": "modo_001",
    "query": "TODO: copiar a query gerada por build_query() para uma empresa conhecida (Notion, Brex, Figma)",
    "mode": "Nome do Modo",
    "expected_sections": ["TODO: listar seções do Report Structure do prompt"]
  },
  {
    "id": "modo_002",
    "query": "TODO: segunda empresa diferente da primeira",
    "mode": "Nome do Modo",
    "expected_sections": ["mesmas seções do Report Structure"]
  }
]
```

<details>
<summary>Ver solução completa</summary>

O test set é o que torna a avaliação **reproduzível**. Se você mudar o prompt do Due Diligence e rodar a mesma query de antes, pode comparar os scores diretamente.

Crie `tests/evals/queries/due_diligence.json`:

```json
[
  {
    "id": "dd_001",
    "query": "Due diligence research on Notion operating in the Productivity / B2B SaaS sector. Context: Investment evaluation. Deliverables: risk assessment, financial signals, reputation and legal flags, leadership background, and any red flags relevant to the deal type.",
    "mode": "Due Diligence",
    "expected_sections": ["Executive Summary", "Financial Signals", "Legal", "Risk Summary", "Sources"]
  },
  {
    "id": "dd_002",
    "query": "Due diligence research on Brex operating in the Fintech / Corporate Cards sector. Context: M&A evaluation. Deliverables: risk assessment, financial signals, reputation and legal flags, leadership background, and any red flags relevant to the deal type.",
    "mode": "Due Diligence",
    "expected_sections": ["Executive Summary", "Financial Signals", "Legal", "Risk Summary", "Sources"]
  }
]
```

> **Por que empresas reais e conhecidas no test set?**
> Empresas como Notion, Brex, e Figma têm cobertura pública ampla. Se o agente não conseguir encontrar informações sobre elas, o problema é o agente — não a ausência de dados. Empresas obscuras introduzem ruído na avaliação.

> **Por que salvar o `expected_sections`?**
> Uma das métricas mais simples e confiáveis é cobertura de seções: o relatório tem todas as seções que o modo exige? Se o prompt manda gerar "Risk Summary" e o relatório não tem, o score cai automaticamente.

---

</details>

- [ ] **Step 1.1: Diretório `tests/evals/queries/` criado com um arquivo por modo do Sprint 1.**
- [ ] **Step 1.2: Cada arquivo tem 2+ queries com campos `id`, `query`, `mode`, `expected_sections`.**
- [ ] **Step 1.3: Todas as queries usam empresas com cobertura pública ampla (Notion, Brex, Figma, Stripe).**
- [ ] **Step 1.4: `expected_sections` corresponde às seções do `Report Structure` do prompt de cada modo.**

### Resumo
> *Preencher apos concluir a task: o que foi alterado, qual verificacao passou, e qual risco ainda merece atencao?*

---
## Task 2: `tests/evals/judge.py` - O Judge (avaliador LLM)

**Estimativa:** ~1h

**O que é e por que existe**

O judge avalia relatórios gerados sem modificar o pipeline de produção. Usa Haiku (não Sonnet) para minimizar custo em volume — a avaliação é uma task estruturada, não requer raciocínio profundo.

**Files:**
- Criar/Editar: `tests/evals/judge.py`

---

### Conceito: LLM-as-Judge como Observer — avalia sem contaminar o pipeline de produção
> O judge lê o output do agente e retorna scores estruturados. Zero mudanças no pipeline. É o mesmo padrão do `UsageTracker` em `tests/run_agent.py`. Usar Haiku para o judge e Sonnet para gerar evita viés de auto-avaliação.
>
> | Escolha | Por que |
> |---|---|
> | Haiku como judge | 10× mais barato; task estruturada não requer raciocínio profundo |
> | JSON com 4 scores | Scores comparáveis entre runs; sem parsing manual de texto livre |
> | Truncar a 8000 chars | Custo reduzido sem perda de precisão — seções aparecem no início do relatório |

---

### Documentação
- https://docs.anthropic.com/en/api/messages - referencia para `client.messages.create`.
- https://docs.python.org/3/library/json.html - referencia para `json.loads` com tratamento de exceção.

---

### O que você precisa fazer

1. Crie `judge.py` com a função `judge_report(report: str, expected_sections: list[str]) -> dict`.
2. Implemente o prompt com os 4 critérios: Factual Specificity, Section Coverage, Citation Quality, Actionability (cada 0-25).
3. Use `claude-haiku-4-5-20251001` — não Sonnet.
4. Adicione `except json.JSONDecodeError` — se o LLM não retornar JSON válido, retorne `{"total_score": 0}` sem lançar exceção.

### Esqueleto

```python
def judge_report(report: str, expected_sections: list[str]) -> dict:
    # TODO: montar JUDGE_PROMPT com {expected_sections} e {report[:8000]}
    # TODO: client.messages.create com claude-haiku-4-5-20251001
    # TODO: json.loads(message.content[0].text)
    # TODO: except json.JSONDecodeError: return {"total_score": 0, "rationale": str(e)}
    pass
```

<details>
<summary>Ver solução completa</summary>

Crie `tests/evals/judge.py`:

```python
"""LLM-as-Judge para avaliar qualidade dos relatórios de inteligência.

O judge recebe um relatório gerado e retorna um score de 0-100 com justificativa.
Usa um LLM separado do agente para evitar viés de auto-avaliação.
"""
import os
import json
from anthropic import Anthropic

client = Anthropic()

JUDGE_PROMPT = """You are an expert evaluator of corporate intelligence reports.
Score the following report from 0 to 100 based on these criteria:

1. **Factual Specificity** (0-25): Does the report cite specific data points
   (numbers, dates, names) rather than vague generalizations?
2. **Section Coverage** (0-25): Are all required sections present and substantive?
   Required sections: {expected_sections}
3. **Citation Quality** (0-25): Are sources cited with URLs? Are they credible
   (not just Wikipedia or generic news)?
4. **Actionability** (0-25): Does the report give the reader something concrete
   to act on? Or is it just a neutral summary?

Return a JSON object with this exact structure:
{{
  "total_score": <int 0-100>,
  "factual_specificity": <int 0-25>,
  "section_coverage": <int 0-25>,
  "citation_quality": <int 0-25>,
  "actionability": <int 0-25>,
  "rationale": "<one paragraph explaining the scores>"
}}

REPORT TO EVALUATE:
---
{report}
---"""


def judge_report(report: str, expected_sections: list[str]) -> dict:
    """
    Avalia um relatório usando o LLM como juiz.

    Args:
        report: conteúdo do relatório em Markdown
        expected_sections: seções que devem estar presentes

    Returns:
        dict com scores e justificativa
    """
    prompt = JUDGE_PROMPT.format(
        expected_sections=", ".join(expected_sections),
        report=report[:8000],  # trunca para evitar context overflow no judge
    )

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",  # modelo mais barato para avaliação em volume
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    try:
        return json.loads(message.content[0].text)
    except json.JSONDecodeError:
        # Se o LLM não retornou JSON válido, retorna score zero com erro
        return {
            "total_score": 0,
            "rationale": f"Judge failed to return valid JSON: {message.content[0].text[:200]}"
        }
```

> **Por que usar `claude-haiku-4-5-20251001` para o judge?**
> O judge roda em volume — uma query por modo, potencialmente múltiplas vezes por semana. Haiku é 10× mais barato que Sonnet e suficiente para avaliação estruturada. Reserve o Sonnet para gerar os relatórios.

> **Por que truncar o relatório para 8000 chars?**
> Relatórios longos não precisam ser lidos na íntegra para ser avaliados. O judge precisa verificar seções, especificidade, e citações — tudo isso aparece na primeira metade do relatório. Truncar reduz custo sem perder precisão na avaliação.

> **Padrão de design: Observer**
> O judge é um Observer não-intrusivo: ele lê o output do agente sem modificar o pipeline. Esse é o mesmo padrão do `UsageTracker` em `tests/run_agent.py` — zero mudanças no código de produção.

---

</details>

- [ ] **Step 2.1: `judge_report(report, ["Sources"])` retorna dict com `total_score` e 4 dimensões.**
- [ ] **Step 2.2: Output inválido do LLM retorna `{"total_score": 0}` sem lançar exceção.**
- [ ] **Step 2.3: Judge usa `claude-haiku-4-5-20251001`, não Sonnet.**
- [ ] **Step 2.4: Prompt do judge inclui os 4 critérios com peso 0-25 cada.**

### Resumo
> *Preencher apos concluir a task: o que foi alterado, qual verificacao passou, e qual risco ainda merece atencao?*

---
## Task 3: `tests/evals/run_evals.py` - O Script Principal de Evals

**Estimativa:** ~45min

**O que é e por que existe**

Este script orquestra queries → scoring → salvamento. Salvar em `results/{data}/` garante que cada run é um snapshot histórico imutável, comparável com runs anteriores.

**Files:**
- Criar/Editar: `tests/evals/run_evals.py`

---

### Conceito: Resultados por data — baseline imutável, runs comparáveis por período
> Sobrescrever o mesmo arquivo apagaria evidência de regressão. `results/{data}/` torna cada run imutável. A `baseline/` copiada depois da primeira run é o ponto de comparação fixo para todas as mudanças futuras.
>
> | Estrutura de output | Consequência |
> |---|---|
> | Arquivo único sobrescrito | Perde histórico; impossível detectar regressão |
> | `results/{data}/{modo}_score.json` | Cada run é imutável; comparação por data |
> | `baseline/` copiada do primeiro run | Referência fixa para comparações futuras |

---

### Documentação
- https://docs.python.org/3/library/datetime.html - referencia para `datetime.now().strftime("%Y-%m-%d")`.
- https://docs.python.org/3/library/pathlib.html - referencia para `Path.mkdir(parents=True, exist_ok=True)`.

---

### O que você precisa fazer

1. Crie `run_evals.py` com funções `run_query(query, mode)`, `run_eval_for_mode(mode_key)`, e `save_results(results, mode_key)`.
2. `save_results` cria `results/{data}/` com `mkdir(parents=True, exist_ok=True)`.
3. Suporte `--mode due_diligence` via `argparse` para rodar apenas um modo durante desenvolvimento.
4. Após a primeira run completa, copie para `tests/evals/baseline/` manualmente.

### Esqueleto

```python
def save_results(results: list[dict], mode_key: str):
    # TODO: date_str = datetime.now().strftime("%Y-%m-%d")
    # TODO: output_dir = RESULTS_DIR / date_str
    # TODO: output_dir.mkdir(parents=True, exist_ok=True)
    # TODO: salvar JSON em output_dir / f"{mode_key}_score.json"
    pass

if __name__ == "__main__":
    # TODO: argparse com --mode opcional
    # TODO: loop por modos selecionados: run_eval_for_mode → save_results
    pass
```

<details>
<summary>Ver solução completa</summary>

Crie `tests/evals/run_evals.py`:

```python
"""
Roda evals para todos os modos e salva resultados em tests/evals/results/.

Uso:
    python tests/evals/run_evals.py
    python tests/evals/run_evals.py --mode due_diligence  # apenas um modo
"""
import argparse
import json
import httpx
import os
from datetime import datetime
from pathlib import Path
from httpx_sse import connect_sse

from judge import judge_report  # importa o judge do mesmo diretório

API_URL = os.getenv("RESEARCH_API_URL", "http://localhost:8005/research/stream")
QUERIES_DIR = Path(__file__).parent / "queries"
RESULTS_DIR = Path(__file__).parent / "results"

MODE_FILES = {
    "due_diligence": "Due Diligence",
    "competitor_intel": "Competitor Intel",
    "vendor_evaluation": "Vendor Evaluation",
    "sales_intel": "Sales Intel",
    # adicionar novos modos aqui à medida que são criados no Sprint 2
}


def run_query(query: str, mode: str) -> str:
    """Roda uma query no agente via SSE e retorna o relatório completo."""
    report = ""
    with httpx.Client(timeout=300) as client:
        with connect_sse(client, "POST", API_URL, json={"query": query, "mode": mode}) as source:
            for event in source.iter_sse():
                if event.event == "token":
                    try:
                        data = json.loads(event.data)
                        report += data.get("content", "")
                    except json.JSONDecodeError:
                        pass
                elif event.event == "done":
                    break
    return report


def run_eval_for_mode(mode_key: str) -> list[dict]:
    """Roda todas as queries de um modo e retorna os resultados."""
    queries_file = QUERIES_DIR / f"{mode_key}.json"
    if not queries_file.exists():
        print(f"[SKIP] No queries file for mode: {mode_key}")
        return []

    queries = json.loads(queries_file.read_text())
    mode_name = MODE_FILES[mode_key]
    results = []

    for q in queries:
        print(f"[RUN] {q['id']} — {q['query'][:60]}...")
        report = run_query(q["query"], mode_name)
        score = judge_report(report, q.get("expected_sections", []))
        results.append({
            "query_id": q["id"],
            "mode": mode_name,
            "score": score,
            "report_length": len(report),
        })
        print(f"       Score: {score.get('total_score', 0)}/100")

    return results


def save_results(results: list[dict], mode_key: str):
    """Salva resultados em tests/evals/results/{data}/{modo}_score.json"""
    date_str = datetime.now().strftime("%Y-%m-%d")
    output_dir = RESULTS_DIR / date_str
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"{mode_key}_score.json"
    output_file.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"[SAVED] {output_file}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", help="Rodar apenas este modo (ex: due_diligence)")
    args = parser.parse_args()

    modes_to_run = [args.mode] if args.mode else list(MODE_FILES.keys())

    for mode_key in modes_to_run:
        print(f"\n=== Eval: {mode_key} ===")
        results = run_eval_for_mode(mode_key)
        if results:
            save_results(results, mode_key)


if __name__ == "__main__":
    main()
```

---

</details>

- [ ] **Step 3.1: `run_evals.py --mode due_diligence` roda uma query e cria arquivo de resultado.**
- [ ] **Step 3.2: Arquivo salvo em `tests/evals/results/{data}/due_diligence_score.json`.**
- [ ] **Step 3.3: Run sem `--mode` processa todos os modos com arquivo de queries.**
- [ ] **Step 3.4: Baseline copiada em `tests/evals/baseline/` após a primeira run completa.**

### Resumo
> *Preencher apos concluir a task: o que foi alterado, qual verificacao passou, e qual risco ainda merece atencao?*

---
## Task 4: `backend/prompts/modes/*.md` - Interpretar os Resultados

**Estimativa:** ~30min

**O que é e por que existe**

Esta task não cria código — usa os scores gerados para diagnosticar onde os prompts precisam de ajuste. Cada dimensão do score aponta para um artefato específico.

**Files:**
- Criar/Editar: `backend/prompts/modes/*.md` (ajustes conforme scores)

---

### Conceito: Score baixo aponta onde ajustar — cada dimensão mapeia para um artefato específico
> O judge retorna 4 scores independentes. Cada um revela onde está o problema — não é necessário adivinhar qual parte do prompt está falhando.
>
> | Score baixo em | Causa provável | Onde ajustar |
> |---|---|---|
> | Factual Specificity | Agente generalizando | Termos de busca concretos no Search Strategy |
> | Section Coverage | Seções faltando | Tornar seções mais explícitas no Report Structure |
> | Citation Quality | Fontes fracas | Adicionar "prefer primary sources" no Search Strategy |
> | Actionability | Relatório neutro demais | Adicionar "help the reader make a decision" no tom do prompt |

---

### Documentação
- `tests/evals/results/` - localizar os arquivos de resultado para leitura.
- "Critérios de Qualidade por Modo" (seção na solução completa abaixo) — scores mínimos aceitáveis por modo.

---

### O que você precisa fazer

1. Rode `python tests/evals/run_evals.py` para todos os 4 modos do Sprint 1.
2. Abra os arquivos de resultado e identifique qual dimensão está mais baixa por modo.
3. Para cada dimensão abaixo do mínimo aceitável (total < 70/100), ajuste o artefato correspondente.
4. Re-rode o eval após cada ajuste e confirme que o score melhorou.

### Esqueleto

```bash
# TODO: rodar evals para todos os modos
python tests/evals/run_evals.py

# TODO: abrir results/{data}/ e ler cada arquivo de score
# Se total_score < 70: identificar dimensão mais baixa e ajustar o artefato
# Factual Specificity baixo → editar Search Strategy em backend/prompts/modes/{modo}.md
# Section Coverage baixo → tornar seções mais explícitas no Report Structure
# Após ajuste: re-rodar o eval e comparar scores
```

<details>
<summary>Ver solução completa</summary>

### Lendo um arquivo de resultado

```json
[
  {
    "query_id": "dd_001",
    "mode": "Due Diligence",
    "score": {
      "total_score": 74,
      "factual_specificity": 18,
      "section_coverage": 22,
      "citation_quality": 17,
      "actionability": 17,
      "rationale": "The report covers all required sections and cites
                    specific funding rounds. Citation quality is limited
                    by reliance on generic news sources rather than
                    primary documents. Actionability is moderate —
                    the risk summary is clear but lacks prioritization."
    },
    "report_length": 4821
  }
]
```

### Como usar os scores para melhorar prompts

| Score baixo em... | Causa provável | Onde ajustar |
|---|---|---|
| Factual Specificity | Agente está generalizando em vez de buscar dados | `search_depth` no `tavily_search` ou adicionar termos de busca específicos no prompt do modo |
| Section Coverage | Agente está omitindo seções | Tornar as seções mais explícitas no prompt; adicionar `REQUIRED: include this section even if empty` |
| Citation Quality | Agente cita fontes fracas | Adicionar no Search Strategy do prompt: "prefer primary sources: regulatory filings, official press releases, analyst reports" |
| Actionability | Relatório é neutro demais | Adicionar ao prompt: "your job is not to summarize — it is to help the reader make a decision" |

### Estabelecendo a baseline

Depois de rodar os evals pela primeira vez (antes de qualquer ajuste de prompt), salve esse resultado como a baseline oficial:

```bash
cp tests/evals/results/2026-04-01/ tests/evals/baseline/
```

A partir daí, todo ajuste de prompt é comparado contra a baseline. Se o score do Due Diligence cair de 74 para 62 depois de uma mudança, você sabe que o ajuste piorou o modo.

---

## Critérios de Qualidade por Modo

### Due Diligence
| Critério | Score mínimo aceitável |
|---|---|
| Factual Specificity | ≥ 18/25 |
| Section Coverage | ≥ 20/25 |
| Citation Quality | ≥ 15/25 |
| Actionability | ≥ 15/25 |
| **Total** | **≥ 70/100** |

### Competitor Intel
| Critério | Score mínimo aceitável |
|---|---|
| Factual Specificity | ≥ 20/25 (comparações precisam ser concretas) |
| Section Coverage | ≥ 20/25 |
| Citation Quality | ≥ 15/25 |
| Actionability | ≥ 18/25 (deve identificar exploitable weaknesses) |
| **Total** | **≥ 73/100** |

### Sales Intel
| Critério | Score mínimo aceitável |
|---|---|
| Factual Specificity | ≥ 16/25 |
| Section Coverage | ≥ 22/25 (deve sempre ter tech stack e decision-makers) |
| Citation Quality | ≥ 12/25 |
| Actionability | ≥ 20/25 (conversation hooks são o core deliverable) |
| **Total** | **≥ 70/100** |

---

## Armadilhas do LLM-as-Judge

**O judge também pode errar.** Se o judge usa o mesmo modelo que o agente, há risco de viés de confirmação — o modelo tende a achar bom o que ele próprio produziria. Use um modelo diferente (Haiku para julgar, Sonnet para gerar) ou varie os critérios de avaliação.

**Não confunda score alto com relatório correto.** O judge avalia estrutura e especificidade — mas não verifica se os fatos são verdadeiros. Um relatório pode ter score 90/100 e citar números errados. Para verificação factual, você ainda precisa de revisão humana amostral.

**O test set não pode ser público.** Se as queries de teste forem muito similares às usadas durante o desenvolvimento de prompts, você está overfitting o prompt para o test set. Separe: use algumas queries para desenvolvimento de prompt, outras para eval final.

---

</details>

- [ ] **Step 4.1: Evals rodados para os 4 modos do Sprint 1 com scores salvos em `results/`.**
- [ ] **Step 4.2: Nenhum modo com `total_score` abaixo de 70/100.**
- [ ] **Step 4.3: Para cada ajuste de prompt, re-eval confirma que o score melhorou (não caiu).**
- [ ] **Step 4.4: Baseline salva em `tests/evals/baseline/` como snapshot imutável.**

### Resumo
> *Preencher apos concluir a task: o que foi alterado, qual verificacao passou, e qual risco ainda merece atencao?*

---

## Resumo do Sprint 3

| Artefato | Localização | O que faz |
|---|---|---|
| Test set por modo | `tests/evals/queries/*.json` | Queries fixas e reproduzíveis |
| LLM Judge | `tests/evals/judge.py` | Pontua relatórios contra critérios objetivos |
| Script de eval | `tests/evals/run_evals.py` | Orquestra queries + scoring + salvamento |
| Resultados | `tests/evals/results/YYYY-MM-DD/` | Histórico de performance por modo e data |
| Baseline | `tests/evals/baseline/` | Referência para comparar mudanças futuras |

**Critério de conclusão do Sprint:** baseline estabelecida para todos os modos do Sprint 1 e Sprint 2, com scores salvos em `tests/evals/baseline/`. Nenhum modo abaixo de 70/100 no total.

## Solo Developer Ready

- [ ] API FastAPI esta rodando em `http://localhost:8005`.
- [ ] `RESEARCH_API_URL=http://localhost:8005/research/stream` foi definido quando necessario.
- [ ] O runner diferencia erro de API, env var ausente, judge invalido e relatorio ruim.
- [ ] Baseline foi salva com `case_id`, `mode`, `query`, `report`, `scores`, `error` e timestamp.
- [ ] Sei quais prompts precisam ajuste a partir dos scores.
