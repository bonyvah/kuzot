"""Typed tools over competitor data, shared by the agent and the MCP server.

Inputs and outputs are Pydantic models, so both callers get the same validation
and the same JSON schema. Inputs reject unknown fields: a workspace id sent by a
model is an error, never a filter.
"""

from collections.abc import Awaitable, Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from app.agent.data import InsightQuery, ToolContext
from app.agent.pricing import Money, PriceChange, diff_prices, extract_prices
from app.insights.builder import line_diff
from app.models.monitored_url import URLType
from app.rag.search import SearchFilters
from app.schemas.insight import DiffLine

MAX_DIFF_LINES = 40
MAX_LINE_CHARS = 300
MAX_PLANS_PER_PAGE = 30


class ToolError(Exception):
    """A bad request the caller can correct; the message says how."""


def _naive_utc(value: datetime | None) -> datetime | None:
    # stored datetimes are naive UTC
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


Since = Annotated[datetime | None, AfterValidator(_naive_utc)]


class ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Evidence(BaseModel):
    """Something the tool read from a page, which an answer can cite."""

    id: str
    competitor: str
    url: str
    source: int | None = Field(
        default=None, description="Cite as [source]. Set only inside the agent."
    )

    def summary(self) -> str:
        raise NotImplementedError


class ToolOutput(BaseModel):
    def evidence(self) -> Iterator[Evidence]:
        yield from _walk(self)


def _walk(value: object) -> Iterator[Evidence]:
    if isinstance(value, Evidence):
        yield value
    if isinstance(value, BaseModel):
        for name in type(value).model_fields:
            yield from _walk(getattr(value, name))
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


class ChangeEvent(Evidence):
    kind: Literal["change", "monitoring_started"] = "change"
    url_type: URLType
    label: str | None = None
    detected_at: datetime
    headline: str
    diff: list[DiffLine] = Field(description="Changed lines with a little context.")
    added_count: int
    removed_count: int

    def summary(self) -> str:
        return self.headline


class MoneyOut(BaseModel):
    amount: float
    currency: str
    period: Literal["month", "year"] | None = None


class PlanPrice(Evidence):
    label: str = Field(description="Plan or product; empty when the page doesn't say.")
    price: MoneyOut
    raw: str = Field(description="The page line the price was read from.")
    first_seen_at: datetime

    def summary(self) -> str:
        if not self.label or self.label.casefold() in self.raw.casefold():
            return self.raw
        return f"{self.label}: {self.raw}"


class PriceChangeOut(Evidence):
    label: str
    direction: Literal["increase", "decrease", "added", "removed", "terms_changed"]
    old: MoneyOut | None = None
    new: MoneyOut | None = None
    change_pct: float | None = Field(
        default=None, description="Only when currency and period stayed the same."
    )
    detected_at: datetime

    def summary(self) -> str:
        return f"{self.label or 'Price'}: {_shown(self.old)} to {_shown(self.new)}"


def _shown(price: MoneyOut | None) -> str:
    if price is None:
        return "none"
    per = f"/{price.period}" if price.period else ""
    return f"{price.amount:g} {price.currency}{per}"


class SearchChangesInput(ToolInput):
    query: str = Field(min_length=1, max_length=500)
    competitors: list[str] | None = Field(
        default=None, description="Competitor names; omit for all of them."
    )
    url_types: list[URLType] | None = None
    since: Since = Field(
        default=None, description="Only changes at or after this time."
    )
    limit: int = Field(default=8, ge=1, le=20)


class SearchChangesOutput(ToolOutput):
    matches: list[ChangeEvent] = Field(description="Changes closest to the query.")
    other_recent_changes: list[ChangeEvent] = Field(
        description="Newest other changes, which may have nothing to do with the query."
    )


class PageHistoryInput(ToolInput):
    competitor: str = Field(min_length=1)
    url_type: URLType | None = None
    since: Since = None
    limit: int = Field(default=15, ge=1, le=50)


class PageHistoryOutput(ToolOutput):
    competitor: str
    events: list[ChangeEvent] = Field(description="Newest first.")


class ComparePricingInput(ToolInput):
    competitors: list[str] | None = Field(
        default=None, description="Competitor names; omit for all of them."
    )
    since: Since = Field(
        default=None, description="Only price changes after this time."
    )


