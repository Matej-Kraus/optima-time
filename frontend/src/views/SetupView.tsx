import { useEffect, useRef, useState } from "react";
import {
  api,
  errorText,
  FIELD_ID_PATTERN,
  nextFieldId,
  rectFromPoints,
  type FieldConfig,
  type FieldType,
  type LiveState,
  type Point,
  type Profile,
} from "../api";
import { AdvancedPanel } from "../components/AdvancedPanel";
import { FieldEditor } from "../components/FieldEditor";
import { Magnifier } from "../components/Magnifier";
import { OutputPanel } from "../components/OutputPanel";
import { Overlay } from "../components/Overlay";
import { ProfilesPanel } from "../components/ProfilesPanel";
import { SourcePanel } from "../components/SourcePanel";
import { useElementSize, useStreamKey } from "../hooks";
import { cs } from "../i18n/cs";

type DrawMode = "none" | "field" | "anchor";

const DEFAULTS: Record<FieldType, Partial<FieldConfig>> = {
  clock: { tenths: false, style: "as_is" },
  number: { style: "strip_zeros" },
  period: {},
};

interface Props {
  profile: Profile;
  live: LiveState | null;
  tick: number;
  save: (p: Profile) => void;
  setProfile: (p: Profile) => void;
  reloadProfile: () => void;
  onError: (message: string | null) => void;
}

