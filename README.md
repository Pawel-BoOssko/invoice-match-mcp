# invoice-match-mcp

A small [MCP](https://modelcontextprotocol.io) server that lets an AI model **three-way-match supplier invoices** (invoice vs purchase order vs goods received) without ever being the one who decides.

The model calls the tools and explains the outcome. The decision comes from a deterministic rule engine, so it is reproducible, testable and auditable. That split is the point of this repo: *LLM as interface, rules as policy, evals as proof.*

## What it exposes

| MCP item | Purpose |
|---|---|
| `check_invoice(invoice_json, register=false)` | Returns `APPROVE`, `HOLD_PRICE`, `HOLD_QTY`, `HOLD_NO_PO`, `HOLD_DUPLICATE`, `HOLD_CURRENCY` or `REVIEW`, with human-readable reasons. Never posts or pays anything. |
| `list_open_purchase_orders(supplier)` | Lets the model look up PO lines, received quantities and agreed prices before it answers. |
| resource `policy://matching` | The policy in plain language, so the model can quote it. |

Rules: unit price within 2 % of the PO; invoiced quantity not above received quantity; same currency; same supplier plus invoice number twice is a duplicate; no PO number gives `REVIEW` at best, never `APPROVE`.

## Run it

Requires Python 3.10+ and the MCP Python SDK 2.x.

```bash
pip install -e ".[dev]"
python -m invoice_match.server        # stdio MCP server
```

Claude Desktop / any MCP client:

```json
{ "mcpServers": { "invoice-match": { "command": "python", "args": ["-m", "invoice_match.server"] } } }
```

Use your own purchase orders by pointing `INVOICE_MATCH_PO_FILE` at a CSV with the columns of `data/purchase_orders.csv`.

## Evals

```bash
python evals/run_evals.py
```

`evals/golden_cases.json` holds 11 invoices with the expected decision (clean match, price drift, over-billing, unknown PO, wrong supplier, currency, ambiguous PO, ...). The same file can grade an LLM agent: give the model each invoice with the server attached and compare its final answer to `expect`. One source of truth for engine, tools and agent.

`pytest` covers the engine (including the exact 2 % boundary and purity) and starts the real server over stdio, calling the tool the way a model would.

## Why this exists

Built by [Paweł Boruta-Ośko](https://www.linkedin.com/in/pawel-boruta-osko/), who ran an omnichannel retailer for almost 20 years (ERP, WMS, 50+ integrations) and now builds agentic systems. See also [OpenFill](https://github.com/Pawel-BoOssko/OpenFill), an MCP browser agent. All data in this repo is fictional. Written with substantial help from Claude (Anthropic): the matching rules and scope were specified by the author, the code, tests and evals were drafted by Claude Code and reviewed by him.

MIT licence.