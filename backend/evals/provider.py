"""Promptfoo provider: runs one eval case against the real code."""

import asyncio
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
os.chdir(BACKEND)  # settings read .env from here
sys.path.insert(0, str(BACKEND))

from pydantic import ValidationError  # noqa: E402

from app.agent.graph import ask  # noqa: E402
from app.agent.pricing import diff_prices  # noqa: E402
from app.agent.tools import TOOLS, ToolError  # noqa: E402
from evals.fixtures import fixture_context  # noqa: E402

# one loop for the whole process: the OpenAI client keeps connections bound to it
_loop = asyncio.new_event_loop()


def _money(value) -> dict | None:
    if value is None:
        return None
    return {
        "amount": float(value.amount),
        "currency": value.currency,
        "period": value.period,
    }


def _run_price_diff(variables: dict) -> dict:
    return {
        "changes": [
            {
                "label": c.label,
                "direction": c.direction,
                "old": _money(c.old),
                "new": _money(c.new),
                "change_pct": c.change_pct,
            }
            for c in diff_prices(variables["hunks"])
        ]
    }


def _run_tool(variables: dict) -> dict:
    spec = TOOLS[variables["tool"]]
    try:
        params = spec.input_model(**variables.get("args", {}))
        output = _loop.run_until_complete(spec.fn(fixture_context(), params))
    except (ValidationError, ToolError) as exc:
        return {"error": str(exc)}
    return {"tool": spec.name, "result": output.model_dump(mode="json")}


def call_api(prompt: str, options: dict, context: dict) -> dict:
    variables = context["vars"]
    mode = variables.get("mode", "agent")
    if mode == "price_diff":
        return {"output": _run_price_diff(variables)}
    if mode == "tool":
        return {"output": _run_tool(variables)}
    result = _loop.run_until_complete(ask(prompt, fixture_context()))
    return {
        "output": result.model_dump(mode="json"),
        "tokenUsage": {
            "prompt": result.usage.input_tokens,
            "completion": result.usage.output_tokens,
            "total": result.usage.input_tokens + result.usage.output_tokens,
        },
    }
