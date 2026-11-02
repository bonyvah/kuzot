import type { ReactNode } from "react";

import { Dialog } from "./Dialog";
import { useSave } from "./useSave";

interface ConfirmDialogProps {
  title: string;
  confirmLabel: string;
  children: ReactNode;
  onConfirm: () => Promise<void>;
  onClose: () => void;
  /** Red confirm button; off for non-destructive actions. */
  danger?: boolean;
}

/** Asks before an action runs; destructive by default. */
export function ConfirmDialog({ title, confirmLabel, children, onConfirm, onClose, danger = true }: ConfirmDialogProps) {
  const save = useSave(onConfirm);
  return (
    <Dialog
      open
      danger={danger}
      title={title}
      confirmLabel={confirmLabel}
      onClose={onClose}
      onSubmit={() => save.run()}
      busy={save.busy}
      error={save.error}
    >
      <p>{children}</p>
    </Dialog>
  );
}
