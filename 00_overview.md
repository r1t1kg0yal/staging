# Financial AI / MCP Competitive Feature Spec

As of 2026-03-30. Scope: public materials only. This workbook separates documented facts, strong inferences, and opaque gaps so you can use it as a diligence sheet rather than a marketing memo.

## Vendor Overview

### RavenPack / Bigdata

**Core orientation:** Retrieval-first finance data/context layer with search, KG, content enrichment, structured APIs, Research Agent, Workflows, and remote/local MCP options.

**Strongest public differentiator:** Most detailed public description of the unstructured retrieval stack: finance-tuned embeddings, cross-encoder reranking, source intelligence, novelty/freshness, contextual analytics, and a large finance KG.

**Weakest visible blind spot:** Hosted production MCP/server internals, orchestration scheduler, exact ontology governance, and evaluation/observability stack are not public.

**Public code transparency:** Medium-high

**Best comparison angle:** Use it as the benchmark for data layer + ontology + tagging + context engineering + private-content fusion.

**Key URLs:**

- https://bigdata.com/
- https://bigdata.com/blog/architecting-bigdata-com-search
- https://docs.bigdata.com/
- https://docs.bigdata.com/mcp-reference/introduction

### Anthropic Financial Services core

**Core orientation:** A workflow/orchestration shell: file-based plugins, skills, commands, and MCP connector packaging for finance use cases.

**Strongest public differentiator:** Very transparent skill/command packaging: 41 skills, 38 commands, 11 MCP integrations, plus Office-oriented workflow surfaces.

**Weakest visible blind spot:** No native financial data layer or proprietary ontology; capability depends on partner MCP servers.

**Public code transparency:** High on packaging, low on model/tool-ranking internals

**Best comparison angle:** Compare your analyst workflow shell, command system, and office-deliverable layer against it—not your raw data layer.

**Key URLs:**

- https://www.anthropic.com/news/claude-for-financial-services
- https://www.anthropic.com/news/advancing-claude-for-financial-services
- https://github.com/anthropics/financial-services-plugins/blob/main/README.md

### LSEG on Claude / MCP

**Core orientation:** Deterministic analytics + licensed content + semantic data model exposed via a remote MCP server into Claude, Excel, and PowerPoint.

**Strongest public differentiator:** Clear 'meaning layer' thesis: governed identifiers, taxonomies, analytics, yield curves, pricing, fundamentals, estimates, and Yield Book outputs as deterministic anchors.

**Weakest visible blind spot:** Less public detail on unstructured retrieval architecture, tagging pipeline, and ontology scale metrics than Bigdata.

**Public code transparency:** Medium-high on plugin layer; low on server internals

**Best comparison angle:** Use it as the benchmark for deterministic analytics, entitlements, instrument semantics, and analyst productivity in office workflows.

**Key URLs:**

- https://www.lseg.com/en/solutions/ai-finance-solutions/anthropic
- https://www.lseg.com/en/insights/ai-ready-financial-intelligence-native-in-excel-and-powerpoint-supported-by-lseg
- https://github.com/LSEG-API-Samples/lseg-claude-plugin
- https://github.com/LSEG-API-Samples/lseg-claude-plugin/blob/main/CONNECTORS.md

### Bloomberg / ASKB

**Core orientation:** Application-first, terminal-native agentic layer that orchestrates multiple agents across Bloomberg data, research, analytics, BQL, and BQuant.

**Strongest public differentiator:** ASKB is integrated directly into the Bloomberg Terminal, cites underlying sources, and emits BQL code that analysts can extend in Excel or BQuant.

**Weakest visible blind spot:** I did not find a publicly documented external customer-facing MCP server equivalent to LSEG/FactSet/S&P in the official materials reviewed.

**Public code transparency:** Medium on app layer; low on customer-facing server code

**Best comparison angle:** Use it as the benchmark for analyst workstation UX, code generation, and internally governed multi-agent infrastructure.

**Key URLs:**

- https://professional.bloomberg.com/solutions/ai/
- https://www.bloomberg.com/company/stories/closing-the-agentic-ai-productionization-gap-bloomberg-embraces-mcp/
- https://www.bloomberg.com/professional/insights/uncategorized/meet-askb-a-first-look-at-the-future-of-the-bloomberg-terminal-in-the-age-of-agentic-ai/

### S&P Global / Kensho

