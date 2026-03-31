# RavenPack / Bigdata — public feature spec

*Method: each row separates what is explicitly public, what is strongly inferable, and what remains opaque.*

## Platform orientation / product surface

**Publicly documented:** Bigdata is presented as RavenPack's advanced agentic AI platform and as the 'definitive data layer for AI in finance'. Public surfaces include the Assistant, Search Service, Research Agent, Workflows API, Structured Data APIs, Content API, remote MCP integrations, and Bigdata docs tooling.

**Strongly inferred:** The commercial platform is designed as a retrieval-and-grounding substrate that can feed both hosted agents and external MCP clients, not merely as a chat frontend.

**Opaque / unknown:** Server-side orchestration, scheduler/runtime topology, provider routing, evaluation loop, and internal infra beyond public docs are not disclosed.

**Why it matters for comparison:** If your system is differentiated at the data/context layer, this is the closest public benchmark.

**Evidence status:** Mostly documented

**Key URLs:**

- https://bigdata.com/
- https://docs.bigdata.com/
- https://docs.bigdata.com/app/introduction
- https://docs.bigdata.com/getting-started/introduction

## Data layer

**Publicly documented:** The Assistant docs say Bigdata spans 13,500+ financially relevant web sources, SEC filings, transcripts for 40,000 listed companies, premium/gated content (including RavenPack, FactSet, MT Newswires, Benzinga, The Fly, Alliance News, FXStreet, LinkUp), and internal enterprise sources such as file servers, eComms, CRM, ERP, and BI tools. Separate Structured Data APIs expose company, market, analyst, ESG, holdings, and financial data.

**Strongly inferred:** The platform is intentionally multi-modal across structured datasets, indexed documents, and private corpora, with a shared identity/context layer.

**Opaque / unknown:** Exact freshness SLAs, partner-specific field coverage, normalization logic, and internal storage layout are not public.

**Why it matters for comparison:** Use this row to benchmark breadth of licensed + public + private content in your own stack.

**Evidence status:** Documented + some inference

**Key URLs:**

- https://docs.bigdata.com/app/introduction
- https://docs.bigdata.com/structured-data/introduction
- https://docs.bigdata.com/api-rest/content_introduction

## Ontology / knowledge graph

**Publicly documented:** Bigdata describes a proprietary Knowledge Graph with more than 12 million entities, 30+ entity types, point-in-time-aware IDs, and more than 7,000 event/topic categories. KG docs also state it tracks 7M+ companies and resolves aliases / identifiers.

**Strongly inferred:** The KG acts as the canonical semantic spine joining search, filters, entity resolution, structured data, and tearsheets.

**Opaque / unknown:** Ontology governance, update cadence, edge taxonomy, versioning, and full schema cardinality are not public.

**Why it matters for comparison:** This is one of the strongest public ontology comparators in finance AI.

**Evidence status:** Mostly documented

**Key URLs:**

- https://bigdata.com/blog/architecting-bigdata-com-search
- https://docs.bigdata.com/getting-started/knowledge_graph/introduction
- https://docs.bigdata.com/api-reference/companies/find-by-details

## Tagging / annotation / enrichment

**Publicly documented:** Private content is enriched into annotated JSON with entities, sentences, and sentiment. Documents can be tagged and filtered by tags; docs mention examples such as sender/recipient for email content. Content API docs cover connectors, documents, and tags. Uploaded content has both an original file and a structured annotated representation.

**Strongly inferred:** Tagging is not just user metadata; it appears integrated into the retrieval/filter layer so private docs can be queried like first-class content.

**Opaque / unknown:** The exact annotation schema, custom taxonomy extension path, and whether users can author ontology-level tags versus only document metadata are not public.

**Why it matters for comparison:** If your system has a superior enrichment pipeline, compare it against this row carefully.

**Evidence status:** Mostly documented

**Key URLs:**

- https://docs.bigdata.com/api-rest/content_introduction
- https://docs.bigdata.com/api-reference/documents/upload-document
- https://docs.bigdata.com/release-notes/api_changelog
- https://docs.bigdata.com/how-to-guides/search_in_uploaded_files

