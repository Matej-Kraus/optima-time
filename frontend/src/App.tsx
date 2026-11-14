import { useCallback, useEffect, useRef, useState } from "react";
import {
  api,
  ApiError,
  FIELD_ID_PATTERN,
  nextFieldId,
  rectFromPoints,
  type FieldConfig,
  type FieldType,
  type LiveState,
  type Point,
  type Profile,
} from "./api";
import { Overlay } from "./components/Overlay";
import { usePoll, useTick } from "./hooks";
import { cs } from "./i18n/cs";

type SaveState = "idle" | "saving" | "saved" | "error";

const DEFAULTS: Record<FieldType, Partial<FieldConfig>> = {
  clock: { tenths: false, style: "as_is" },
  number: { style: "strip_zeros" },
  period: {},
};

export default function App() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [drawing, setDrawing] = useState(false);
  const [draft, setDraft] = useState<[Point, Point] | null>(null);
  const [dragCorner, setDragCorner] = useState<number | null>(null);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [saveError, setSaveError] = useState<string | null>(null);
  const tick = useTick(400);
  const getState = useCallback(() => api.getState(), []);
  const live = usePoll<LiveState>(getState, 300);
  const saveTimer = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    api.getProfile().then(setProfile);
  }, []);

  const save = useCallback((next: Profile) => {
    setProfile(next);
    clearTimeout(saveTimer.current);
    setSaveState("saving");
    saveTimer.current = setTimeout(async () => {
      try {
        setProfile(await api.putProfile(next));
        setSaveState("saved");
        setSaveError(null);
      } catch (e) {
        setSaveState("error");
        setSaveError(e instanceof ApiError ? JSON.stringify(e.detail) : String(e));
      }
    }, 250);
  }, []);

  if (!profile) return <main className="app">…</main>;

  const hasFrame = live?.frame != null;
  const corners = profile.geometry.corners;
  const field = profile.fields.find((f) => f.id === selected) ?? null;

  const setCorner = (i: number, p: Point, persist: boolean) => {
    const next = structuredClone(profile);
    next.geometry.corners[i] = p;
    if (persist) save(next);
    else setProfile(next);
  };

  const updateField = (id: string, patch: Partial<FieldConfig>) => {
    const next = structuredClone(profile);
    next.fields = next.fields.map((f) => (f.id === id ? { ...f, ...patch } : f));
    if (patch.id !== undefined) setSelected(patch.id);
    save(next);
  };

  const changeType = (f: FieldConfig, type: FieldType) => {
    // drop the old type's options; the backend fills in the new type's defaults
    const { id, label, roi, enabled } = f;
    const next = structuredClone(profile);
    next.fields = next.fields.map((x) =>
      x.id === f.id ? ({ id, label, roi, enabled, type, ...DEFAULTS[type] } as FieldConfig) : x,
    );
    save(next);
  };

  const finishDraft = () => {
    if (!draft) return;
    const roi = rectFromPoints(draft[0], draft[1]);
    setDraft(null);
    setDrawing(false);
    if (roi.w < 0.01 || roi.h < 0.01) return;
    const id = nextFieldId(profile.fields);
    const next = structuredClone(profile);
    next.fields.push({ id, label: "", type: "number", roi, enabled: true, ...DEFAULTS.number } as FieldConfig);
    setSelected(id);
    save(next);
  };

  const idError = (value: string): string | null => {
    if (!FIELD_ID_PATTERN.test(value)) return cs.invalidId;
    if (profile.fields.some((f) => f.id === value && f.id !== selected)) return cs.duplicateId;
    return null;
  };

  return (
    <main className="app">
      <header>
        <h1>{cs.appName}</h1>
        <StatusBar live={live} />
        <span className={`save ${saveState}`}>
          {saveState === "saving" ? cs.saving : saveState === "saved" ? cs.saved : saveState === "error" ? cs.saveError : ""}
        </span>
      </header>
      {saveError && <div className="error-bar">{saveError}</div>}

      <div className="panels">
        <section>
          <h2>{cs.sourcePanel}</h2>
          <p className="hint">{cs.sourceHint}</p>
          <Overlay
            src={hasFrame ? api.frameUrl("source", tick) : null}
            emptyText={cs.noFrame}
            onPointerMove={(p) => dragCorner !== null && setCorner(dragCorner, p, false)}
            onPointerUp={(p) => {
              if (dragCorner !== null) setCorner(dragCorner, p, true);
              setDragCorner(null);
            }}
          >
            <polygon className="board-outline" points={corners.map((c) => c.join(",")).join(" ")} />
            {corners.map((c, i) => (
              <circle
                key={i}
                className="handle"
                cx={c[0]}
                cy={c[1]}
                r={0.012}
                onPointerDown={() => setDragCorner(i)}
              />
            ))}
          </Overlay>
        </section>

        <section>
          <h2>{cs.boardPanel}</h2>
          <p className="hint">{cs.boardHint}</p>
          <div className="toolbar">
            <button onClick={() => setDrawing((d) => !d)} className={drawing ? "active" : undefined}>
              {drawing ? cs.cancelAdd : cs.addField}
            </button>
          </div>
          <Overlay
            src={hasFrame ? api.frameUrl("rectified", tick) : null}
            emptyText={cs.noFrame}
            crosshair={drawing}
            onPointerDown={(p) => drawing && setDraft([p, p])}
            onPointerMove={(p) => draft && setDraft([draft[0], p])}
            onPointerUp={finishDraft}
          >
            {profile.fields.map((f) => (
              <rect
                key={f.id}
                className={`field-rect ${f.id === selected ? "selected" : ""} ${live?.fields[f.id]?.status ?? ""}`}
                x={f.roi.x}
                y={f.roi.y}
                width={f.roi.w}
                height={f.roi.h}
                onPointerDown={(e) => {
                  if (!drawing) {
                    e.stopPropagation();
                    setSelected(f.id);
                  }
                }}
              />
            ))}
            {draft && <rect className="field-rect draft" {...toSvgRect(draft)} />}
          </Overlay>
        </section>
      </div>

      <section>
        <h2>{cs.fieldsPanel}</h2>
        <div className="fields">
          <table>
            <tbody>
              {profile.fields.map((f) => {
                const s = live?.fields[f.id];
                return (
                  <tr key={f.id} className={f.id === selected ? "selected" : ""} onClick={() => setSelected(f.id)}>
                    <td className="fid">{f.id}</td>
                    <td className="value">{s?.text ?? "—"}</td>
                    <td className={`status ${s?.status ?? ""}`}>{s ? cs.status[s.status] : ""}</td>
                    <td className="meta">
                      {cs.raw}: {s?.raw ?? "—"} · {cs.confidence}: {s?.confidence ?? "—"} · {cs.contrast}:{" "}
                      {s?.contrast ?? "—"}
                    </td>
                    <td>{hasFrame && <img className="crop" src={api.cropUrl(f.id, tick)} alt="" />}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {field && (
            <FieldEditor
              key={field.id}
              field={field}
              idError={idError}
              onChange={(patch) => updateField(field.id, patch)}
              onType={(t) => changeType(field, t)}
              onDelete={() => {
                const next = structuredClone(profile);
                next.fields = next.fields.filter((x) => x.id !== field.id);
                setSelected(null);
                save(next);
              }}
            />
          )}
        </div>
      </section>
    </main>
  );
}

function toSvgRect([a, b]: [Point, Point]) {
  const r = rectFromPoints(a, b);
  return { x: r.x, y: r.y, width: r.w, height: r.h };
}

function StatusBar({ live }: { live: LiveState | null }) {
  if (!live) return <span className="statusbar">…</span>;
  const s = live.source;
  const ok = s.state === "ok";
  return (
    <span className="statusbar">
      <span className={`dot ${ok ? "ok" : "bad"}`} /> {cs.source}: {s.state}
      {s.width ? ` ${s.width}×${s.height} @ ${s.fps?.toFixed(1)}` : ""}
      {s.dropped ? ` · ${cs.dropped} ${s.dropped}` : ""} · {cs.processing}: {live.processing_fps} {cs.fps}
      {live.frame ? ` · ${live.frame.timings_ms.total.toFixed(1)} ms` : ""}
      {s.error ? ` · ${s.error}` : ""}
    </span>
  );
}

interface EditorProps {
  field: FieldConfig;
  idError: (id: string) => string | null;
  onChange: (patch: Partial<FieldConfig>) => void;
  onType: (t: FieldType) => void;
  onDelete: () => void;
}

function FieldEditor({ field, idError, onChange, onType, onDelete }: EditorProps) {
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
          <label>
            {cs.style}
            <select value={String(field.style)} onChange={(e) => onChange({ style: e.target.value })}>
              {Object.entries(cs.clockStyles).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </label>
        </>
      )}
      {field.type === "number" && (
        <label>
          {cs.style}
          <select value={String(field.style)} onChange={(e) => onChange({ style: e.target.value })}>
            {Object.entries(cs.numberStyles).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </label>
      )}
      <label>
        {cs.blank}
        <select value={String(field.blank ?? "hold")} onChange={(e) => onChange({ blank: e.target.value })}>
          {Object.entries(cs.blankPolicies).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
      </label>
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
