import { useState } from "react";
import { api, type FieldConfig, type LiveState } from "../api";
import { cs } from "../i18n/cs";

interface Props {
  fields: FieldConfig[];
  live: LiveState | null;
  selected: string | null;
  onSelect: (id: string) => void;
  tick: number;
  showCrops: boolean;
}

/** Published values in big type, their status, the raw reading, and the manual hold. */
export function FieldsTable({ fields, live, selected, onSelect, tick, showCrops }: Props) {
  return (
    <table className="fields-table">
      <tbody>
        {fields.map((f) => {
          const s = live?.fields[f.id];
          return (
            <tr key={f.id} className={`${f.id === selected ? "selected" : ""} ${s?.held ? "held" : ""}`} onClick={() => onSelect(f.id)}>
              <td className="fid">
                {f.id}
                {f.label && <div className="label">{f.label}</div>}
              </td>
              <td className="value">{s?.text || "—"}</td>
              <td className={`status ${s?.status ?? ""}`}>
                {s ? cs.fieldStatus[s.status] : ""}
                {s?.pending && (
                  <div className="meta">
                    {cs.pendingValue}: {s.pending}
                  </div>
                )}
              </td>
              <td className="meta">
                {cs.raw}: {s?.raw ?? "—"} · {cs.confidence}: {s?.confidence ?? "—"} · {cs.contrast}: {s?.contrast ?? "—"}
              </td>
              <td>{showCrops && <img className="crop" src={api.cropUrl(f.id, tick)} alt="" />}</td>
              <td onClick={(e) => e.stopPropagation()}>
                <HoldControl id={f.id} held={s?.held ?? false} current={s?.text ?? ""} />
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function HoldControl({ id, held, current }: { id: string; held: boolean; current: string }) {
  const [text, setText] = useState("");
  if (held) {
    return (
      <button className="active" onClick={() => api.release(id)}>
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
      <input value={text} onChange={(e) => setText(e.target.value)} placeholder={cs.holdPlaceholder} size={11} />
      <button type="submit">{cs.hold}</button>
    </form>
  );
}
