"""End-to-end: start the real MCP server over stdio and call its tools like a model would."""
import json
import sys
from pathlib import Path

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]


async def _call(tool: str, args: dict):
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "invoice_match.server"],
        env={"PYTHONPATH": str(ROOT / "src")},
    )
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = {t.name for t in (await s.list_tools()).tools}
            res = await s.call_tool(tool, args)
            return tools, res


def test_tools_are_listed_and_check_invoice_works():
    invoice = {"invoice_number": "S-1", "supplier": "Baltic Oil", "po_number": "PO-1004", "currency": "EUR",
               "lines": [{"sku": "OIL-5W", "qty": 500, "unit_price": 3.2}]}
    tools, res = anyio.run(_call, "check_invoice", {"invoice_json": json.dumps(invoice)})
    assert {"check_invoice", "list_open_purchase_orders"} <= tools
    payload = json.loads(res.content[0].text)
    assert payload["status"] == "APPROVE"