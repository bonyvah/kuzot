import { useId, type InputHTMLAttributes, type Ref } from "react";
import "./TextField.css";

interface TextFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "placeholder"> {
  label: string;
  error?: string | null;
  ref?: Ref<HTMLInputElement>;
}

/** Material outlined text field with a floating label. */
export function TextField({ label, error, id, ref, ...input }: TextFieldProps) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const errorId = `${inputId}-error`;

  return (
    <div className={`field${error ? " field--error" : ""}`}>
      <div className="field__box">
        {/* A blank placeholder lets CSS detect "has value" via :placeholder-shown. */}
        <input
          {...input}
          ref={ref}
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
          <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
            <path
              fill="currentColor"
              d="M12 7c.55 0 1 .45 1 1v4c0 .55-.45 1-1 1s-1-.45-1-1V8c0-.55.45-1 1-1zm-.01-5C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm1-3h-2v-2h2v2z"
            />
          </svg>
          {error}
        </div>
      )}
    </div>
  );
}
