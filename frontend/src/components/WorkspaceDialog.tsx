import { useState } from "react";

import type { WorkspaceInput } from "../api/monitoring";
import { Dialog } from "./Dialog";
import { TextField } from "./TextField";
import { useSave } from "./useSave";

interface WorkspaceDialogProps {
  title: string;
  confirmLabel: string;
  initial?: WorkspaceInput;
  onSave: (input: WorkspaceInput) => Promise<void>;
  onClose: () => void;
}

export function WorkspaceDialog({ title, confirmLabel, initial, onSave, onClose }: WorkspaceDialogProps) {
  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const save = useSave(onSave);

  const submit = () => {
    if (!name.trim()) return save.setError("Enter a name");
    save.run({ name: name.trim(), description: description.trim() || null });
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
      <TextField label="Name" value={name} onChange={(e) => setName(e.target.value)} autoFocus maxLength={255} />
      <TextField label="Description (optional)" value={description} onChange={(e) => setDescription(e.target.value)} />
    </Dialog>
  );
}
