import { useEffect, useRef, useState, type ReactNode } from "react";

import { ApiError, errorText } from "../../api/client";
import { discoveryApi, type ChannelHint, type Competitor, type UrlType } from "../../api/monitoring";
import { useCreateCompetitor } from "../../api/queries";
import { Button } from "../Button";
import { TextArea } from "../TextArea";
import { TextField } from "../TextField";
import { urlError } from "../urlForm";
import { newRow, PageReviewList, rowsError, rowsToInputs, type ReviewRow } from "./PageReviewList";
import "../Dialog.css";
import "./Discovery.css";

type Step = 1 | 2 | 3;

type ChannelKey = "instagram" | "telegram" | "facebook" | "x" | "web";

const CHANNELS: { key: ChannelKey; label: string; type: UrlType; placeholder: string; icon: ReactNode }[] = [
  { key: "instagram", label: "Instagram", type: "instagram", placeholder: "@handle or link", icon: <IconInstagram /> },
  { key: "telegram", label: "Telegram", type: "telegram", placeholder: "@channel or t.me link", icon: <IconTelegram /> },
  { key: "facebook", label: "Facebook", type: "facebook", placeholder: "Page name or link", icon: <IconFacebook /> },
  { key: "x", label: "X", type: "x", placeholder: "@handle or link", icon: <IconX /> },
  { key: "web", label: "Web", type: "homepage", placeholder: "Another web page, e.g. a marketplace listing", icon: <IconWeb /> },
];

interface Custom {
  key: number;
  label: string;
  value: string;
}

interface CompetitorWizardProps {
  workspaceId: string;
  onClose: () => void;
  onCreated: (competitor: Competitor) => void;
}

/**
 * Add a competitor in three steps: basics, optional hints about where they
 * post, then a reviewed list of pages that Kuzot found (or just the website).
 */
