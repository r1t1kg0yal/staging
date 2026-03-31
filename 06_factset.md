# FactSet — public feature spec

*Method: each row separates what is explicitly public, what is strongly inferable, and what remains opaque.*

## Platform orientation

**Publicly documented:** FactSet markets a native, production-grade MCP server for direct access to curated financial datasets, plus broader AI-ready data and enterprise AI positioning.

**Strongly inferred:** FactSet is adapting its existing API/microservice estate into MCP as a first-class enterprise delivery channel.

**Opaque / unknown:** Detailed product decomposition beyond public marketing and architecture posts is not public.

**Why it matters for comparison:** Best benchmark for direct governed data access over MCP.

**Evidence status:** Mostly documented

**Key URLs:**

- https://developer.factset.com/mcp
- https://developer.factset.com/mcp/factset-ai-ready-data-mcp
- https://investor.factset.com/news-releases/news-release-details/factset-meets-demand-ai-ready-data-first-announce-mcp-sans/

## Data layer

**Publicly documented:** FactSet's launch materials highlight nine datasets including Fundamentals, Consensus Estimates, Ownership, M&A, Global Pricing, People, Events, Supply Chain, and Geographic Revenue Exposure. Other materials describe access to structured and unstructured data through content APIs and vector stores.

**Strongly inferred:** The MCP server is a curated front door into existing FactSet content APIs rather than a standalone greenfield system.

**Opaque / unknown:** Document/corpus scale and field-level breadth are not exhaustively enumerated in one public source.

**Why it matters for comparison:** Good comparator for breadth of enterprise-grade reference data.

**Evidence status:** Mostly documented

**Key URLs:**

- https://investor.factset.com/news-releases/news-release-details/factset-meets-demand-ai-ready-data-first-announce-mcp-sans/
- https://www.factset.com/ai

## Ontology / context layer

**Publicly documented:** FactSet emphasizes embedded context, traceability, and entitlements at the connectivity layer. Its AI pages mention content APIs and vector stores for structured and unstructured access.

**Strongly inferred:** The semantic/context layer is present but explained more from an enterprise architecture/governance perspective than from an ontology-count perspective.

**Opaque / unknown:** Public materials do not enumerate taxonomy size, entity graph counts, or point-in-time modeling specifics.

**Why it matters for comparison:** If your system has a richer publicly articulated ontology, that is a narrative edge against FactSet.

**Evidence status:** Partly documented

**Key URLs:**

- https://www.factset.com/ai
- https://insight.factset.com/modular-ai-agents-and-the-new-operating-system-of-finance

## Tagging / enrichment / unstructured data

**Publicly documented:** FactSet has discussed AI-ready unstructured data and the use of vector stores, but public MCP materials remain more focused on governed access than on a visible document-tagging/enrichment pipeline.

**Strongly inferred:** Unstructured support exists but is not the center of the public MCP story.

**Opaque / unknown:** Annotation schemas, ingest pipeline, and customer private-content workflows are not public in the reviewed sources.

**Why it matters for comparison:** Potential gap if your stack is stronger on enrichment and proprietary document handling.

**Evidence status:** Partly documented

**Key URLs:**

- https://www.factset.com/ai
- https://insight.factset.com/?_hsenc=p2ANqtz-_rXUhdZLIiM872oK6-tymXT2g_8875zkDwjMwfvfRmmU92CAb6pAaoP-abHZ-5k3ualsjd

## MCP topology / runtime stance

**Publicly documented:** FactSet describes MCP as direct, unified, AI-ready access without intermediaries and frames its server as production-grade. Thought-leadership posts describe tools/resources/prompts, proxying, controller-worker patterns, and enterprise deployment concerns.

**Strongly inferred:** FactSet is thinking about MCP as enterprise middleware sitting over an existing service mesh/API estate.

**Opaque / unknown:** Exact public tool inventory, server topology, and customer setup mechanics are less visible than with LSEG's GitHub examples.

**Why it matters for comparison:** Strong benchmark for enterprise MCP posture even if interface examples are less rich.

**Evidence status:** Mostly documented conceptually

**Key URLs:**

- https://developer.factset.com/mcp
- https://insight.factset.com/enterprise-mcp-model-context-protocol-part-two
- https://investor.factset.com/news-releases/news-release-details/factset-meets-demand-ai-ready-data-first-announce-mcp-sans/

## Security / governance

**Publicly documented:** FactSet's public MCP/security materials emphasize OAuth, fine-grained authorization, scope-based control, input validation, schema validation, rate limiting, and comprehensive audit trails. The company also stresses entitlements and hybrid/cloud/on-prem flexibility.

**Strongly inferred:** This is a flagship differentiator for FactSet's MCP story.

**Opaque / unknown:** How much of this is GA versus architectural direction is not always explicit.

**Why it matters for comparison:** If your system has strong governance, compare it directly to this row.

**Evidence status:** Strongly documented at architecture level

**Key URLs:**

- https://insight.factset.com/enterprise-mcp-part-3-security-and-governance
- https://insight.factset.com/modular-ai-agents-and-the-new-operating-system-of-finance

## Skills / workflows / outputs

**Publicly documented:** Compared with Anthropic/LSEG/Bigdata, FactSet's public materials are lighter on reusable skill packages and richer on data-access and architecture themes.

**Strongly inferred:** FactSet expects customers or partners to build higher-level workflows on top of the governed data layer.

**Opaque / unknown:** Official packaged analyst workflows and artifact-generation templates are not prominent in the reviewed sources.

**Why it matters for comparison:** Potential gap if your solution has a stronger out-of-the-box workflow shell.

**Evidence status:** Inference-heavy

**Key URLs:**

- https://developer.factset.com/mcp
- https://www.factset.com/ai

## Public code transparency

**Publicly documented:** FactSet exposes developer portals and architecture articles, but not a public GitHub repo for the server implementation in the reviewed sources.

**Strongly inferred:** Customers see the interface and architecture posture more than the code.

**Opaque / unknown:** Actual server implementation and sample client repos were not evident in the reviewed official materials.

**Why it matters for comparison:** Useful if you want to claim more transparent or open customization paths.

**Evidence status:** Mixed

**Key URLs:**

- https://developer.factset.com/mcp
- https://investor.factset.com/news-releases/news-release-details/factset-meets-demand-ai-ready-data-first-announce-mcp-sans/

## Net comparison takeaway

**Publicly documented:** FactSet is strongest publicly on governed direct-data MCP access and enterprise security framing.

**Strongly inferred:** It is a weaker public comparator for retrieval-stack sophistication or workflow packaging.

**Opaque / unknown:** Much of the actual product runtime remains closed.

**Why it matters for comparison:** Use FactSet to benchmark governance and data entitlements, not only agent UX.

**Evidence status:** Synthesis

**Key URLs:**

- https://developer.factset.com/mcp
- https://insight.factset.com/enterprise-mcp-part-3-security-and-governance
