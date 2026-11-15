"""Promptfoo assertions. All deterministic: no model grades another model."""

import os
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
os.chdir(BACKEND)
sys.path.insert(0, str(BACKEND))

from pydantic import ValidationError  # noqa: E402

from app.agent.tools import TOOLS  # noqa: E402
from app.rag.citations import cited_numbers, invalid_numbers  # noqa: E402
from app.schemas.agent import AskResponse  # noqa: E402

_AMOUNT = re.compile(
    r"[$€£]\s?(\d[\d,]*(?:\.\d+)?)|(\d[\d,]*(?:\.\d+)?)\s?(?:USD|EUR|GBP)\b"
)


def _result(problems: list[str]) -> dict:
    passed = not problems
    return {
        "pass": passed,
        "score": 1 if passed else 0,
        "reason": "ok" if passed else "; ".join(problems),
    }


def _amounts(text: str) -> set[float]:
    return {float((a or b).replace(",", "")) for a, b in _AMOUNT.findall(text)}


def schema_valid(output: dict, context: dict) -> dict:
    """The output parses as the type the code promises."""
    mode = context["vars"].get("mode", "agent")
    try:
        if mode == "agent":
            AskResponse.model_validate(output)
        elif mode == "tool" and "error" not in output:
            TOOLS[output["tool"]].output_model.model_validate(output["result"])
    except ValidationError as exc:
        return _result([f"schema: {exc}"])
    return _result([])


def citations_valid(output: dict, context: dict) -> dict:
    """Every [n] is a real source, and every amount quoted is in a cited source."""
    answer, sources = output["answer"], output["sources"]
    problems = []
    if not output["citations_valid"]:
        problems.append("agent flagged its own citations as invalid")
    invalid = invalid_numbers(answer, len(sources))
    if invalid:
        problems.append(f"cites sources that don't exist: {sorted(invalid)}")
    cited = cited_numbers(answer, len(sources))
    cited_text = "\n".join(s["text"] for s in sources if s["number"] in cited)
    backed = _amounts(cited_text)
    # "up $6" is arithmetic on two quoted prices, not an invented price
    backed |= {round(abs(a - b), 2) for a in backed for b in backed}
    unbacked = _amounts(answer) - backed
    if unbacked:
        problems.append(f"amounts not in any cited source: {sorted(unbacked)}")
    return _result(problems)


def agent_behaviour(output: dict, context: dict) -> dict:
    """The case's own expectations for tools used and what the answer says."""
    expect = context["vars"].get("expect", {})
    answer = output["answer"]
    cited = cited_numbers(answer, len(output["sources"]))
    used = {call["name"] for call in output["tool_calls"]}
    problems = []
    for tool in expect.get("tools", []):
        if tool not in used:
            problems.append(f"didn't call {tool} (called {sorted(used)})")
    for text in expect.get("contains", []):
        if text.casefold() not in answer.casefold():
            problems.append(f"missing {text!r}")
    for text in expect.get("not_contains", []):
        if text.casefold() in answer.casefold():
            problems.append(f"shouldn't say {text!r}")
    if expect.get("must_cite") and not cited:
        problems.append("cites nothing")
    if expect.get("no_amounts") and _amounts(answer):
        problems.append(f"invented amounts: {sorted(_amounts(answer))}")
    return _result(problems)


def price_changes_match(output: dict, context: dict) -> dict:
    """Exact comparison: a pricing diff is either right or wrong."""
    expected = context["vars"]["expect"]
    actual = [
        {k: c[k] for k in ("label", "direction", "change_pct")} | _amount_pair(c)
        for c in output["changes"]
    ]
    if actual != expected:
        return _result([f"expected {expected}, got {actual}"])
    return _result([])


def _amount_pair(change: dict) -> dict:
    return {
        "old": change["old"]["amount"] if change["old"] else None,
        "new": change["new"]["amount"] if change["new"] else None,
    }


def tool_result_matches(output: dict, context: dict) -> dict:
    expect = context["vars"]["expect"]
    if "error_contains" in expect:
        error = output.get("error", "")
        if expect["error_contains"] not in error:
            return _result(
                [f"expected error with {expect['error_contains']!r}, got {output}"]
            )
        return _result([])
    if "error" in output:
        return _result([f"tool failed: {output['error']}"])
    result = output["result"]
    if "plans" in expect:
        competitors = {c["competitor"]: c for c in result["competitors"]}
        for name, plans in expect["plans"].items():
            found = {
                p["label"]: p["price"]["amount"] for p in competitors[name]["plans"]
            }
            if found != plans:
                return _result([f"{name}: expected {plans}, got {found}"])
    if (
        "no_prices_found" in expect
        and result["no_prices_found"] != expect["no_prices_found"]
    ):
        return _result([f"no_prices_found: {result['no_prices_found']}"])
    if "first_match_contains" in expect:
        top = result["matches"][0]["headline"] if result["matches"] else ""
        if expect["first_match_contains"] not in top:
            return _result([f"top match was {top!r}"])
    return _result([])