export function CompetitorWizard({ workspaceId, onClose, onCreated }: CompetitorWizardProps) {
  const create = useCreateCompetitor(workspaceId);
  const [step, setStep] = useState<Step>(1);

  // Step 1
  const [name, setName] = useState("");
  const [website, setWebsite] = useState("");
  const [description, setDescription] = useState("");
  const [basicsErrors, setBasicsErrors] = useState<{ name?: string | null; website?: string | null }>({});

  // Step 2
  const [notes, setNotes] = useState("");
  const [picked, setPicked] = useState<Partial<Record<ChannelKey, string>>>({});
  const [customs, setCustoms] = useState<Custom[]>([]);

  // Step 3
  const [rows, setRows] = useState<ReviewRow[]>([]);
  const [findings, setFindings] = useState<string[]>([]);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abort = useRef<AbortController | null>(null);
  // Why a search was aborted: "back" leaves step 3, "stop" stays on it.
  const stoppedBy = useRef<"back" | "stop">("stop");
  const leftViaBack = () => stoppedBy.current === "back";

  const dialogRef = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    dialogRef.current?.showModal();
    return () => abort.current?.abort();
  }, []);

  const site = website.trim();
  const basicsValid = () => {
    const errors = { name: name.trim() ? null : "Enter a name", website: site ? urlError(site) : null };
    setBasicsErrors(errors);
    return !errors.name && !errors.website;
  };

  /** Without hints: just the website, as a daily-checked homepage. */
  const skipToReview = () => {
    setRows(site ? [newRow(site, "homepage")] : []);
    setFindings([]);
    setError(null);
    setStep(3);
  };

  const findPages = async () => {
    setStep(3);
    setRows([]);
    setFindings([]);
    setError(null);
    setSearching(true);
    stoppedBy.current = "stop";
    abort.current = new AbortController();
    const hints: ChannelHint[] = [
      ...CHANNELS.filter((c) => picked[c.key] !== undefined && !(c.key === "web" && !picked[c.key]?.trim())).map(
        (c) => ({ url_type: c.type, value: picked[c.key]?.trim() ?? "" }),
      ),
      ...customs
        .filter((c) => c.value.trim())
        .map((c) => ({ url_type: "other" as const, value: c.value.trim(), label: c.label.trim() || null })),
    ];
    try {
      const result = await discoveryApi.forNewCompetitor(
        workspaceId,
        {
          name: name.trim(),
          website: site || null,
          description: description.trim() || null,
          notes: notes.trim() || null,
          hints,
        },
        abort.current.signal,
      );
      setRows(
        result.pages.map((p) =>
          newRow(p.url, p.url_type, { label: p.label ?? "", reason: p.reason || undefined }),
        ),
      );
      setFindings(result.notes);
    } catch (err) {
      if ((err as Error).name === "AbortError") {
        if (leftViaBack()) return;
        skipToReview();
        setFindings(["Search cancelled. Add pages yourself, or go back and try again."]);
      } else {
        // Fall back to the website so the user can still continue.
        setRows(site ? [newRow(site, "homepage")] : []);
        setError(err instanceof ApiError ? `Couldn't find pages: ${err.message}` : errorText(err));
      }
    } finally {
      setSearching(false);
    }
  };

  const save = async () => {
    const problem = rowsError(rows);
    if (problem) return setError(problem);
    setError(null);
    try {
      const competitor = await create.mutateAsync({
        name: name.trim(),
        website_url: site || null,
        description: description.trim() || null,
        initial_urls: rowsToInputs(rows),
      });
      onCreated(competitor);
    } catch (err) {
      setError(errorText(err));
    }
  };

  const busy = searching || create.isPending;
  const hasHints =
    !!notes.trim() || Object.keys(picked).length > 0 || customs.some((c) => c.value.trim());

  return (
    <dialog
      ref={dialogRef}
      className="dialog wizard"
      aria-labelledby="wizard-title"
      onCancel={(e) => {
        e.preventDefault();
        if (!create.isPending) onClose();
      }}
    >
      <div className="dialog__form">
        <ol className="wizard__steps" aria-label="Steps">
          {["Basics", "Channels", "Pages"].map((label, i) => (
            <li key={label} className={step === i + 1 ? "is-current" : step > i + 1 ? "is-done" : ""} aria-current={step === i + 1 ? "step" : undefined}>
              <span>{i + 1}</span>
              {label}
            </li>
          ))}
        </ol>

        {step === 1 && (
          <>
            <h2 id="wizard-title" className="dialog__title">
              Add a competitor
            </h2>
            <div className="dialog__body">
              <TextField label="Name" value={name} onChange={(e) => setName(e.target.value)} error={basicsErrors.name} autoFocus maxLength={255} />
              <TextField
                label="Website"
                type="url"
                inputMode="url"
                value={website}
                onChange={(e) => setWebsite(e.target.value)}
                error={basicsErrors.website}
              />
              <TextArea label="Description (optional)" value={description} onChange={(e) => setDescription(e.target.value)} rows={2} maxLength={2000} />
            </div>
          </>
        )}

        {step === 2 && (
          <>
            <h2 id="wizard-title" className="dialog__title">
              Help us find their channels
            </h2>
            <p className="dialog__lead">
              Optional. Tick where {name.trim() || "they"} post{name.trim() ? "s" : ""}; add a handle if you know it, or leave it
              empty and Kuzot will look.
            </p>
            <div className="dialog__body">
              <TextArea
                label="What should we watch? (optional)"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={2}
                maxLength={2000}
              />
              <div className="channels" role="group" aria-label="Channels">
                {CHANNELS.map((c) => {
                  const on = picked[c.key] !== undefined;
                  return (
                    <button
                      key={c.key}
                      type="button"
                      className={`channel${on ? " channel--on" : ""}`}
                      aria-pressed={on}
                      onClick={() =>
                        setPicked((p) => {
                          const next = { ...p };
                          if (on) delete next[c.key];
                          else next[c.key] = "";
                          return next;
                        })
                      }
                    >
                      {c.icon}
                      {c.label}
                    </button>
                  );
                })}
                <button
                  type="button"
                  className="channel"
                  onClick={() => setCustoms((cs) => [...cs, { key: Date.now(), label: "", value: "" }])}
                >
                  <IconPlus />
                  More…
                </button>
              </div>
              <div className="channel-fields">
                {CHANNELS.filter((c) => picked[c.key] !== undefined).map((c) => (
                  <label key={c.key} className="channel-field">
                    <span className="channel-field__name">
                      {c.icon}
                      {c.label}
                    </span>
                    <input
                      value={picked[c.key]}
                      placeholder={c.key === "web" ? c.placeholder : `${c.placeholder} (optional)`}
                      onChange={(e) => setPicked((p) => ({ ...p, [c.key]: e.target.value }))}
                    />
                  </label>
                ))}
                {customs.map((c) => (
                  <div key={c.key} className="channel-field channel-field--custom">
                    <input
                      className="channel-field__label"
                      placeholder="Channel, e.g. LinkedIn"
                      aria-label="Channel name"
                      value={c.label}
                      onChange={(e) => setCustoms((cs) => cs.map((x) => (x.key === c.key ? { ...x, label: e.target.value } : x)))}
                    />
                    <input
                      placeholder="Link"
                      aria-label="Channel link"
                      value={c.value}
                      onChange={(e) => setCustoms((cs) => cs.map((x) => (x.key === c.key ? { ...x, value: e.target.value } : x)))}
                    />
                    <button
                      type="button"
                      className="channel-field__remove"
                      aria-label="Remove this channel"
                      onClick={() => setCustoms((cs) => cs.filter((x) => x.key !== c.key))}
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}

        {step === 3 && (
          <>
            <h2 id="wizard-title" className="dialog__title">
              Pages to monitor
            </h2>
            {searching ? (
              <div className="wizard__searching" role="status">
                <span className="wizard__spinner" aria-hidden="true" />
                <div>
                  <p>Looking through {site || "the web"}{hints(picked, customs)} for useful pages…</p>
                  <p className="page__note">This usually takes a few seconds.</p>
                </div>
              </div>
            ) : (
              <>
                <p className="dialog__lead">
                  {rows.length
                    ? "Untick what you don't need, and fix types or frequency. You can change all of this later."
                    : "Add at least one page to monitor."}
                </p>
                {findings.map((n) => (
                  <p key={n} className="wizard__note">
                    {n}
                  </p>
                ))}
                <PageReviewList rows={rows} onChange={setRows} />
              </>
            )}
          </>
        )}

        {error && (
          <p className="dialog__error" role="alert">
            {error}
          </p>
        )}

        <div className="dialog__actions wizard__actions">
          {step > 1 && (
            <Button
              variant="text"
              className="wizard__back"
              disabled={create.isPending}
              onClick={() => {
                stoppedBy.current = "back";
                abort.current?.abort();
                setError(null);
                setStep((s) => (s - 1) as Step);
              }}
            >
              Back
            </Button>
          )}
          <Button variant="text" onClick={searching ? () => abort.current?.abort() : onClose} disabled={create.isPending}>
            {searching ? "Stop searching" : "Cancel"}
          </Button>
          {step === 1 && (
            <Button variant="text" onClick={() => basicsValid() && setStep(2)}>
              Next
            </Button>
          )}
          {step === 2 && (
            <>
              <Button variant="text" onClick={skipToReview}>
                Skip
              </Button>
              <Button variant="text" onClick={findPages} disabled={!hasHints && !site}>
                Find pages
              </Button>
            </>
          )}
          {step === 3 && !searching && (
            <Button variant="text" onClick={save} disabled={busy}>
              {create.isPending ? "Creating…" : "Create competitor"}
            </Button>
          )}
        </div>
      </div>
    </dialog>
  );
}

function hints(picked: Partial<Record<ChannelKey, string>>, customs: Custom[]): string {
  const names = CHANNELS.filter((c) => picked[c.key] !== undefined && c.key !== "web").map((c) => c.label);
  names.push(...customs.filter((c) => c.value.trim()).map((c) => c.label.trim() || "your links"));
  return names.length ? ` and ${names.join(", ")}` : "";
}

// Simple channel glyphs (not brand logos).
function Glyph({ children }: { children: ReactNode }) {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      {children}
    </svg>
  );
}
function IconInstagram() {
  return (
    <Glyph>
      <rect x="3.5" y="3.5" width="17" height="17" rx="5" />
      <circle cx="12" cy="12" r="4" />
      <circle cx="17.2" cy="6.8" r="0.6" fill="currentColor" />
    </Glyph>
  );
}
function IconTelegram() {
  return (
    <Glyph>
      <path d="M21 4 3 11l6 2.5L19 7l-8 8.2V20l3.2-3.4L18 19z" />
    </Glyph>
  );
}
function IconFacebook() {
  return (
    <Glyph>
      <path d="M14 8h3V4h-3a4 4 0 0 0-4 4v3H7v4h3v6h4v-6h3l1-4h-4V8z" />
    </Glyph>
  );
}
function IconX() {
  return (
    <Glyph>
      <path d="m5 4 14 16M19 4 5 20" />
    </Glyph>
  );
}
function IconWeb() {
  return (
    <Glyph>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M3.5 12h17M12 3.5c2.5 2.6 3.5 5.5 3.5 8.5s-1 5.9-3.5 8.5c-2.5-2.6-3.5-5.5-3.5-8.5s1-5.9 3.5-8.5z" />
    </Glyph>
  );
}
function IconPlus() {
  return (
    <Glyph>
      <path d="M12 5v14M5 12h14" />
    </Glyph>
  );
}