## Context layer / retrieval architecture

**Publicly documented:** Bigdata's search architecture blog describes multiple ranking layers: deep semantics, KG grounding, source intelligence, novelty/freshness, and contextual analytics. It uses finance-tuned embeddings, contrastive learning on financial corpora/QA pairs, cross-encoder reranking, proprietary event/topic taxonomies, and Vespa for billion-scale vector search. Search docs also expose content diversification and smart versus fast modes.

**Strongly inferred:** The 'context layer' is engineered as a ranking stack, not just a vector store, and likely determines much of Bigdata's edge relative to generic RAG.

**Opaque / unknown:** Reranker model identities, training data composition, offline evaluation metrics, and query routing thresholds are not public.

**Why it matters for comparison:** This is the most important row if your claimed edge is context engineering or grounded reasoning quality.

**Evidence status:** Strongly documented

**Key URLs:**

- https://bigdata.com/blog/architecting-bigdata-com-search
- https://docs.bigdata.com/api-reference/search/search-documents
- https://docs.bigdata.com/getting-started/search/overview
- https://docs.bigdata.com/release-notes/api_changelog

## Research Agent / conversational layer

**Publicly documented:** Bigdata publicly separates Research Agent from Search. Research Agent is described as conversational RAG for reasoning and analysis; search is retrieval-only. The Research Agent quickstart supports lite and standard research effort, where standard performs multi-step Deep Research. Streaming responses include usage accounting.

**Strongly inferred:** The hosted Research Agent likely performs planning over the same underlying search/KG/content substrate rather than relying on a generic chat pipeline.

**Opaque / unknown:** The actual planner, model orchestration, prompt chain, and memory management are not public.

**Why it matters for comparison:** Useful when comparing your hosted agent versus a lower-level tool API.

**Evidence status:** Mostly documented

**Key URLs:**

- https://docs.bigdata.com/getting-started/introduction
- https://docs.bigdata.com/getting-started/quickstart_guide_research_agent

## Workflows / skills

**Publicly documented:** Bigdata distinguishes templated Workflows API from conversational Research Agent. Public release notes describe Jinja2-templated prompts, parameterized inputs, research plans, model selection, community templates, and workflow CRUD. Bigdata also publishes a Financial Research Analyst skill that automates company briefs, earnings previews/digests, risk assessments, investment memos, and pitch content.

**Strongly inferred:** Workflows are the repeatability layer, while skills are reusable client-side packaging around MCP tools and templates.

**Opaque / unknown:** The internal workflow runtime, scheduling, approval logic, and benchmarking across models are not public.

**Why it matters for comparison:** Benchmark your repeatable research automation layer against this—not just the chat UX.

**Evidence status:** Documented + inferred

**Key URLs:**

- https://docs.bigdata.com/getting-started/introduction
- https://docs.bigdata.com/release-notes/api_changelog
- https://github.com/Bigdata-com/skills-financial-research-analyst/blob/main/README.md

## MCP server / tools

**Publicly documented:** The MCP reference documents remote tools such as bigdata_search, find_companies, bigdata_events_calendar, bigdata_company_tearsheet, bigdata_country_tearsheet, bigdata_market_tearsheet, plus a docs-assistant tool. Bigdata also launched a separate remote MCP endpoint for OpenAI Deep Research with search/fetch tools and tool-call visibility.

**Strongly inferred:** Bigdata is operating more than one hosted MCP surface, tailored to different client experiences.

**Opaque / unknown:** The production hosted server code, auth architecture beyond API-key/OAuth integration surfaces, internal transport topology, and scaling approach are not public.

**Why it matters for comparison:** Good benchmark for breadth of MCP-exposed finance tools and agent-ready surfaces.

**Evidence status:** Mostly documented

**Key URLs:**

- https://docs.bigdata.com/mcp-reference/introduction
- https://docs.bigdata.com/mcp-reference/introduction
- https://bigdata.com/

## Custom MCP / public code execution path

