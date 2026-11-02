import type { ReactNode } from "react";

import { Dialog } from "./Dialog";
import { useSave } from "./useSave";

interface ConfirmDialogProps {
  title: string;
  confirmLabel: string;
  children: ReactNode;
  onConfirm: () => Promise<void>;
  onClose: () => void;
}

/** Confirmation for a destructive action. */
export function ConfirmDialog({ title, confirmLabel, children, onConfirm, onClose }: ConfirmDialogProps) {
  const save = useSave(onConfirm);
  return (
    <Dialog
      open
      danger
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
