## Melhores frameworks para construir agentes de IA em 2025 (guia prático)

### 1) LangGraph (ecossistema LangChain)
LangGraph é uma camada de orquestração **stateful e baseada em grafo** (nós/arestas) pensada para construir agentes e workflows com mais controle do que um “loop de prompt”. Um diferencial importante em 2025 é a ênfase em **persistência/checkpointing**, o que permite retomar execuções, manter estado por “threads” e habilitar padrões de **human-in-the-loop** e **replay** para depuração/auditoria [1]. É uma escolha especialmente forte quando o “agente” é, na prática, um workflow de várias etapas com ramificações, retries e pontos de aprovação.

### 2) LangChain
LangChain continua sendo um dos frameworks mais usados para compor aplicações com LLMs (tools, chains, integrações). Em 2025, é comum usar LangChain como “cola” de integrações e o LangGraph como o motor de orquestração dos fluxos agentic (quando há complexidade). A documentação principal e o ecossistema oficial estão no site do projeto [2].

### 3) LlamaIndex
LlamaIndex é uma das opções mais fortes quando o problema central é **RAG / grounding em dados** (conectores, indexação, query engines e componentes para chat com base documental). É muito usado para copilots corporativos conectados a múltiplas fontes, com boa ergonomia para ingestão e recuperação. Documentação e repositório oficiais: [3], [4].

### 4) Microsoft AutoGen
AutoGen é um framework voltado a **sistemas multiagente**, onde vários agentes colaboram por meio de conversas/coordenação (papéis como planner/executor/reviewer, etc.). O projeto tem grande tração e, em 2024–2025, há sinalização de evolução para mais robustez e extensibilidade (incluindo iniciativas como AutoGen Studio e mudanças de versão mencionadas em guias executivos e materiais relacionados) [5]. Repositório oficial: [6].

### 5) CrewAI
CrewAI popularizou um modelo mental simples para **“equipes de agentes” orientadas a papéis e tarefas** (bom para pipelines de pesquisa → escrita → revisão e automações de negócio). É uma opção forte quando a prioridade é produtividade e rapidez de implementação, e quando o fluxo pode ser expresso bem como tarefas e papéis. Documentação e repositório: [7], [8].

### 6) Haystack (deepset)
Haystack é um framework maduro para **pipelines de RAG e search/QA**, com arquitetura modular para retrieval/ranking/generation e foco em aplicações de busca e perguntas/respostas em produção. Documentação e repositório: [9], [10].

### 7) Semantic Kernel (Microsoft)
Semantic Kernel é um SDK focado em integrar LLMs a aplicações via **plugins/funções**, com encaixe natural em ambientes Microsoft (.NET/C# e Azure). É uma escolha forte quando a stack e a governança já estão no ecossistema Microsoft. Documentação e repositório: [11], [12].

### 8) OpenAI Assistants API / OpenAI Agents SDK
Para quem prefere uma abordagem **API-first** (com mais capacidades gerenciadas pelo provedor, dependendo do recurso), a plataforma da OpenAI fornece APIs e SDKs para construir assistentes/agentes com tool use. O repositório do **OpenAI Agents SDK (JS/TS)** é uma referência oficial útil para implementação [13], e a documentação da plataforma concentra guias e referências de API [14].

### 9) DSPy (para “programar” e otimizar pipelines LLM)
DSPy não é um framework de orquestração de agentes completo, mas é muito relevante em 2025 como camada para **construir e otimizar** módulos/pipelines LLM de forma mais sistemática (reduzindo tentativa-e-erro manual de prompt), especialmente quando há métricas/datasets e necessidade de qualidade consistente. Repositório: [15].

## Como escolher (recomendação por cenário)

- **Workflows agentic complexos em produção (ramificações, retries, retomada, auditoria, HITL)**: LangGraph se destaca por ser stateful e por oferecer primitivas de persistência/checkpointing e replay [1].
- **App LLM generalista com muitas integrações** (tools, provedores, componentes): LangChain como base e, quando necessário, LangGraph para orquestração [2].
- **RAG como problema principal** (chat com base documental, múltiplas fontes, conectores): LlamaIndex ou Haystack (a escolha tende a depender do estilo de pipeline e preferências do time) [3], [9].
- **Multiagente (coordenação por papéis/conversas)**:
  - AutoGen quando a arquitetura “sociedade de agentes” é o centro e a coordenação por conversas é natural [6].
  - CrewAI quando o objetivo é um fluxo de tarefas por papéis com alto foco em time-to-market [7].
- **Ecossistema Microsoft (.NET/Azure) e governança corporativa**: Semantic Kernel (e, em alguns casos, combinado com AutoGen) [11], [12].
- **Quando o gargalo é qualidade/consistência de prompts/pipelines**: DSPy como camada de otimização/compilação, frequentemente combinada com orquestradores [15].

## Comparativo rápido (alto nível)

| Framework | Melhor para | Pontos fortes | Atenções |
|---|---|---|---|
| LangGraph | Workflows stateful e produção | Grafo + estado, checkpoints, replay, HITL [1] | Curva de aprendizado; requer modelagem explícita |
| LangChain | Composição/integrações LLM | Ecossistema amplo [2] | Pode ficar “pesado” sem necessidade |
| LlamaIndex | RAG/dados | Conectores + index/query engines [3] | Para agentes complexos, pode precisar de orquestração extra |
| AutoGen | Multiagente | Coordenação por conversa; patterns multi-agent [6] | Em produção, exige governança/terminação/observabilidade |
| CrewAI | “Equipes” por tarefas | Modelo simples de papéis/tarefas [7] | Menos controle fino que grafos |
| Haystack | Pipelines de search/QA | Pipeline modular para RAG [9] | Agentic tool use não é foco |
| Semantic Kernel | Stack Microsoft | Plugins/funções; .NET/Azure [11] | Melhor quando há alinhamento com stack MS |
| OpenAI APIs/SDK | API-first | Menos infra (dependendo do recurso); SDKs oficiais [13][14] | Lock-in do provedor e limites de plataforma |
| DSPy | Otimização/“programação” LLM | Iteração com métricas/datasets [15] | Não substitui orquestrador de agentes |

### Sources
[1] LangChain Docs — LangGraph Persistence (JS): https://docs.langchain.com/oss/javascript/langgraph/persistence
[2] LangChain Python Docs: https://python.langchain.com/
[3] LlamaIndex Docs: https://docs.llamaindex.ai/
[4] LlamaIndex GitHub: https://github.com/run-llama/llama_index
[5] Baytech Consulting — Microsoft AutoGen: A Practical Executive Guide to AI Agents: https://www.baytechconsulting.com/blog/microsoft-autogen
[6] Microsoft AutoGen GitHub: https://github.com/microsoft/autogen
[7] CrewAI Docs: https://docs.crewai.com/
[8] CrewAI GitHub: https://github.com/crewAIInc/crewAI
[9] Haystack Docs: https://docs.haystack.deepset.ai/
[10] Haystack GitHub: https://github.com/deepset-ai/haystack
[11] Microsoft Learn — Semantic Kernel: https://learn.microsoft.com/semantic-kernel/
[12] Semantic Kernel GitHub: https://github.com/microsoft/semantic-kernel
[13] OpenAI — openai-agents-js GitHub: https://github.com/openai/openai-agents-js
[14] OpenAI Platform Docs: https://platform.openai.com/docs
[15] DSPy GitHub: https://github.com/stanfordnlp/dspy