**Publicly documented:** Bigdata publishes a 'Build your own MCP' cookbook showing a local FastMCP server using bigdata-research-tools and bigdata-client, with examples such as watchlist management, thematic screening, and concurrent search. Public repos exist for bigdata-cookbook, bigdata-research-tools, briefs, and skill packages.

**Strongly inferred:** Bigdata wants customers to treat its search/services as building blocks inside custom agents, not only inside its hosted app.

**Opaque / unknown:** There is no public repo for the official hosted MCP server itself.

**Why it matters for comparison:** This row is critical for comparing how easy it is to recompose the stack into your own architecture.

**Evidence status:** Strongly documented

**Key URLs:**

- https://docs.bigdata.com/use-cases/research-tools/build-your-own-mcp
- https://github.com/Bigdata-com/bigdata-research-tools/blob/main/README.md
- https://github.com/Bigdata-com/bigdata-cookbook

## Structured tools / tearsheets / analytics

**Publicly documented:** Bigdata exposes structured endpoints and MCP tools for company/country/market tearsheets, company profiles, screeners, financial statements, key metrics, ESG scores, events calendars, analyst estimates/ratings, earnings surprise, and holdings data.

**Strongly inferred:** The tearsheet tools are aggregation/orchestration layers on top of multiple structured APIs and KG lookups.

**Opaque / unknown:** Computation methodology for each tearsheet tile and any proprietary factor models are not public.

**Why it matters for comparison:** Important if your system blends generative reasoning with deterministic reference data.

**Evidence status:** Mostly documented

**Key URLs:**

- https://docs.bigdata.com/structured-data/introduction
- https://docs.bigdata.com/mcp-reference/introduction

## Security / governance / privacy

**Publicly documented:** Docs state user data is not used for model training; enterprise security references include ISO 27001 and SOC 2 expected by year-end. Private content can be uploaded, indexed, queried, and deleted along with its annotated and chunked representations.

**Strongly inferred:** The platform is meant for enterprise deployment where source control and context scoping matter as much as answer quality.

**Opaque / unknown:** Fine-grained entitlements, row/field-level ACLs, audit logging, and policy controls are not described at the same depth as FactSet or Bloomberg engineering materials.

**Why it matters for comparison:** Use this row to see whether your governance story is more enterprise-explicit than Bigdata's public materials.

**Evidence status:** Partly documented

**Key URLs:**

- https://docs.bigdata.com/app/introduction
- https://docs.bigdata.com/api-rest/content_introduction

## Public code / SDKs / packages

**Publicly documented:** Bigdata exposes at least two SDK paths publicly: bigdata-client and bigdata-research-tools. The GitHub org also contains cookbooks and downstream packages such as briefs and skills. Legacy RavenPack python-api remains public as well.

**Strongly inferred:** The public code is intentionally positioned as a customer-extensible ecosystem, but only at the SDK/examples layer.

**Opaque / unknown:** No public source for core hosted retrieval infrastructure, event extraction pipeline, or official remote MCP runtime.

**Why it matters for comparison:** This row helps you frame 'how much of the platform is inspectable/rebuildable by customers'.

**Evidence status:** Documented + opaque core

**Key URLs:**

- https://github.com/Bigdata-com/bigdata-research-tools/blob/main/README.md
- https://github.com/Bigdata-com/bigdata-cookbook
- https://github.com/Bigdata-com/skills-financial-research-analyst/blob/main/README.md
- https://github.com/RavenPack/python-api

## Public-doc caveats / unresolved mismatches

**Publicly documented:** Public docs cite 7,000+ event/topic categories in some places and 2,400 topics in topic-filter docs. Both appear official.

**Strongly inferred:** The most likely explanation is that 'categories' refers to the full taxonomy while filterable 'topics' are a subset or a different namespace.

**Opaque / unknown:** The authoritative ontology count and crosswalk are not publicly clarified.

**Why it matters for comparison:** When you build your own spec, separate category counts, topic counts, and operational filter namespaces so your architecture looks cleaner and more rigorous.

**Evidence status:** Needs diligence

**Key URLs:**

- https://bigdata.com/blog/architecting-bigdata-com-search
- https://docs.bigdata.com/getting-started/search/query_filters
