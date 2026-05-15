---
name: sprint-writing
description: Use when writing sprint plans for any technical project — establishes task structure with theory blocks, skeleton code, collapsible solutions, step checkboxes, and explore-before-implement ordering for software, data science, API, and ML workflows
---

# Sprint Writing

## Overview

Sprint plans follow a three-layer structure: **theory → skeleton → solution**. Each task teaches while guiding implementation. Tasks are ordered so the learner experiments before formalizing: exploration first, prototype second, production implementation third.

## Task Ordering

For any implementation task, sequence:

```
1. Explore     → investigate the raw material (data, API, codebase), validate assumptions
2. Prototype   → interactive proof-of-concept (notebook, REPL, scratch file)
3. Implement   → production code using decisions made in the prototype
```

**Why this matters:** The prototype must be self-contained — it cannot depend on the implementation's output. It uses permissive parameters to reveal the full solution space. The implementation formalizes what the prototype confirmed.

**Examples by domain:**

| Domain | Explore | Prototype | Implement |
|--------|---------|-----------|-----------|
| ML pipeline | EDA in notebook | Algorithm in notebook (inline fit) | Production script |
| API integration | Curl / Postman queries | Scratch file / notebook | Service module |
| Database migration | Schema inspection | Test migration on sample | Production migration |
| Frontend feature | Browser devtools / Figma | Isolated component | Integrated component |

## Task Structure

Every task follows this sequence:

~~~markdown
## Task N: `path/to/file` — short description

**O que é e por que existe**
[What it does + why it needs to exist in the pipeline context]

**Files:**
- Criar/Editar: `exact/path/to/file`

---

### Conceito: [Topic Name]
> [Blockquote explaining WHY the concept matters, not just what it is.
>  Include a table or concrete example if it clarifies.]

---

### Documentação
- [Official docs link] — one-line description

---

### O que você precisa fazer
[Numbered line-by-line explanation of each step, with inline code snippets
 showing the key calls and explaining what each argument does]

### Esqueleto

```python
def function_name(arg: Type) -> ReturnType:
    # TODO: step 1 description
    # TODO: step 2 description
    pass
```

<details>
<summary>Ver solução completa</summary>

```python
def function_name(arg: Type) -> ReturnType:
    # complete working implementation
    pass
```

</details>

- [ ] **Step N.M: [Action verb + what]**

### Resumo
> *Preencher após concluir a task.*
~~~

## Interactive Cell Pattern (Notebook / REPL)

When a task uses an interactive environment (Jupyter, IPython, browser devtools, SQL client), each cell gets a `> **Por que esta célula existe:**` block before the skeleton. This is mandatory — the learner must understand the decision each cell informs.

~~~markdown
> **Célula N — Por que [cell name]:**
> [Explain what question this cell answers and what DECISION it informs downstream.
>  Connect explicitly to a parameter or architectural choice in the final implementation.]

```python
# Célula N — [name]
# context variables already available: [list them]

# TODO: step 1
# TODO: step 2
# TODO: imprimir/plotar resultado esperado
```
~~~

The `<details>` solution block comes **once** after all skeleton cells, not per cell.

## Conceito Block Rules

- Every non-trivial technical decision needs a `### Conceito:` block before the skeleton
- Use blockquotes (`>`) for the entire explanation
- Include a before/after table or concrete mini-example when possible
- End with the practical consequence: "Without this, X breaks because Y"

**Required Conceitos for tasks involving:**
- Ordering constraints (why steps must run in a specific sequence)
- Fit/transform splits (fit only on train — data leakage applies beyond ML)
- Threshold or parameter selection (why the chosen value, not the documentation default)
- Artifact persistence (why save the full pipeline, not individual components)

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Prototype depends on implementation output | Make prototype self-contained; compute inline |
| Permissive param only in implementation | Use permissive params in prototype to show full solution space |
| No "Por que" before each interactive cell | Add blockquote explaining what decision the cell informs |
| Solution only, no skeleton | Always include skeleton with `# TODO:` comments first |
| Steps mix prototype and production work | Separate into distinct tasks with separate step lists |
| "Preencher depois" in Resumo before task is done | Only fill after all steps are checked |

---

## Domain Extensions

### ML / Data Science

#### EDA Cell Checklist

Every EDA section must answer these questions (one cell each):

| Cell | Question answered | Decision it informs |
|------|-------------------|---------------------|
| Setup | Is the data shape/type as expected? | Confirms pipeline upstream worked |
| Target distribution | Is the target balanced? | `class_weight` strategy in training |
| Feature variance | Are there near-zero-variance features? | Whether `MIN_UNIQUE` threshold was enough |
| Missing values | Is NaN random or systematic? | Whether to impute or drop periods |
| Correlation | Are features correlated? | Validates dimensionality reduction as the right technique |

#### PCA / Dimensionality Reduction Prototype Cell Checklist

| Cell | Purpose | Key variable |
|------|---------|--------------|
| Fit pipeline inline | Self-contained experiment | `X_proto`, `pca_proto` |
| Scree plot | Decide threshold visually | `var_ratio`, `cum_var` |
| Scatter PC1×PC2 | Validate class separability | Class labels from original df |
| Loadings heatmap | Explain PCs in domain terms | `pca_proto.components_` |
| Distribution comparison | Detect temporal drift | Train vs val/test split |

#### Required ML Conceitos

- Why the pipeline order matters (Imputer → Scaler → PCA)
- Why fit only on train, transform on all (data leakage)
- Why the threshold was chosen from the scree plot, not the documentation default
- Why artifacts are saved as a pipeline, not individual components

---

## Verification (Iron Law Note)

> **Iron Law compliance:** This skill was written from observed patterns, not after a formal RED baseline with subagents. Before relying on it for a new domain, run one sprint task through an agent WITHOUT this skill loaded and verify it deviates from the patterns above. Then re-run WITH the skill to confirm compliance.
