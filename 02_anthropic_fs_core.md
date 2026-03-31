# Anthropic / FS / Core — public feature spec

*Method: each row separates what is explicitly public, what is strongly inferable, and what remains opaque.*

## Platform orientation

**Publicly documented:** Anthropic's financial-services offering is positioned around Claude for Financial Services, Claude Code / Enterprise, pre-built MCP connectors, and partner-built plugins for domain workflows.

**Strongly inferred:** This layer is an orchestration shell and analyst copilot experience rather than a proprietary financial data layer.

**Opaque / unknown:** How Claude internally ranks skills, commands, connectors, and tool strategies is not public.

**Why it matters for comparison:** Compare your workflow shell and analyst UX here, not your data moat.

**Evidence status:** Mostly documented

**Key URLs:**

- https://www.anthropic.com/news/claude-for-financial-services
- https://www.anthropic.com/news/advancing-claude-for-financial-services

## Data layer

**Publicly documented:** Anthropic describes pre-built MCP connectors to providers such as LSEG, Moody's, MT Newswires, Chronograph, Egnyte and others. The open plugin repo lists provider-integrated plugins including LSEG and S&P Global.

**Strongly inferred:** The core Anthropic layer intentionally outsources authoritative data to partner MCP servers instead of owning a vertically integrated financial ontology.

**Opaque / unknown:** Any internal caching, connector normalization, or semantic reconciliation across providers is not public.

**Why it matters for comparison:** Do not over-credit Anthropic for partner data-layer features when benchmarking.

**Evidence status:** Documented + inferred

**Key URLs:**

- https://www.anthropic.com/news/advancing-claude-for-financial-services
- https://github.com/anthropics/financial-services-plugins/blob/main/README.md

## Packaging model

**Publicly documented:** The public repo says plugins are file-based and consist of plugin.json, .mcp.json, commands/, and skills/, with no code, infrastructure, or build steps required. CLAUDE.md in the repo also references hooks and MCP config.

**Strongly inferred:** Anthropic is standardizing financial workflow packaging as declarative prompt/instruction assets layered over MCP tools.

**Opaque / unknown:** Any hidden runtime schema, connector registry behavior, or evaluation tooling behind Claude's product is not public.

**Why it matters for comparison:** This is the clean benchmark for a modular skill/command layer.

**Evidence status:** Strongly documented

**Key URLs:**

- https://github.com/anthropics/financial-services-plugins/blob/main/README.md
- https://github.com/anthropics/financial-services-plugins

## Ontology / tagging / context

**Publicly documented:** Anthropic does not market a proprietary financial ontology here. Instead, domain expertise is encoded inside skills and commands, while context comes from MCP-connected tools and partner datasets.

**Strongly inferred:** The effective 'context layer' is prompt- and workflow-level orchestration rather than a first-class ontological graph exposed by Anthropic.

**Opaque / unknown:** There is no public detail on cross-partner entity reconciliation or shared finance ontology inside the core plugin framework.

**Why it matters for comparison:** If your system has a real semantic layer, this is an area where you may exceed Anthropic's public story.

**Evidence status:** Inferred from absence + repo structure

**Key URLs:**

- https://github.com/anthropics/financial-services-plugins/blob/main/README.md
- https://www.anthropic.com/news/claude-for-financial-services

## Skills / commands

**Publicly documented:** The repo advertises 41 skills, 38 commands, and 11 MCP integrations. Skills encode domain workflows; commands provide slash-command entrypoints; add-ons cover IB, equity research, PE, wealth management, and more.

**Strongly inferred:** Anthropic's edge is likely workflow composition and packaging discipline rather than proprietary finance data ingestion.

**Opaque / unknown:** How these skills are selected, ranked, or composed dynamically at runtime is not public.

**Why it matters for comparison:** Benchmark your command grammar, role-specific flows, and skill discoverability here.

**Evidence status:** Strongly documented

**Key URLs:**

https://github.com/anthropics/financial-services-plugins/blob/main/README.md

## MCP connections / partner topology

**Publicly documented:** The repo and product pages show financial workflows connected to partner MCP servers. Providers listed publicly include LSEG, S&P Global, Daloopa, Morningstar, FactSet, Moody's, MT Newswires, Aiera, PitchBook, Chronograph, and Egnyte.

**Strongly inferred:** Anthropic's financial-services architecture is a federation of partner MCP surfaces rather than a monolithic server.

**Opaque / unknown:** Partner quality control, compatibility testing, and runtime fallback logic are not public.

**Why it matters for comparison:** Use this as the benchmark for partner ecosystem breadth.

**Evidence status:** Mostly documented

**Key URLs:**

- https://github.com/anthropics/financial-services-plugins/blob/main/README.md
- https://www.anthropic.com/news/advancing-claude-for-financial-services

## Code execution / outputs

**Publicly documented:** Anthropic highlights Monte Carlo simulations, risk modeling, and code-oriented work via Claude Code / Enterprise. The plugin ecosystem also targets downstream Excel, PowerPoint, and Word workflows, especially through office add-ins and partner skills.

**Strongly inferred:** The shell is designed to hand off from tool retrieval to code/artifact generation rather than to own the deterministic compute layer itself.

**Opaque / unknown:** The exact office runtime, sandboxing, and code-execution safeguards are not public in the reviewed materials.

**Why it matters for comparison:** Useful for comparing output surfaces and analyst productivity, less so for comparing data architecture.

**Evidence status:** Partly documented

**Key URLs:**

- https://www.anthropic.com/news/claude-for-financial-services
- https://github.com/anthropics/financial-services-plugins/blob/main/README.md

## Security / governance

**Publicly documented:** Anthropic markets enterprise controls and pre-built connectors, but the repo itself is mostly a packaging framework. Data governance is largely inherited from the partner MCP/data provider plus enterprise Claude deployment controls.

**Strongly inferred:** Governance strength depends heavily on who the data partner is and what that MCP server exposes.

**Opaque / unknown:** Tool-level entitlements, audit depth, and cross-connector security policy enforcement are not public.

**Why it matters for comparison:** This is where a tightly integrated proprietary stack may outscore the federated Anthropic approach.

**Evidence status:** Partly documented

**Key URLs:**

- https://www.anthropic.com/news/claude-for-financial-services
- https://github.com/anthropics/financial-services-plugins

## Public code transparency

**Publicly documented:** The packaging layer is unusually inspectable: skills and commands are plain files on GitHub and can be modified directly.

**Strongly inferred:** Anthropic is intentionally lowering the barrier to customizing workflow logic even when the underlying model and partner servers remain closed.

**Opaque / unknown:** The actual model behavior, internal planner, and hosted services remain proprietary.

**Why it matters for comparison:** If your system is configurable, show whether your configuration is equally legible and auditable.

**Evidence status:** Strongly documented on packaging only

**Key URLs:**

- https://github.com/anthropics/financial-services-plugins
- https://github.com/anthropics/financial-services-plugins/blob/main/README.md

## Net comparison takeaway

**Publicly documented:** Anthropic is strongest publicly as a modular workflow/connector shell.

**Strongly inferred:** It should not be treated as equivalent to Bigdata, LSEG, or Bloomberg at the data-layer level.

**Opaque / unknown:** Any internal finance-specific latent capabilities beyond public docs are not knowable from the reviewed material.

**Why it matters for comparison:** When you compare your own system, isolate orchestration, skills, and UX from the underlying content/analytics providers.

**Evidence status:** Synthesis

**Key URLs:**

- https://www.anthropic.com/news/claude-for-financial-services
- https://github.com/anthropics/financial-services-plugins/blob/main/README.md
