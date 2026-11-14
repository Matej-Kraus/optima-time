import { useState } from "react";
import { api, type FieldConfig, type LiveState } from "../api";
import { cs } from "../i18n/cs";

interface Props {
  fields: FieldConfig[];
  live: LiveState | null;
  selected: string | null;
  onSelect: (id: string) => void;
}

function dotLevel(status: string | undefined): string {
  if (status === "new" || status === "same") return "ok";
  if (status === "blank" || !status) return "";
  return "warn";
}

/** One row per field: what is on air, its state and read confidence. Click to hold it by hand. */
export function FieldRows({ fields, live, selected, onSelect }: Props) {
  return (
    <ul className="field-list">
      {fields.map((f) => {
        const s = live?.fields[f.id];
        const conf = s?.confidence;
        return (
          <li key={f.id}>
            <button
              className={`field-row ${f.id === selected ? "selected" : ""} ${s?.held ? "held" : ""}`}
              onClick={() => onSelect(f.id)}
              aria-pressed={f.id === selected}
              title={s ? `${cs.raw}: ${s.raw ?? "—"} · ${cs.contrast}: ${s.contrast ?? "—"}` : undefined}
            >
              <span className={`dot ${dotLevel(s?.status)}`} aria-hidden />
              <span className="fid">{f.id}</span>
              <span className="fval">{s?.text || "—"}</span>
              <span className={`status-chip ${s?.status ?? ""}`}>
                {s ? cs.fieldStatus[s.status] : ""}
                {s?.pending ? ` ${s.pending}` : ""}
              </span>
              <span className={`pct ${conf != null && conf < 0.8 ? "low" : ""}`}>
                {conf != null ? `${Math.round(conf * 100)} %` : "—"}
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

/** Type a value for the selected field and hold it on air until released. */
export function HoldForm({ id, live }: { id: string | null; live: LiveState | null }) {
  const [text, setText] = useState("");
  if (!id) return <p className="hint section-gap">{cs.live.selectField}</p>;
  const s = live?.fields[id];
  if (s?.held) {
    return (
      <div className="hold-form">
        <span className="dim">
          {cs.fieldStatus.held}: <b>{s.text}</b>
        </span>
        <button className="primary" onClick={() => api.release(id)}>
          {cs.release}
        </button>
      </div>
    );
  }
  return (
    <form
      className="hold-form"
      onSubmit={(e) => {
        e.preventDefault();
        api.hold(id, text || s?.text || "");
        setText("");
      }}
    >
      <input
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={s?.text || cs.holdPlaceholder}
        aria-label={cs.live.holdFor(id)}
      />
      <button type="submit" className="warn">
        {cs.hold} {id}
      </button>
    </form>
  );
}
