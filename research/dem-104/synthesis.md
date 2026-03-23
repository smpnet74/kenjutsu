# Kenjutsu Research Synthesis

**Date:** 2026-03-23
**Research:** 6 deliverables across competitive analysis, PR-Agent deep-dive, GitHub integration, context/RAG strategies, differentiation, and technical feasibility.

---

## The Opportunity

The AI code review market is large ($24-30/seat/month price point), well-funded (CodeRabbit $60M, Greptile $25M, Graphite $52M), and growing — but every existing tool shares the same critical flaw: **false positives are the universal adoption killer.** CodeRabbit scores 28% noise, Greptile produces 5x the false positives of CodeRabbit in benchmarks, and PR-Agent reviews are "comparable to simply prompting an LLM directly."

The market is moving from static review toward agentic review. Regulatory tailwinds (EU AI Act Aug 2026, Colorado AI Act Jun 2026) are creating enterprise demand for governance-aware tooling that no competitor currently serves.

## Key Findings

### 1. Context depth is the #1 differentiator
Greptile's benchmark: 82% bug detection with full codebase indexing vs 44% for diff-only. PR-Agent's diff-only approach is fast but shallow. Any serious entrant must solve the context problem.

### 2. AGPL kills the fork path
PR-Agent switched from Apache 2.0 to AGPL-3.0 in May 2025. Forking current PR-Agent is not viable for commercial SaaS. The v0.29 (last Apache) fork is possible but carries significant tech debt (global state, 33% type coverage, 43 bare excepts, 1.5K-line god file).

### 3. Build from scratch is the right path
Study PR-Agent's prompt engineering and diff algorithms, but build clean architecture. Estimated MVP: **10-14 weeks with 2-3 engineers**, producing a GitHub App that reviews PRs with codebase-aware context.

### 4. GitHub App is the right integration
Highest rate limits (5K-12.5K/hr), exclusive Checks API, bot identity. Content creation limit (80/min, 500/hr) is the binding constraint — requires pending review pattern and comment batching.

### 5. Three-layer context pipeline
- **Layer 1 (free):** Import graphs, co-change analysis, heuristic file expansion — always available, zero cost
- **Layer 2 (semantic):** tree-sitter AST parsing → function-level chunks → Voyage-code-3 embeddings → hybrid BM25+vector retrieval → cross-encoder reranking
- **Layer 3 (agentic):** Multi-step search for complex PRs, reference tracing, cross-repo reasoning

### 6. Our unique advantages
- **Paperclip multi-agent orchestration** — no competitor has this. Enables specialized review agents (security, performance, style) coordinated by a lead reviewer.
- **Adapter-based deployment** — self-hosted story from day one
- **Governance layer** — agent provenance, budget-aware processing, audit trails. Enterprise differentiator that no competitor offers.

## Recommended Positioning

**"High-signal, governance-aware, multi-agent code review."**

Lead with precision (win developer trust) → layer governance (enterprise sales) → differentiate with multi-agent (defensibility).

## MVP Scope (10-14 weeks)

| Component | Description |
|---|---|
| Webhook server | FastAPI, GitHub App event handling |
| GitHub provider | PyGithub, pending review pattern, Check Runs |
| Diff processor | tree-sitter AST, token-aware chunking |
| Context retriever | Layer 1 heuristics + Layer 2 embeddings |
| Review engine | LiteLLM multi-provider, self-reflection FP filter |
| Config system | `.kenjutsu.yaml` per-repo config |
| Publisher | Batched PR reviews + Check Run annotations |

**Stack:** Python, FastAPI, LiteLLM, tree-sitter, PyGithub, Pydantic
**Monthly cost:** Under $250 (infra $20-95 + LLM $5-150 for small team)
**Primary risk:** Prompt engineering iteration for <5% FP rate (budget 3-4 weeks)

## Decision Needed

This research is complete. The board should decide:

1. **Go / no-go** on building Kenjutsu
2. If go: approve moving to **architecture phase** (Chief Architect produces detailed technical spec)
3. **Team allocation** — 2-3 engineers for 10-14 week MVP

## Research Deliverables

All files in `projects/kenjutsu/research/`:
- `competitive-analysis.md` — comparison matrix (CodeRabbit, Greptile, PR-Agent)
- `pr-agent-deep-dive.md` — architecture, diff handling, AGPL finding
- `github-integration.md` — App vs Action vs webhook analysis
- `context-rag-strategies.md` — embedding, retrieval, and RAG pipeline design
- `differentiation.md` — market gaps, positioning, competitive advantages
- `technical-feasibility.md` — MVP architecture, build vs fork, cost estimates
