from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.agent.data import InsightQuery, MongoCompetitorData
from app.agent.tools import (
    ComparePricingInput,
    PageHistoryInput,
    SearchChangesInput,
    ToolError,
    compare_pricing,
    get_page_history,
    search_changes,
)
from evals.fixtures import BRIGHTDESK, WORKSPACE_ID, fixture_context


async def test_search_ranks_query_matches_above_other_changes():
    out = await search_changes(
        fixture_context(), SearchChangesInput(query="single sign-on SSO")
    )
    assert out.matches[0].competitor == "Nimbus"
    assert "SSO" in out.matches[0].headline
    assert all(
        e.id not in {m.id for m in out.matches} for e in out.other_recent_changes
    )
    assert len(out.matches) + len(out.other_recent_changes) <= 8


async def test_search_drops_chunks_from_a_first_scrape():
    ctx = fixture_context()
    hit = (await ctx.data.search("Pro", _filters(), 1))[0]
    baseline = type(hit)(**{**hit.__dict__, "first_seen_at": datetime(2026, 7, 1, 9)})

    async def only_baseline(*_):
        return [baseline]

    ctx.data.search = only_baseline
    out = await search_changes(ctx, SearchChangesInput(query="Pro"))
    assert out.matches == []


def _filters():
    from app.rag.search import SearchFilters

    return SearchFilters(workspace_id=WORKSPACE_ID)


async def test_tools_reject_unknown_competitors_naming_the_known_ones():
    with pytest.raises(ToolError, match="Unknown competitor: Acme. Known: Brightdesk"):
        await get_page_history(fixture_context(), PageHistoryInput(competitor="Acme"))


def test_inputs_reject_fields_they_do_not_declare():
    with pytest.raises(ValidationError):
        SearchChangesInput(query="x", workspace_id="another-tenant")


def test_inputs_reject_out_of_range_limits():
    with pytest.raises(ValidationError):
        SearchChangesInput(query="x", limit=500)


def test_since_is_normalised_to_naive_utc():
    params = SearchChangesInput(query="x", since=datetime(2026, 1, 1, tzinfo=UTC))
    assert params.since == datetime(2026, 1, 1)


async def test_history_is_newest_first_and_ends_at_monitoring_start():
    out = await get_page_history(
        fixture_context(), PageHistoryInput(competitor="brightdesk", url_type="pricing")
    )
    assert out.competitor == "Brightdesk"
    assert [e.kind for e in out.events] == ["change", "change", "monitoring_started"]
    assert out.events[0].detected_at > out.events[1].detected_at


async def test_compare_pricing_gives_current_prices_and_changes():
    out = await compare_pricing(
        fixture_context(), ComparePricingInput(competitors=["Brightdesk", "Nimbus"])
    )
    brightdesk, nimbus = out.competitors
    assert {(p.label, p.price.amount) for p in brightdesk.plans} == {
        ("Starter", 19.0),
        ("Pro", 39.0),
        ("Team plan", 99.0),
    }
    assert [(c.label, c.direction, c.change_pct) for c in nimbus.changes] == [
        ("Starter", "increase", 31.6)
    ]
    # each price is its own source, so a citation shows the line it quotes
    assert len({p.id for p in brightdesk.plans}) == 3


async def test_compare_pricing_lists_competitors_without_prices():
    out = await compare_pricing(fixture_context(), ComparePricingInput())
    assert out.no_prices_found == ["Quietly"]


async def test_compare_pricing_skips_deleted_pages():
    ctx = fixture_context()
    ctx = type(ctx)(**{**ctx.__dict__, "monitored_url_ids": frozenset()})
    out = await compare_pricing(ctx, ComparePricingInput(competitors=["Brightdesk"]))
    assert out.competitors[0].plans == []
    assert out.competitors[0].changes  # the history of what happened still stands


class FakeCursor:
    def __init__(self, docs):
        self.docs = docs

    def sort(self, *_):
        return self

    def limit(self, *_):
        return self

    def __aiter__(self):
        self._it = iter(self.docs)
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration


class FakeCollection:
    def __init__(self):
        self.filters = []

    def find(self, match, projection=None):
        self.filters.append(match)
        return FakeCursor([])


async def test_mongo_queries_are_always_scoped_to_the_workspace():
    mongo = type(
        "Mongo", (), {"insights": FakeCollection(), "page_chunks": FakeCollection()}
    )()
    data = MongoCompetitorData(mongo, "org", "ws-1")
    await data.insights(InsightQuery(competitor_ids=[BRIGHTDESK]))
    await data.current_pricing_chunks([BRIGHTDESK])
    assert mongo.insights.filters[0]["workspace_id"] == "ws-1"
    assert mongo.insights.filters[0]["kind"] == {"$ne": "monitoring_started"}
    assert mongo.page_chunks.filters[0]["workspace_id"] == "ws-1"
    assert mongo.page_chunks.filters[0]["removed_at"] is None


async def test_mongo_search_stays_in_the_org_namespace(monkeypatch):
    from app.agent import data as data_module

    calls = []

    def fake_search(query, org_id, filters, top_k):
        calls.append(org_id)
        return []

    monkeypatch.setattr(data_module, "search", fake_search)
    await MongoCompetitorData(AsyncMock(), "org-1", "ws-1").search("q", _filters(), 3)
    assert calls == ["org-1"]


async def test_price_sources_say_which_plan_and_change_they_are():
    out = await compare_pricing(
        fixture_context(), ComparePricingInput(competitors=["Tallyline"])
    )
    [tally] = out.competitors
    assert tally.plans[0].summary() == "Plus: €200/year"
    assert tally.changes[0].summary() == "Plus: 20 EUR/month to 200 EUR/year"


async def test_each_price_change_in_an_insight_is_its_own_source():
    from evals.fixtures import INSIGHTS

    doc = {
        **INSIGHTS[3],
        "diff": [
            [
                {"op": "removed", "text": "Pro: $49/month"},
                {"op": "added", "text": "Pro: $39/month"},
                {"op": "removed", "text": "Team: $99/month"},
                {"op": "added", "text": "Team: $89/month"},
            ]
        ],
    }
    ctx = fixture_context()

    async def one_insight(_):
        return [doc]

    ctx.data.insights = one_insight
    out = await compare_pricing(ctx, ComparePricingInput(competitors=["Brightdesk"]))
    assert len({c.id for c in out.competitors[0].changes}) == 2
