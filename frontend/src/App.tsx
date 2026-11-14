import { useCallback, useEffect, useRef, useState } from "react";
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
} from "./api";
import { AdvancedPanel } from "./components/AdvancedPanel";
import { EventLog } from "./components/EventLog";
import { FieldEditor } from "./components/FieldEditor";
import { FieldsTable } from "./components/FieldsTable";
import { Magnifier } from "./components/Magnifier";
import { OutputPanel } from "./components/OutputPanel";
import { ProfilesPanel } from "./components/ProfilesPanel";
import { ToolsPanel } from "./components/ToolsPanel";
import { Overlay } from "./components/Overlay";
import { SourcePanel } from "./components/SourcePanel";
import { StatusBar } from "./components/StatusBar";
import { useElementSize, usePoll, useTick } from "./hooks";
import { cs } from "./i18n/cs";

type SaveState = "idle" | "saving" | "saved" | "error";
type DrawMode = "none" | "field" | "anchor";

const DEFAULTS: Record<FieldType, Partial<FieldConfig>> = {
  clock: { tenths: false, style: "as_is" },
  number: { style: "strip_zeros" },
  period: {},
};

const LIVE_KEY = "optima-time.live";

function readLiveFlag(): boolean {
  try {
    return localStorage.getItem(LIVE_KEY) === "1";
  } catch {
    return false;
  }
}

