"""A minimal MCP server over stdio (JSON-RPC 2.0, newline-delimited).

Replaces the `mcp` package's FastMCP so the servers need no install step.
Implements what Claude Code and Claude Desktop use: initialize, ping,
tools/list and tools/call. Tool input schemas are derived from the Python
signature and the docstring's "Args:" section.

    server = Server("funnelwise-spotify", instructions="...")

    @server.tool()
    def spotify_get_show(show_id: str = "") -> dict:
        '''Get the show's metadata.

        Args:
            show_id: Optional; defaults to the brand's show.
        '''

    server.run()

A tool returns a dict/list (sent as JSON text) or a str. Raising ToolError (or
any exception) returns an MCP error result (isError: true) instead of crashing.
"""
from __future__ import annotations

import inspect
import json
import re
import sys
import traceback
import typing
from typing import Any, Callable, Dict, List, Optional

PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")


class ToolError(Exception):
    """An expected failure with a message meant for the user (no traceback)."""


_JSON_TYPES = {str: "string", int: "integer", float: "number", bool: "boolean", dict: "object", list: "array"}


def _schema_for(annotation: Any) -> dict:
    if annotation is inspect.Parameter.empty or annotation is Any:
        return {}
    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)
    if origin is typing.Union:
        non_none = [a for a in args if a is not type(None)]
        return _schema_for(non_none[0]) if len(non_none) == 1 else {}
    if origin in (list, List):
        schema = {"type": "array"}
        if args:
            schema["items"] = _schema_for(args[0])
        return schema
    if origin in (dict, Dict):
        return {"type": "object"}
    if annotation in _JSON_TYPES:
        return {"type": _JSON_TYPES[annotation]}
    return {}


def _parse_arg_docs(doc: str) -> dict:
    """Return {name: description} from a Google-style "Args:" block.

    Expects the cleandoc'd layout: "Args:" at column 0, each argument at 4
    spaces ("name: text"), continuation lines at 8+ spaces.
    """
    out, current, in_args = {}, None, False
    for line in doc.splitlines():
        if line.strip() in ("Args:", "Arguments:"):
            in_args, current = True, None
            continue
        if not in_args:
            continue
        if line and not line.startswith(" "):  # next section, e.g. "Returns:"
            break
        m = re.match(r"^ {4}(\w+)(?:\s*\([^)]*\))?:\s*(.*)$", line)
        if m:
            current = m.group(1)
            out[current] = m.group(2)
        elif current and line.startswith(" " * 8):
            out[current] += " " + line.strip()
    return out


def _description(doc: str) -> str:
    """The docstring without its Args: section."""
    return re.split(r"\n\s*(Args|Arguments):\s*\n", doc, maxsplit=1)[0].strip()


class Tool:
    def __init__(self, fn: Callable):
        self.fn = fn
        self.name = fn.__name__
        doc = inspect.cleandoc(fn.__doc__ or "")
        self.description = _description(doc)
        arg_docs = _parse_arg_docs(doc)
        hints = typing.get_type_hints(fn)
        props, required = {}, []
        for pname, param in inspect.signature(fn).parameters.items():
            schema = _schema_for(hints.get(pname, param.annotation))
            if pname in arg_docs:
                schema["description"] = arg_docs[pname]
            if param.default is inspect.Parameter.empty:
                required.append(pname)
            elif param.default is not None:
                schema["default"] = param.default
            props[pname] = schema
        self.input_schema = {"type": "object", "properties": props}
        if required:
            self.input_schema["required"] = required

    def spec(self) -> dict:
        return {"name": self.name, "description": self.description, "inputSchema": self.input_schema,
                "annotations": {"readOnlyHint": True}}


class Server:
    def __init__(self, name: str, version: str = "0.1.0", instructions: str = ""):
        self.name = name
        self.version = version
        self.instructions = instructions
        self.tools = {}  # type: Dict[str, Tool]

    def tool(self) -> Callable:
        def register(fn: Callable) -> Callable:
            self.tools[fn.__name__] = Tool(fn)
            return fn
        return register

    # -- protocol -----------------------------------------------------------

    def call_tool(self, name: str, arguments: Optional[dict]) -> dict:
        tool = self.tools.get(name)
        if tool is None:
            return _error_result(f"Unknown tool: {name}")
        try:
            result = tool.fn(**(arguments or {}))
        except ToolError as e:
            return _error_result(str(e))
        except TypeError as e:
            return _error_result(f"Bad arguments for {name}: {e}")
        except Exception as e:  # noqa: BLE001 - report, never crash the server
            traceback.print_exc(file=sys.stderr)
            return _error_result(f"{type(e).__name__}: {e}")
        text = result if isinstance(result, str) else json.dumps(result, indent=2, ensure_ascii=False, default=str)
        return {"content": [{"type": "text", "text": text}], "isError": False}

    def handle(self, msg: dict) -> Optional[dict]:
        method, msg_id = msg.get("method"), msg.get("id")
        if msg_id is None:  # notification (e.g. notifications/initialized)
            return None
        params = msg.get("params") or {}
        if method == "initialize":
            requested = params.get("protocolVersion")
            result = {
                "protocolVersion": requested if requested in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0],
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": self.name, "version": self.version},
            }
            if self.instructions:
                result["instructions"] = self.instructions
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": [t.spec() for t in self.tools.values()]}
        elif method == "tools/call":
            result = self.call_tool(params.get("name", ""), params.get("arguments"))
        elif method in ("resources/list", "prompts/list"):
            result = {method.split("/")[0]: []}
        else:
            return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    def run(self) -> None:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                _write({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}})
                continue
            reply = self.handle(msg)
            if reply is not None:
                _write(reply)


def _error_result(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}], "isError": True}


def _write(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()
