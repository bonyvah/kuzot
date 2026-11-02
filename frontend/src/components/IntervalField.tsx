import { useId, useState } from "react";

import { SelectField } from "./SelectField";
import { INTERVAL_PRESETS, INTERVAL_UNITS } from "./urlForm";
import "./IntervalField.css";

interface IntervalFieldProps {
  /** Minutes between scrapes; null for manual only. */
  value: number | null;
  onChange: (minutes: number | null) => void;
  error?: string | null;
}

const MANUAL = "manual";
const CUSTOM = "custom";

/** Pick a preset, "manual only", or any custom number of minutes, hours or days. */
export function IntervalField({ value, onChange, error }: IntervalFieldProps) {
  const id = useId();
  const preset = value === null ? MANUAL : INTERVAL_PRESETS.find((p) => p.minutes === value) ? String(value) : CUSTOM;
  const [custom, setCustom] = useState(preset === CUSTOM);
  const [unit, setUnit] = useState(() => bestUnit(value));
  const [amount, setAmount] = useState(() => (value ? String(value / Number(bestUnit(value))) : "3"));

  const choose = (next: string) => {
    if (next === CUSTOM) {
      setCustom(true);
      onChange(Number(amount) * Number(unit));
    } else {
      setCustom(false);
      onChange(next === MANUAL ? null : Number(next));
    }
  };

  return (
    <div className={`interval${error ? " interval--error" : ""}`}>
      <SelectField
        label="Check"
        value={custom ? CUSTOM : preset}
        onChange={(e) => choose(e.target.value)}
        options={[
          ...INTERVAL_PRESETS.map((p) => ({ value: String(p.minutes), label: p.label })),
          { value: CUSTOM, label: "Custom…" },
          { value: MANUAL, label: "Manual only" },
        ]}
      />
      {custom && (
        <div className="interval__custom" role="group" aria-labelledby={`${id}-every`}>
          <span id={`${id}-every`} className="interval__every">
            Every
          </span>
          <input
            className="interval__amount"
            type="number"
            min={1}
            inputMode="numeric"
            aria-label="Amount"
            value={amount}
            onChange={(e) => {
              setAmount(e.target.value);
              onChange(Number(e.target.value) * Number(unit));
            }}
          />
          <select
            className="interval__unit"
            aria-label="Unit"
            value={unit}
            onChange={(e) => {
              setUnit(e.target.value);
              onChange(Number(amount) * Number(e.target.value));
            }}
          >
            {INTERVAL_UNITS.map((u) => (
              <option key={u.value} value={u.value}>
                {u.label}
              </option>
            ))}
          </select>
        </div>
      )}
      {error && <div className="field__error">{error}</div>}
    </div>
  );
}

/** The largest unit that divides the interval evenly. */
function bestUnit(minutes: number | null): string {
  if (!minutes) return "1440";
  return [...INTERVAL_UNITS].reverse().find((u) => minutes % Number(u.value) === 0)?.value ?? "1";
}
