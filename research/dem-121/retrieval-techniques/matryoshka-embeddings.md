# Matryoshka Embeddings

## Overview
- **Category:** Embedding strategy
- **Key papers/implementations:** "Matryoshka Representation Learning" — Kusupati et al. (NeurIPS 2022). Adopted by OpenAI (text-embedding-3-small/large), Nomic (nomic-embed-text-v1.5), Jina (jina-embeddings-v3), Cohere (embed-v3), and Mixedbread (mxbai-embed-large).
- **Maturity:** Production-proven — supported by major embedding providers; standard feature in modern embedding models

## How It Works

Matryoshka Representation Learning (MRL) trains embedding models so that the first `d` dimensions of the full embedding are themselves a useful embedding at that reduced dimensionality. Named after Russian nesting dolls, each "layer" (prefix of dimensions) contains a progressively more detailed representation.

During training, the loss function is computed not just on the full embedding but simultaneously on multiple prefixes (e.g., dimensions 32, 64, 128, 256, 512, 768). Each prefix sub-embedding must independently perform well on the training objective (typically contrastive loss). This is achieved by summing loss terms across prefix lengths:

```python
# Simplified training objective
total_loss = 0
for d in [32, 64, 128, 256, 512, 768]:
    prefix_embedding = full_embedding[:d]  # first d dimensions
    loss_d = contrastive_loss(prefix_embedding, labels)
    total_loss += weight_d * loss_d

# Result: embedding[:64] works as a 64-dim embedding
#         embedding[:256] works as a 256-dim embedding
#         embedding[:768] is the full-quality embedding
```

At inference time, you choose a dimensionality based on your precision/cost trade-off. Lower dimensions = smaller index, faster retrieval, lower storage, slightly lower quality. The quality degradation is remarkably graceful — typically <5% recall loss at half the dimensions.

**Key insight:** Information is front-loaded into earlier dimensions during training. The first 256 dimensions carry most of the discriminative signal; later dimensions add nuance.

## Relevance to Code Retrieval
- **Applicable to Kenjutsu?** Yes — enables flexible precision/cost trade-offs at different pipeline stages
- **Which pipeline stage?** Indexing and retrieval (affects embedding storage and ANN search)
- **Complementary or replacement?** Complementary — a property of the embedding model, not a retrieval strategy itself

### Code-Specific Strengths
- **Tiered retrieval for code**: Use low-dimensional embeddings (128-256d) for fast initial candidate retrieval across entire codebase, then full-dimensional embeddings (768-1024d) for precise reranking of top candidates
- **Cost-effective large codebase indexing**: Code repositories can be massive (millions of functions); Matryoshka allows indexing at reduced dimensions to keep the index manageable
- **A/B testing quality vs. cost**: Easy to benchmark retrieval quality at different dimensions for code-specific queries without retraining

### Code-Specific Limitations
- **No code-specific information ordering**: MRL doesn't guarantee that code-relevant features (syntax, structure) are in early dimensions vs. late — the ordering is learned from general training data
- **Diminishing returns if base model is weak on code**: MRL doesn't improve what the model understands, only how efficiently it stores representations; a model that doesn't understand code won't improve at any dimension
- **Fixed at training time**: You can't retroactively add Matryoshka to an existing model; must be trained with MRL from the start (or fine-tuned with it)

## Known Implementations
- **OpenAI text-embedding-3-small/large** — native Matryoshka support via `dimensions` parameter (256 to 3072)
- **Nomic nomic-embed-text-v1.5** — supports dimension truncation (64 to 768)
- **Jina jina-embeddings-v3** — MRL-trained, supports configurable output dimensions
- **Mixedbread mxbai-embed-large-v1** — MRL-trained, supports truncation
- **Sentence-Transformers** — `MatryoshkaLoss` wrapper for training custom MRL models
- **LlamaIndex / LangChain** — transparent support; just set `dimensions` on supported embedding models

## Trade-offs

### Pros
- **Zero additional complexity** — if your embedding model supports MRL, it's a free parameter choice; no pipeline changes needed
- **Smooth quality-cost curve** — unlike fixed-dimension models, you can tune the trade-off continuously
- **Composes with everything** — the output is a standard dense vector at whatever dimension you choose; all downstream components work unchanged
- **Storage savings scale linearly** — half the dimensions = half the storage, half the memory, ~40% faster ANN search
- **Enables tiered retrieval** — different dimensions for different stages without separate models

### Cons
- **Not available on all models** — requires MRL training; older models and some code-specific models don't support it
- **Quality loss is real at extreme compression** — below ~128 dimensions, quality drops significantly; not suitable for ultra-low-dimension use
- **Front-loaded dimensions may not align with your domain** — the information ordering is optimized for the training distribution, which may not prioritize code-specific features
- **Complexity cost:** Very Low — literally just changing a `dimensions` parameter on supported models

## Composability

| Technique | Compatible? | Notes |
|-----------|------------|-------|
| Late chunking | Yes | MRL applies to the pooled chunk embeddings regardless of how they were produced |
| Binary/scalar quantization | Yes | Apply quantization after dimension truncation for compound compression |
| Hybrid BM25 + dense | Yes | MRL affects only the dense side; BM25 is unchanged |
| ColBERT/late interaction | No | ColBERT uses per-token embeddings, not pooled vectors; MRL doesn't apply |
| Reranking | Yes | Retrieval at lower dims, reranking at full dims or with cross-encoder |
| HyDE | Yes | MRL applies to the embedding of the hypothetical document |

## Verdict for Kenjutsu
- **Recommendation:** ADOPT
- **Priority:** MVP — select an MRL-capable embedding model from the start
- **Rationale:** Matryoshka is a free capability when present in the embedding model and enables important operational flexibility. Kenjutsu should prioritize MRL-capable models (Nomic, Jina v3, OpenAI v3) in the embedding model selection. This is not a technique to "add later" — it's a model selection criterion that pays dividends throughout the system's lifetime. The ability to tune precision/cost without retraining or re-indexing is especially valuable during Kenjutsu's early iteration when the optimal quality/cost balance is unknown.
