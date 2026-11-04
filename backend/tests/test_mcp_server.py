import json

import pytest
from mcp import Client

from app import mcp_server
from evals.fixtures import fixture_context


@pytest.fixture(autouse=True)
def fixture_world(monkeypatch):
    async def context():
        return fixture_context()

    async def nothing():
        return None

    monkeypatch.setattr(mcp_server, "_context", context)
    monkeypatch.setattr(mcp_server, "connect_to_mongo", nothing)
    monkeypatch.setattr(mcp_server, "close_mongo_connection", nothing)


async def test_tools_are_listed_with_typed_schemas():
    async with Client(mcp_server.mcp) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}
    assert set(tools) == {"search_changes", "get_page_history", "compare_pricing"}
    pricing = tools["compare_pricing"]
    assert "pricing pages" in pricing.description
    assert "ComparePricingInput" in json.dumps(pricing.input_schema)
    assert pricing.output_schema["title"]


async def test_call_returns_typed_structured_output():
    async with Client(mcp_server.mcp) as client:
        result = await client.call_tool(
            "compare_pricing", {"params": {"competitors": ["Nimbus"]}}
        )
    assert result.is_error is False
    assert result.structured_content["competitors"][0]["competitor"] == "Nimbus"


async def test_workspace_argument_is_refused():
    async with Client(mcp_server.mcp) as client:
        result = await client.call_tool(
            "compare_pricing", {"params": {"workspace_id": "another-tenant"}}
        )
    assert result.is_error is True


async def test_correctable_errors_reach_the_client():
    async with Client(mcp_server.mcp) as client:
        result = await client.call_tool(
            "get_page_history", {"params": {"competitor": "Acme"}}
        )
    assert result.is_error is True
    assert "Known: Brightdesk" in result.content[0].text
