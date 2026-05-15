# Sprint 2 — New Intelligence Modes: Guia Instrucional

## Contexto e Objetivo

O Sprint 2 expande o produto de 4 para 11 modos de inteligência. O valor do sprint está em entender o **padrão de extensão** — cada modo novo segue exatamente a mesma estrutura, e compreender esse padrão é o que permite adicionar modos sem introduzir bugs ou regressions.

---

## A Anatomia de um Modo

Cada modo é composto de **3 artefatos interdependentes**. A tabela abaixo mostra os 4 modos existentes como referência:

| Artefato | Localização | Responsabilidade |
|---|---|---|
| Prompt de modo | `backend/prompts/modes/{modo}.md` | Instrui o agente sobre o que pesquisar e como estruturar o relatório |
| Formulário de entrada | `frontend/app/pages/research.py` | Coleta as variáveis específicas do modo do usuário |
| Função de query | `build_query()` em `research.py` | Monta o prompt final combinando os campos do formulário |
| Registro do modo | `MODE_FILES` em `backend/api.py` | Permite que a API carregue o prompt correto por nome |

Se você adicionar o prompt mas esquecer de registrar em `MODE_FILES`, a API vai ignorar o prompt e passar a query sem instrução de modo. Silenciosamente — sem erro.

---

## Padrões de Design Envolvidos

### Template Method (o mais importante aqui)

O prompt de cada modo é um **template** que define a *estrutura* do relatório: seções obrigatórias, prioridades de pesquisa, estratégia de busca. O conteúdo específico (empresa, setor, critérios) é preenchido pela query do usuário em tempo de execução.

```
[prompt do modo em prompts/modes/]  ← Template (estrutura fixa)
         +
[query montada por build_query()]   ← Dados específicos da requisição
         ↓
[relatório gerado pelo agente]      ← Output do template preenchido
```

O Template Method é aplicado em dois níveis:
1. **Estrutura do relatório** — o prompt define as seções e ordem
2. **Estratégia de busca** — o prompt diz quais termos combinar, quais fontes priorizar

### Per-request Prompt Injection (`api.py::_load_mode_prompt`)

O prompt do modo **não** faz parte do system prompt do agente. Ele é injetado na mensagem do usuário em tempo de requisição:

```python
# api.py, linha 56
full_query = f"{mode_prompt}\n\n---\n\n{request.query}" if mode_prompt else request.query
```

**Por que não está no system prompt?** O `build_agent()` roda uma vez no startup. Colocar o modo no system prompt exigiria reconstruir o agente a cada requisição. Ao colocar no user message, o agente permanece stateless entre requisições e o sistema escala sem custo.

---

## Guia de Implementação: Adicionando um Modo Novo

Vamos usar **Market Mapping** como exemplo completo. Os outros 6 seguem o mesmo padrão.

## Matriz completa dos modos novos

Use esta tabela como contrato para implementar todos os modos sem inventar nomes no meio do caminho. O nome em `MODE_FILES`, o label no `MODES` do frontend e o valor usado em `build_query()` devem ser idênticos.

| Modo | Arquivo de prompt | Campos obrigatórios | Campos opcionais | Deliverable mínimo em `build_query()` |
|---|---|---|---|---|
| Market Mapping | `market_mapping.md` | `sector` | `geography`, `customer_segment`, `focus` | player landscape, market segmentation, competitive dynamics, white space |
| Leadership Intel | `leadership_intel.md` | `person_or_company` | `role`, `focus` | executive profile, track record, connections, public statements |
| Funding & Deal Intelligence | `funding_deal_intelligence.md` | `company` | `deal_type`, `focus` | funding history, deal signals, investors/acquirers, strategic implications |
| Risk Assessment | `risk_assessment.md` | `target`, `risk_dimensions` | `sector`, `focus` | multidimensional risk scorecard with evidence |
| Regulatory Watch | `regulatory_watch.md` | `sector`, `jurisdiction` | `time_horizon`, `focus` | regulatory changes, affected players, impact assessment |
| Talent Signal | `talent_signal.md` | `company` | `period`, `focus` | hiring patterns, role clusters, strategic inference |
| Partnership & Ecosystem Mapping | `partnership_ecosystem_mapping.md` | `company` | `partnership_type`, `focus` | partner map, integrations, ecosystem strategy |

