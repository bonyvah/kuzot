import type { ReactNode } from "react";

import { URL_TYPES, type Competitor, type SearchFilters, type UrlType } from "../api/monitoring";
import { urlTypeLabel } from "./urlForm";
import "./FilterBar.css";

export interface FilterState {
  competitorIds: string[];
  urlTypes: UrlType[];
  /** Days back, or 0 for any time. */
  changedWithinDays: number;
}

export const EMPTY_FILTERS: FilterState = { competitorIds: [], urlTypes: [], changedWithinDays: 0 };

const CHANGED_OPTIONS = [
  { days: 0, label: "Any time" },
  { days: 1, label: "Last 24 hours" },
  { days: 7, label: "Last 7 days" },
  { days: 30, label: "Last 30 days" },
];

/** Request filters; an empty selection means "all". */
export function toApiFilters(f: FilterState, now = Date.now()): SearchFilters {
  return {
    competitor_ids: f.competitorIds.length ? f.competitorIds : null,
    url_types: f.urlTypes.length ? f.urlTypes : null,
    // The backend compares against naive UTC timestamps.
    changed_since: f.changedWithinDays
      ? new Date(now - f.changedWithinDays * 86_400_000).toISOString().replace("Z", "")
      : null,
  };
}

function toggle<T>(list: T[], value: T): T[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
}

interface FilterBarProps {
  competitors: Competitor[];
  value: FilterState;
  onChange: (next: FilterState) => void;
}

export function FilterBar({ competitors, value, onChange }: FilterBarProps) {
  return (
    <div className="filters">
      {competitors.length > 0 && (
        <fieldset className="filters__group">
          <legend className="filters__legend">Competitors</legend>
          <FilterChip active={!value.competitorIds.length} onClick={() => onChange({ ...value, competitorIds: [] })}>
            All
          </FilterChip>
          {competitors.map((c) => (
            <FilterChip
              key={c.id}
              active={value.competitorIds.includes(c.id)}
              onClick={() => onChange({ ...value, competitorIds: toggle(value.competitorIds, c.id) })}
            >
              {c.name}
            </FilterChip>
          ))}
        </fieldset>
      )}
      <fieldset className="filters__group">
        <legend className="filters__legend">Content</legend>
        <FilterChip active={!value.urlTypes.length} onClick={() => onChange({ ...value, urlTypes: [] })}>
          All
        </FilterChip>
        {URL_TYPES.map((t) => (
          <FilterChip
            key={t}
            active={value.urlTypes.includes(t)}
            onClick={() => onChange({ ...value, urlTypes: toggle(value.urlTypes, t) })}
          >
            {urlTypeLabel(t)}
          </FilterChip>
        ))}
      </fieldset>
      <fieldset className="filters__group">
        <legend className="filters__legend">Changed</legend>
        {CHANGED_OPTIONS.map((o) => (
          <FilterChip
            key={o.days}
            active={value.changedWithinDays === o.days}
            onClick={() => onChange({ ...value, changedWithinDays: o.days })}
          >
            {o.label}
          </FilterChip>
        ))}
      </fieldset>
    </div>
  );
}

export function FilterChip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button type="button" className={`filter-chip${active ? " filter-chip--on" : ""}`} aria-pressed={active} onClick={onClick}>
      {active && (
        <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
          <path fill="currentColor" d="M9 16.17 4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" />
        </svg>
      )}
      {children}
    </button>
  );
}
