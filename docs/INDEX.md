# Kenjutsu — Research & Decision Index

## Research Deliverables

| # | Document | Description | Status |
|---|----------|-------------|--------|
| 1 | [Synthesis](../research/synthesis.md) | Executive summary of all research — key findings, recommended positioning, and strategic next steps | Review |
| 2 | [Competitive Analysis](../research/competitive-analysis.md) | Comparison of CodeRabbit, Greptile, and PR-Agent/Qodo Merge across architecture, pricing, strengths, and weaknesses | Review |
| 3 | [PR-Agent Deep-Dive](../research/pr-agent-deep-dive.md) | End-to-end architecture analysis of PR-Agent, AGPL license implications, and fork vs. build evaluation | Review |
| 4 | [GitHub Integration](../research/github-integration.md) | GitHub App vs. Action vs. raw webhooks — rate limits, API access, deployment trade-offs | Review |
| 5 | [Context & RAG Strategies](../research/context-rag-strategies.md) | Codebase indexing approaches — AST parsing, embedding models, hybrid retrieval, and the cost of blind vector stuffing | Review |
| 6 | [Differentiation](../research/differentiation.md) | Market positioning analysis — false positive problem, governance gap, and Paperclip multi-agent advantage | Review |
| 7 | [Technical Feasibility](../research/technical-feasibility.md) | MVP architecture, build-from-scratch recommendation, 10-14 week estimate, and primary technical risks | Review |

## How to Read This Research

**Start here:** [Synthesis](../research/synthesis.md) is the executive summary. It distills the key findings from all six research deliverables into a single document — read it first to understand the opportunity, the recommended approach, and our unique advantages.

**Then drill into what matters to you:**

- **"What does the competitive landscape look like?"** → [Competitive Analysis](../research/competitive-analysis.md) — detailed comparison matrix of the three main players, their architectures, pricing, and where they fall short.

- **"Can we fork PR-Agent?"** → [PR-Agent Deep-Dive](../research/pr-agent-deep-dive.md) — the answer is no (AGPL license), but the architecture and prompt engineering are worth studying. This document explains exactly what to learn and what to avoid.

- **"How do we integrate with GitHub?"** → [GitHub Integration](../research/github-integration.md) — GitHub App is the recommended primary integration. This covers rate limits, the Checks API, content creation constraints, and why a GitHub Action makes sense as a secondary option.

- **"How do we make reviews actually good?"** → [Context & RAG Strategies](../research/context-rag-strategies.md) — full codebase context is the #1 quality differentiator (82% vs 44% bug detection). This covers the three-layer context pipeline: cheap heuristics, semantic retrieval, and agentic search.

- **"What makes us different?"** → [Differentiation](../research/differentiation.md) — Paperclip multi-agent orchestration, governance/compliance readiness, and the self-hosted story. These are capabilities no current competitor offers.

- **"Can we actually build this?"** → [Technical Feasibility](../research/technical-feasibility.md) — yes. MVP is 10-14 weeks with 2-3 engineers. This document covers the architecture, infrastructure requirements, and the primary risk (prompt engineering iteration for false positive rates).
