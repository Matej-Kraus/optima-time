import { useState } from "react";
import type { FieldConfig, FieldType } from "../api";
import { cs } from "../i18n/cs";
import { formatNames, parseNames } from "../periodNames";

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
          <Select
            label={cs.direction}
            value={String(field.direction ?? "auto")}
            options={cs.directions}
            onChange={(v) => onChange({ direction: v })}
          />
        </>
      )}
      {field.type === "period" && (
        <label>
          {cs.periodNames}
          <input
            defaultValue={formatNames(field.names)}
            onBlur={(e) => {
              const names = parseNames(e.target.value);
              if (names) onChange({ names });
            }}
          />
        </label>
      )}
      {field.type === "indicator" && (
        <>
          <p className="hint">{cs.indicator.hint}</p>
          <label>
            {cs.indicator.onText}
            <input defaultValue={String(field.on_text ?? "1")} onBlur={(e) => onChange({ on_text: e.target.value })} />
          </label>
          <label>
            {cs.indicator.offText}
            <input defaultValue={String(field.off_text ?? "0")} onBlur={(e) => onChange({ off_text: e.target.value })} />
          </label>
          <NumberInput label={cs.indicator.litLevel} value={field.lit_level ?? 110} step={5} onChange={(v) => onChange({ lit_level: v })} />
          <NumberInput label={cs.indicator.reads} value={field.reads ?? 3} step={1} onChange={(v) => onChange({ reads: v })} />
        </>
      )}
      {field.type === "number" && (
        <Select label={cs.style} value={String(field.style)} options={cs.numberStyles} onChange={(v) => onChange({ style: v })} />
      )}
      {field.type !== "indicator" && (
        <Select
          label={cs.blank}
          value={String(field.blank ?? "hold")}
          options={cs.blankPolicies}
          onChange={(v) => onChange({ blank: v })}
        />
      )}
      <label className="check">
        <input type="checkbox" checked={field.enabled} onChange={(e) => onChange({ enabled: e.target.checked })} />
        {cs.enabled}
      </label>
      <details>
        <summary>{cs.advanced}</summary>
        <NumberInput label={cs.minConfidence} value={field.min_confidence} step={0.05} onChange={(v) => onChange({ min_confidence: v })} />
        <NumberInput label={cs.minContrast} value={field.min_contrast} step={5} onChange={(v) => onChange({ min_contrast: v })} />
        <NumberInput label={cs.margin} value={field.margin} step={0.05} onChange={(v) => onChange({ margin: v })} />
        <NumberInput label={cs.blankDelay} value={field.blank_delay_ms} step={50} onChange={(v) => onChange({ blank_delay_ms: v })} />
        {field.type === "number" && (
          <NumberInput label={cs.maxDigits} value={field.max_digits} step={1} onChange={(v) => onChange({ max_digits: v })} />
        )}
        <Select label={cs.align} value={String(field.align ?? "none")} options={cs.aligns} onChange={(v) => onChange({ align: v })} />
        <NumberInput label={cs.alignWidth} value={field.align_width} step={1} onChange={(v) => onChange({ align_width: v })} />
        {field.type === "period" && (
          <NumberInput label={cs.maxPeriod} value={field.max_value} step={1} onChange={(v) => onChange({ max_value: v })} />
        )}
      </details>
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

function NumberInput(props: { label: string; value: unknown; step: number; onChange: (v: number) => void }) {
  return (
    <label>
      {props.label}
      <input
        type="number"
        step={props.step}
        defaultValue={typeof props.value === "number" ? props.value : undefined}
        onBlur={(e) => {
          const v = Number(e.target.value);
          if (e.target.value !== "" && Number.isFinite(v) && v !== props.value) props.onChange(v);
        }}
      />
    </label>
  );
}