**Verificação por modo:** depois de adicionar cada modo, rode uma pesquisa manual no Streamlit e confirme três coisas: o modo aparece no radio, o payload enviado para `/research/stream` contém `mode` com o mesmo nome registrado em `MODE_FILES`, e o relatório contém as seções exigidas pelo prompt.

## Task 1: `backend/prompts/modes/{mode}.md` - Criar o prompt do modo

**Estimativa:** ~20min

**O que é e por que existe**

O prompt de cada modo instrui o agente sobre o que pesquisar, como pesquisar, e como estruturar o output. Sem essas 3 seções, o relatório será genérico ou incompleto em alguma dimensão.

**Files:**
- Criar/Editar: `backend/prompts/modes/{mode}.md`

---

### Conceito: Prompt como Template em 3 seções obrigatórias
> Cada seção tem uma responsabilidade distinta. Se uma for vaga, o relatório será vago nessa mesma dimensão — o agente não inventa instruções que estão faltando.
>
> | Seção | Define | Consequência se vaga |
> |---|---|---|
> | Research Priorities | O que o agente deve encontrar | Relatório genérico sem dados específicos |
> | Search Strategy | Termos de busca e fontes preferidas | Agente usa termos genéricos; resultados rasos |
> | Report Structure | Seções e ordem de output | Seções faltando; score de Section Coverage cai |

---

### Documentação
- https://docs.anthropic.com/en/prompt-library - exemplos de prompts estruturados para referência.
- `backend/prompts/modes/due_diligence.md` - template de referência com as 3 seções.

---

### O que você precisa fazer

1. Abra `backend/prompts/modes/due_diligence.md` como referência das 3 seções obrigatórias.
2. Crie o arquivo do novo modo com as 3 seções preenchidas de forma específica.
3. Preencha termos de busca concretos no Search Strategy — não deixe genérico.
4. Rode `python tests/run_agent.py "query do novo modo"` para validar o output antes de registrar em `MODE_FILES`.

### Esqueleto

```markdown
## Intelligence Mode: {NomeDoModo}

### Research Priorities
# TODO: listar 3-5 prioridades de pesquisa específicas para este modo

### Search Strategy
# TODO: listar termos de busca específicos (ex: "nome + funding", "nome + market share")
# TODO: listar fontes preferidas (ex: Crunchbase, SEC filings, analyst reports)

### Report Structure
# TODO: listar seções em ordem com descrição de uma linha cada
1. **Seção 1** — o que inclui
2. **Sources**
```

<details>
<summary>Ver solução completa</summary>

Crie `backend/prompts/modes/market_mapping.md`:

```markdown
## Intelligence Mode: Market Mapping

You are conducting a market mapping analysis. The objective is to produce a
structured view of a sector: who the major players are, how the market is
segmented, and where the competitive white spaces are.

### Research Priorities

- **Market size & growth**: TAM estimates, growth rates, analyst projections
- **Player landscape**: tier-1 (dominant), tier-2 (challengers), tier-3 (niche)
- **Segmentation**: by geography, customer size, use case, or delivery model
- **Competitive dynamics**: consolidation trends, M&A activity, new entrants
- **Positioning map**: how players differentiate (price, product depth, segment focus)

### Search Strategy

Search for the sector name combined with: "market size", "market share",
"competitive landscape", "top players", "market map", "industry report".
Prefer analyst reports (Gartner, Forrester, IDC, G2) and sector-specific
publications.

### Report Structure

1. **Market Overview** — size, growth rate, key drivers
2. **Player Landscape** — tiered table: player, segment, differentiator, size signal
3. **Market Segmentation** — how the market splits by customer type or use case
4. **Competitive Dynamics** — consolidation, M&A, new entrants
5. **White Space Analysis** — underserved segments or positioning gaps
6. **Sources**
```