**Core orientation:** LLM-ready API + built-in MCP server + partner-built skills for tear sheets, earnings previews, funding digests, and data retrieval tasks.

**Strongest public differentiator:** Clean API posture for LLMs and function-calling, source-linked outputs, and direct integration into Claude/ChatGPT workflows.

**Weakest visible blind spot:** Less public detail on retrieval/reranking, ontology size, and private-content handling.

**Public code transparency:** Medium

**Best comparison angle:** Use it as the benchmark for LLM-ready data API design and source-linked structured outputs.

**Key URLs:**

- https://www.marketplace.spglobal.com/en/solutions/kensho-llm-ready-api-%28a156fe9f-5564-4f60-a624-95d8645dc98f%29
- https://press.spglobal.com/2025-07-15-S-P-Global-and-Anthropic-Announce-Integration-of-S-P-Globals-Trusted-Financial-Data-into-Claude
- https://github.com/anthropics/financial-services-plugins/blob/main/partner-built/spglobal/skills/tear-sheet/SKILL.md

### FactSet MCP

**Core orientation:** Native production-grade MCP server exposing curated FactSet datasets directly to AI systems without an intermediary warehouse/export layer.

**Strongest public differentiator:** Strong governance story: direct access, entitlements, hybrid deployment options, scope-based security, audit, and connectivity-layer controls.

**Weakest visible blind spot:** Less public visibility into workflows/skills, ontology richness, and full tool inventory than LSEG or Bigdata.

**Public code transparency:** Medium-low

**Best comparison angle:** Use it as the benchmark for enterprise MCP governance, curated datasets, and direct-data access.

**Key URLs:**

- https://developer.factset.com/mcp
- https://developer.factset.com/mcp/factset-ai-ready-data-mcp
- https://investor.factset.com/news-releases/news-release-details/factset-meets-demand-ai-ready-data-first-announce-mcp-sans/
- https://insight.factset.com/enterprise-mcp-part-3-security-and-governance

### AlphaSense

**Core orientation:** Premium-content research platform plus developer Agent API, MCP tools, pre-built skills, deep research, workflow agents, and slide generation.

**Strongest public differentiator:** Multi-agent deep research over 500M+ premium documents with citations, filters, internal-content support, and built-in slide creation.

**Weakest visible blind spot:** Low-level MCP topology, ontology details, and server internals are less public than for LSEG or Bigdata.

**Public code transparency:** Medium-low

**Best comparison angle:** Use it as the benchmark for premium-content deep research UX and report generation rather than server transparency.

**Key URLs:**

- https://developer.alpha-sense.com/api/next/getting-started
- https://www.alpha-sense.com/solutions/market-intelligence-platform/
- https://help.alpha-sense.com/hc/en-us/articles/42591266633875-Quick-Start-Guide-to-Generative-Search
- https://help.alpha-sense.com/hc/en-us/articles/42391092171795-Deep-Research-Conduct-In-Depth-Multi-Step-Research-Autonomously

---

## Legend

| Status | Meaning | Typical use in this workbook |
|--------|---------|------------------------------|
| Documented | Explicitly stated in official docs, product pages, or public source code | Treat as evidence-backed feature surface |
| Strongly inferred | Deduced from public examples, repo structure, API behavior, or architecture descriptions | Useful for design comparison, but confirm before making claims |
| Opaque / unknown | Likely exists in production but not disclosed publicly | Use as diligence gap or ask vendors directly |

## Top Takeaways

1. RavenPack / Bigdata has the richest public description of the retrieval stack itself. It exposes search, Research Agent, Workflows, content enrichment, structured APIs, a finance KG, and public code samples for custom MCP servers.

2. Anthropic's financial-services layer is not the data substrate. It is a packaging/orchestration layer for skills, commands, and partner MCP connectors.

3. LSEG is the cleanest public example of a deterministic analytics + semantic finance layer delivered through MCP into analyst workflows.

4. Bloomberg looks strongest as an integrated workstation product, but its public customer-facing MCP surface is less explicit than its internal engineering writeups.

5. FactSet and S&P/Kensho emphasize governed, LLM-ready access to licensed datasets; AlphaSense emphasizes premium-corpus research and deliverable generation.

6. For comparing your own system, use different benchmarks for different layers: Bigdata for retrieval/context, LSEG for deterministic analytics, Bloomberg for workstation UX, Anthropic for skill packaging, FactSet for governance, AlphaSense for deep-research deliverables.
