import { useState } from "react";

import type { CompetitorInput, UrlInput } from "../api/monitoring";
import { Dialog } from "./Dialog";
import { defaultPageSettings, PageFields, pageSettingsErrors } from "./PageFields";
import { TextField } from "./TextField";
import { useSave } from "./useSave";
import { urlError } from "./urlForm";

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
  const [page, setPage] = useState(() => defaultPageSettings("homepage"));
  const [fieldErrors, setFieldErrors] = useState<{
    name?: string | null;
    website?: string | null;
    label?: string | null;
    interval?: string | null;
  }>({});
  const save = useSave(onSave);

  const submit = () => {
    const site = website.trim();
    const errors = {
      name: name.trim() ? null : "Enter a name",
      website: site ? urlError(site) : null,
      ...(withFirstUrl && site ? pageSettingsErrors(page) : {}),
    };
    setFieldErrors(errors);
    if (Object.values(errors).some(Boolean)) return;

    const firstUrl: UrlInput | null =
      withFirstUrl && site
        ? {
            url: site,
            url_type: page.urlType,
            label: page.urlType === "other" ? page.label.trim() : null,
            scrape_interval_minutes: page.interval,
          }
        : null;
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
          <PageFields value={page} onChange={setPage} errors={fieldErrors} />
        </>
      )}
    </Dialog>
  );
}
