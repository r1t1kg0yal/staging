# LSEG / Claude / MCP — public feature spec

*Method: each row separates what is explicitly public, what is strongly inferable, and what remains opaque.*

## Platform orientation

**Publicly documented:** LSEG positions its Anthropic integration as access to licensed data and AI-ready content via MCP, embedded in Claude and native in Excel & PowerPoint.

**Strongly inferred:** LSEG is treating MCP as a distribution layer for its existing licensed content and analytics rather than as a separate AI product stack.

**Opaque / unknown:** Internal service topology behind the MCP endpoint is not public.

**Why it matters for comparison:** Use LSEG as the benchmark for enterprise-grade data delivery into analyst workflows.

**Evidence status:** Mostly documented

**Key URLs:**

- https://www.lseg.com/en/solutions/ai-finance-solutions/anthropic
- https://www.lseg.com/en/insights/ai-ready-financial-intelligence-native-in-excel-and-powerpoint-supported-by-lseg

## Data layer

**Publicly documented:** Anthropic and LSEG state that Claude can access live market data including fixed-income pricing, equities, FX rates, macroeconomic indicators, analyst estimates, Reuters News, and content licensed through Workspace and Financial Analytics.

**Strongly inferred:** The data mix is intentionally heavy on deterministic reference/market data plus news, rather than being centered on unstructured search over a giant mixed corpus.

**Opaque / unknown:** Exact corpus breadth, freshness tiers, and any private-document ingestion path are not detailed publicly.

**Why it matters for comparison:** Critical comparator if your system claims superior structured-data depth or rights/entitlements handling.

**Evidence status:** Mostly documented

**Key URLs:**

- https://www.anthropic.com/news/advancing-claude-for-financial-services
- https://www.lseg.com/en/solutions/ai-finance-solutions/anthropic
- https://www.lseg.com/en/insights/ai-ready-financial-intelligence-native-in-excel-and-powerpoint-supported-by-lseg

## Ontology / semantic layer

**Publicly documented:** LSEG explicitly describes a 'meaning layer' / semantic depth: entities, instruments, datapoints, taxonomies, standardized definitions, identifiers, and cross-references linking issuers, securities, peers, filings, and estimates.

**Strongly inferred:** This semantic layer is what lets free-form finance questions be decomposed into precise, executable tool calls.

**Opaque / unknown:** Public materials do not disclose ontology counts, coverage statistics, or versioning details.

**Why it matters for comparison:** This is the key row if you want to contrast your ontology with LSEG's semantics.

**Evidence status:** Strongly documented conceptually

**Key URLs:**

- https://www.lseg.com/en/insights/ai-ready-financial-intelligence-native-in-excel-and-powerpoint-supported-by-lseg
- https://www.lseg.com/en/solutions/ai-finance-solutions/anthropic

## Tagging / contextualized content

**Publicly documented:** LSEG defines 'AI-ready content' and 'contextualised content' as structured, accessible, enriched with metadata such as asset class, geography, and time period.

**Strongly inferred:** LSEG's tagging layer is metadata-centric and tied to data governance and instrument semantics rather than being marketed as open-ended document tagging.

**Opaque / unknown:** Public docs do not explain whether customers can inject their own tagged corpora or extend LSEG taxonomies.

**Why it matters for comparison:** If your system allows richer user-defined tagging or private ontology extension, that is an important differentiator.

**Evidence status:** Mostly documented conceptually

**Key URLs:**

https://www.lseg.com/en/solutions/ai-finance-solutions/anthropic

## Deterministic analytics layer

**Publicly documented:** LSEG emphasizes that fundamentals, macro series, validated consensus, yield curve analytics, spread duration, and Yield Book outputs are deterministic anchors around which Claude reasons.

**Strongly inferred:** The LSEG stack deliberately separates probabilistic language synthesis from calculation-sensitive financial analytics.

**Opaque / unknown:** The full computation graph, method provenance per tool, and latency/caching policies are not public.

**Why it matters for comparison:** This is where LSEG is strongest relative to generic RAG systems.

**Evidence status:** Strongly documented

**Key URLs:**

https://www.lseg.com/en/insights/ai-ready-financial-intelligence-native-in-excel-and-powerpoint-supported-by-lseg

## MCP server / tool topology

**Publicly documented:** The public GitHub plugin uses a single MCP server URL and exposes tools such as bond_price, bond_future_price, fx_spot_price, fx_forward_price, interest_rate_curve, inflation_curve, credit_curve, vol surfaces, option_value, qa_company_fundamentals, qa_ibes_consensus, qa_historical_equity_price, qa_macroeconomic, tscc historical pricing, and Yield Book tools.

