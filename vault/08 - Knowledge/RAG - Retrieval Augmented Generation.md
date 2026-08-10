# RAG — Retrieval Augmented Generation

The technique that gives LLMs access to external knowledge at query time. The most widely adopted pattern in production AI (2024–2026).

---

## What is RAG?

**RAG = Retrieve relevant documents → Augment the prompt with them → Generate an answer grounded in those documents.**

Instead of relying solely on what the model memorized during training, RAG fetches real-time, domain-specific information and injects it into the context window.

```
┌──────────┐     ┌──────────────┐     ┌──────────────┐
│  User    │────►│  Retriever   │────►│  Generator   │
│  Query   │     │  (find docs) │     │  (LLM)       │
└──────────┘     └──────┬───────┘     └──────┬───────┘
                        │                     │
                 ┌──────▼───────┐      ┌──────▼───────┐
                 │ Vector DB /  │      │  Grounded    │
                 │ Knowledge    │      │  Answer      │
                 │ Store        │      │  + Citations │
                 └──────────────┘      └──────────────┘
```

---

## The 7-Stage Pipeline

| Stage | What Happens | Tools |
|-------|-------------|-------|
| **1. Load** | Ingest raw documents (PDF, web, DB, API) | LangChain loaders, Unstructured, LlamaIndex |
| **2. Chunk** | Split into passages (512–1024 tokens typical) | Recursive text splitter, semantic chunking |
| **3. Embed** | Convert chunks to vectors | OpenAI `text-embedding-3-large`, Cohere Embed v4, BGE |
| **4. Store** | Index vectors in a database | Pinecone, Weaviate, Qdrant, ChromaDB, pgvector |
| **5. Retrieve** | Find top-k relevant chunks for a query | Cosine similarity, hybrid search, BM25 |
| **6. Augment** | Inject retrieved chunks into the LLM prompt | System prompt + context window |
| **7. Generate** | LLM produces answer grounded in retrieved docs | GPT-4o, Claude, Gemini |

---

## RAG vs Fine-Tuning vs Long Context

| | RAG | Fine-Tuning | Long Context |
|---|---|---|---|
| **Best for** | Dynamic/changing data | Teaching style/format | Small static knowledge |
| **Data freshness** | Real-time | Frozen at training | Frozen at prompt time |
| **Cost** | Low (API + vector DB) | High (training GPU) | Medium (token cost) |
| **Hallucination** | Low (grounded) | Medium | Low |
| **Setup effort** | Medium | High | Low |
| **Token efficiency** | High (only relevant chunks) | N/A | Low (entire corpus in prompt) |
| **Update frequency** | Add docs anytime | Retrain needed | Re-submit entire context |

**Rule of thumb:** If the data changes weekly or more → RAG. If you need a specific tone/format → Fine-tune. If the dataset fits in 200K tokens → Long context might be enough.

---

## Types of RAG

### 1. Naive RAG
The simplest implementation — retrieve then read, linear pipeline.

```
Query → Embed → Vector Search → Top-K docs → LLM → Answer
```

- **Pros:** Easy to build, fast
- **Cons:** Brittle with complex queries, no query optimization, noisy retrieval
- **When to use:** Prototyping, simple Q&A over small document sets

### 2. Advanced RAG
Adds pre-retrieval and post-retrieval optimization stages.

```
Query → Rewrite/Expand → Embed → Hybrid Search → Rerank → Compress → LLM → Answer
```

**Pre-retrieval techniques:**
- Query rewriting (rephrase for better retrieval)
- Query expansion (generate sub-questions)
- Query routing (choose the right index)
- HyDE (Hypothetical Document Embeddings — generate a hypothetical answer, embed that)

**Post-retrieval techniques:**
- Reranking (cross-encoder scores relevance more accurately)
- Compression (extract only the relevant sentences)
- Deduplication (remove redundant chunks)
- Filtering (metadata-based, date, source type)

**This is where most production systems land.**

### 3. Modular RAG
A composable architecture where every component is swappable.

```
┌─────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐
│ Loader  │→ │ Chunker  │→ │ Embedder │→ │ Retriever│→ │ Generator │
│ (swap)  │  │ (swap)   │  │ (swap)   │  │ (swap)   │  │ (swap)    │
└─────────┘  └──────────┘  └──────────┘  └──────────┘  └───────────┘
```

- Each module is independently configurable
- Can mix dense + sparse retrievers
- Can add validators, fact-checkers, citation extractors as middleware

### 4. Agentic RAG
The agent decides **when, what, and how** to retrieve. The dominant pattern in 2026.

```
Query → Agent decides:
  ├── Simple question? → Direct LLM answer (no retrieval)
  ├── Single-doc question? → Standard RAG
  ├── Multi-step question? → Iterative retrieval loop
  └── Cross-domain? → Route to specialized retrievers
```

- Agent can reformulate queries based on initial results
- Can decide retrieval is insufficient and try alternative strategies
- Can validate retrieved information before generating
- Uses ReAct pattern: Reason → Act (retrieve) → Observe → Reason again

### 5. Graph RAG
Uses knowledge graphs instead of (or alongside) vector stores.

```
Query → Entity extraction → Graph traversal → Subgraph retrieval → LLM → Answer
```

- Excels at multi-hop reasoning ("Who is the CEO of the company that acquired X?")
- Captures relationships that flat vector search misses
- Microsoft's GraphRAG: builds community summaries from document graphs
- Can combine with vector RAG for best of both worlds

### 6. Self-RAG
The model decides whether to retrieve, and self-evaluates its own output.

```
Query → LLM decides: "Do I need retrieval?"
  ├── Yes → Retrieve → Generate → Self-evaluate → Refine if needed
  └── No → Generate directly
```

