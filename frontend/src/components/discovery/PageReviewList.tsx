import { useState } from "react";

import type { UrlInput, UrlType } from "../../api/monitoring";
import { DEFAULT_INTERVAL, INTERVAL_PRESETS, URL_TYPE_OPTIONS, urlError } from "../urlForm";
import { formatInterval } from "../../format";
import "./Discovery.css";

export interface ReviewRow {
  key: string;
  url: string;
  urlType: UrlType;
  label: string;
  interval: number | null;
  keep: boolean;
  /** Why it was suggested; empty for pages the user typed. */
  reason?: string;
}

let nextKey = 0;
export const newRow = (url: string, urlType: UrlType, extra: Partial<ReviewRow> = {}): ReviewRow => ({
  key: `row-${nextKey++}`,
  url,
  urlType,
  label: "",
  interval: DEFAULT_INTERVAL,
  keep: true,
  ...extra,
});

/** Kept rows as monitored-page inputs, without duplicates. */
export function rowsToInputs(rows: ReviewRow[]): UrlInput[] {
  const seen = new Set<string>();
  return rows
    .filter((r) => r.keep && !seen.has(r.url) && seen.add(r.url))
    .map((r) => ({
      url: r.url,
      url_type: r.urlType,
      label: r.urlType === "other" ? r.label.trim() || null : null,
      scrape_interval_minutes: r.interval,
    }));
}

/** Problems that block saving, if any. */
export function rowsError(rows: ReviewRow[]): string | null {
  const kept = rows.filter((r) => r.keep);
  if (!kept.length) return "Keep or add at least one page to monitor";
  if (kept.some((r) => r.urlType === "other" && !r.label.trim())) return "Say what each “Other” page is";
  return null;
}

const INTERVALS = [
  ...INTERVAL_PRESETS.map((p) => ({ value: String(p.minutes), label: p.label })),
  { value: "manual", label: "Manual only" },
];

interface PageReviewListProps {
  rows: ReviewRow[];
  onChange: (rows: ReviewRow[]) => void;
  /** Allow typing in another URL below the list. */
  allowAdd?: boolean;
}

/** Suggested pages to keep or drop, each with an editable type and check frequency. */
export function PageReviewList({ rows, onChange, allowAdd = true }: PageReviewListProps) {
  const [draft, setDraft] = useState("");
  const [draftError, setDraftError] = useState<string | null>(null);
  const set = (key: string, patch: Partial<ReviewRow>) =>
    onChange(rows.map((r) => (r.key === key ? { ...r, ...patch } : r)));

  const add = () => {
    const url = draft.trim();
    const problem = urlError(url);
    setDraftError(problem);
    if (problem) return;
    if (rows.some((r) => r.url === url)) return setDraftError("Already in the list");
    onChange([...rows, newRow(url, "homepage")]);
    setDraft("");
  };

  return (
    <div className="review">
      <ul className="review__list">
        {rows.map((r) => (
          <li key={r.key} className={`review__row${r.keep ? "" : " review__row--off"}`}>
            <input
              type="checkbox"
              className="review__keep"
              checked={r.keep}
              onChange={(e) => set(r.key, { keep: e.target.checked })}
              aria-label={`Monitor ${r.url}`}
            />
            <div className="review__main">
              <span className="review__url" title={r.url}>
                {r.url}
              </span>
              {r.reason && <span className="review__reason">{r.reason}</span>}
              <div className="review__controls">
                <select
                  value={r.urlType}
                  aria-label={`Page type of ${r.url}`}
                  onChange={(e) => set(r.key, { urlType: e.target.value as UrlType })}
                  disabled={!r.keep}
                >
                  {URL_TYPE_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
                {r.urlType === "other" && (
                  <input
                    className="review__label"
                    placeholder="What is it? e.g. LinkedIn"
                    aria-label={`What ${r.url} is`}
                    value={r.label}
                    maxLength={100}
                    onChange={(e) => set(r.key, { label: e.target.value })}
                    disabled={!r.keep}
                  />
                )}
                <select
                  value={r.interval === null ? "manual" : String(r.interval)}
                  aria-label={`Check frequency of ${r.url}`}
                  onChange={(e) => set(r.key, { interval: e.target.value === "manual" ? null : Number(e.target.value) })}
                  disabled={!r.keep}
                >
                  {r.interval !== null && !INTERVALS.some((o) => o.value === String(r.interval)) && (
                    <option value={String(r.interval)}>{formatInterval(r.interval)}</option>
                  )}
                  {INTERVALS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </li>
        ))}
      </ul>
      {allowAdd && (
        <div className="review__add">
          <input
            type="url"
            inputMode="url"
            placeholder="Add another page, e.g. https://example.com/pricing"
            aria-label="Add another page"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                add();
              }
            }}
          />
          <button type="button" className="btn btn--text" onClick={add}>
            Add
          </button>
        </div>
      )}
      {draftError && <p className="review__error">{draftError}</p>}
    </div>
  );
}
