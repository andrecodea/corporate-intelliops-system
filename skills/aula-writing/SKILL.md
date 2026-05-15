---
name: aula-writing
description: Use when revitalizing, creating, or structuring Jupyter notebook lessons for math, data science, or ML courses — when content needs pedagogical progression from motivation to concept to interactive cells, with ML/IA connections, exercise skeletons with collapsible solutions, and progress checkboxes.
---

# Aula Writing

## Overview

Lessons follow a four-layer structure: **motivação → conceito → células interativas → exercício**. Each lesson teaches while guiding — the learner understands WHY before implementing HOW, and sees the connection to ML/IA before closing the notebook.

## Lesson Ordering

For every lesson, sequence:

```
1. Motivação    → why this concept appears in real ML/IA pipelines
2. Conceito     → theoretical block with tables, before/after examples
3. Demonstração → interactive cells with "Por que esta célula existe" before each one
4. Exercício    → skeleton with TODOs → collapsible solution
5. Conexão      → explicit link to ML/IA use case (loss function, embedding, preprocessing)
```

## Lesson Structure

Every lesson follows this template:

~~~markdown
## Aula N: [Topic Name]

> **Objetivo:** [One sentence — what the learner will be able to DO, not just know.]
> **Conexão com ML/IA:** [Where does this appear in a real pipeline? Name it explicitly.]

---

### Conceito: [Topic Name]

> [Blockquote explaining WHY the concept matters — not just what it is.
>  Include a table or before/after example if it clarifies.]
>
> | Onde aparece em ML/IA | Por quê |
> |---|---|
> | [context] | [reason] |

---

### Demonstração

> **Célula N — Por que [cell name]:**
> [What question does this cell answer? What DECISION does it inform downstream?]

```python
# Célula N — [name]
# variáveis disponíveis: [list]

# TODO: passo 1
# TODO: passo 2
# TODO: imprimir/plotar resultado
```

<details>
<summary>Ver solução completa</summary>

```python
# solução completa funcional
```

</details>

---

### Exercício

```python
def nome_funcao(arg: Tipo) -> TipoRetorno:
    # TODO: passo 1
    # TODO: passo 2
    pass
```

<details>
<summary>Ver solução</summary>

```python
def nome_funcao(arg: Tipo) -> TipoRetorno:
    # implementação completa
    pass
```

</details>

- [ ] **N.1: [Ação concreta com verbo]**
- [ ] **N.2: [Ação concreta com verbo]**
- [ ] **N.3: Consigo explicar [conceito] sem olhar o material**

### Resumo
> *Preencher após concluir a aula: o que você mudaria num pipeline real com base nesta aula?*
~~~

## Interactive Cell Pattern

Every cell in the Demonstração section **MUST** have a `> **Célula N — Por que:**` block before the skeleton. This is mandatory — the learner must understand what DECISION the cell informs.

**The block must answer:**
1. What question does running this cell answer?
2. What downstream choice does the result inform?

Without this, the learner is just watching code run, not building judgment.

## Conceito Block Rules

- Every non-trivial concept needs a `### Conceito:` block
- Use blockquotes (`>`) for the entire explanation
- Always include a "Onde aparece em ML/IA" table
- End with the practical consequence: "Sem isso, X quebra porque Y"

**Required Conceitos for:**
- Transformações que alteram a distribuição dos dados (log, normalização, embedding)
- Funções de custo e otimização (por que minimizamos isso?)
- Operações vetoriais com semântica geométrica (dot product, cosseno, norma)
- Qualquer conceito que o aluno poderia usar mecanicamente sem entender o porquê

## Conexão ML/IA

Each lesson must name at least one **concrete** use in ML/IA. Not vague ("usado em redes neurais") — specific formula, algorithm, or pipeline stage:

| Conceito da aula | Conexão concreta |
|---|---|
| Logaritmos | Cross-entropy loss: `L = -Σ y·log(ŷ)` — log penaliza probabilidades próximas de 0 |
| Funções trigonométricas | Positional encoding em Transformers: `PE(pos,2i) = sin(pos/10000^(2i/d))` |
| Produto escalar | Similaridade de cosseno em sistemas de recomendação e busca semântica |
| Transformação log | Pré-processamento de features com distribuição assimétrica (preços, contagens) |
| Gradiente | Backpropagation — direção de atualização dos pesos da rede neural |
| Espaço vetorial | Word embeddings e representação semântica de tokens em LLMs |

## Common Mistakes

| Mistake | Fix |
|---|---|
| Célula sem "Por que" | Adicionar blockquote antes do skeleton explicando a decisão que a célula informa |
| Conexão ML/IA genérica ("usado em IA") | Nomear a fórmula, o algoritmo, ou o estágio do pipeline específico |
| Conceito sem tabela ML | Adicionar "Onde aparece em ML/IA" em todo bloco Conceito |
| Solução sem skeleton | Sempre incluir skeleton com `# TODO:` antes da `<details>` |
| Objetivo vago ("entender logaritmos") | Reescrever como ação: "aplicar transformação log em features assimétricas" |
| Resumo preenchido antes de concluir | Só preencher após todos os checkboxes marcados |
| Checkbox sem verbo | Iniciar com ação: "Calcular...", "Plotar...", "Verificar...", "Explicar..." |

## Iron Law Note

> **Verificação de conformidade:** Esta skill foi derivada do rascunho validado em sessão real (Cap02 — funções e logaritmos, curso DSA). Antes de usar em novo domínio matemático, gere uma aula sem a skill carregada e verifique desvios dos padrões acima.