- Trained to output special tokens: `[Retrieve]`, `[IsRel]`, `[IsSup]`, `[IsUseful]`
- Reduces unnecessary retrieval (faster, cheaper)

### 7. Corrective RAG (CRAG)
Adds a retrieval evaluator that grades document relevance.

```
Query → Retrieve → Evaluate relevance:
  ├── Correct → Use documents → Generate
  ├── Ambiguous → Refine query → Re-retrieve
  └── Incorrect → Fall back to web search → Generate
```

### 8. Multimodal RAG
Retrieves and reasons over images, tables, audio, video — not just text.

```
Query → Retrieve text chunks + images + tables → Multimodal LLM → Answer
```

- Uses CLIP/SigLIP for image embeddings
- ColPali for document-level visual retrieval
- Growing fast with GPT-4o, Claude, Gemini vision capabilities

---

## Chunking Strategies

| Strategy | Description | Best For |
|----------|-------------|----------|
| **Fixed-size** | Split every N tokens with overlap | Simple, fast |
| **Recursive** | Split by paragraphs → sentences → words | General purpose (most common) |
| **Semantic** | Split where topic/meaning changes | Long-form documents |
| **Document-aware** | Respect headers, sections, tables | Structured docs (legal, technical) |
| **Agentic** | LLM decides chunk boundaries | High-quality, expensive |
| **Late chunking** | Embed full doc first, then chunk the embeddings | Better context preservation |

**Common settings:** 512–1024 tokens per chunk, 10–20% overlap.

---

## Vector Databases (2026)

| Database | Type | Best For |
|----------|------|----------|
| **Pinecone** | Managed cloud | Production, zero-ops |
| **Weaviate** | Open-source + cloud | Hybrid search, multimodal |
| **Qdrant** | Open-source + cloud | Performance, filtering |
| **ChromaDB** | Open-source | Prototyping, local dev |
| **pgvector** | PostgreSQL extension | Already using Postgres |
| **Milvus** | Open-source | Large-scale, enterprise |
| **FAISS** | Library (Meta) | In-memory, research |
| **LanceDB** | Open-source | Multimodal, serverless |

---

## Embedding Models (2026)

| Model | Provider | Dimensions | Notes |
|-------|----------|-----------|-------|
| `text-embedding-3-large` | OpenAI | 3072 | Most popular, Matryoshka support |
| `text-embedding-3-small` | OpenAI | 1536 | Budget option |
| `embed-v4` | Cohere | 1024 | Best for search + classification |
| `voyage-3-large` | Voyage AI | 1024 | Top MTEB scores |
| `BGE-M3` | BAAI | 1024 | Open-source, multilingual |
| `nomic-embed-text` | Nomic | 768 | Open-source, Matryoshka |
| `Gemini Embedding` | Google | 768/3072 | Built into Gemini ecosystem |

---

## Retrieval Techniques

| Technique | How it Works | When to Use |
|-----------|-------------|-------------|
| **Dense retrieval** | Semantic similarity via embeddings | Default, meaning-based search |
| **Sparse retrieval (BM25)** | Keyword/term matching | Exact terms, codes, names |
| **Hybrid search** | Dense + sparse combined | Best of both (production default) |
| **Reranking** | Cross-encoder re-scores top-k results | Always improves quality |
| **Multi-query** | Generate multiple query variants | Complex or ambiguous queries |
| **Parent-child** | Retrieve small chunks, return parent doc | Need surrounding context |
| **Contextual retrieval** | Add document context to each chunk before embedding | Anthropic's approach, +49% accuracy |

---

## Production Considerations

### Quality Metrics
- **Retrieval precision/recall** — Are you finding the right documents?
- **Answer faithfulness** — Is the answer grounded in retrieved docs?
- **Answer relevance** — Does the answer actually address the query?
- **Context relevance** — Are retrieved chunks relevant to the query?

### Evaluation Tools
- **RAGAS** — Open-source RAG evaluation framework
- **DeepEval** — LLM-as-judge evaluation
- **TruLens** — Feedback functions for RAG quality
- **LangSmith** — Tracing and evaluation (LangChain)

### Common Failure Modes
1. **Wrong chunks retrieved** → Fix: better chunking, hybrid search, reranking
2. **Right chunks, wrong answer** → Fix: better prompting, chain-of-thought
3. **Hallucination despite retrieval** → Fix: add citations, fact-checking step
4. **Outdated information** → Fix: metadata filtering by date, refresh schedule
5. **Too many irrelevant chunks** → Fix: reduce top-k, add reranking

---

## Our Project's RAG Connection

> [!note] How RAG relates to our AI Software Company
> 
> Our **Researcher agent** uses a RAG-adjacent pattern:
> - It performs **web search** (Tavily) to retrieve real-time information
> - It **augments** its analysis with retrieved search results
> - It **generates** a research report grounded in web findings
>
> This is closer to **Agentic RAG** — the agent decides what to search, evaluates results, and iterates.
>
> If we added a document knowledge base (e.g., past project reports, SIH problem statements), we'd implement full RAG with a vector store.

---

## Quick Reference: When to Use Which RAG

| Scenario | RAG Type |
|----------|----------|
| Simple Q&A chatbot | Naive RAG |
| Production customer support | Advanced RAG |
| Enterprise with multiple data sources | Modular RAG |
| Complex research questions | Agentic RAG |
| Relationship-heavy data (org charts, supply chains) | Graph RAG |
| Cost-sensitive with mixed query types | Self-RAG |
| High-stakes accuracy (legal, medical) | Corrective RAG |
| Documents with images/tables | Multimodal RAG |

---

See [[Agentic AI - Master Guide]] | [[Agent Design Patterns]] | [[Our AI Software Company]]

#agentic-ai #RAG #retrieval #knowledge #vector-db
