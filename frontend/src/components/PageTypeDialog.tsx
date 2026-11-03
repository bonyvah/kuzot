import { useState } from "react";

import type { UrlType } from "../api/monitoring";
import { Dialog } from "./Dialog";
import { SelectField } from "./SelectField";
import { TextField } from "./TextField";
import { useSave } from "./useSave";
import { URL_TYPE_OPTIONS } from "./urlForm";

/** Change an existing page's type; "other" pages also need a label. */
export function PageTypeDialog({
  current,
  currentLabel,
  onSave,
  onClose,
}: {
  current: UrlType;
  currentLabel: string | null;
  onSave: (change: { url_type: UrlType; label: string | null }) => Promise<void>;
  onClose: () => void;
}) {
  const [urlType, setUrlType] = useState(current);
  const [label, setLabel] = useState(currentLabel ?? "");
  const [error, setError] = useState<string | null>(null);
  const save = useSave(onSave);

  const submit = () => {
    const problem = urlType === "other" && !label.trim() ? "Say what this page is" : null;
    setError(problem);
    if (!problem) save.run({ url_type: urlType, label: urlType === "other" ? label.trim() : null });
  };

  return (
    <Dialog open title="Page type" onClose={onClose} onSubmit={submit} busy={save.busy} error={save.error}>
      <SelectField
        label="Page type"
        value={urlType}
        onChange={(e) => setUrlType(e.target.value as UrlType)}
        options={URL_TYPE_OPTIONS}
      />
      {urlType === "other" && (
        <TextField
          label="What is this page? e.g. LinkedIn"
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          error={error}
          maxLength={100}
        />
      )}
    </Dialog>
  );
}
