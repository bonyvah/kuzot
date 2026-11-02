import { useId, type SelectHTMLAttributes } from "react";
import "./TextField.css";

interface SelectFieldProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string;
  options: readonly { value: string; label: string }[];
}

/** Outlined select styled like <TextField>; the label always sits floated. */
export function SelectField({ label, options, id, ...select }: SelectFieldProps) {
  const autoId = useId();
  const selectId = id ?? autoId;

  return (
    <div className="field field--select">
      <div className="field__box">
        <select {...select} id={selectId} className="field__input">
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <label htmlFor={selectId} className="field__label">
          {label}
        </label>
      </div>
    </div>
  );
}