/** The one-time setup, in the order it is done (OPERATOR.md part B). */
export function SetupView({ profile, live, tick, save, setProfile, reloadProfile, onError }: Props) {
  const [selected, setSelected] = useState<string | null>(null);
  const [drawMode, setDrawMode] = useState<DrawMode>("none");
  const [draft, setDraft] = useState<[Point, Point] | null>(null);
  const [dragCorner, setDragCorner] = useState<number | null>(null);
  const [activeCorner, setActiveCorner] = useState<number | null>(null);
  const [streamKey, reconnect] = useStreamKey(live !== null);
  const sourceHost = useRef<HTMLDivElement>(null);
  const sourceSize = useElementSize(sourceHost);
  const hasFrame = live?.frame != null;
  const corners = profile.geometry.corners;
  const field = profile.fields.find((f) => f.id === selected) ?? null;

  useEffect(() => {
    // arrow keys move the selected corner by one source pixel, with Shift by 10 (SPEC 13.1)
    const onKey = (e: KeyboardEvent) => {
      if (activeCorner === null) return;
      const target = e.target as HTMLElement | null;
      if (target && ["INPUT", "SELECT", "TEXTAREA"].includes(target.tagName)) return;
      const steps: Record<string, Point> = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
      const d = steps[e.key];
      if (!d) return;
      e.preventDefault();
      const n = e.shiftKey ? 10 : 1;
      const w = live?.source.width || 1920;
      const h = live?.source.height || 1080;
      const next = structuredClone(profile);
      const [x, y] = next.geometry.corners[activeCorner];
      next.geometry.corners[activeCorner] = [x + (d[0] * n) / w, y + (d[1] * n) / h];
      save(next);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [activeCorner, profile, live?.source.width, live?.source.height, save]);

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
    const { id, label, roi, enabled } = f; // the backend fills in the new type's defaults
    const next = structuredClone(profile);
    next.fields = next.fields.map((x) => (x.id === f.id ? ({ id, label, roi, enabled, type, ...DEFAULTS[type] } as FieldConfig) : x));
    save(next);
  };

  const finishDraft = async () => {
    if (!draft) return;
    const roi = rectFromPoints(draft[0], draft[1]);
    const mode = drawMode;
    setDraft(null);
    setDrawMode("none");
    if (roi.w < 0.01 || roi.h < 0.01) return;
    if (mode === "anchor") {
      try {
        setProfile(await api.addAnchor(roi));
        onError(null);
      } catch (e) {
        onError(errorText(e));
      }
      return;
    }
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

  const toggleDraw = (mode: DrawMode) => setDrawMode((m) => (m === mode ? "none" : mode));

  return (
    <ol className="steps">
      <li className="step">
        <h2>{cs.steps.source}</h2>
        <SourcePanel profile={profile} locked={false} onProfile={save} />
      </li>

      <li className="step">
        <h2>{cs.steps.corners}</h2>
        <p className="hint">{cs.sourceHint} {cs.cornerKeys}</p>
        <div className="magnifier-host" ref={sourceHost}>
          {dragCorner !== null && hasFrame && (
            <Magnifier
              src={api.frameUrl("source", tick).replace("max_width=960", "max_width=0")}
              at={corners[dragCorner]}
              hostWidth={sourceSize.width}
              hostHeight={sourceSize.height}
            />
          )}
          <Overlay
            src={hasFrame ? api.previewUrl("source", streamKey) : null}
            emptyText={cs.noFrame}
            onImageError={reconnect}
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
                className={`handle ${i === activeCorner ? "active" : ""}`}
                cx={c[0]}
                cy={c[1]}
                r={0.012}
                onPointerDown={() => {
                  setDragCorner(i);
                  setActiveCorner(i);
                }}
              />
            ))}
          </Overlay>
        </div>
      </li>

      <li className="step">
        <h2>{cs.steps.fields}</h2>
        <p className="hint">{cs.boardHint}</p>
        <div className="toolbar">
          <button onClick={() => toggleDraw("field")} className={drawMode === "field" ? "primary" : undefined}>
            {drawMode === "field" ? cs.cancelDraw : cs.addField}
          </button>
          <button onClick={() => toggleDraw("anchor")} className={drawMode === "anchor" ? "primary" : undefined}>
            {drawMode === "anchor" ? cs.cancelDraw : cs.addAnchor}
          </button>
          {profile.guard.anchors.map((_, i) => (
            <button
              key={i}
              className="quiet"
              onClick={async () => {
                try {
                  setProfile(await api.deleteAnchor(i));
                } catch (e) {
                  onError(errorText(e));
                }
              }}
            >
              {cs.deleteAnchor} {i + 1}
            </button>
          ))}
          {live?.guard && live.guard.state !== "off" && (
            <span className="muted">
              {cs.anchor}: {live.guard.state === "ok" ? "sedí" : live.guard.state} ({live.guard.scores.join(", ")})
            </span>
          )}
        </div>
        <div className="fields-setup">
          <Overlay
            src={hasFrame ? api.previewUrl("rectified", streamKey) : null}
            emptyText={cs.noFrame}
            onImageError={reconnect}
            crosshair={drawMode !== "none"}
            onPointerDown={(p) => drawMode !== "none" && setDraft([p, p])}
            onPointerMove={(p) => draft && setDraft([draft[0], p])}
            onPointerUp={finishDraft}
          >
            {profile.guard.anchors.map((a, i) => (
              <rect key={`a${i}`} className="anchor-rect" x={a.roi.x} y={a.roi.y} width={a.roi.w} height={a.roi.h} />
            ))}
            {profile.fields.map((f) => (
              <rect
                key={f.id}
                className={`field-rect ${f.id === selected ? "selected" : ""} ${live?.fields[f.id]?.read_status ?? ""}`}
                x={f.roi.x}
                y={f.roi.y}
                width={f.roi.w}
                height={f.roi.h}
                onPointerDown={(e) => {
                  if (drawMode === "none") {
                    e.stopPropagation();
                    setSelected(f.id);
                  }
                }}
              />
            ))}
            {draft && (() => {
              const r = rectFromPoints(draft[0], draft[1]);
              return <rect className={`field-rect draft ${drawMode}`} x={r.x} y={r.y} width={r.w} height={r.h} />;
            })()}
          </Overlay>
          <div className="field-side">
            <ul className="field-list">
              {profile.fields.map((f) => (
                <li key={f.id}>
                  <button className={f.id === selected ? "selected" : ""} onClick={() => setSelected(f.id)}>
                    <code>{f.id}</code>
                    <span>{live?.fields[f.id]?.read_text ?? live?.fields[f.id]?.text ?? "—"}</span>
                  </button>
                </li>
              ))}
            </ul>
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
        </div>
      </li>

      <li className="step">
        <h2>{cs.steps.output}</h2>
        <OutputPanel key={profile.outputs.xml_file.path} profile={profile} locked={false} onProfile={save} />
      </li>

      <li className="step">
        <h2>{cs.steps.profile}</h2>
        <ProfilesPanel locked={false} onSwitched={reloadProfile} />
        <AdvancedPanel
          key={JSON.stringify([profile.geometry.rotate, profile.guard.threshold, profile.detection, profile.preprocess])}
          profile={profile}
          locked={false}
          onProfile={save}
        />
      </li>
    </ol>
  );
}
