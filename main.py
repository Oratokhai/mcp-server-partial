"""
Partial MCP server — deliberately broken in specific ways.
Target verdict: PARTIALLY COMPLIANT (~61%)

Deliberate failures:
  CHECK-04 FAIL  — returns "jsonrpc": "1.0" on all responses
  CHECK-05 FAIL  — echoes req_id + 100 instead of the real id
  CHECK-09 FAIL  — returns success (not error) for unknown tools
  CHECK-10 FAIL  — returns success (not error) for missing required params
  CHECK-13 WARN  — returns error code -1 for unknown methods (not -32601)
  CHECK-15 FAIL  — returns success when params is a string
  CHECK-17 FAIL  — Content-Type: text/plain (not application/json)
  CHECK-12 WARN  — tool responses omit isError field
"""
import datetime
import json
from fastapi import FastAPI, Request
from fastapi.responses import Response

app = FastAPI(title="MCP Server — Partial")

TOOLS = [
    {
        "name": "ping",
        "description": "Returns pong.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "echo",
        "description": "Echoes back the provided message.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Message to echo."}
            },
            "required": ["message"]
        }
    },
    {
        "name": "get_time",
        "description": "Returns the current UTC time.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]

# Intentionally wrong Content-Type
BAD_CT = "text/plain"


def bad_id(req_id):
    if isinstance(req_id, int):
        return req_id + 100
    return str(req_id) + "_x"


def rpc_ok(req_id, result):
    # jsonrpc "1.0" — fails CHECK-04; bad id — fails CHECK-05
    return {"jsonrpc": "1.0", "id": bad_id(req_id), "result": result}


def rpc_err(req_id, code, message):
    return {"jsonrpc": "1.0", "id": bad_id(req_id), "error": {"code": code, "message": message}}


def resp(data):
    return Response(content=json.dumps(data), media_type=BAD_CT)


@app.get("/")
async def health():
    return {"status": "ok", "server": "mcp-server-partial"}


@app.post("/mcp")
async def handle(request: Request):
    try:
        body = await request.json()
    except Exception:
        return resp({"jsonrpc": "1.0", "id": None, "error": {"code": -32700, "message": "Parse error"}})

    req_id = body.get("id")
    method = body.get("method", "")
    params = body.get("params", {})

    # Notifications (no id) — handle gracefully so CHECK-14 passes
    if req_id is None:
        return Response(content="{}", status_code=200, media_type=BAD_CT)

    # String params: return success instead of error — fails CHECK-15
    if not isinstance(params, dict):
        return resp(rpc_ok(req_id, {"ok": True}))

    if method == "initialize":
        return resp(rpc_ok(req_id, {
            "protocolVersion": "2025-03-26",
            "serverInfo": {"name": "mcp-server-partial", "version": "1.0.0"},
            "capabilities": {"tools": {}}
        }))

    elif method == "tools/list":
        return resp(rpc_ok(req_id, {"tools": TOOLS}))

    elif method == "tools/call":
        name = params.get("name", "")
        args = params.get("arguments") or {}

        tool = next((t for t in TOOLS if t["name"] == name), None)

        # Unknown tool: return success instead of error — fails CHECK-09
        if tool is None:
            return resp(rpc_ok(req_id, {"content": [{"type": "text", "text": "ok"}]}))

        # Missing required params: return success anyway — fails CHECK-10
        # (intentionally skip the required param check)

        if name == "ping":
            content = [{"type": "text", "text": "pong"}]
        elif name == "echo":
            content = [{"type": "text", "text": args.get("message", "(no message)")}]
        elif name == "get_time":
            content = [{"type": "text", "text": datetime.datetime.utcnow().isoformat() + "Z"}]
        else:
            content = []

        # isError intentionally omitted — triggers CHECK-12 WARN
        return resp(rpc_ok(req_id, {"content": content}))

    else:
        # Wrong error code (-1 instead of -32601) — triggers CHECK-13 WARN
        return resp(rpc_err(req_id, -1, "Unknown method"))
