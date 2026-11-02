import type { ReactNode } from "react";
import "./Chip.css";

export type ChipTone = "neutral" | "info" | "success" | "error" | "warning";

/** Small status label. `pulse` marks work in progress. */
export function Chip({ tone = "neutral", pulse, children }: { tone?: ChipTone; pulse?: boolean; children: ReactNode }) {
  return (
    <span className={`chip chip--${tone}`}>
      {pulse && <span className="chip__pulse" aria-hidden="true" />}
      {children}
    </span>
  );
}