> **Dica de qualidade de prompt:** as 3 seções (`Research Priorities`, `Search Strategy`, `Report Structure`) correspondem a *o quê pesquisar*, *como pesquisar*, e *como estruturar o output*. Se uma dessas seções for vaga, o relatório vai ser vago nessa dimensão. Se o Search Strategy não listar termos de busca específicos, o agente vai usar termos genéricos e obter resultados rasos.

</details>

- [ ] **Step 1.1: Arquivo `backend/prompts/modes/{modo}.md` criado com as 3 seções obrigatórias.**
- [ ] **Step 1.2: Search Strategy tem termos de busca específicos (não apenas "pesquise sobre X").**
- [ ] **Step 1.3: `python tests/run_agent.py "query do novo modo"` gera relatório sem erros de API.**
- [ ] **Step 1.4: Relatório gerado contém as seções definidas no Report Structure.**

### Resumo
> *Preencher apos concluir a task: o que foi alterado, qual verificacao passou, e qual risco ainda merece atencao?*

---
## Task 2: `backend/api.py` - Registrar o modo em `api.py`

**Estimativa:** ~15min

**O que é e por que existe**

O dict `MODE_FILES` em `api.py` é a tabela de lookup que conecta o nome do modo (enviado pelo frontend) ao arquivo de prompt no disco. Sem essa entrada, o agente roda sem instrução de modo — sem erro, mas sem relatório estruturado.

**Files:**
- Criar/Editar: `backend/api.py`

---

### Conceito: Contrato de nome — string em MODE_FILES deve ser idêntica ao que o frontend envia
> `_load_mode_prompt(mode)` faz lookup por string exata. Se o frontend envia `"Market Mapping"` mas o dict tem `"market_mapping"`, o lookup retorna `None` silenciosamente. Nenhuma exceção é levantada — degradação graceful, mas invisível.
>
> | Cenário | Resultado |
> |---|---|
> | Nome idêntico em ambos | Prompt carregado, relatório estruturado |
> | Typo ou case diferente | `mode_prompt = None`, relatório sem instrução de modo |

---

### Documentação
- `backend/api.py` linhas com `MODE_FILES` - localizar o dict para adicionar a entrada.
- https://docs.python.org/3/library/pathlib.html - referencia para `Path` usado como valor no dict.

---

### O que você precisa fazer

1. Abra `backend/api.py` e localize o dict `MODE_FILES`.
2. Adicione a entrada: `"NomeDoModo": MODES_DIR / "nome_do_arquivo.md"`.
3. Confirme que a string é idêntica ao label no dict `MODES` do frontend.
4. Suba a API e confirme que `POST /research/stream` com o novo modo não retorna 422.

### Esqueleto

```python
MODE_FILES = {
    # modos existentes...
    # TODO: adicionar "{NomeDoModo}": MODES_DIR / "{arquivo_do_modo}.md"
    # ATENÇÃO: a string deve ser idêntica ao label no dict MODES do frontend
}
```

<details>
<summary>Ver solução completa</summary>

```python
# backend/api.py — adicionar em MODE_FILES
MODE_FILES = {
    "Due Diligence": MODES_DIR / "due_diligence.md",
    "Competitor Intel": MODES_DIR / "competitor_intel.md",
    "Vendor Evaluation": MODES_DIR / "vendor_evaluation.md",
    "Sales Intel": MODES_DIR / "sales_intel.md",
    "Market Mapping": MODES_DIR / "market_mapping.md",      # novo
    "Leadership Intel": MODES_DIR / "leadership_intel.md",  # novo
    # ... demais modos
}
```

> **Por que um dict com string → Path?** A string é o nome que o frontend envia no campo `mode` do JSON. O Path é onde o arquivo está no disco. A função `_load_mode_prompt` faz o lookup em O(1). Se você digitar o nome errado no dict, a API retorna prompt vazio silenciosamente — não é um erro, é degradação graceful (o agente ainda funciona, só sem instrução de modo).

