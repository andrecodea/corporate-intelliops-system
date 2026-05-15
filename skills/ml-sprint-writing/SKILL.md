---
name: ml-sprint-writing
description: Use when writing sprint plans for data science or ML projects — establishes task structure with theory blocks, skeleton code, collapsible solutions, step checkboxes, and ordering for EDA/notebook/script workflows
---

# ML Sprint Writing

## Overview

Sprint plans for ML/data science projects follow a three-layer structure: **theory → skeleton → solution**. Each task teaches while guiding implementation. Tasks are ordered so the learner experiments before formalizing: EDA first, notebook prototype second, production script third.

## Task Ordering

For any data transformation or ML pipeline task, always sequence:

```
1. EDA          → explore raw data, validate assumptions, decide parameters
2. Notebook     → prototype the algorithm interactively, self-contained, decide threshold
3. Script       → production implementation using the decided parameters
```

**Why this matters:** The notebook must be self-contained — it cannot depend on the script's output. It uses permissive parameters (e.g., `n_components=0.999`) to show the full curve and inform the threshold decision. The script then formalizes what the notebook confirmed.

## Task Structure

Every task follows this sequence:

```markdown
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
```

## Notebook Cell Pattern

Each notebook cell in a sprint gets a `> **Por que esta célula existe:**` block before the skeleton. This is mandatory — the learner needs to explain their methods.

```markdown
> **Célula N — Por que [cell name]:**
> [Explain what question this cell answers and what DECISION it informs downstream.
>  Connect explicitly to a parameter or architectural choice in the script.]

```python
# Célula N — [name]
# context variables already available: [list them]

# TODO: step 1
# TODO: step 2
# TODO: imprimir/plotar resultado esperado
```
```

The `<details>` solution block comes ONCE after all skeleton cells, not per cell.

## Conceito Block Rules

- Every non-trivial technical decision needs a `### Conceito:` block before the skeleton
- Use blockquotes (`>`) for the entire explanation
- Include a before/after table or concrete mini-example when possible
- End with the practical consequence: "Without this, X breaks because Y"

**Required Conceitos for ML tasks:**
- Why the pipeline order matters (Imputer → Scaler → PCA)
- Why fit only on train, transform on all (data leakage)
- Why the threshold/parameter was chosen (scree plot, not documentation default)
- Why artifacts are saved as a pipeline (not individual components)

## EDA Cell Checklist

Every EDA section must answer these questions (one cell each):

| Cell | Question answered | Decision it informs |
|------|-------------------|---------------------|
| Setup | Is the data shape/type as expected? | Confirms pipeline upstream worked |
| Target distribution | Is the target balanced? | `class_weight` strategy in training |
| Feature variance | Are there near-zero-variance features? | Whether `MIN_UNIQUE` threshold was enough |
| Missing values | Is NaN random or systematic? | Whether to impute or drop periods |
| Correlation | Are features correlated? | Validates PCA as the right technique |

## Notebook Prototype Cell Checklist

For PCA or dimensionality reduction tasks:

| Cell | Purpose | Key variable |
|------|---------|--------------|
| Fit pipeline inline | Self-contained experiment | `X_proto`, `pca_proto` |
| Scree plot | Decide threshold visually | `var_ratio`, `cum_var` |
| Scatter PC1×PC2 | Validate class separability | Class labels from original df |
| Loadings heatmap | Explain PCs in domain terms | `pca_proto.components_` |
| Distribution comparison | Detect temporal drift | Train vs val/test split |

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Notebook cells depend on script output | Make cells self-contained; fit inline |
| `n_components=0.95` in notebook | Use `0.999` to show full curve |
| No "Por que" before each cell | Add blockquote explaining decision it informs |
| Solution only, no skeleton | Always include skeleton with `# TODO:` comments first |
| Steps mix notebook and script work | Separate into distinct tasks with separate step lists |
| "Preencher depois" in Resumo before task is done | Only fill after all steps are checked |

## Verification (Iron Law Note)

> **Iron Law compliance:** This skill was written from observed patterns, not after a formal RED baseline with subagents. Before relying on it for a new project, run one sprint task through an agent WITHOUT this skill loaded and verify it deviates from the patterns above. Then re-run WITH the skill to confirm compliance.