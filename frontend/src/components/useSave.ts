import { useState } from "react";

import { errorText } from "../api/client";

/** Busy and error state for a dialog's save action. */
export function useSave<A extends unknown[]>(save: (...args: A) => Promise<unknown>) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async (...args: A) => {
    setBusy(true);
    setError(null);
    try {
      await save(...args);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  };

  return { run, busy, error, setError };
}