class CompetitorPricing(BaseModel):
    competitor: str
    pricing_pages: list[str]
    plans: list[PlanPrice] = Field(description="Prices on the page now.")
    changes: list[PriceChangeOut] = Field(description="Price changes, newest first.")


class ComparePricingOutput(ToolOutput):
    competitors: list[CompetitorPricing]
    no_prices_found: list[str] = Field(
        description="Competitors with no readable price on a monitored pricing page."
    )


def _resolve(ctx: ToolContext, names: list[str] | None) -> list[str] | None:
    """Names to competitor ids; None means every competitor in the workspace."""
    if not names:
        return None
    by_name = {name.casefold(): id_ for id_, name in ctx.competitors.items()}
    unknown = [n for n in names if n.casefold() not in by_name]
    if unknown:
        known = ", ".join(sorted(ctx.competitors.values())) or "none"
        raise ToolError(f"Unknown competitor: {', '.join(unknown)}. Known: {known}")
    return [by_name[n.casefold()] for n in names]


def _hunks(doc: dict) -> list[list[dict]]:
    # insights stored before line diffs existed only have the passages
    return doc.get("diff") or line_diff(doc.get("removed", []), doc.get("added", []))


def _change_event(doc: dict, ctx: ToolContext) -> ChangeEvent:
    lines = [line for hunk in _hunks(doc) for line in hunk]
    return ChangeEvent(
        id=str(doc["_id"]),
        kind=doc.get("kind", "change"),
        competitor=ctx.competitors[doc["competitor_id"]],
        url=doc["url"],
        url_type=doc["url_type"],
        label=doc.get("label"),
        detected_at=doc["detected_at"],
        headline=doc["headline"],
        diff=[
            DiffLine(op=line["op"], text=line["text"][:MAX_LINE_CHARS])
            for line in lines[:MAX_DIFF_LINES]
        ],
        added_count=doc["added_count"],
        removed_count=doc["removed_count"],
    )


def _live(docs: list[dict], ctx: ToolContext) -> list[dict]:
    # insights of deleted competitors stay in Mongo but aren't shown anywhere
    return [d for d in docs if d["competitor_id"] in ctx.competitors]


def _epoch(value: datetime) -> int:
    return int(value.replace(tzinfo=UTC).timestamp())


def _money(value: Money | None) -> MoneyOut | None:
    if value is None:
        return None
    return MoneyOut(
        amount=float(value.amount), currency=value.currency, period=value.period
    )


async def search_changes(
    ctx: ToolContext, params: SearchChangesInput
) -> SearchChangesOutput:
    """Search what competitors changed on their pages, by meaning.

    Use for questions about what changed or was launched. Returns changes closest
    to the query, then the newest others in case the search missed something.
    """
    competitor_ids = _resolve(ctx, params.competitors)
    url_types = [str(t) for t in params.url_types] if params.url_types else None
    hits = await ctx.data.search(
        params.query,
        SearchFilters(
            workspace_id=ctx.workspace_id,
            competitor_ids=competitor_ids,
            url_types=url_types,
            changed_since=params.since,
        ),
        min(params.limit * 3, 50),
    )
    docs = _live(
        await ctx.data.insights(InsightQuery(competitor_ids, url_types, params.since)),
        ctx,
    )
    # A chunk's dates equal the scrape that added or removed it. One with no
    # insight on either date came from a page's first scrape, so it isn't a change.
    by_scrape = {(d["monitored_url_id"], _epoch(d["detected_at"])): d for d in docs}
    matched: dict[str, dict] = {}
    for hit in hits:
        for at in (hit.removed_at, hit.first_seen_at):
            doc = by_scrape.get((hit.monitored_url_id, _epoch(at))) if at else None
            if doc is not None:
                matched.setdefault(str(doc["_id"]), doc)
    matches = list(matched.values())[: params.limit]
    others = [d for d in docs if str(d["_id"]) not in matched]
    others = others[: params.limit - len(matches)]
    return SearchChangesOutput(
        matches=[_change_event(d, ctx) for d in matches],
        other_recent_changes=[_change_event(d, ctx) for d in others],
    )