</details>

- [ ] **Step 2.1: Entrada adicionada em `MODE_FILES` com nome idêntico ao label no frontend.**
- [ ] **Step 2.2: `POST /research/stream` com `"mode": "{NomeDoModo}"` não retorna erro 422.**
- [ ] **Step 2.3: Relatório gerado com o novo modo contém seções estruturadas (não apenas texto genérico).**
- [ ] **Step 2.4: Todos os 7 novos modos registrados em `MODE_FILES`.**

### Resumo
> *Preencher apos concluir a task: o que foi alterado, qual verificacao passou, e qual risco ainda merece atencao?*

---
## Task 3: `frontend/app/pages/research.py` - Adicionar a descrição do modo no frontend

**Estimativa:** ~15min

**O que é e por que existe**

O dict `MODES` é o registro declarativo da UI: ícone, caption e description de cada modo são definidos aqui, e o loop de renderização gera o radio automaticamente. Adicionar um modo = adicionar uma entrada no dict.

**Files:**
- Criar/Editar: `frontend/app/pages/research.py`

---

### Conceito: Dict MODES como registro declarativo — UI gerada a partir dos dados
> O Streamlit não conhece a lista de modos — ele lê o `MODES` dict. Colocar o ícone, caption e description diretamente no código HTML (hardcoded) exigiria mudanças em múltiplos lugares. Com o dict, é um lugar só.
>
> | Abordagem | Onde alterar | Risco |
> |---|---|---|
> | Hardcoded no template | Vários arquivos | Fácil esquecer um lugar |
> | Dict `MODES` centralizado | Uma entrada no dict | Zero — UI regenera automaticamente |

---

### Documentação
- https://docs.streamlit.io/develop/api-reference/widgets/st.radio - referencia para radio com opções customizadas.
- `frontend/app/pages/research.py` — localizar o dict `MODES` para ver o padrão existente.

---

### O que você precisa fazer

1. Abra `research.py` e localize o dict `MODES` (busque por `"Due Diligence"` para achar a linha).
2. Adicione a entrada com `icon`, `caption`, e `description`.
3. Rode `uv run streamlit run frontend/app/app.py` e confirme que o novo modo aparece no radio.
4. Confirme que o nome no dict é idêntico ao registrado em `MODE_FILES`.

### Esqueleto

```python
MODES = {
    # modos existentes...
    # TODO: adicionar "{NomeDoModo}": {
    #     "icon": ":material/nome_icone:",
    #     "caption": "uma linha descritiva curta",
    #     "description": "2-3 frases explicando o output esperado",
    # },
}
```

<details>
<summary>Ver solução completa</summary>

Em `frontend/app/pages/research.py`, adicione a entrada no dict `MODES` (linha 104):

```python
MODES = {
    # ... modos existentes ...
    "Market Mapping": {
        "icon": ":material/map:",
        "caption": "Panorama competitivo de um setor ou mercado",
        "description": (
            "Mapeia os principais players, segmentos e dinâmicas de um mercado. "
            "Identifica white spaces, tendências de consolidação e como as empresas "
            "se posicionam relativamente. "
            "Output: mapa competitivo com análise de posicionamento."
        ),
    },
}
```

</details>

- [ ] **Step 3.1: Novo modo aparece no radio do Streamlit sem erro de renderização.**
- [ ] **Step 3.2: Caption e description aparecem ao selecionar o modo.**
- [ ] **Step 3.3: Nome do modo em `MODES` é idêntico ao registrado em `MODE_FILES`.**
- [ ] **Step 3.4: Todos os 7 novos modos adicionados ao dict `MODES`.**

### Resumo
> *Preencher apos concluir a task: o que foi alterado, qual verificacao passou, e qual risco ainda merece atencao?*

---
## Task 4: `frontend/app/pages/research.py` - Adicionar campos de input para o modo

**Estimativa:** ~30min

**O que é e por que existe**

Cada modo tem campos diferentes. Esta task cria o bloco `elif mode ==` com os inputs corretos, distinguindo claramente campos obrigatórios de opcionais.

