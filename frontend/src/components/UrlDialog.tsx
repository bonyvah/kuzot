import { useState } from "react";

import type { UrlInput, UrlType } from "../api/monitoring";
import { Dialog } from "./Dialog";
import { SelectField } from "./SelectField";
import { TextField } from "./TextField";
import { useSave } from "./useSave";
import { INTERVAL_OPTIONS, URL_TYPE_OPTIONS, urlError } from "./urlForm";

interface UrlDialogProps {
  onSave: (input: UrlInput) => Promise<void>;
  onClose: () => void;
}

export function UrlDialog({ onSave, onClose }: UrlDialogProps) {
  const [url, setUrl] = useState("");
  const [urlType, setUrlType] = useState<UrlType>("pricing");
  const [interval, setInterval] = useState("60");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const save = useSave(onSave);

  const submit = () => {
    const value = url.trim();
    const problem = urlError(value);
    setFieldError(problem);
    if (problem) return;
    save.run({ url: value, url_type: urlType, scrape_interval_minutes: Number(interval) });
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
        error={fieldError}
        autoFocus
      />
      <div className="dialog__row">
        <SelectField
          label="Page type"
          value={urlType}
          onChange={(e) => setUrlType(e.target.value as UrlType)}
          options={URL_TYPE_OPTIONS}
        />
        <SelectField label="Check" value={interval} onChange={(e) => setInterval(e.target.value)} options={INTERVAL_OPTIONS} />
      </div>
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
  onSave: (minutes: number) => Promise<void>;
  onClose: () => void;
}) {
  const known = INTERVAL_OPTIONS.some((o) => o.value === String(current));
  const options = known || !current ? INTERVAL_OPTIONS : [{ value: String(current), label: `Every ${current} min` }, ...INTERVAL_OPTIONS];
  const [interval, setInterval] = useState(String(current ?? 60));
  const save = useSave(onSave);

  return (
    <Dialog
      open
      title="Check frequency"
      onClose={onClose}
      onSubmit={() => save.run(Number(interval))}
      busy={save.busy}
      error={save.error}
    >
      <SelectField label="Check" value={interval} onChange={(e) => setInterval(e.target.value)} options={options} />
    </Dialog>
  );
}
