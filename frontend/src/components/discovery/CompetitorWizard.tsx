import { useEffect, useRef, useState } from "react";

import { ApiError, errorText } from "../../api/client";
import { discoveryApi, type Competitor } from "../../api/monitoring";
import { useCreateCompetitor } from "../../api/queries";
import { Button } from "../Button";
import { TextArea } from "../TextArea";
import { TextField } from "../TextField";
import { urlError } from "../urlForm";
import { CHANNELS, ChannelPicker, channelHints, type Custom, type Picked } from "./channels";
import { newRow, PageReviewList, rowsError, rowsToInputs, type ReviewRow } from "./PageReviewList";
import "../Dialog.css";
import "./Discovery.css";

type Step = 1 | 2 | 3;

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
  const [picked, setPicked] = useState<Picked>({});
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
    const hints = channelHints(picked, customs);
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
              <ChannelPicker picked={picked} onPick={setPicked} customs={customs} onCustoms={setCustoms} />
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

function hints(picked: Picked, customs: Custom[]): string {
  const names = CHANNELS.filter((c) => picked[c.key] !== undefined && c.key !== "web").map((c) => c.label);
  names.push(...customs.filter((c) => c.value.trim()).map((c) => c.label.trim() || "your links"));
  return names.length ? ` and ${names.join(", ")}` : "";
}
