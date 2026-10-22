from __future__ import annotations

import json
from typing import List, Optional

from lib.mcp_stdio import Server, ToolError


def make_server() -> Server:
    s = Server("t", "9.9.9", instructions="hello")

    @s.tool()
    def echo(text: str, times: int = 1, tags: Optional[List[str]] = None, flag: bool = False) -> dict:
        """Repeat text.

        Args:
            text: What to repeat.
            times: How many times. A second
                line of description.
            tags: Optional labels.
        """
        return {"out": text * times, "tags": tags or [], "flag": flag}

    @s.tool()
    def boom() -> str:
        """Always fails."""
        raise ToolError("nice message")

    @s.tool()
    def crash() -> str:
        """Unexpected failure."""
        raise ValueError("bad")

    return s


def test_schema_from_signature_and_docstring():
    spec = {t["name"]: t for t in make_server().handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})["result"]["tools"]}
    echo = spec["echo"]
    assert echo["description"] == "Repeat text."
    props = echo["inputSchema"]["properties"]
    assert echo["inputSchema"]["required"] == ["text"]
    assert props["text"] == {"type": "string", "description": "What to repeat."}
    assert props["times"]["type"] == "integer" and props["times"]["default"] == 1
    assert props["times"]["description"] == "How many times. A second line of description."
    assert props["tags"] == {"type": "array", "items": {"type": "string"}, "description": "Optional labels."}
    assert "default" not in props["tags"]  # None defaults are omitted
    assert props["flag"]["type"] == "boolean"
    assert echo["annotations"] == {"readOnlyHint": True}


def test_initialize_negotiates_version_and_sends_instructions():
    s = make_server()
    r = s.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}})["result"]
    assert r["protocolVersion"] == "2024-11-05"
    assert r["serverInfo"] == {"name": "t", "version": "9.9.9"}
    assert r["instructions"] == "hello"
    r = s.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "1999-01-01"}})["result"]
    assert r["protocolVersion"] == "2025-06-18"


def test_tool_call_results_and_errors():
    s = make_server()
    ok = s.call_tool("echo", {"text": "ab", "times": 2})
    assert ok["isError"] is False and json.loads(ok["content"][0]["text"])["out"] == "abab"
    assert s.call_tool("boom", {}) == {"content": [{"type": "text", "text": "nice message"}], "isError": True}
    crash = s.call_tool("crash", {})
    assert crash["isError"] and crash["content"][0]["text"] == "ValueError: bad"
    assert s.call_tool("echo", {"nope": 1})["isError"]
    assert "Unknown tool" in s.call_tool("missing", {})["content"][0]["text"]


def test_notifications_get_no_reply_and_unknown_methods_error():
    s = make_server()
    assert s.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    assert s.handle({"jsonrpc": "2.0", "id": 5, "method": "ping"})["result"] == {}
    assert s.handle({"jsonrpc": "2.0", "id": 6, "method": "nope"})["error"]["code"] == -32601
    assert s.handle({"jsonrpc": "2.0", "id": 7, "method": "resources/list"})["result"] == {"resources": []}