**Files:**
- Criar/Editar: `frontend/app/pages/research.py`

---

### Conceito: Label como contrato de UX — `(opcional)` não é detalhe, é informação funcional
> O usuário não lê documentação. Se um campo é opcional, o label deve dizer `(opcional)`. Sem isso, usuários bloqueiam ao não saber se podem deixar em branco — ou preenchem campos desnecessários que diluem a query.
>
> | Label | O que o usuário entende |
> |---|---|
> | `"Setor"` | Obrigatório — precisa preencher |
> | `"Setor (opcional)"` | Pode deixar em branco |
> | Sem placeholder | Usuário não sabe o formato esperado |

---

### Documentação
- https://docs.streamlit.io/develop/api-reference/widgets/st.text_input - referencia para `label`, `placeholder`, e `key`.
- "Matriz completa dos modos novos" (tabela acima neste arquivo) — colunas "Campos obrigatórios" e "Campos opcionais".

---

### O que você precisa fazer

1. Consulte a tabela "Matriz completa dos modos novos" para saber os campos obrigatórios e opcionais.
2. Crie o bloco `elif mode == "{NomeDoModo}":` com `st.columns(2)`.
3. Campos obrigatórios: label sem `(opcional)`. Campos opcionais: label com `(opcional)`.
4. Todo campo deve ter `placeholder` com exemplo concreto (ex: `"e.g. HR Tech, Cloud Storage"`).

### Esqueleto

```python
elif mode == "{NomeDoModo}":
    col1, col2 = st.columns(2)
    with col1:
        fields["campo_obrigatorio"] = st.text_input(
            "Label do campo",
            placeholder="e.g. exemplo concreto"
        )
    with col2:
        fields["campo_opcional"] = st.text_input(
            "Label (opcional)",
            placeholder="e.g. exemplo"
        )
```

<details>
<summary>Ver solução completa</summary>

Ainda em `research.py`, dentro do bloco `if mode == ...`:

```python
elif mode == "Market Mapping":
    col1, col2 = st.columns(2)
    with col1:
        fields["sector"] = st.text_input("Setor / mercado", placeholder="e.g. HR Tech, Cloud Storage, EdTech")
        fields["geography"] = st.text_input("Geografia (opcional)", placeholder="e.g. Brasil, América Latina, Global")
    with col2:
        fields["customer_segment"] = st.text_input(
            "Segmento de cliente (opcional)",
            placeholder="e.g. PMEs, Enterprise, B2C",
        )
        fields["focus"] = st.text_input("Foco adicional (opcional)", placeholder="e.g. apenas players com funding recente")
```

> **Dica de UX:** campos opcionais devem ter `(opcional)` no label — o usuário precisa saber o que é obrigatório sem precisar ler documentação.

</details>

- [ ] **Step 4.1: Campos obrigatórios renderizam sem `(opcional)` no label.**
- [ ] **Step 4.2: Campos opcionais têm `(opcional)` no label.**
- [ ] **Step 4.3: Todos os campos têm `placeholder` com exemplo concreto.**
- [ ] **Step 4.4: Selecionar o modo no radio mostra o formulário correto sem erro.**

### Resumo
> *Preencher apos concluir a task: o que foi alterado, qual verificacao passou, e qual risco ainda merece atencao?*

---
## Task 5: `frontend/app/pages/research.py` - Adicionar o branch em `build_query()`

**Estimativa:** ~45min

**O que é e por que existe**

`build_query()` monta a string que vai para o agente. Para campos opcionais, usa `fields.get()` — não `fields[]` — porque o usuário pode ter deixado o campo vazio.

**Files:**
- Criar/Editar: `frontend/app/pages/research.py`

---

