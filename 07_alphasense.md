# AlphaSense — public feature spec

*Method: each row separates what is explicitly public, what is strongly inferable, and what remains opaque.*

## Platform orientation

**Publicly documented:** AlphaSense positions itself as a market-intelligence and research platform with Generative Search, Deep Research, Workflow Agents, Slide Builder, and a developer Agent API with MCP tools and pre-built skills.

**Strongly inferred:** This is an integrated premium-content research stack with developer access layered on top.

**Opaque / unknown:** Internal runtime decomposition is not public.

**Why it matters for comparison:** Benchmark your research UX and premium-content orchestration against this.

**Evidence status:** Mostly documented

**Key URLs:**

- https://developer.alpha-sense.com/api/next/getting-started
- https://www.alpha-sense.com/solutions/market-intelligence-platform/

## Data layer

**Publicly documented:** AlphaSense says it retrieves and reasons across 500M+ premium documents and data points, including filings, transcripts, sell-side research, expert interviews, financials, and other structured and unstructured sources. It also supports firm/internal data in enterprise workflows.

**Strongly inferred:** The platform's edge is corpus breadth plus premium content rather than a public financial analytics API inventory.

**Opaque / unknown:** The exact dataset decomposition and normalization internals are not public.

**Why it matters for comparison:** Important comparator if your system competes on research corpus quality.

**Evidence status:** Mostly documented

**Key URLs:**

- https://www.alpha-sense.com/solutions/market-intelligence-platform/
- https://help.alpha-sense.com/hc/en-us/articles/41666587181203-Interacting-with-Generative-Search

## Ontology / context layer

**Publicly documented:** Generative Search creates a research plan and coordinates multiple specialized agents to gather and synthesize information from trusted sources, returning structured cited deliverables.

**Strongly inferred:** AlphaSense has a strong context/planning layer, but it is explained more as multi-agent research planning than as a public knowledge-graph specification.

**Opaque / unknown:** Ontology counts, identifier systems, and graph/taxonomy details are not public in the reviewed sources.

**Why it matters for comparison:** If your semantic layer is explicit and inspectable, that is a point of contrast.

**Evidence status:** Partly documented

**Key URLs:**

- https://help.alpha-sense.com/hc/en-us/articles/41666587181203-Interacting-with-Generative-Search
- https://help.alpha-sense.com/hc/en-us/articles/42591266633875-Quick-Start-Guide-to-Generative-Search

## Tagging / filters / user control

**Publicly documented:** Users can define companies, industries, document types, and sources, or rely on natural-language filtering. AlphaSense also supports internal documents/firm data and lets users verify citations directly.

**Strongly inferred:** The context layer is strongly filterable and user-steerable even if public docs do not expose a raw tagging schema.

**Opaque / unknown:** Custom metadata extension, ontology authoring, and low-level annotation pipelines are not public.

**Why it matters for comparison:** Useful for comparing user-controlled scoping and source governance.

**Evidence status:** Mostly documented at UX level

**Key URLs:**

- https://help.alpha-sense.com/hc/en-us/articles/42591266633875-Quick-Start-Guide-to-Generative-Search
- https://www.alpha-sense.com/solutions/market-intelligence-platform/

## Deep Research / workflow agents

**Publicly documented:** Deep Research may run 50-100 searches, cite 100+ sources, and produce structured reports. AlphaSense also offers Workflow Agents, custom/scheduled agents, and agent creation from a response.

**Strongly inferred:** This is one of the strongest public multi-agent deep-research experiences in the market.

**Opaque / unknown:** Planner internals, model routing, and evaluation metrics are not public.

**Why it matters for comparison:** Strong comparator for autonomous research/report-generation workflows.

**Evidence status:** Mostly documented

**Key URLs:**

- https://help.alpha-sense.com/hc/en-us/articles/42391092171795-Deep-Research-Conduct-In-Depth-Multi-Step-Research-Autonomously
- https://help.alpha-sense.com/hc/en-us/articles/42591266633875-Quick-Start-Guide-to-Generative-Search

## MCP tools / developer API

**Publicly documented:** The developer portal describes an Agent API with GenSearch, ThinkLonger, DeepResearch, MCP tools, and pre-built Skills.

**Strongly inferred:** AlphaSense exposes some of its internal product capabilities through a developer layer, but the public MCP topology is less explicit than LSEG's or FactSet's.

**Opaque / unknown:** Tool inventory, transport, and deployment/topology details are not public in the reviewed sources.

**Why it matters for comparison:** Good comparator for app-to-API continuity, weaker one for low-level server transparency.

**Evidence status:** Partly documented

**Key URLs:**

https://developer.alpha-sense.com/api/next/getting-started

## Code execution / deliverables

**Publicly documented:** AlphaSense can create slide decks from responses, generate reports, and let users create agents from research outputs.

**Strongly inferred:** Artifact generation is a prominent part of the product value proposition.

**Opaque / unknown:** Arbitrary code execution and notebook/runtime surfaces are not public in the reviewed materials.

**Why it matters for comparison:** Strong comparator for report/slide generation, weaker for open compute environments.

**Evidence status:** Mostly documented

**Key URLs:**

https://help.alpha-sense.com/hc/en-us/articles/42591266633875-Quick-Start-Guide-to-Generative-Search

## Security / enterprise readiness

**Publicly documented:** AlphaSense cites enterprise SSO, SOC 2 Type II, private cloud availability, and traceable source attribution.

**Strongly inferred:** Security is productized at the application layer rather than exposed as a richly public MCP architecture story.

**Opaque / unknown:** Fine-grained MCP authz and tool-level policy controls are not public.

**Why it matters for comparison:** Use this row to compare app-level enterprise readiness.

**Evidence status:** Mostly documented

**Key URLs:**

- https://www.alpha-sense.com/solutions/market-intelligence-platform/
- https://developer.alpha-sense.com/api/next/getting-started

## Public code transparency

**Publicly documented:** AlphaSense has developer docs, but not the kind of public GitHub skill/server repos that Anthropic, LSEG, or Bigdata expose.

**Strongly inferred:** The platform is optimized for managed product usage rather than code-level inspectability.

**Opaque / unknown:** Core runtime and tool implementation remain closed.

**Why it matters for comparison:** Potential differentiator if your system is more transparent or easier to extend.

**Evidence status:** Mixed

**Key URLs:**

https://developer.alpha-sense.com/api/next/getting-started

## Net comparison takeaway

**Publicly documented:** AlphaSense is strongest publicly on premium-corpus deep research, multi-agent report generation, and slide outputs.

**Strongly inferred:** It is a weaker public comparator for explicit ontology design or external MCP server transparency.

**Opaque / unknown:** A large amount of the technical stack remains productized rather than openly described.

**Why it matters for comparison:** Use AlphaSense to benchmark deep-research UX and deliverables.

**Evidence status:** Synthesis

**Key URLs:**

- https://www.alpha-sense.com/solutions/market-intelligence-platform/
- https://help.alpha-sense.com/hc/en-us/articles/42391092171795-Deep-Research-Conduct-In-Depth-Multi-Step-Research-Autonomously
