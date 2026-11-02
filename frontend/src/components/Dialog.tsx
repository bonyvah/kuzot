import { useEffect, useRef, type FormEvent, type ReactNode } from "react";

import { Button } from "./Button";
import "./Dialog.css";

interface DialogProps {
  open: boolean;
  title: string;
  onClose: () => void;
  /** When set, the body is a form and the confirm button submits it. */
  onSubmit?: () => void;
  confirmLabel?: string;
  /** Styles the confirm button for destructive actions. */
  danger?: boolean;
  busy?: boolean;
  error?: string | null;
  children?: ReactNode;
}

/** Modal built on <dialog>: focus trap, Escape and the backdrop come from the browser. */
export function Dialog({
  open,
  title,
  onClose,
  onSubmit,
  confirmLabel = "Save",
  danger,
  busy,
  error,
  children,
}: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!busy) onSubmit?.();
  };

  return (
    <dialog
      ref={ref}
      className="dialog"
      aria-labelledby="dialog-title"
      // Escape fires "cancel"; keep React state the source of truth.
      onCancel={(e) => {
        e.preventDefault();
        if (!busy) onClose();
      }}
    >
      {open && (
        <form className="dialog__form" onSubmit={submit} noValidate>
          <h2 id="dialog-title" className="dialog__title">
            {title}
          </h2>
          <div className="dialog__body">{children}</div>
          {error && (
            <p className="dialog__error" role="alert">
              {error}
            </p>
          )}
          <div className="dialog__actions">
            <Button variant="text" onClick={onClose} disabled={busy}>
              Cancel
            </Button>
            <Button type="submit" variant="text" className={danger ? "btn--danger" : undefined} disabled={busy}>
              {busy ? "Working…" : confirmLabel}
            </Button>
          </div>
        </form>
      )}
    </dialog>
  );
}
