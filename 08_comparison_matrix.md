# Cross-vendor comparison matrix

This sheet compresses the public picture into comparable dimensions. Use it to decide which vendor is the right benchmark for each layer of your own stack.

## Primary orientation

**RavenPack / Bigdata:** Retrieval-first finance data/context platform

**Anthropic FS Core:** Workflow shell + plugin packaging

**LSEG:** Deterministic analytics + licensed data over MCP

**Bloomberg:** Application-first analyst workstation

**S&P / Kensho:** LLM-ready structured-data API + MCP

**FactSet:** Governed direct-data MCP server

**AlphaSense:** Premium-content deep research platform

**Public leader:** No single leader

**Why it matters:** Different systems optimize different layers; compare like with like.

## Unstructured retrieval sophistication

**RavenPack / Bigdata:** Very explicit: finance embeddings, reranking, novelty, source intelligence, contextual analytics

**Anthropic FS Core:** Depends on partner connectors

**LSEG:** Not the public center of gravity

**Bloomberg:** Strong product evidence, thinner low-level public detail

**S&P / Kensho:** Secondary to API/data access

**FactSet:** Present, but less publicly detailed

**AlphaSense:** Very strong product-level deep research over premium corpus

**Public leader:** RavenPack / Bigdata

**Why it matters:** This is the key benchmark for grounded RAG quality.

## Structured data / deterministic analytics

**RavenPack / Bigdata:** Good breadth via structured APIs and tearsheets

**Anthropic FS Core:** Partner-dependent

**LSEG:** Excellent; curves, pricing, consensus, Yield Book, macro

**Bloomberg:** Excellent through Bloomberg datasets, BQL, analytics

**S&P / Kensho:** Strong structured data coverage

**FactSet:** Strong curated datasets

**AlphaSense:** Useful, but not the core public pitch

**Public leader:** LSEG / Bloomberg

**Why it matters:** If your system claims analyst-grade financial correctness, this row matters more than generic reasoning.

## Ontology / identifier richness

**RavenPack / Bigdata:** Very explicit KG story with point-in-time IDs

**Anthropic FS Core:** No visible proprietary ontology

**LSEG:** Strong semantic 'meaning layer' story

**Bloomberg:** Likely strong, but less quantified publicly

**S&P / Kensho:** Implied through S&P datasets, less explicit

**FactSet:** Contextual/semantic framing present but not heavily quantified

**AlphaSense:** Planning/citation layer more visible than ontology counts

**Public leader:** RavenPack / Bigdata

**Why it matters:** If your edge is semantic finance reasoning, benchmark here.

## Tagging / enrichment / annotation

**RavenPack / Bigdata:** Strongest visible tagging/enrichment pipeline for private docs

**Anthropic FS Core:** Mostly workflow-level, not native data tagging

**LSEG:** Metadata-centric contextualization

**Bloomberg:** Structured context embedded in apps

**S&P / Kensho:** Source linkage stronger than tagging story

**FactSet:** Not a major public differentiator

**AlphaSense:** Strong filtering + source control at UX level

**Public leader:** RavenPack / Bigdata

**Why it matters:** Important if your product unifies internal and external knowledge.

## Private content handling

**RavenPack / Bigdata:** Explicit Content API, connectors, tags, annotated docs

**Anthropic FS Core:** Connector-dependent

**LSEG:** Not prominent publicly

**Bloomberg:** Customer docs/workspace support exists inside products

**S&P / Kensho:** Not prominent publicly

**FactSet:** Not prominent publicly

**AlphaSense:** Supports firm data / internal content

**Public leader:** RavenPack / Bigdata / AlphaSense

**Why it matters:** This separates enterprise research platforms from simple market-data MCP servers.

## Skills / workflow packaging

**RavenPack / Bigdata:** Strong: Workflows API + published skill repo

**Anthropic FS Core:** Strongest public skill/command packaging

**LSEG:** Clear but narrower plugin/skill layer

**Bloomberg:** Internal/app-embedded workflows, not public packages

**S&P / Kensho:** Visible mainly through Anthropic partner skill(s)

**FactSet:** Less visible publicly

**AlphaSense:** Workflow agents and pre-built skills, but less code-visible

**Public leader:** Anthropic FS Core

**Why it matters:** Best benchmark for reusable analyst workflow abstractions.

## MCP surface clarity

**RavenPack / Bigdata:** Clear remote MCP docs + build-your-own path

**Anthropic FS Core:** Clear packaging for connector layer

**LSEG:** Very clear tool inventory via repo

**Bloomberg:** Internal infra clear; external customer MCP less explicit

**S&P / Kensho:** Built-in MCP exists, tool inventory less explicit

**FactSet:** Clear product stance, less public interface detail than LSEG

**AlphaSense:** Mentions MCP tools, less low-level detail

**Public leader:** RavenPack / Bigdata / LSEG

**Why it matters:** Crucial for side-by-side architecture comparisons.

## Code execution / downstream artifacts

**RavenPack / Bigdata:** Cookbooks, skills, reports, some Excel/HTML/PDF flows

**Anthropic FS Core:** Strong office/add-in and code-oriented shell

**LSEG:** Office-native retrieval and analyst workflows

**Bloomberg:** BQL output + Excel + BQuant is exceptional

**S&P / Kensho:** Python lib + Word deliverable skill

**FactSet:** Less public artifact detail

**AlphaSense:** Strong report and slide generation

**Public leader:** Bloomberg

**Why it matters:** Important if your edge is not just answers but executable/reusable output.

## Governance / entitlements / audit

**RavenPack / Bigdata:** Solid privacy claims; less explicit fine-grained governance publicly

**Anthropic FS Core:** Depends on enterprise deployment + partners

**LSEG:** Strong governed/licensed-data posture

**Bloomberg:** Very strong internal infra and identity/governance writeup

**S&P / Kensho:** Trusted-data posture, less explicit MCP security detail

**FactSet:** Strongest public MCP security/governance narrative

**AlphaSense:** Strong enterprise app posture

**Public leader:** FactSet / Bloomberg / LSEG

**Why it matters:** Mission-critical in regulated finance environments.

## Public code transparency

**RavenPack / Bigdata:** High for SDKs/examples; core server closed

**Anthropic FS Core:** Highest at packaging layer

**LSEG:** Good on plugin layer; server closed

**Bloomberg:** Low on customer-facing MCP code

**S&P / Kensho:** Medium

**FactSet:** Medium-low

**AlphaSense:** Low

**Public leader:** Anthropic FS Core

**Why it matters:** Transparency affects diligence, extensibility, and trust.

## Best benchmark use against your own stack

**RavenPack / Bigdata:** Data layer, ontology, tagging, retrieval stack

**Anthropic FS Core:** Skills, commands, office workflow shell

**LSEG:** Deterministic analytics, identifiers, licensing

**Bloomberg:** Integrated workstation UX and code handoff

**S&P / Kensho:** LLM-ready API and source-linked deliverables

**FactSet:** Governed enterprise MCP architecture

**AlphaSense:** Deep-research UX and slide/report generation

**Public leader:** Use all selectively

**Why it matters:** A serious side-by-side should benchmark each layer against the right vendor.
