# Financial Analytics Skill System -- Architecture & Adaptation Spec

This document specifies the complete architecture of the Anthropic financial-services-plugins system so that an internal AI system can replicate it against an internal data layer. The actual skill and command markdown files are taken directly from the open-source repo at `github.com/anthropics/financial-services-plugins`. This document explains the system they plug into and exactly what must be adapted.

## System Overview

The system has three layers. Only the bottom layer (data) needs adaptation. The top two layers (skills and commands) port as-is.

```
LAYER 3 -- COMMANDS (port as-is)
  Explicit slash-commands the user invokes.
  Each is a single markdown file in commands/.
  Contains: numbered workflow steps, tool call sequence, output format.
  Example: /analyze-bond-rv triggers commands/analyze-bond-rv.md

LAYER 2 -- SKILLS (port as-is)
  Domain expertise that auto-activates when context is relevant.
  Each is a SKILL.md in skills/<skill-name>/.
  Contains: expert persona, core principles, tool chaining workflow,
  output table templates, synthesis/judgment framework.
  Commands reference skills; skills reference tools.

LAYER 1 -- TOOLS / DATA LAYER (adapt this)
  MCP tool endpoints that skills and commands call by name.
  Original: LSEG Financial Analytics MCP Server.
  Adaptation: map each tool name to an internal data source/API.
  The skill files call tools by exact string name (e.g., "bond_price").
  Your data layer must expose endpoints matching these tool names,
  accepting the inputs and returning the outputs specified in
  TOOL-INTERFACE-CONTRACT.md.
```

## Plugin File Structure

Every plugin follows this layout:

```
plugin-name/
├── .claude-plugin/plugin.json   # Manifest: name, version, description, author
├── .mcp.json                    # Tool connections (data layer wiring)
├── commands/                    # Slash commands (user-invoked workflows)
│   └── *.md                     # One file per command
├── skills/                      # Domain knowledge (auto-activated)
│   └── skill-name/
│       └── SKILL.md             # One SKILL.md per skill
└── hooks/
    └── hooks.json               # Lifecycle hooks (optional)
```

### plugin.json (manifest)

```json
{
  "name": "lseg",
  "version": "1.0.0",
  "description": "Financial analytics: bonds, FX, curves, options, macro",
  "author": "LSEG"
}
```

For adaptation: change `name`, `description`, `author` to reflect the internal system.

### .mcp.json (data layer wiring)

Original LSEG configuration:

```json
{
  "mcpServers": {
    "lseg": {
      "type": "http",
      "url": "https://api.analytics.lseg.com/lfa/mcp/server-cl"
    }
  }
}
```

For adaptation: replace with the internal MCP server endpoint. If the internal system uses a different connection mechanism (direct API calls, internal service mesh, etc.), this file defines the routing. The key constraint is that the 23 tool names referenced in skills/commands must resolve to working endpoints.

## Command Anatomy

A command file is markdown with YAML frontmatter:

```yaml
---
description: Human-readable description of what the command does
argument-hint: "<required args> [optional args]"
---
```

The body contains:
- A reference to which skill provides domain knowledge
- A numbered workflow (Step 1, Step 2, ...) specifying which tools to call in what order
- What to extract from each tool's response
- How to synthesize the final output
- Output format specification

Commands are procedural. They tell the AI "do this, then this, then this." The skill provides the judgment layer on top.

### What to Change in Commands

Almost nothing. Commands reference tools by name (e.g., "Call `bond_price`"). If your data layer exposes the same tool names with compatible I/O, commands work as-is. If your internal tool names differ, do a find-and-replace of tool names in the command files.

The only structural change: update the reference to CONNECTORS.md if you maintain your own tool reference document.

## Skill Anatomy

A skill file is markdown with YAML frontmatter:

```yaml
---
name: skill-identifier
description: >
  Multi-sentence description of what this skill does and WHEN TO USE IT.
  This description is the activation trigger -- the AI matches it against
  conversation context to decide whether to load this skill.
---
```

The body contains these sections in order:

1. **Expert Persona** -- "You are an expert [role] specializing in [domain]."
2. **Core Principles** -- Domain knowledge, frameworks, judgment rules.
3. **Available MCP Tools** -- Bulleted list of tool names with descriptions of what each returns. This is the skill's view of the data layer.
4. **Tool Chaining Workflow** -- Numbered sequence: which tools to call, what to extract, how to chain outputs.
5. **Output Format** -- Table templates, section structure, synthesis instructions.

