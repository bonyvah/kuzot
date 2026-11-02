import { useState } from "react";

import type { CompetitorInput } from "../api/monitoring";
import { Dialog } from "./Dialog";
import { TextField } from "./TextField";
import { useSave } from "./useSave";
import { urlError } from "./urlForm";

interface CompetitorDialogProps {
  initial: CompetitorInput;
  onSave: (input: CompetitorInput) => Promise<void>;
  onClose: () => void;
}

/** Edit a competitor's name, website and description. Adding one uses the wizard. */
export function CompetitorDialog({ initial, onSave, onClose }: CompetitorDialogProps) {
  const [name, setName] = useState(initial.name);
  const [website, setWebsite] = useState(initial.website_url ?? "");
  const [description, setDescription] = useState(initial.description ?? "");
  const [fieldErrors, setFieldErrors] = useState<{ name?: string | null; website?: string | null }>({});
  const save = useSave(onSave);

  const submit = () => {
    const site = website.trim();
    const errors = { name: name.trim() ? null : "Enter a name", website: site ? urlError(site) : null };
    setFieldErrors(errors);
    if (errors.name || errors.website) return;
    save.run({ name: name.trim(), website_url: site || null, description: description.trim() || null });
  };

  return (
    <Dialog open title="Edit competitor" onClose={onClose} onSubmit={submit} busy={save.busy} error={save.error}>
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
    </Dialog>
  );
}
