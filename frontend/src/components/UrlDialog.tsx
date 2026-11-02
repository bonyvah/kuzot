import { useState } from "react";

import type { UrlInput } from "../api/monitoring";
import { Dialog } from "./Dialog";
import { IntervalField } from "./IntervalField";
import { defaultPageSettings, PageFields, pageSettingsErrors } from "./PageFields";
import { TextField } from "./TextField";
import { useSave } from "./useSave";
import { intervalError, urlError } from "./urlForm";

interface UrlDialogProps {
  onSave: (input: UrlInput) => Promise<void>;
  onClose: () => void;
}

export function UrlDialog({ onSave, onClose }: UrlDialogProps) {
  const [url, setUrl] = useState("");
  const [page, setPage] = useState(() => defaultPageSettings("pricing"));
  const [errors, setErrors] = useState<{ url?: string | null; label?: string | null; interval?: string | null }>({});
  const save = useSave(onSave);

  const submit = () => {
    const value = url.trim();
    const next = { url: urlError(value), ...pageSettingsErrors(page) };
    setErrors(next);
    if (next.url || next.label || next.interval) return;
    save.run({
      url: value,
      url_type: page.urlType,
      label: page.urlType === "other" ? page.label.trim() : null,
      scrape_interval_minutes: page.interval,
    });
  };

  return (
    <Dialog
      open
      title="Monitor a page"
      confirmLabel="Add"
      onClose={onClose}
      onSubmit={submit}
      busy={save.busy}
      error={save.error}
    >
      <TextField
        label="Page address"
        type="url"
        inputMode="url"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        error={errors.url}
        autoFocus
      />
      <PageFields value={page} onChange={setPage} errors={errors} />
    </Dialog>
  );
}

/** Change how often an existing page is checked. */
export function IntervalDialog({
  current,
  onSave,
  onClose,
}: {
  current: number | null;
  onSave: (minutes: number | null) => Promise<void>;
  onClose: () => void;
}) {
  const [interval, setInterval] = useState(current);
  const [error, setError] = useState<string | null>(null);
  const save = useSave(onSave);

  const submit = () => {
    const problem = intervalError(interval);
    setError(problem);
    if (!problem) save.run(interval);
  };

  return (
    <Dialog open title="Check frequency" onClose={onClose} onSubmit={submit} busy={save.busy} error={save.error}>
      <IntervalField value={interval} onChange={setInterval} error={error} />
    </Dialog>
  );
}