async def get_page_history(
    ctx: ToolContext, params: PageHistoryInput
) -> PageHistoryOutput:
    """List one competitor's page changes in time order, newest first.

    Use for how a competitor's page evolved. Includes when monitoring started, so
    an empty history before that date means Kuzot wasn't watching yet.
    """
    competitor_id = _resolve(ctx, [params.competitor])[0]
    docs = await ctx.data.insights(
        InsightQuery(
            competitor_ids=[competitor_id],
            url_types=[str(params.url_type)] if params.url_type else None,
            since=params.since,
            include_started=True,
            limit=params.limit,
        )
    )
    return PageHistoryOutput(
        competitor=ctx.competitors[competitor_id],
        events=[_change_event(d, ctx) for d in docs],
    )


def _plans(chunks: list[dict], competitor: str) -> list[PlanPrice]:
    plans: dict[tuple, PlanPrice] = {}
    for chunk in chunks:
        for mention in extract_prices(chunk["text"].splitlines()):
            key = (chunk["url"], mention.label.casefold(), mention.money)
            plans.setdefault(
                key,
                PlanPrice(
                    # per price: a citation has to lead to the very line it quotes
                    id=f"price:{chunk['monitored_url_id']}:{mention.raw}",
                    competitor=competitor,
                    url=chunk["url"],
                    label=mention.label,
                    price=_money(mention.money),
                    raw=mention.raw[:MAX_LINE_CHARS],
                    first_seen_at=chunk["first_seen_at"],
                ),
            )
    return list(plans.values())[:MAX_PLANS_PER_PAGE]


def _price_changes(doc: dict, competitor: str) -> list[PriceChangeOut]:
    return [
        _price_change_out(change, doc, competitor)
        for change in diff_prices(_hunks(doc))
    ]


def _price_change_out(
    change: PriceChange, doc: dict, competitor: str
) -> PriceChangeOut:
    return PriceChangeOut(
        # per change: one page edit can move several prices
        id=f"{doc['_id']}:{change.label}",
        competitor=competitor,
        url=doc["url"],
        label=change.label,
        direction=change.direction,
        old=_money(change.old),
        new=_money(change.new),
        change_pct=change.change_pct,
        detected_at=doc["detected_at"],
    )


async def compare_pricing(
    ctx: ToolContext, params: ComparePricingInput
) -> ComparePricingOutput:
    """Compare competitors' current prices and how those prices changed.

    Prices are parsed from monitored pricing pages, not estimated. Use for any
    question about how much a competitor charges or how prices moved.
    """
    ids = _resolve(ctx, params.competitors) or list(ctx.competitors)
    chunks = [
        c
        for c in await ctx.data.current_pricing_chunks(ids)
        if c["monitored_url_id"] in ctx.monitored_url_ids
    ]
    docs = _live(
        await ctx.data.insights(InsightQuery(ids, ["pricing"], params.since)), ctx
    )
    results, without = [], []
    for competitor_id in ids:
        name = ctx.competitors[competitor_id]
        plans = _plans([c for c in chunks if c["competitor_id"] == competitor_id], name)
        changes = [
            change
            for doc in docs
            if doc["competitor_id"] == competitor_id
            for change in _price_changes(doc, name)
        ]
        if not plans and not changes:
            without.append(name)
            continue
        results.append(
            CompetitorPricing(
                competitor=name,
                pricing_pages=sorted({p.url for p in plans}),
                plans=plans,
                changes=changes,
            )
        )
    return ComparePricingOutput(competitors=results, no_prices_found=without)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_model: type[ToolInput]
    output_model: type[ToolOutput]
    fn: Callable[[ToolContext, ToolInput], Awaitable[ToolOutput]]

    def openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_model.model_json_schema(),
            },
        }


def _spec(fn, input_model, output_model) -> ToolSpec:
    return ToolSpec(
        name=fn.__name__,
        description=" ".join(fn.__doc__.split()),
        input_model=input_model,
        output_model=output_model,
        fn=fn,
    )


TOOLS = {
    spec.name: spec
    for spec in (
        _spec(search_changes, SearchChangesInput, SearchChangesOutput),
        _spec(get_page_history, PageHistoryInput, PageHistoryOutput),
        _spec(compare_pricing, ComparePricingInput, ComparePricingOutput),
    )
}
