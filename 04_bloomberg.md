# Bloomberg — public feature spec

*Method: each row separates what is explicitly public, what is strongly inferable, and what remains opaque.*

## Platform orientation

**Publicly documented:** Bloomberg's flagship AI surface is ASKB, a conversational interface in beta on the Bloomberg Terminal that coordinates a network of AI agents over Bloomberg data, research, analytics, and news.

**Strongly inferred:** Bloomberg is leading with an integrated workstation experience rather than a public 'MCP-first' API narrative.

**Opaque / unknown:** The precise external product decomposition behind ASKB is not public.

**Why it matters for comparison:** Use Bloomberg as the benchmark for integrated analyst workstation UX.

**Evidence status:** Mostly documented

**Key URLs:**

- https://professional.bloomberg.com/solutions/ai/
- https://www.bloomberg.com/professional/insights/uncategorized/meet-askb-a-first-look-at-the-future-of-the-bloomberg-terminal-in-the-age-of-agentic-ai/

## Data layer

**Publicly documented:** Bloomberg says ASKB draws on hundreds of millions of documents, 800+ research providers, Bloomberg Intelligence / Economics / NEF research, and AI News Summaries spanning 30,000+ sources.

**Strongly inferred:** The data substrate is enormous and deeply tied to Bloomberg's existing terminal content/entitlement system.

**Opaque / unknown:** Public materials do not expose the index architecture, freshness design, or customer-accessible tool schemas.

**Why it matters for comparison:** Good benchmark for corpus scale and integrated research depth.

**Evidence status:** Mostly documented

**Key URLs:**

https://professional.bloomberg.com/solutions/ai/

## Ontology / knowledge graph

**Publicly documented:** Bloomberg product pages emphasize grounded answers and transparent attribution, while Bloomberg engineering/ML writeups discuss knowledge-graph-based contextual entity retrieval in news and search.

**Strongly inferred:** Bloomberg almost certainly uses a deep internal entity/relationship layer, but it is not quantified publicly in the reviewed customer-facing materials.

**Opaque / unknown:** Entity counts, taxonomy sizes, versioning, and graph APIs are not public in the reviewed sources.

**Why it matters for comparison:** Bloomberg likely has strong semantics, but the public evidence is thinner than Bigdata's or LSEG's explicit ontology story.

**Evidence status:** Partly documented

**Key URLs:**

- https://professional.bloomberg.com/solutions/ai/
- https://www.bloomberg.com/company/stories/closing-the-agentic-ai-productionization-gap-bloomberg-embraces-mcp/

## Tagging / structured context

**Publicly documented:** Bloomberg markets transparent attribution, Document Workspace that turns multiple docs into structured insight tables, Document Search with citations, Company Financials views, and IB chat parsing into structured data.

**Strongly inferred:** Contextualization is heavily integrated into product workflows and metadata systems, even if not documented as a standalone 'tagging layer'.

**Opaque / unknown:** The underlying annotation schema and whether customers can extend the tagging/ontology layer are not public.

**Why it matters for comparison:** If your system lets users explicitly control or extend context metadata, highlight that against Bloomberg's more app-native abstraction.

**Evidence status:** Partly documented

**Key URLs:**

https://professional.bloomberg.com/solutions/ai/

## MCP / tools infrastructure

**Publicly documented:** Bloomberg engineering states it aligned with MCP after building an internal tool protocol. The architecture described publicly is remote-first and multi-tenant, with identity-aware middleware, client-side proxying for SSO/auth, access control, observability, rate limiting, metering, and AI guardrails.

**Strongly inferred:** Bloomberg treats MCP as enterprise infrastructure across product teams, not just as a developer integration gimmick.

**Opaque / unknown:** I did not find a publicly documented external customer-facing remote MCP server analogous to LSEG/FactSet/S&P in the official materials reviewed.

**Why it matters for comparison:** Bloomberg is the benchmark for production-grade internal MCP governance, but not for public external server transparency.

**Evidence status:** Strong on internal infra, weaker on external product surface

**Key URLs:**

