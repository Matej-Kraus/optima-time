import { useState } from "react";
import { api, type FieldConfig, type LiveState } from "../api";
import { cs } from "../i18n/cs";

interface Props {
  fields: FieldConfig[];
  live: LiveState | null;
  details: boolean;
  tick: number;
}

/** One row per field: what is on air, its state, and the manual hold. */
export function FieldRows({ fields, live, details, tick }: Props) {
  return (
    <div className="rows" role="table">
      {fields.map((f) => {
        const s = live?.fields[f.id];
        return (
          <div key={f.id} className={`row-field ${s?.held ? "held" : ""}`} role="row">
            <div className="name" role="cell">
              <span className="label">{f.label || f.id}</span>
              <code>{f.id}</code>
            </div>
            <div className="value" role="cell">{s?.text || "—"}</div>
            <div className={`chip ${s?.status ?? ""}`} role="cell">
              {s ? cs.fieldStatus[s.status] : ""}
              {s?.pending ? ` ${s.pending}` : ""}
            </div>
            <div className="hold-cell" role="cell">
              <HoldControl id={f.id} held={s?.held ?? false} current={s?.text ?? ""} />
            </div>
            {details && (
              <div className="details" role="cell">
                <img className="crop" src={api.cropUrl(f.id, tick)} alt="" />
                <span>
                  {cs.raw}: {s?.raw ?? "—"} · {cs.confidence}: {s?.confidence ?? "—"} · {cs.contrast}: {s?.contrast ?? "—"}
                </span>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function HoldControl({ id, held, current }: { id: string; held: boolean; current: string }) {
  const [text, setText] = useState("");
  if (held) {
    return (
      <button className="release" onClick={() => api.release(id)}>
        {cs.release}
      </button>
    );
  }
  return (
    <form
      className="hold"
      onSubmit={(e) => {
        e.preventDefault();
        api.hold(id, text || current);
        setText("");
      }}
    >
      <input value={text} onChange={(e) => setText(e.target.value)} placeholder={cs.holdPlaceholder} size={9} aria-label={`${cs.holdPlaceholder} ${id}`} />
      <button type="submit">{cs.hold}</button>
    </form>
  );
}
