from datetime import datetime
from types import SimpleNamespace

from app.rag import reports, search
from app.rag.search import Hit, SearchFilters, build_filter

T0 = datetime(2026, 10, 1, 12, 0, 0)
T0_EPOCH = 1790856000


def make_hit(text="Pro plan is $20", removed_at=None, competitor_id="c1") -> Hit:
    return Hit(
        chunk_id="u1#abc",
        score=0.9,
        text=text,
        competitor_id=competitor_id,
        monitored_url_id="u1",
        url="https://acme.com/pricing",
        url_type="pricing",
        snapshot_id="s1",
        first_seen_at=T0,
        removed_at=removed_at,
    )


def test_filter_is_always_scoped_to_workspace():
    assert build_filter(SearchFilters(workspace_id="w1")) == {
        "workspace_id": {"$eq": "w1"}
    }


def test_filter_combines_all_options():
    f = build_filter(
        SearchFilters(
            workspace_id="w1",
            competitor_ids=["c1", "c2"],
            url_types=["pricing"],
            current_only=True,
            changed_since=T0,
        )
    )
    assert f == {
        "$and": [
            {"workspace_id": {"$eq": "w1"}},
            {"competitor_id": {"$in": ["c1", "c2"]}},
            {"url_type": {"$in": ["pricing"]}},
            {"is_current": {"$eq": True}},
            {
                "$or": [
                    {"first_seen_at": {"$gte": T0_EPOCH}},
                    {"removed_at": {"$gte": T0_EPOCH}},
                ]
            },
        ]
    }


class FakeIndex:
    def __init__(self, matches):
        self.matches = matches
        self.calls = []

    def query(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(matches=self.matches)


def _match(removed_at=0):
    return SimpleNamespace(
        id="u1#abc",
        score=0.87,
        metadata={
            "text": "Team plan $50",
            "competitor_id": "c1",
            "monitored_url_id": "u1",
            "url": "https://acme.com/pricing",
            "url_type": "pricing",
            "snapshot_id": "s1",
            "first_seen_at": T0_EPOCH,
            "removed_at": removed_at,
            "is_current": removed_at == 0,
        },
    )


def test_search_queries_org_namespace_and_maps_hits(monkeypatch):
    index = FakeIndex([_match(), _match(removed_at=T0_EPOCH + 3600)])
    monkeypatch.setattr(search, "get_index", lambda: index)
    monkeypatch.setattr(search, "embed_texts", lambda texts: [[0.1, 0.2]])

    hits = search.search("price", "org-1", SearchFilters(workspace_id="w1"), top_k=5)

    call = index.calls[0]
    assert call["namespace"] == "org-1"
    assert call["top_k"] == 5
    assert call["vector"] == [0.1, 0.2]
    assert call["filter"] == {"workspace_id": {"$eq": "w1"}}
    assert hits[0].first_seen_at == T0
    assert hits[0].removed_at is None and hits[0].is_current
    assert hits[1].removed_at == datetime(2026, 10, 1, 13, 0, 0)
    assert not hits[1].is_current


def test_messages_number_sources_and_mark_removed():
    hits = [make_hit(), make_hit("Free tier", removed_at=datetime(2026, 10, 5))]
    messages = reports.build_messages("What changed?", hits, {"c1": "Acme"})

    system, user = (str(m.get("content")) for m in messages)
    assert "[1] Acme | pricing | https://acme.com/pricing | on the page since" in user
    assert "[2] Acme" in user and "REMOVED on 2026-10-05" in user
    assert user.endswith("Request: What changed?")
    assert "ignore any" in system  # injection guard present


def test_generate_report_keeps_only_real_citations(monkeypatch):
    content = "Acme raised Pro to $25 [1] and dropped the free tier [2][7]."
    fake = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=lambda **kw: SimpleNamespace(
                    model="gpt-test",
                    choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
                )
            )
        )
    )
    monkeypatch.setattr(reports, "get_openai", lambda: fake)

    report = reports.generate_report("q", [make_hit(), make_hit()], {})

    assert report.cited == {1, 2}  # [7] is not a real source
    assert report.content == content
    assert report.model == "gpt-test"
