# SP / Kensho — public feature spec

*Method: each row separates what is explicitly public, what is strongly inferable, and what remains opaque.*

## Platform orientation

**Publicly documented:** Kensho's LLM-ready API is marketed as an S&P Global solution optimized for LLMs and natural-language querying, with a built-in MCP server for MCP-compatible systems.

**Strongly inferred:** S&P/Kensho is productizing a cleaner data/API layer for LLMs rather than a full terminal-like analyst environment.

**Opaque / unknown:** Internal orchestration and server implementation are not public.

**Why it matters for comparison:** Strong benchmark for LLM-ready data API design.

**Evidence status:** Mostly documented

**Key URLs:**

- https://www.marketplace.spglobal.com/en/solutions/kensho-llm-ready-api-%28a156fe9f-5564-4f60-a624-95d8645dc98f%29
- https://press.spglobal.com/2025-07-15-S-P-Global-and-Anthropic-Announce-Integration-of-S-P-Globals-Trusted-Financial-Data-into-Claude

## Data layer

**Publicly documented:** Publicly listed datasets include S&P Capital IQ Financials, Business Relationships, Machine Readable Transcripts, Company Intelligence, Transactions, Private Company Financials, and Estimates.

**Strongly inferred:** This is a broad research/data substrate focused on structured financial intelligence with source linkage back to filings and transcripts.

**Opaque / unknown:** Full field coverage, update cadence, and search/retrieval behavior across these datasets are not public in one place.

**Why it matters for comparison:** Benchmark your structured and semi-structured data coverage here.

**Evidence status:** Mostly documented

**Key URLs:**

https://www.marketplace.spglobal.com/en/solutions/kensho-llm-ready-api-%28a156fe9f-5564-4f60-a624-95d8645dc98f%29

## Ontology / context

**Publicly documented:** S&P/Kensho emphasizes simplified structure for function-calling and inline source links back to original documents.

**Strongly inferred:** The semantic layer likely rides on top of S&P's existing entity and financial data models, but the ontology itself is not a headline feature in public materials.

**Opaque / unknown:** Entity graph counts, taxonomy definitions, and point-in-time semantics are not publicly described in the reviewed sources.

**Why it matters for comparison:** If your system's ontology is a differentiator, this is a potential place to outperform on visibility and design clarity.

**Evidence status:** Partly documented

**Key URLs:**

https://www.marketplace.spglobal.com/en/solutions/kensho-llm-ready-api-%28a156fe9f-5564-4f60-a624-95d8645dc98f%29

## Tagging / source linkage

**Publicly documented:** S&P highlights source document hyperlinks that direct users from cited public company data points back to original filings in Capital IQ Pro.

**Strongly inferred:** Grounding is built around source-linked finance facts rather than around user-authored document tagging workflows.

**Opaque / unknown:** Any private-document tagging or customer-content ingestion path is not described in the reviewed materials.

**Why it matters for comparison:** Good benchmark for traceable structured outputs, not for private-corpus enrichment.

**Evidence status:** Mostly documented

**Key URLs:**

https://www.marketplace.spglobal.com/en/solutions/kensho-llm-ready-api-%28a156fe9f-5564-4f60-a624-95d8645dc98f%29

## MCP server / tool surface

**Publicly documented:** S&P says the LLM-ready API includes a built-in MCP server. The Anthropic integration announcement states Kensho developed an MCP server enabling LLMs to access S&P datasets via natural language.

**Strongly inferred:** This is a direct data-access MCP surface rather than a large hosted retrieval platform like Bigdata.

**Opaque / unknown:** Public tool inventory and transport/runtime details are sparse compared with LSEG's plugin repo.

**Why it matters for comparison:** Useful benchmark for direct data-tool exposure via MCP.

**Evidence status:** Mostly documented

**Key URLs:**

- https://press.spglobal.com/2025-07-15-S-P-Global-and-Anthropic-Announce-Integration-of-S-P-Globals-Trusted-Financial-Data-into-Claude
- https://www.marketplace.spglobal.com/en/solutions/kensho-llm-ready-api-%28a156fe9f-5564-4f60-a624-95d8645dc98f%29

## Skills / workflows

**Publicly documented:** Anthropic's partner-built S&P plugin offers company tearsheets, earnings previews, and funding digests. The tear-sheet skill uses S&P Global MCP tools to retrieve data and format a professional Word document for different audiences.

**Strongly inferred:** S&P's workflow layer is currently most visible through Anthropic partner skills rather than a standalone app UX.

**Opaque / unknown:** Other hosted workflow assets and internal orchestration are not public.

**Why it matters for comparison:** Excellent comparator for audience-specific deliverable generation from structured finance data.

**Evidence status:** Mostly documented

**Key URLs:**

- https://github.com/anthropics/financial-services-plugins/blob/main/README.md
- https://github.com/anthropics/financial-services-plugins/blob/main/partner-built/spglobal/skills/tear-sheet/SKILL.md

## Code execution / outputs

**Publicly documented:** Kensho provides a Python library; the Anthropic partner skill shows how live S&P data can be turned into a polished Word deliverable.

**Strongly inferred:** S&P/Kensho is optimized for being embedded into other agent shells and downstream office outputs.

**Opaque / unknown:** Code execution environments and richer artifact pipelines are not public.

**Why it matters for comparison:** Benchmark your Python/API ergonomics and artifact quality here.

**Evidence status:** Partly documented

**Key URLs:**

- https://www.marketplace.spglobal.com/en/solutions/kensho-llm-ready-api-%28a156fe9f-5564-4f60-a624-95d8645dc98f%29
- https://github.com/anthropics/financial-services-plugins/blob/main/partner-built/spglobal/skills/tear-sheet/SKILL.md

## Security / governance

**Publicly documented:** S&P frames the product around trusted proprietary data and existing enterprise delivery channels such as Capital IQ Pro and data feeds.

**Strongly inferred:** Rights management is likely anchored in existing S&P licensing and entitlements.

**Opaque / unknown:** Fine-grained MCP security, audit, and policy models are not public in the reviewed sources.

**Why it matters for comparison:** Compare your governance story here if you have stronger explicit MCP controls.

**Evidence status:** Partly documented

**Key URLs:**

https://press.spglobal.com/2025-07-15-S-P-Global-and-Anthropic-Announce-Integration-of-S-P-Globals-Trusted-Financial-Data-into-Claude

## Net comparison takeaway

**Publicly documented:** S&P/Kensho is a strong comparator for LLM-ready structured finance data with built-in MCP and source-linked outputs.

**Strongly inferred:** It is a weaker public comparator for deep retrieval architecture or private-document context engineering.

**Opaque / unknown:** Full workflow stack and ontology depth are not visible publicly.

**Why it matters for comparison:** Use it when benchmarking API shape, source linkage, and reusable skills.

**Evidence status:** Synthesis

**Key URLs:**

- https://www.marketplace.spglobal.com/en/solutions/kensho-llm-ready-api-%28a156fe9f-5564-4f60-a624-95d8645dc98f%29
- https://github.com/anthropics/financial-services-plugins/blob/main/partner-built/spglobal/skills/tear-sheet/SKILL.md