### What to Change in Skills

The "Available MCP Tools" section lists LSEG tool names. If your internal tools have different names, update this section. If your internal tools return slightly different field names or structures, update the extraction instructions in "Tool Chaining Workflow."

The domain expertise (Core Principles, Output Format, Expert Persona) is asset-class knowledge, not LSEG-specific. It ports as-is.

## The LSEG Plugin: Complete Inventory

### 8 Commands (port all)

| File | Slash Command | Tools Called |
|------|--------------|-------------|
| `commands/analyze-bond-rv.md` | `/analyze-bond-rv` | `bond_price`, `interest_rate_curve`, `credit_curve`, `yieldbook_scenario` |
| `commands/analyze-bond-basis.md` | `/analyze-bond-basis` | `bond_future_price`, `bond_price`, `interest_rate_curve`, `tscc_historical_pricing_summaries` |
| `commands/analyze-fx-carry.md` | `/analyze-fx-carry` | `fx_spot_price`, `fx_forward_price`, `fx_forward_curve`, `fx_vol_surface`, `tscc_historical_pricing_summaries`, `interest_rate_curve` |
| `commands/analyze-swap-curve.md` | `/analyze-swap-curve` | `ir_swap`, `interest_rate_curve`, `inflation_curve`, `tscc_historical_pricing_summaries`, `qa_macroeconomic` |
| `commands/analyze-option-vol.md` | `/analyze-option-vol` | `equity_vol_surface` OR `fx_vol_surface`, `option_value`, `option_template_list`, `tscc_historical_pricing_summaries`, `qa_historical_equity_price` |
| `commands/research-equity.md` | `/research-equity` | `qa_ibes_consensus`, `qa_company_fundamentals`, `qa_historical_equity_price`, `tscc_historical_pricing_summaries`, `qa_macroeconomic` |
| `commands/review-fi-portfolio.md` | `/review-fi-portfolio` | `bond_price`, `yieldbook_bond_reference`, `yieldbook_cashflow`, `yieldbook_scenario`, `interest_rate_curve`, `fixed_income_risk_analytics` |
| `commands/macro-rates.md` | `/macro-rates` | `qa_macroeconomic`, `interest_rate_curve`, `inflation_curve`, `ir_swap`, `tscc_historical_pricing_summaries` |

### 8 Skills (port all)

| Directory | Skill Name | Primary Tools |
|-----------|-----------|---------------|
| `skills/bond-relative-value/` | `bond-relative-value` | `bond_price`, `interest_rate_curve`, `credit_curve`, `yieldbook_scenario`, `tscc_historical_pricing_summaries`, `fixed_income_risk_analytics` |
| `skills/bond-futures-basis/` | `bond-futures-basis` | `bond_future_price`, `bond_price`, `interest_rate_curve`, `tscc_historical_pricing_summaries`, `credit_curve` |
| `skills/fx-carry-trade/` | `fx-carry-trade` | `fx_spot_price`, `fx_forward_price`, `fx_forward_curve`, `fx_vol_surface`, `tscc_historical_pricing_summaries`, `interest_rate_curve` |
| `skills/swap-curve-strategy/` | `swap-curve-strategy` | `ir_swap`, `interest_rate_curve`, `inflation_curve`, `tscc_historical_pricing_summaries`, `qa_macroeconomic` |
| `skills/option-vol-analysis/` | `option-vol-analysis` | `equity_vol_surface`, `fx_vol_surface`, `option_value`, `option_template_list`, `tscc_historical_pricing_summaries`, `qa_historical_equity_price` |
| `skills/equity-research/` | `equity-research` | `qa_ibes_consensus`, `qa_company_fundamentals`, `qa_historical_equity_price`, `tscc_historical_pricing_summaries`, `qa_macroeconomic` |
| `skills/fixed-income-portfolio/` | `fixed-income-portfolio` | `bond_price`, `yieldbook_bond_reference`, `yieldbook_cashflow`, `yieldbook_scenario`, `interest_rate_curve`, `fixed_income_risk_analytics` |
| `skills/macro-rates-monitor/` | `macro-rates-monitor` | `qa_macroeconomic`, `interest_rate_curve`, `inflation_curve`, `ir_swap`, `tscc_historical_pricing_summaries` |