### Conceito: build_query como montador incremental — campos opcionais não quebram a query
> `fields.get("campo")` retorna `None` quando o campo não foi preenchido. O pattern `if fields.get("campo"): lines.append(...)` ignora silenciosamente campos vazios. `fields["campo"]` (sem `.get`) levantaria `KeyError` para campos opcionais não preenchidos.
>
> | Padrão | Campo opcional vazio | Resultado |
> |---|---|---|
> | `fields["campo"]` | `KeyError` | Crash ao montar a query |
> | `if fields.get("campo"): lines.append(...)` | Ignorado silenciosamente | Query válida sem o campo |

---

### Documentação
- https://docs.python.org/3/library/stdtypes.html#dict.get - referencia para `dict.get(key)` com fallback `None`.
- `frontend/app/pages/research.py` — localizar `def build_query()` e ler um branch existente como referência.

---

### O que você precisa fazer

1. Leia o branch de um modo existente em `build_query()` como referência do padrão `lines.append`.
2. Crie o branch `elif mode == "{NomeDoModo}":` com a linha obrigatória.
3. Adicione as linhas opcionais dentro de `if fields.get(...)`.
4. Adicione todos os campos opcionais do modo em `OPTIONAL_FIELDS`.

### Esqueleto

```python
elif mode == "{NomeDoModo}":
    lines = [
        # TODO: linha obrigatória com fields['campo_obrigatorio']
        f"Research on {fields['campo_obrigatorio']}.",
    ]
    # TODO: campos opcionais — sempre com fields.get(), nunca fields[]
    if fields.get("campo_opcional"):
        lines.append(f"Optional context: {fields['campo_opcional']}.")
    # TODO: linha de Deliverables conforme a coluna "Deliverable mínimo" da matriz
    lines.append("Deliverables: ...")
    return " ".join(lines)
```

<details>
<summary>Ver solução completa</summary>

```python
elif mode == "Market Mapping":
    lines = [
        f"Market mapping analysis for the {fields['sector']} sector.",
    ]
    if fields.get("geography"):
        lines.append(f"Geographic focus: {fields['geography']}.")
    if fields.get("customer_segment"):
        lines.append(f"Customer segment focus: {fields['customer_segment']}.")
    if fields.get("focus"):
        lines.append(f"Additional focus: {fields['focus']}.")
    lines.append(
        "Deliverables: player landscape (tiered), market segmentation, "
        "competitive dynamics, and white space analysis."
    )
```

E atualize `OPTIONAL_FIELDS`:

```python
OPTIONAL_FIELDS = {"focus", "company_url", "our_company_url", "competitor_url", "target_url", "geography", "customer_segment"}
```

---

## Os 7 Modos Novos — Visão Geral

Para cada modo abaixo, o padrão de implementação é idêntico ao de Market Mapping acima. A diferença está nos campos de input e no conteúdo do prompt.

### 1. Market Mapping
**Pergunta central:** "Quem são os players e como o mercado está estruturado?"
**Campos:** setor, geografia (opt), segmento (opt)
**Deliverable:** mapa competitivo tiered com white spaces

### 2. Leadership Intel
**Pergunta central:** "Quem são os executivos, qual o track record, e que conexões têm?"
**Campos:** nome do executivo ou empresa, cargo (opt)
**Deliverable:** perfil com histórico profissional, decisões marcantes, rede de relacionamentos
**Dica de prompt:** incluir termos de busca como "interview", "keynote", "board member", "previously at" + o nome

### 3. Funding & Deal Intelligence
**Pergunta central:** "Quanto foi captado, por quem, e o que sinaliza sobre estratégia futura?"
**Campos:** empresa, tipo de evento (IPO/M&A/rodada de funding)
**Deliverable:** histórico de deals com tese de investimento inferida
**Dica de prompt:** usar Crunchbase, PitchBook, TechCrunch como fontes primárias nos termos de busca

### 4. Risk Assessment
**Pergunta central:** "Qual é o perfil de risco multidimensional desta empresa ou setor?"
**Campos:** empresa/setor, dimensões de risco (reputacional, financeiro, regulatório, geopolítico)
**Deliverable:** scorecard de risco com evidência por dimensão
**Diferença do Due Diligence:** Due Diligence é focado em deal-specific risks; Risk Assessment é mais amplo e pode ser sobre um setor inteiro

