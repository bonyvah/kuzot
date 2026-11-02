import type { UrlType } from "../api/monitoring";
import { IntervalField } from "./IntervalField";
import { SelectField } from "./SelectField";
import { TextField } from "./TextField";
import { DEFAULT_INTERVAL, intervalError, URL_TYPE_OPTIONS } from "./urlForm";

export interface PageSettings {
  urlType: UrlType;
  label: string;
  interval: number | null;
}

interface PageFieldsProps {
  value: PageSettings;
  onChange: (next: PageSettings) => void;
  errors?: { label?: string | null; interval?: string | null };
}

/** Page type (with a label for "other") and scrape interval. */
export function PageFields({ value, onChange, errors }: PageFieldsProps) {
  return (
    <>
      <div className="dialog__row">
        <SelectField
          label="Page type"
          value={value.urlType}
          onChange={(e) => onChange({ ...value, urlType: e.target.value as UrlType })}
          options={URL_TYPE_OPTIONS}
        />
        <IntervalField
          value={value.interval}
          onChange={(interval) => onChange({ ...value, interval })}
          error={errors?.interval}
        />
      </div>
      {value.urlType === "other" && (
        <TextField
          label="What is this page? e.g. LinkedIn"
          value={value.label}
          onChange={(e) => onChange({ ...value, label: e.target.value })}
          error={errors?.label}
          maxLength={100}
        />
      )}
    </>
  );
}

export const defaultPageSettings = (urlType: UrlType): PageSettings => ({
  urlType,
  label: "",
  interval: DEFAULT_INTERVAL,
});

export function pageSettingsErrors(value: PageSettings) {
  return {
    label: value.urlType === "other" && !value.label.trim() ? "Say what this page is" : null,
    interval: intervalError(value.interval),
  };
}
