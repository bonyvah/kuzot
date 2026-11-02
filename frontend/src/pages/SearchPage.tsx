import { useState } from "react";

import { errorText } from "../api/client";
import type { SearchHit } from "../api/monitoring";
import { useCompetitors, useSearch } from "../api/queries";
import { Button } from "../components/Button";
import { EMPTY_FILTERS, FilterBar, FilterChip, toApiFilters, type FilterState } from "../components/FilterBar";
import { SourceCard } from "../components/SourceCard";
import { TextField } from "../components/TextField";
import { useCurrentWorkspace } from "./WorkspacePage";
import "./Intelligence.css";

/** Semantic search over everything scraped from this workspace's competitors. */
export function SearchPage() {
  const ws = useCurrentWorkspace();
  const competitors = useCompetitors(ws.id);
  const search = useSearch(ws.id);
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState<FilterState>(EMPTY_FILTERS);
  // "all" includes text that has since been removed from the page.
  const [includeRemoved, setIncludeRemoved] = useState(false);
  const [queryError, setQueryError] = useState<string | null>(null);

  const run = () => {
    const q = query.trim();
    if (!q) return setQueryError("Enter what you're looking for");
    setQueryError(null);
    search.mutate({ query: q, scope: includeRemoved ? "all" : "current", top_k: 20, ...toApiFilters(filters) });
  };

  return (
    <section className="page__section" aria-label="Search">
      <form
        className="intel-form"
        role="search"
        onSubmit={(e) => {
          e.preventDefault();
          run();
        }}
      >
        <div className="intel-form__row">
          <TextField
            label="Search competitor pages"
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            error={queryError}
            maxLength={1000}
            autoFocus
          />
          <Button type="submit" disabled={search.isPending}>
            {search.isPending ? "Searching…" : "Search"}
          </Button>
        </div>
        <FilterBar competitors={competitors.data?.items ?? []} value={filters} onChange={setFilters} />
        <fieldset className="filters__group">
          <legend className="filters__legend">History</legend>
          <FilterChip active={includeRemoved} onClick={() => setIncludeRemoved((v) => !v)}>
            Include removed text
          </FilterChip>
        </fieldset>
      </form>

      {search.error && <p className="page__error">{errorText(search.error)}</p>}
      {search.data && <Results hits={search.data.hits} query={search.data.query} />}
    </section>
  );
}

function Results({ hits, query }: { hits: SearchHit[]; query: string }) {
  if (!hits.length) {
    return (
      <div className="blank intel-results">
        <h2 className="blank__title">No matches for “{query}”</h2>
        <p>Try other words or fewer filters. Pages appear here after their first successful scrape.</p>
      </div>
    );
  }
  return (
    <ol className="intel-results hits" aria-label={`${hits.length} results for ${query}`}>
      {hits.map((hit) => (
        <li key={hit.chunk_id}>
          <SourceCard source={hit} />
        </li>
      ))}
    </ol>
  );
}