export default function App() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [drawMode, setDrawMode] = useState<DrawMode>("none");
  const [draft, setDraft] = useState<[Point, Point] | null>(null);
  const [dragCorner, setDragCorner] = useState<number | null>(null);
  const [activeCorner, setActiveCorner] = useState<number | null>(null);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [liveMode, setLiveMode] = useState(readLiveFlag);
  const tick = useTick(400);
  const getState = useCallback(() => api.getState(), []);
  const live = usePoll<LiveState>(getState, 300);
  const saveTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const sourceHost = useRef<HTMLDivElement>(null);
  const sourceSize = useElementSize(sourceHost);

  useEffect(() => {
    api.getProfile().then(setProfile);
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(LIVE_KEY, liveMode ? "1" : "0");
    } catch {
      // a preference only
    }
  }, [liveMode]);

  const reloadProfile = useCallback(() => {
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
        setError(null);
      } catch (e) {
        setSaveState("error");
        setError(errorText(e));
      }
    }, 250);
  }, []);

  useEffect(() => {
    // arrow keys move the selected corner by one source pixel, with Shift by 10 (SPEC 13.1)
    const onKey = (e: KeyboardEvent) => {
      if (activeCorner === null || !profile || liveMode) return;
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
  }, [activeCorner, profile, liveMode, live?.source.width, live?.source.height, save]);

  if (!profile) return <main className="app">…</main>;

  const hasFrame = live?.frame != null;
  const corners = profile.geometry.corners;
  const field = profile.fields.find((f) => f.id === selected) ?? null;
  const locked = liveMode;

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
        setError(null);
      } catch (e) {
        setError(errorText(e));
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
    <main className={`app ${liveMode ? "live" : ""}`}>
      <header>
        <h1>{cs.appName}</h1>
        <StatusBar live={live} />
        <label className="live-toggle" title={cs.liveModeHint}>
          <input
            type="checkbox"
            checked={liveMode}
            onChange={(e) => {
              setLiveMode(e.target.checked);
              if (e.target.checked) setDrawMode("none");
            }}
          />
          {cs.liveMode}
        </label>
        <span className={`save ${saveState}`}>
          {saveState === "saving" ? cs.saving : saveState === "saved" ? cs.saved : saveState === "error" ? cs.saveError : ""}
        </span>
      </header>
      {error && <div className="error-bar">{error}</div>}

      {!locked && (
        <section>
          <h2>{cs.profilesPanel}</h2>
          <ProfilesPanel locked={locked} onSwitched={reloadProfile} />
          <AdvancedPanel key={JSON.stringify([profile.guard.threshold, profile.detection, profile.preprocess])} profile={profile} locked={locked} onProfile={save} />
        </section>
      )}

      <section>
        <h2>{cs.fieldsPanel}</h2>
        <div className="fields">
          <FieldsTable
            fields={profile.fields}
            live={live}
            selected={selected}
            onSelect={setSelected}
            tick={tick}
            showCrops={hasFrame && !liveMode}
          />
          {field && !locked && (
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

      <div className="panels">
        <section>
          <h2>{cs.outputPanel}</h2>
          <OutputPanel
            key={profile.outputs.xml_file.path}
            profile={profile}
            live={live}
            locked={locked}
            onProfile={save}
          />
        </section>
        <section>
          <h2>{cs.eventsPanel}</h2>
          <EventLog />
          <h2>{cs.toolsPanel}</h2>
          <ToolsPanel />
        </section>
      </div>

      <div className="panels">
        <section>
          <h2>{cs.sourcePanel}</h2>
          <SourcePanel profile={profile} locked={locked} onProfile={save} />
          {!locked && <p className="hint">{cs.sourceHint}</p>}
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
            src={hasFrame ? api.previewUrl("source") : null}
            emptyText={cs.noFrame}
            onPointerMove={(p) => dragCorner !== null && setCorner(dragCorner, p, false)}
            onPointerUp={(p) => {
              if (dragCorner !== null) setCorner(dragCorner, p, true);
              setDragCorner(null);
            }}
          >
            <polygon className="board-outline" points={corners.map((c) => c.join(",")).join(" ")} />
            {!locked &&
              corners.map((c, i) => (
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
          {!locked && <p className="hint">{cs.cornerKeys}</p>}
        </section>

        <section>
          <h2>{cs.boardPanel}</h2>
          {!locked && (
            <>
              <p className="hint">{cs.boardHint}</p>
              <div className="toolbar">
                <button onClick={() => toggleDraw("field")} className={drawMode === "field" ? "active" : undefined}>
                  {drawMode === "field" ? cs.cancelDraw : cs.addField}
                </button>
                <button onClick={() => toggleDraw("anchor")} className={drawMode === "anchor" ? "active" : undefined}>
                  {drawMode === "anchor" ? cs.cancelDraw : cs.addAnchor}
                </button>
                {profile.guard.anchors.map((_, i) => (
                  <button
                    key={i}
                    className="danger"
                    onClick={async () => {
                      try {
                        setProfile(await api.deleteAnchor(i));
                      } catch (e) {
                        setError(errorText(e));
                      }
                    }}
                  >
                    {cs.deleteAnchor} {i + 1}
                  </button>
                ))}
              </div>
            </>
          )}
          <Overlay
            src={hasFrame ? api.previewUrl("rectified") : null}
            emptyText={cs.noFrame}
            crosshair={drawMode !== "none"}
            onPointerDown={(p) => drawMode !== "none" && setDraft([p, p])}
            onPointerMove={(p) => draft && setDraft([draft[0], p])}
            onPointerUp={finishDraft}
          >
            {profile.guard.anchors.map((a, i) => (
              <g key={`a${i}`}>
                <rect className="anchor-rect" x={a.roi.x} y={a.roi.y} width={a.roi.w} height={a.roi.h} />
              </g>
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
            {draft && <rect className={`field-rect draft ${drawMode}`} {...toSvgRect(draft)} />}
          </Overlay>
          {live?.guard && live.guard.state !== "off" && (
            <p className="hint">
              {cs.anchor}: {live.guard.state} · {live.guard.scores.join(" · ")}
            </p>
          )}
        </section>
      </div>
    </main>
  );
}

function toSvgRect([a, b]: [Point, Point]) {
  const r = rectFromPoints(a, b);
  return { x: r.x, y: r.y, width: r.w, height: r.h };
}
