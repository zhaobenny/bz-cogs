"""Search Python source in the installed AIUser package."""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any

from aiuser.functions.config_help import can_use_config_help
from aiuser.functions.context import ToolContext
from aiuser.functions.tool_call import ToolCall
from aiuser.functions.types import Function, Parameters, ToolCallSchema

_SOURCE_ROOT = Path(__file__).resolve().parents[1]
_SOURCE_PACKAGES = (
    "config",
    "consent",
    "context",
    "core",
    "dashboard",
    "functions",
    "mcp",
    "providers",
    "response",
    "settings",
    "types",
    "utils",
)
_MAX_FILE_BYTES = 256 * 1024
_MAX_RESULTS = 5
_CONTEXT_LINES = 3


def search_source(query: str) -> list[dict[str, Any]]:
    terms = set(re.findall(r"[a-z0-9]{2,}", query.casefold()))
    if not terms:
        return []

    query = query.casefold()
    paths = [_SOURCE_ROOT / "__init__.py"]
    for package in _SOURCE_PACKAGES:
        directory = _SOURCE_ROOT / package
        if not directory.is_symlink():
            paths.extend(directory.rglob("*.py"))

    matches = []
    for path in sorted(paths):
        relative = path.relative_to(_SOURCE_ROOT)
        if any(part.startswith(".") for part in relative.parts):
            continue
        try:
            if path.resolve() != path or not path.is_file():
                continue
            with path.open("rb") as source:
                content = source.read(_MAX_FILE_BYTES + 1)
            if len(content) > _MAX_FILE_BYTES:
                continue
            lines = content.decode("utf-8").splitlines()
        except (OSError, UnicodeError, RuntimeError):
            continue

        filename = relative.as_posix()
        for index, line in enumerate(lines):
            line = line.casefold()
            matched_terms = sum(term in line for term in terms)
            if matched_terms:
                score = (query in line, matched_terms, query in filename)
                matches.append((score, filename, index, lines))

    results = []
    for _, filename, index, lines in sorted(
        matches, key=lambda hit: hit[0], reverse=True
    ):
        start = max(0, index - _CONTEXT_LINES)
        end = min(len(lines), index + _CONTEXT_LINES + 1)
        if any(
            match["file"] == filename
            and start < match["end_line"]
            and end >= match["start_line"]
            for match in results
        ):
            continue
        results.append(
            {
                "file": filename,
                "start_line": start + 1,
                "end_line": end,
                "source": "\n".join(line[:240] for line in lines[start:end]),
            }
        )
        if len(results) == _MAX_RESULTS:
            break
    return results


class SourceSearchToolCall(ToolCall):
    function_name = "search_aiuser_source"
    schema = ToolCallSchema(
        function=Function(
            name=function_name,
            description=(
                "Search the installed AIUser Python source when the bot owner's current "
                "message asks how AIUser works. Use a short keyword phrase or symbol name. "
                "Returns excerpts with file and line ranges. For live settings, use "
                "inspect_aiuser_settings."
            ),
            parameters=Parameters(
                properties={"query": {"type": "string", "maxLength": 100}},
                required=["query"],
            ),
        )
    )

    async def _handle(
        self, tool_context: ToolContext, arguments: dict[str, Any]
    ) -> str:
        if not await can_use_config_help(tool_context):
            return "AIUser source help is unavailable for this request."

        query = arguments.get("query")
        if not isinstance(query, str) or not query.strip() or len(query) > 100:
            return "Provide a short keyword phrase or symbol name."
        results = await asyncio.to_thread(search_source, query.strip())
        return json.dumps(results) if results else "No matching AIUser source found."