### 5. Regulatory Watch
**Pergunta central:** "Quais regulações estão mudando e como afetam o setor?"
**Campos:** setor, jurisdição (Brasil / UE / EUA / Global), horizonte temporal
**Deliverable:** mapa de mudanças regulatórias com impacto por player
**Dica de prompt:** buscar termos como "regulação", "compliance", "LGPD", "GDPR", nome do setor + "lei" ou "decreto"

### 6. Talent Signal
**Pergunta central:** "O que os padrões de contratação revelam sobre a direção estratégica?"
**Campos:** empresa, período de análise
**Deliverable:** análise de job postings como proxy para iniciativas não-divulgadas
**Dica de prompt:** "job postings" + empresa + LinkedIn, Glassdoor, Indeed como fontes; cargos sendo criados → apostas estratégicas

### 7. Partnership & Ecosystem Mapping
**Pergunta central:** "Com quem esta empresa está se integrando e que ecossistema está construindo?"
**Campos:** empresa, tipo de parceria (tecnologia, canal, go-to-market)
**Deliverable:** mapa de parcerias com análise estratégica de cada aliança
**Dica de prompt:** "partnership", "integration", "marketplace", "app store", "ecosystem" + nome da empresa

---

## Checklist de Implementação por Modo

Para cada um dos 7 modos, complete esta lista:

- [ ] `backend/prompts/modes/{nome_do_modo}.md` criado com as 3 seções obrigatórias
- [ ] Entrada adicionada em `MODE_FILES` em `api.py`
- [ ] Entrada adicionada em `MODES` em `research.py`
- [ ] Campos de input adicionados no bloco `elif mode ==` em `research.py`
- [ ] Branch adicionado em `build_query()` em `research.py`
- [ ] Campos opcionais adicionados em `OPTIONAL_FIELDS`
- [ ] Teste manual rodado com uma query real
- [ ] Relatório gerado avaliado contra o checklist de qualidade do Sprint 1

---

## O que Não Fazer

**Não colocar lógica de negócio no prompt.** O prompt é uma instrução para o agente, não código. Se você precisa de lógica condicional (ex: "se o setor for financeiro, priorize regulação"), essa lógica deve estar em `build_query()` ou num campo de input separado — não embutida no prompt como "se... então...".

**Não duplicar os Deliverables do prompt em `build_query()`.** O `build_query()` já inclui uma linha de Deliverables (ex: `"Deliverables: player landscape..."`) porque o prompt do modo pode não ser carregado em todos os contextos. Mas não repita parágrafos inteiros — o contexto fica redundante e confuso para o agente.

**Não adicionar campos de input desnecessários.** Cada campo a mais é fricção para o usuário. Se uma informação pode ser inferida pelo agente (ex: "ano de fundação da empresa"), não peça ao usuário — deixe o agente descobrir.

</details>

- [ ] **Step 5.1: Query gerada com todos os campos preenchidos contém empresa/setor, contexto e deliverables.**
- [ ] **Step 5.2: Query gerada sem campos opcionais não contém `None` ou string vazia.**
- [ ] **Step 5.3: Todos os campos opcionais de todos os 7 modos estão em `OPTIONAL_FIELDS`.**
- [ ] **Step 5.4: Checklist de implementação por modo (no bloco `<details>`) está 100% completo para os 7 modos.**

### Resumo
> *Preencher apos concluir a task: o que foi alterado, qual verificacao passou, e qual risco ainda merece atencao?*

---

## Solo Developer Ready

- [ ] Adicionei os 7 modos da matriz, nao apenas o exemplo Market Mapping.
- [ ] Cada modo tem prompt, entrada em `MODE_FILES`, UI, campos e branch em `build_query()`.
- [ ] Rodei uma pesquisa manual por modo no Streamlit.
- [ ] Confirmei que o payload enviado para `/research/stream` usa o mesmo nome registrado no backend.
- [ ] Comparei cada relatorio com o checklist de qualidade do Sprint 1.
