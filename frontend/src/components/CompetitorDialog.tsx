import { useState } from "react";

import type { CompetitorInput, UrlInput, UrlType } from "../api/monitoring";
import { Dialog } from "./Dialog";
import { SelectField } from "./SelectField";
import { TextField } from "./TextField";
import { useSave } from "./useSave";
import { INTERVAL_OPTIONS, URL_TYPE_OPTIONS, urlError } from "./urlForm";

interface CompetitorDialogProps {
  title: string;
  confirmLabel: string;
  initial?: CompetitorInput;
  /** New competitors can start with one monitored URL. */
  withFirstUrl?: boolean;
  onSave: (input: CompetitorInput, firstUrl: UrlInput | null) => Promise<void>;
  onClose: () => void;
}

export function CompetitorDialog({ title, confirmLabel, initial, withFirstUrl, onSave, onClose }: CompetitorDialogProps) {
  const [name, setName] = useState(initial?.name ?? "");
  const [website, setWebsite] = useState(initial?.website_url ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [urlType, setUrlType] = useState<UrlType>("pricing");
  const [interval, setInterval] = useState("60");
  const [fieldErrors, setFieldErrors] = useState<{ name?: string; website?: string }>({});
  const save = useSave(onSave);

  const submit = () => {
    const site = website.trim();
    const errors = {
      name: name.trim() ? undefined : "Enter a name",
      website: site ? (urlError(site) ?? undefined) : undefined,
    };
    setFieldErrors(errors);
    if (errors.name || errors.website) return;

    const firstUrl: UrlInput | null =
      withFirstUrl && site ? { url: site, url_type: urlType, scrape_interval_minutes: Number(interval) || null } : null;
    save.run({ name: name.trim(), website_url: site || null, description: description.trim() || null }, firstUrl);
  };

  return (
    <Dialog
      open
      title={title}
      confirmLabel={confirmLabel}
      onClose={onClose}
      onSubmit={submit}
      busy={save.busy}
      error={save.error}
    >
      <TextField
        label="Name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        error={fieldErrors.name}
        autoFocus
        maxLength={255}
      />
      <TextField
        label="Website (optional)"
        type="url"
        inputMode="url"
        value={website}
        onChange={(e) => setWebsite(e.target.value)}
        error={fieldErrors.website}
      />
      <TextField label="Description (optional)" value={description} onChange={(e) => setDescription(e.target.value)} />
      {withFirstUrl && (
        <>
          <p className="dialog__hint">The website is also added as the first monitored page.</p>
          <div className="dialog__row">
            <SelectField
              label="Page type"
              value={urlType}
              onChange={(e) => setUrlType(e.target.value as UrlType)}
              options={URL_TYPE_OPTIONS}
            />
            <SelectField
              label="Check"
              value={interval}
              onChange={(e) => setInterval(e.target.value)}
              options={INTERVAL_OPTIONS}
            />
          </div>
        </>
      )}
    </Dialog>
  );
}