### 23 Unique Tools Referenced

These are every tool name that appears across all skills and commands. Your data layer must implement all 23 to achieve full coverage. Partial implementation is possible -- see the dependency table above to identify which skills/commands break if a tool is missing.

```
bond_price                          bond_future_price
fx_spot_price                       fx_forward_price
interest_rate_curve                 credit_curve
inflation_curve                     fx_forward_curve
ir_swap
option_value                        option_template_list
fx_vol_surface                      equity_vol_surface
qa_ibes_consensus                   qa_company_fundamentals
qa_historical_equity_price          qa_macroeconomic
tscc_historical_pricing_summaries
yieldbook_bond_reference            yieldbook_cashflow
yieldbook_scenario                  fixed_income_risk_analytics
```

## Adaptation Procedure

### Step 1: Clone the Raw Skill/Command Files

Take these directories directly from `github.com/anthropics/financial-services-plugins/partner-built/lseg/`:

```
commands/          (8 files, use as-is or with tool name substitution)
skills/            (8 directories, each with SKILL.md)
```

### Step 2: Build the Tool Interface Layer

Using TOOL-INTERFACE-CONTRACT.md as the specification, implement each of the 23 tools against internal data sources. Each tool must:
- Accept the specified inputs (identifiers, parameters)
- Return the specified output fields
- Follow the interaction pattern (direct call vs two-phase list-then-calculate)

### Step 3: Wire the Data Layer

Create the equivalent of `.mcp.json` pointing to internal endpoints. If the internal system uses a different protocol than MCP (REST API, gRPC, internal SDK), the wiring mechanism changes but the tool interface contract remains the same.

### Step 4: Update Tool Names (if different)

If internal tool names differ from the LSEG names, do a bulk find-and-replace across all skill and command files. The mapping is defined in the `internal_tool_name` column of TOOL-INTERFACE-CONTRACT.md.

### Step 5: Validate Coverage

For each skill, verify that every tool it references is implemented and returns the expected fields. The "Tool Chaining Workflow" section of each skill specifies exactly what fields are extracted from each tool call.

## Tool Interaction Patterns

Two patterns exist across all 23 tools:

### Pattern A: Direct Call (17 tools)

```
Request:  { tool_name, inputs }
Response: { output_fields }
```

Single call, single response. Most tools follow this pattern.

### Pattern B: Two-Phase Discovery + Calculation (6 tools)

```
Phase 1 -- Discovery
  Request:  { tool_name, mode: "list" | "search", filter_params }
  Response: { available_items[] }

Phase 2 -- Calculation
  Request:  { tool_name, mode: "calculate" | "price", item_id_from_phase_1 }
  Response: { output_fields }
```

Tools using this pattern: `interest_rate_curve`, `credit_curve`, `inflation_curve`, `fx_forward_curve`, `ir_swap`. The skill files handle both phases in their workflow steps.

If your internal system can serve the data in a single call (e.g., you already know the curve identifier), you can simplify to Pattern A and update the skill workflow steps to skip the discovery phase.

## Cross-Plugin Compatibility

The LSEG plugin is a "partner-built" add-on within a larger ecosystem. The broader `financial-services-plugins` repo contains 5 additional plugins (financial-analysis, investment-banking, equity-research, private-equity, wealth-management) with 33 more skills and 30 more commands. These use the same tool interface layer. Implementing the 23 tools specified here also enables compatibility with those additional plugins if desired.

## Identifier Systems

The LSEG tools accept standard financial identifiers:

| Type | Format | Example | Used By |
|------|--------|---------|---------|
| ISIN | 12-char alphanumeric | US912810TM25 | `bond_price`, `yieldbook_*`, `fixed_income_risk_analytics` |
| RIC | Reuters Instrument Code | .SPX, TYA, EURUSD= | All tools (universal) |
| CUSIP | 9-char alphanumeric | 912810TM2 | `bond_price`, `yieldbook_*` |
| AssetId | LSEG internal ID | (numeric) | `bond_price` |
| ISO Currency | 3-char | USD, EUR, GBP | FX tools, curve tools, swap tools |
| Ticker | Exchange ticker | AAPL.O | `qa_*` tools |

For adaptation: map these to whatever identifier system the internal data layer uses. If internal systems use a different identifier (e.g., BBGID, internal security master ID), add an identifier resolution step or implement a lookup layer.
