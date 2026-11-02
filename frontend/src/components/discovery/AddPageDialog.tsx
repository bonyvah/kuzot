import { useEffect, useRef, useState } from "react";

import { errorText } from "../../api/client";
import { discoveryApi, type UrlInput } from "../../api/monitoring";
import { Button } from "../Button";
import { defaultPageSettings, PageFields, pageSettingsErrors } from "../PageFields";
import { TextField } from "../TextField";
import { urlError } from "../urlForm";
import { newRow, PageReviewList, rowsError, rowsToInputs, type ReviewRow } from "./PageReviewList";
import "../Dialog.css";
import "./Discovery.css";

interface AddPageDialogProps {
  competitorId: string;
  competitorName: string;
  /** Saves the pages one after another. */
  onSave: (pages: UrlInput[]) => Promise<void>;
  onClose: () => void;
}

/** Add a page to a competitor: type its address, or describe it and let Kuzot find it. */
export function AddPageDialog({ competitorId, competitorName, onSave, onClose }: AddPageDialogProps) {
  const [mode, setMode] = useState<"address" | "find">("address");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Address mode
  const [url, setUrl] = useState("");
  const [page, setPage] = useState(() => defaultPageSettings("pricing"));
  const [fieldErrors, setFieldErrors] = useState<{ url?: string | null; label?: string | null; interval?: string | null }>({});

  // Find mode
  const [query, setQuery] = useState("");
  const [rows, setRows] = useState<ReviewRow[] | null>(null);
  const [findings, setFindings] = useState<string[]>([]);
  const [searching, setSearching] = useState(false);
  const abort = useRef<AbortController | null>(null);

  const dialogRef = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    dialogRef.current?.showModal();
    return () => abort.current?.abort();
  }, []);

  const find = async () => {
    if (!query.trim()) return setError("Describe the page you're looking for");
    setError(null);
    setSearching(true);
    setRows(null);
    abort.current = new AbortController();
    try {
      const result = await discoveryApi.findPage(competitorId, query.trim(), abort.current.signal);
      // Nothing is added until the user ticks it.
      setRows(result.pages.map((p) => newRow(p.url, p.url_type, { label: p.label ?? "", reason: p.reason, keep: false })));
      setFindings(result.notes);
    } catch (err) {
      if ((err as Error).name !== "AbortError") setError(errorText(err));
    } finally {
      setSearching(false);
    }
  };

  const save = async () => {
    let pages: UrlInput[];
    if (mode === "address") {
      const value = url.trim();
      const errors = { url: urlError(value), ...pageSettingsErrors(page) };
      setFieldErrors(errors);
      if (errors.url || errors.label || errors.interval) return;
      pages = [
        {
          url: value,
          url_type: page.urlType,
          label: page.urlType === "other" ? page.label.trim() : null,
          scrape_interval_minutes: page.interval,
        },
      ];
    } else {
      const problem = rows ? rowsError(rows) : "Find pages first";
      if (problem) return setError(problem === "Keep or add at least one page to monitor" ? "Tick the pages to add" : problem);
      pages = rowsToInputs(rows ?? []);
    }
    setError(null);
    setSaving(true);
    try {
      await onSave(pages);
    } catch (err) {
      setError(errorText(err));
      setSaving(false);
    }
  };

  const picked = rows?.filter((r) => r.keep).length ?? 0;

  return (
    <dialog
      ref={dialogRef}
      className="dialog wizard"
      aria-labelledby="add-page-title"
      onCancel={(e) => {
        e.preventDefault();
        if (!saving) onClose();
      }}
    >
      <form
        className="dialog__form"
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          if (mode === "find" && !rows && !searching) find();
          else if (!saving && !searching) save();
        }}
      >
        <h2 id="add-page-title" className="dialog__title">
          Monitor a page
        </h2>
        <div className="dialog-tabs" role="tablist">
          <button type="button" role="tab" aria-selected={mode === "address"} onClick={() => setMode("address")}>
            Enter address
          </button>
          <button type="button" role="tab" aria-selected={mode === "find"} onClick={() => setMode("find")}>
            ✨ Find with AI
          </button>
        </div>

        {mode === "address" ? (
          <div className="dialog__body" role="tabpanel">
            <TextField
              label="Page address"
              type="url"
              inputMode="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              error={fieldErrors.url}
              autoFocus
            />
            <PageFields value={page} onChange={setPage} errors={fieldErrors} />
          </div>
        ) : (
          <div className="dialog__body" role="tabpanel">
            <div className="add-page__find">
              <TextField
                label={`What should we find on ${competitorName}?`}
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setRows(null);
                }}
                autoFocus
                maxLength={500}
              />
              <Button type="button" onClick={find} disabled={searching}>
                {searching ? "Searching…" : "Find"}
              </Button>
            </div>
            <p className="add-page__hint">For example: their pricing page, Telegram channel, release notes.</p>
            {searching && (
              <div className="wizard__searching" role="status">
                <span className="wizard__spinner" aria-hidden="true" />
                <p>Looking through {competitorName}'s site{findings.length ? "" : " and the web"}…</p>
              </div>
            )}
            {rows && !searching && (
              <div className="add-page__results">
                {findings.map((n) => (
                  <p key={n} className="wizard__note">
                    {n}
                  </p>
                ))}
                {rows.length ? (
                  <>
                    <p className="dialog__lead">Tick the pages to add.</p>
                    <PageReviewList rows={rows} onChange={setRows} allowAdd={false} />
                  </>
                ) : (
                  <p className="page__note">Nothing new found. Try describing it differently, or enter the address.</p>
                )}
              </div>
            )}
          </div>
        )}

        {error && (
          <p className="dialog__error" role="alert">
            {error}
          </p>
        )}
        <div className="dialog__actions">
          <Button variant="text" onClick={searching ? () => abort.current?.abort() : onClose} disabled={saving}>
            {searching ? "Stop searching" : "Cancel"}
          </Button>
          <Button type="submit" variant="text" disabled={saving || searching || (mode === "find" && !picked)}>
            {saving ? "Adding…" : mode === "find" && picked > 1 ? `Add ${picked} pages` : "Add"}
          </Button>
        </div>
      </form>
    </dialog>
  );
}
