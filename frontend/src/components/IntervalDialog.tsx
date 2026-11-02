import { useState } from "react";

import { Dialog } from "./Dialog";
import { IntervalField } from "./IntervalField";
import { useSave } from "./useSave";
import { intervalError } from "./urlForm";

/** Change how often an existing page is checked. */
export function IntervalDialog({
  current,
  onSave,
  onClose,
}: {
  current: number | null;
  onSave: (minutes: number | null) => Promise<void>;
  onClose: () => void;
}) {
  const [interval, setInterval] = useState(current);
  const [error, setError] = useState<string | null>(null);
  const save = useSave(onSave);

  const submit = () => {
    const problem = intervalError(interval);
    setError(problem);
    if (!problem) save.run(interval);
  };

  return (
    <Dialog open title="Check frequency" onClose={onClose} onSubmit={submit} busy={save.busy} error={save.error}>
      <IntervalField value={interval} onChange={setInterval} error={error} />
    </Dialog>
  );
}