https://www.bloomberg.com/company/stories/closing-the-agentic-ai-productionization-gap-bloomberg-embraces-mcp/

## Skills / workflows

**Publicly documented:** ASKB is described as coordinating multiple specialized agents in parallel. Bloomberg does not market external 'skills' packages the way Anthropic/LSEG/Bigdata do in the sources reviewed.

**Strongly inferred:** Bloomberg's workflow layer is embedded in application experiences rather than exposed as reusable markdown-based skill repos.

**Opaque / unknown:** The internal skill registry, tool taxonomy, and prompting assets are not public.

**Why it matters for comparison:** Good place to show if your architecture externalizes skills more cleanly than Bloomberg.

**Evidence status:** Mixed

**Key URLs:**

- https://professional.bloomberg.com/solutions/ai/
- https://www.bloomberg.com/company/stories/closing-the-agentic-ai-productionization-gap-bloomberg-embraces-mcp/

## Code execution / outputs

**Publicly documented:** ASKB returns underlying Bloomberg Query Language (BQL) code for data analysis so users can extend work in Excel, BQuant Desktop, or BQuant Enterprise. Bloomberg also supports Pythonic workflows through BQuant.

**Strongly inferred:** This is a major differentiator: the AI layer can hand off into executable analyst code within Bloomberg's environment.

**Opaque / unknown:** The full code-execution safeguards and runtime controls are not public.

**Why it matters for comparison:** Benchmark your code-to-analysis handoff and artifact path against BQL/BQuant.

**Evidence status:** Mostly documented

**Key URLs:**

- https://professional.bloomberg.com/solutions/ai/
- https://www.bloomberg.com/company/stories/bquant-behind-the-scenes-how-bloomberg-leveled-the-playing-field-for-quantitative-analysis-in-finance/

## Security / governance

**Publicly documented:** Bloomberg's MCP engineering writeup highlights identity exchange, token/data isolation, authn/authz, observability, policy enforcement, rate limiting, and guardrails for enterprise deployments.

**Strongly inferred:** This governance stack is a core reason Bloomberg can move agentic tooling into production safely.

**Opaque / unknown:** Specific customer-admin controls and tool-level scopes are not public in the reviewed materials.

**Why it matters for comparison:** This is where Bloomberg sets a high bar operationally even if the public interface is less explicit.

**Evidence status:** Strongly documented at infra principle level

**Key URLs:**

https://www.bloomberg.com/company/stories/closing-the-agentic-ai-productionization-gap-bloomberg-embraces-mcp/

## Public code / external ecosystem

**Publicly documented:** Bloomberg publishes API bindings (e.g., BLPAPI libraries) and there are community MCP wrappers for BLPAPI and Hypermedia API. In the reviewed official materials, I did not find an official public GitHub repo for a customer-facing Bloomberg MCP server.

**Strongly inferred:** Developers can build Bloomberg-adjacent MCP layers, but official external MCP packaging is less open than Anthropic/LSEG/Bigdata.

**Opaque / unknown:** Any private beta / partner-only customer-facing MCP surfaces are not publicly clear from the reviewed sources.

**Why it matters for comparison:** Important if you want to claim better transparency or easier self-hosting than Bloomberg.

**Evidence status:** Mixed

**Key URLs:**

- https://github.com/bloomberg/blpapi-node
- https://professional.bloomberg.com/solutions/ai/

## Net comparison takeaway

**Publicly documented:** Bloomberg is strongest publicly as a vertically integrated analyst environment with AI agents, citations, BQL output, and enterprise infra.

**Strongly inferred:** It is not the cleanest public comparator for external MCP server architecture because that layer is less openly documented.

**Opaque / unknown:** Many of Bloomberg's deepest advantages likely remain behind product and entitlement boundaries.

**Why it matters for comparison:** Compare your system to Bloomberg on workstation UX and code handoff, not only on MCP transparency.

**Evidence status:** Synthesis

**Key URLs:**

- https://professional.bloomberg.com/solutions/ai/
- https://www.bloomberg.com/company/stories/closing-the-agentic-ai-productionization-gap-bloomberg-embraces-mcp/