**Strongly inferred:** LSEG is exposing multiple backend analytics/data services through one MCP surface and one plugin package.

**Opaque / unknown:** Server implementation, tool auth model, multi-tenant architecture, and versioning are not public.

**Why it matters for comparison:** This row is central if you want to compare tool breadth and quantitative coverage.

**Evidence status:** Strongly documented at interface level

**Key URLs:**

- https://github.com/LSEG-API-Samples/lseg-claude-plugin/blob/main/.mcp.json
- https://github.com/LSEG-API-Samples/lseg-claude-plugin/blob/main/CONNECTORS.md

## Skills / workflows

**Publicly documented:** LSEG publishes a Claude plugin repo with 8 high-level workflows/commands covering fixed income, FX, equities, and macro. The equity-research skill tells Claude to let tools provide the data and synthesize the thesis.

**Strongly inferred:** The public repo is a thin but useful map of how LSEG expects users to chain deterministic tools into narratives.

**Opaque / unknown:** Server-side workflow enhancements, hidden prompts, or production client differences are not public.

**Why it matters for comparison:** Good comparator for tool-anchored research workflows.

**Evidence status:** Mostly documented

**Key URLs:**

- https://github.com/LSEG-API-Samples/lseg-claude-plugin
- https://github.com/LSEG-API-Samples/lseg-claude-plugin/blob/main/commands/research-equity.md
- https://github.com/LSEG-API-Samples/lseg-claude-plugin/blob/main/skills/equity-research/SKILL.md

## Code execution / analyst outputs

**Publicly documented:** LSEG's materials stress that users can retrieve and structure LSEG content through natural language directly in Excel and PowerPoint via Claude. The plugin examples also organize data retrieval first, thesis-writing second.

**Strongly inferred:** LSEG is optimizing for office-native analyst workflows rather than a standalone research UI.

**Opaque / unknown:** Specific export formats, workbook generation logic, and code execution runtimes are not public.

**Why it matters for comparison:** If your system outputs analyst-ready artifacts better than office-native copilot flows, highlight that explicitly.

**Evidence status:** Mostly documented

**Key URLs:**

- https://www.lseg.com/en/insights/ai-ready-financial-intelligence-native-in-excel-and-powerpoint-supported-by-lseg
- https://github.com/LSEG-API-Samples/lseg-claude-plugin

## Security / governance / licensing

**Publicly documented:** LSEG repeatedly emphasizes licensing governance, trusted content, governed services, and secure access via MCP. Its value proposition is that the same rights/licensing structure remains intact in AI workflows.

**Strongly inferred:** This is a major differentiator versus ad hoc data scraping or generic RAG.

**Opaque / unknown:** Public materials do not detail scope models, audit primitives, or entitlement enforcement mechanics.

**Why it matters for comparison:** Important benchmark if your system claims institutional production readiness.

**Evidence status:** Strongly documented at principle level

**Key URLs:**

- https://www.lseg.com/en/solutions/ai-finance-solutions/anthropic
- https://www.lseg.com/en/insights/ai-ready-financial-intelligence-native-in-excel-and-powerpoint-supported-by-lseg

## Public code transparency

**Publicly documented:** The command/skill layer is public on GitHub and is enough to infer tool coverage and user workflow design.

**Strongly inferred:** The public repo is illustrative rather than a full mirror of production LSEG infrastructure.

**Opaque / unknown:** The actual remote MCP service and backend analytics stack are closed.

**Why it matters for comparison:** You can compare interface design, but not the hidden server implementation.

**Evidence status:** Mixed

**Key URLs:**

https://github.com/LSEG-API-Samples/lseg-claude-plugin

## Net comparison takeaway

**Publicly documented:** LSEG is the clearest public comparator for governed deterministic analytics via MCP.

**Strongly inferred:** It is a weaker comparator for open-ended unstructured retrieval or user-authored private content workflows than Bigdata or AlphaSense.

**Opaque / unknown:** Any additional internal retrieval stack is not visible from public sources.

**Why it matters for comparison:** Frame your side-by-side against LSEG around exactness, semantic identifiers, entitlements, and quant tool depth.

**Evidence status:** Synthesis

**Key URLs:**

- https://www.lseg.com/en/solutions/ai-finance-solutions/anthropic
- https://github.com/LSEG-API-Samples/lseg-claude-plugin
