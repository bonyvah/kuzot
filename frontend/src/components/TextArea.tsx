import { useId, type TextareaHTMLAttributes } from "react";
import "./TextField.css";

interface TextAreaProps extends Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "placeholder"> {
  label: string;
  error?: string | null;
}

/** Multi-line <TextField>. */
export function TextArea({ label, error, id, ...textarea }: TextAreaProps) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const errorId = `${inputId}-error`;

  return (
    <div className={`field field--multiline${error ? " field--error" : ""}`}>
      <div className="field__box">
        <textarea
          {...textarea}
          id={inputId}
          className="field__input"
          placeholder=" "
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? errorId : undefined}
        />
        <label htmlFor={inputId} className="field__label">
          {label}
        </label>
      </div>
      {error && (
        <div id={errorId} className="field__error">
          {error}
        </div>
      )}
    </div>
  );
}
