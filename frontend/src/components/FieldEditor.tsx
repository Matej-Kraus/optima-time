import { useState } from "react";
import type { FieldConfig, FieldType } from "../api";
import { cs } from "../i18n/cs";

interface Props {
  field: FieldConfig;
  idError: (id: string) => string | null;
  onChange: (patch: Partial<FieldConfig>) => void;
  onType: (t: FieldType) => void;
  onDelete: () => void;
}

export function FieldEditor({ field, idError, onChange, onType, onDelete }: Props) {
  const [id, setId] = useState(field.id);
  const error = id !== field.id ? idError(id) : null;
  return (
    <div className="editor">
      <label>
        {cs.id}
        <input
          value={id}
          onChange={(e) => setId(e.target.value)}
          onBlur={() => !error && id !== field.id && onChange({ id })}
          className={error ? "invalid" : undefined}
        />
        <small>{error ?? cs.idHelp}</small>
      </label>
      <label>
        {cs.label}
        <input defaultValue={field.label} onBlur={(e) => onChange({ label: e.target.value })} />
      </label>
      <label>
        {cs.type}
        <select value={field.type} onChange={(e) => onType(e.target.value as FieldType)}>
          {(Object.keys(cs.types) as FieldType[]).map((t) => (
            <option key={t} value={t}>
              {cs.types[t]}
            </option>
          ))}
        </select>
      </label>
      {field.type === "clock" && (
        <>
          <label className="check">
            <input type="checkbox" checked={Boolean(field.tenths)} onChange={(e) => onChange({ tenths: e.target.checked })} />
            {cs.tenths}
          </label>
          <Select label={cs.style} value={String(field.style)} options={cs.clockStyles} onChange={(v) => onChange({ style: v })} />
        </>
      )}
      {field.type === "number" && (
        <Select label={cs.style} value={String(field.style)} options={cs.numberStyles} onChange={(v) => onChange({ style: v })} />
      )}
      <Select
        label={cs.blank}
        value={String(field.blank ?? "hold")}
        options={cs.blankPolicies}
        onChange={(v) => onChange({ blank: v })}
      />
      <label className="check">
        <input type="checkbox" checked={field.enabled} onChange={(e) => onChange({ enabled: e.target.checked })} />
        {cs.enabled}
      </label>
      <button className="danger" onClick={onDelete}>
        {cs.deleteField}
      </button>
    </div>
  );
}

function Select(props: { label: string; value: string; options: Record<string, string>; onChange: (v: string) => void }) {
  return (
    <label>
      {props.label}
      <select value={props.value} onChange={(e) => props.onChange(e.target.value)}>
        {Object.entries(props.options).map(([k, v]) => (
          <option key={k} value={k}>
            {v}
          </option>
        ))}
      </select>
    </label>
  );
}
