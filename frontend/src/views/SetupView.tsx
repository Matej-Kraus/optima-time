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
  type Roi,
} from "../api";
import { AdvancedPanel } from "../components/AdvancedPanel";
import { FieldEditor } from "../components/FieldEditor";
import { Magnifier } from "../components/Magnifier";
import { OutputPanel } from "../components/OutputPanel";
import { Overlay } from "../components/Overlay";
import { ProfilesPanel } from "../components/ProfilesPanel";
import { DerivedPanel } from "../components/DerivedPanel";
import { VmixApiPanel } from "../components/VmixApiPanel";
import { ImagePanel } from "../components/ImagePanel";
import { LockButton, ReadyList, XmlCheck } from "../components/SetupChecks";
import { SourcePanel } from "../components/SourcePanel";
import { useElementSize, useStreamKey } from "../hooks";
import { cs } from "../i18n/cs";
import { applyDrag, corners as rectCorners, nudge, type DragMode } from "../roiEdit";
import { addTemplate } from "../setupTools";

type DrawMode = "none" | "field" | "anchor";
type Target = { kind: "field"; id: string } | { kind: "anchor"; index: number };
interface Drag {
  target: Target;
  mode: DragMode;
  start: Point;
  orig: Roi;
}

const DEFAULTS: Record<FieldType, Partial<FieldConfig>> = {
  clock: { tenths: false, style: "as_is" },
  number: { style: "strip_zeros" },
  period: {},
  indicator: { on_text: "1", off_text: "0" },
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

function stepFromHash(): number {
  const n = Number(window.location.hash.split("/")[1]);
  return n >= 1 && n <= 5 ? n : 1;
}

export function SetupView({ profile, live, tick, save, setProfile, reloadProfile, onError }: Props) {
  const [step, setStep] = useState(stepFromHash);
  const goStep = (n: number) => {
    window.location.hash = `setup/${n}`;
    window.scrollTo(0, 0);
  };
  const [selected, setSelected] = useState<string | null>(null);
  const [drawMode, setDrawMode] = useState<DrawMode>("none");
  const [draft, setDraft] = useState<[Point, Point] | null>(null);
  const [dragCorner, setDragCorner] = useState<number | null>(null);
  const [activeCorner, setActiveCorner] = useState<number | null>(null);
  const [selAnchor, setSelAnchor] = useState<number | null>(null);
  const [drag, setDrag] = useState<Drag | null>(null);
  const [anchorDraft, setAnchorDraft] = useState<{ index: number; roi: Roi } | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const grab = useRef<{ target: Target; mode: DragMode } | null>(null);
  const anchorTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const autoTried = useRef(false);
  const [streamKey, reconnect] = useStreamKey(live !== null);
  const sourceHost = useRef<HTMLDivElement>(null);
  const sourceSize = useElementSize(sourceHost);
  const hasFrame = live?.frame != null;
  const corners = profile.geometry.corners;
  const field = profile.fields.find((f) => f.id === selected) ?? null;

  async function runAuto() {
    try {
      const next = await api.autoAnchors();
      setProfile(next);
      setNotice(cs.autoAnchorsDone(next.guard.anchors.length));
      onError(null);
    } catch (e) {
      setNotice(null);
      onError(errorText(e));
    }
  }

  const commitAnchor = useCallback(
    async (index: number, roi: Roi) => {
      try {
        setProfile(await api.updateAnchor(index, roi));
        onError(null);
      } catch (e) {
        onError(errorText(e));
      } finally {
        setAnchorDraft(null);
      }
    },
    [setProfile, onError],
  );

  useEffect(() => {
    // arrow keys move the selected corner by one source pixel, with Shift by 10 (SPEC 13.1)
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target && ["INPUT", "SELECT", "TEXTAREA"].includes(target.tagName)) return;
      const steps: Record<string, Point> = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
      const d = steps[e.key];
      if (!d) return;
      const n = e.shiftKey ? 10 : 1;
      const rsize = (live?.rectified_size ?? [1280, 650]) as [number, number];
      if (selAnchor !== null && profile.guard.anchors[selAnchor]) {
        e.preventDefault();
        const base = anchorDraft?.index === selAnchor ? anchorDraft.roi : profile.guard.anchors[selAnchor].roi;
        const roi = nudge(base, d[0] * n, d[1] * n, rsize);
        setAnchorDraft({ index: selAnchor, roi });
        clearTimeout(anchorTimer.current);
        anchorTimer.current = setTimeout(() => commitAnchor(selAnchor, roi), 400);
        return;
      }
      if (selected && activeCorner === null) {
        const f = profile.fields.find((x) => x.id === selected);
        if (!f) return;
        e.preventDefault();
        const next = structuredClone(profile);
        next.fields = next.fields.map((x) => (x.id === selected ? { ...x, roi: nudge(f.roi, d[0] * n, d[1] * n, rsize) } : x));
        save(next);
        return;
      }
      if (activeCorner === null) return;
      e.preventDefault();
      const w = live?.source.width || 1920;
      const h = live?.source.height || 1080;
      const next = structuredClone(profile);
      const [x, y] = next.geometry.corners[activeCorner];
      next.geometry.corners[activeCorner] = [x + (d[0] * n) / w, y + (d[1] * n) / h];
      save(next);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [activeCorner, selected, selAnchor, anchorDraft, profile, live?.source.width, live?.source.height, live?.rectified_size, save, commitAnchor]);

  useEffect(() => {
    const onHash = () => setStep(stepFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    // anchors are suggested automatically once the fields exist (then edited by hand)
    if (autoTried.current || !hasFrame || !profile.fields.length || profile.guard.anchors.length) return;
    autoTried.current = true;
    runAuto();
  });

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

  const roiOf = (t: Target): Roi | null => {
    if (t.kind === "field") return profile.fields.find((f) => f.id === t.id)?.roi ?? null;
    if (anchorDraft?.index === t.index) return anchorDraft.roi;
    return profile.guard.anchors[t.index]?.roi ?? null;
  };

  const select = (t: Target) => {
    setActiveCorner(null);
    if (t.kind === "field") {
      setSelected(t.id);
      setSelAnchor(null);
    } else {
      setSelAnchor(t.index);
      setSelected(null);
    }
  };

  const onBoardDown = (p: Point) => {
    const g = grab.current;
    grab.current = null;
    if (g) {
      const orig = roiOf(g.target);
      if (orig) setDrag({ target: g.target, mode: g.mode, start: p, orig });
      return;
    }
    if (drawMode !== "none") {
      setDraft([p, p]);
      return;
    }
    setSelected(null);
    setSelAnchor(null);
  };

  const onBoardMove = (p: Point) => {
    if (drag) {
      const roi = applyDrag(drag.orig, drag.mode, drag.start, p);
      if (drag.target.kind === "field") {
        const id = drag.target.id;
        setProfile({ ...profile, fields: profile.fields.map((f) => (f.id === id ? { ...f, roi } : f)) });
      } else {
        setAnchorDraft({ index: drag.target.index, roi });
      }
      return;
    }
    if (draft) setDraft([draft[0], p]);
  };

  const onBoardUp = (p: Point) => {
    if (drag) {
      const roi = applyDrag(drag.orig, drag.mode, drag.start, p);
      const t = drag.target;
      setDrag(null);
      if (t.kind === "field") {
        const next = structuredClone(profile);
        next.fields = next.fields.map((f) => (f.id === t.id ? { ...f, roi } : f));
        save(next);
      } else {
        commitAnchor(t.index, roi);
      }
      return;
    }
    finishDraft();
  };

  const grabber = (target: Target, mode: DragMode) => () => {
    if (drawMode !== "none") return;
    grab.current = { target, mode };
    select(target);
  };

  const handles = (target: Target, r: Roi) => {
    const [w, h] = live?.rectified_size ?? [1280, 650];
    const hw = 0.012;
    const hh = (0.012 * w) / h;
    return rectCorners(r).map(([mode, x, y]) => (
      <rect
        key={mode}
        className={`resize-handle ${mode}`}
        x={x - hw / 2}
        y={y - hh / 2}
        width={hw}
        height={hh}
        onPointerDown={grabber(target, mode)}
      />
    ));
  };

  const [srcW, srcH] = [live?.source.width || 1920, live?.source.height || 1080];
  const moveCorner = (i: number, dx: number, dy: number) => {
    const [x, y] = corners[i];
    setCorner(i, [Math.min(1, Math.max(0, x + dx / srcW)), Math.min(1, Math.max(0, y + dy / srcH))], true);
  };
  const guardOk = live?.guard?.state === "ok";
  const done = [
    live?.source.state === "ok",
    live?.source.state === "ok" && live?.rectified_size != null,
    profile.fields.length > 0 && profile.guard.anchors.length > 0 && guardOk,
    !!profile.outputs.xml_file.path && live?.outputs.workers.xml_file?.ok === true,
    false,
  ];
  const stepNames = [cs.steps.source, cs.steps.corners, cs.steps.fields, cs.steps.output, cs.steps.profile];
  const next =
    step < 5 ? (
      <button className="primary next-btn" onClick={() => goStep(step + 1)}>
        {cs.setup.next(step + 1, stepNames[step])}
      </button>
    ) : null;
  const ac = activeCorner ?? 0;

  const sourceCanvas = (
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
        labels={
          step === 2 &&
          corners.map((c, i) => (
            <span key={i} className="corner-label" style={{ left: `${c[0] * 100}%`, top: `${c[1] * 100}%` }}>
              C{i + 1} [{Math.round(c[0] * srcW)}, {Math.round(c[1] * srcH)}]
            </span>
          ))
        }
      >
        <polygon className="board-outline" points={corners.map((c) => c.join(",")).join(" ")} />
        {step === 2 &&
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
                setSelected(null);
                setSelAnchor(null);
              }}
            />
          ))}
      </Overlay>
    </div>
  );

  if (live?.locked) {
    return (
      <div className="setup-grid">
        <section className="card locked-card">
          <div className="card-head">
            <h2 className="panel-title">🔒 {cs.lock.lockedTitle}</h2>
            <LockButton live={live} onError={onError} />
          </div>
          <p className="hint">{cs.lock.lockedHint}</p>
          <Overlay src={hasFrame ? api.previewUrl("rectified", streamKey) : null} emptyText={cs.noFrame} onImageError={reconnect}>
            {profile.fields.map((f) => (
              <rect key={f.id} className={`field-rect ${live.fields[f.id]?.read_status ?? ""}`} x={f.roi.x} y={f.roi.y} width={f.roi.w} height={f.roi.h} />
            ))}
          </Overlay>
        </section>
        <section className="card">
          <div className="card-head">
            <h2 className="panel-title">{cs.ready.title}</h2>
          </div>
          <ReadyList profile={profile} live={live} />
        </section>
      </div>
    );
  }

  return (
    <div>
      <nav className="wizard" aria-label="Kroky nastavení">
        {stepNames.map((name, i) => (
          <a
            key={i}
            href={`#setup/${i + 1}`}
            className={i + 1 === step ? "current" : done[i] ? "done" : undefined}
            aria-current={i + 1 === step ? "step" : undefined}
          >
            <span className="n">{done[i] && i + 1 !== step ? "✓" : i + 1}</span>
            {name}
          </a>
        ))}
      </nav>

      {step === 1 && (
        <div className="setup-grid">
          <section className="card">
            <div className="card-head">
              <h2 className="panel-title">{cs.setup.canvasSource}</h2>
            </div>
            {sourceCanvas}
          </section>
          <div className="side-col">
            <section className="card">
              <div className="card-head">
                <h2 className="panel-title">{cs.steps.source}</h2>
              </div>
              <SourcePanel profile={profile} locked={false} onProfile={save} />
            </section>
            {next}
          </div>
        </div>
      )}

      {step === 2 && (
        <div className="setup-grid">
          <section className="card">
            <div className="card-head">
              <h2 className="panel-title">{cs.setup.canvasSource}</h2>
              <span className="label-mono">
                {srcW}×{srcH}
              </span>
            </div>
            <p className="hint">
              {cs.sourceHint} {cs.cornerKeys}
            </p>
            {sourceCanvas}
          </section>
          <div className="side-col">
            <section className="card">
              <div className="card-head">
                <h2 className="panel-title">{cs.setup.activePoint}</h2>
                <span className="label-mono">{cs.setup.corners[ac]}</span>
              </div>
              <div className="corner-tabs" role="group">
                {corners.map((_, i) => (
                  <button key={i} className={i === ac ? "on" : undefined} aria-pressed={i === ac} onClick={() => setActiveCorner(i)} title={cs.setup.corners[i]}>
                    C{i + 1}
                  </button>
                ))}
              </div>
              <div className="coords">
                {(["X", "Y"] as const).map((axis, k) => (
                  <div key={axis} className="coord">
                    <span className="label-mono">{axis} (px)</span>
                    <div className="stepper">
                      <button aria-label={`${axis} −1`} onClick={() => moveCorner(ac, k === 0 ? -1 : 0, k === 1 ? -1 : 0)}>
                        −
                      </button>
                      <b>{Math.round(corners[ac][k] * (k === 0 ? srcW : srcH))}</b>
                      <button aria-label={`${axis} +1`} onClick={() => moveCorner(ac, k === 0 ? 1 : 0, k === 1 ? 1 : 0)}>
                        +
                      </button>
                    </div>
                  </div>
                ))}
              </div>
              <div className="canvas-tools">
                <button
                  onClick={() => {
                    const n = structuredClone(profile);
                    n.geometry.corners = [
                      [0.1, 0.1],
                      [0.9, 0.1],
                      [0.9, 0.9],
                      [0.1, 0.9],
                    ];
                    save(n);
                  }}
                >
                  {cs.setup.resetCorners}
                </button>
              </div>
            </section>
            <section className="card">
              <div className="card-head">
                <h2 className="panel-title">{cs.setup.canvasBoard}</h2>
              </div>
              <Overlay src={hasFrame ? api.previewUrl("rectified", streamKey) : null} emptyText={cs.noFrame} onImageError={reconnect} />
            </section>
            <section className="card">
              <div className="card-head">
                <h2 className="panel-title">{cs.image.title}</h2>
              </div>
              <ImagePanel key={profile.name} profile={profile} save={save} onNotice={setNotice} />
              {notice && <p className="notice section-gap">{notice}</p>}
            </section>
            {next}
          </div>
        </div>
      )}

      {step === 3 && (
        <div className="setup-grid">
          <section className="card">
            <div className="card-head">
              <h2 className="panel-title">{cs.setup.canvasBoard}</h2>
              {live?.guard && live.guard.state !== "off" && (
                <span className={`badge ${guardOk ? "" : "warn"}`}>
                  {cs.anchor}: {guardOk ? "sedí" : live.guard.state}
                </span>
              )}
            </div>
            <p className="hint">{cs.boardHint}</p>
            <Overlay
              src={hasFrame ? api.previewUrl("rectified", streamKey) : null}
              emptyText={cs.noFrame}
              onImageError={reconnect}
              crosshair={drawMode !== "none"}
              onPointerDown={onBoardDown}
              onPointerMove={onBoardMove}
              onPointerUp={onBoardUp}
            >
              {profile.guard.anchors.map((a, i) => {
                const r = anchorDraft?.index === i ? anchorDraft.roi : a.roi;
                const target: Target = { kind: "anchor", index: i };
                return (
                  <g key={`a${i}`}>
                    <rect
                      className={`anchor-rect ${selAnchor === i ? "selected" : ""}`}
                      x={r.x}
                      y={r.y}
                      width={r.w}
                      height={r.h}
                      onPointerDown={grabber(target, "move")}
                    />
                    {selAnchor === i && handles(target, r)}
                  </g>
                );
              })}
              {profile.fields.map((f) => {
                const target: Target = { kind: "field", id: f.id };
                return (
                  <g key={f.id}>
                    <rect
                      className={`field-rect ${f.id === selected ? "selected" : ""} ${live?.fields[f.id]?.read_status ?? ""}`}
                      x={f.roi.x}
                      y={f.roi.y}
                      width={f.roi.w}
                      height={f.roi.h}
                      onPointerDown={grabber(target, "move")}
                    />
                    {f.id === selected && handles(target, f.roi)}
                  </g>
                );
              })}
              {draft &&
                (() => {
                  const r = rectFromPoints(draft[0], draft[1]);
                  return <rect className={`field-rect draft ${drawMode}`} x={r.x} y={r.y} width={r.w} height={r.h} />;
                })()}
            </Overlay>
            <div className="canvas-tools">
              <button onClick={() => toggleDraw("field")} className={drawMode === "field" ? "primary" : "cyan"}>
                {drawMode === "field" ? cs.cancelDraw : cs.addField}
              </button>
              <button onClick={() => toggleDraw("anchor")} className={drawMode === "anchor" ? "primary" : "warn"}>
                {drawMode === "anchor" ? cs.cancelDraw : cs.addAnchor}
              </button>
              <button onClick={runAuto} disabled={!hasFrame || !profile.fields.length}>
                {cs.autoAnchors}
              </button>
              <button
                title={cs.template.hint}
                onClick={() => {
                  const { fields, added } = addTemplate(profile.fields);
                  setNotice(cs.template.added(added));
                  if (!added.length) return;
                  const n = structuredClone(profile);
                  n.fields = fields;
                  save(n);
                }}
              >
                {cs.template.floorball}
              </button>
              {selAnchor !== null && (
                <button
                  className="danger"
                  onClick={async () => {
                    try {
                      const i = selAnchor;
                      setSelAnchor(null);
                      setProfile(await api.deleteAnchor(i));
                    } catch (e) {
                      onError(errorText(e));
                    }
                  }}
                >
                  {cs.deleteAnchor} {selAnchor + 1}
                </button>
              )}
            </div>
            <p className="hint section-gap">{cs.editHint}</p>
            {notice && <p className="notice">{notice}</p>}
          </section>
          <div className="side-col">
            <section className="card">
              <div className="card-head">
                <h2 className="panel-title">{cs.setup.fieldsAnchors}</h2>
              </div>
              <ul className="field-picker">
                {profile.fields.map((f) => {
                  const s = live?.fields[f.id];
                  return (
                    <li key={f.id}>
                      <button className={f.id === selected ? "selected" : ""} onClick={() => select({ kind: "field", id: f.id })}>
                        <code>{f.id}</code>
                        <span>
                          <b>{s?.read_text ?? s?.text ?? "—"}</b>
                          {s?.confidence != null && <span className="dim"> {Math.round(s.confidence * 100)} %</span>}
                        </span>
                      </button>
                    </li>
                  );
                })}
                {profile.guard.anchors.map((_, i) => (
                  <li key={`a${i}`}>
                    <button className={selAnchor === i ? "selected" : ""} onClick={() => select({ kind: "anchor", index: i })}>
                      <code>
                        {cs.anchor} {i + 1}
                      </code>
                      <span className="dim">{live?.guard?.scores[i]?.toFixed(2) ?? "—"}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </section>
            {field && (
              <section className="card">
                <FieldEditor
                  key={field.id}
                  field={field}
                  idError={idError}
                  onChange={(patch) => updateField(field.id, patch)}
                  onType={(t) => changeType(field, t)}
                  onDelete={() => {
                    const n = structuredClone(profile);
                    n.fields = n.fields.filter((x) => x.id !== field.id);
                    setSelected(null);
                    save(n);
                  }}
                />
              </section>
            )}
            {next}
          </div>
        </div>
      )}

      {step === 4 && (
        <div className="setup-grid">
          <section className="card">
            <div className="card-head">
              <h2 className="panel-title">{cs.steps.output}</h2>
            </div>
            <OutputPanel key={profile.outputs.xml_file.path} profile={profile} locked={false} onProfile={save} />
          </section>
          <section className="card">
            <div className="card-head">
              <h2 className="panel-title">{cs.derived.title}</h2>
            </div>
            <DerivedPanel profile={profile} live={live} locked={false} onProfile={save} />
          </section>
          <div className="side-col">
            <section className="card">
              <div className="card-head">
                <h2 className="panel-title">{cs.testData}</h2>
              </div>
              <div className="quick">
                <button className="cyan" onClick={() => api.output("test")}>
                  {cs.testData}
                </button>
                <button className="primary" onClick={() => api.output("live")}>
                  {cs.backToLive}
                </button>
              </div>
            </section>
            <section className="card">
              <div className="card-head">
                <h2 className="panel-title">{cs.vmixApi.title}</h2>
              </div>
              <VmixApiPanel key={profile.name} profile={profile} live={live} locked={false} onProfile={save} />
            </section>
            <section className="card">
              <div className="card-head">
                <h2 className="panel-title">{cs.xmlCheck.title}</h2>
              </div>
              <XmlCheck
                ids={[...profile.fields.map((f) => f.id), ...(profile.derived ?? []).map((d) => d.id)]}
                onRename={(from, to) => {
                  if (profile.fields.some((f) => f.id === from)) updateField(from, { id: to });
                  else save({ ...profile, derived: profile.derived.map((d) => (d.id === from ? { ...d, id: to } : d)) });
                }}
              />
            </section>
            {next}
          </div>
        </div>
      )}

      {step === 5 && (
        <div className="setup-grid">
          <div className="side-col">
          <section className="card">
            <div className="card-head">
              <h2 className="panel-title">{cs.ready.title}</h2>
              <LockButton live={live} onError={onError} />
            </div>
            <ReadyList profile={profile} live={live} />
          </section>
          <section className="card">
            <div className="card-head">
              <h2 className="panel-title">{cs.advancedPanel}</h2>
            </div>
            <AdvancedPanel
              key={JSON.stringify([profile.geometry.rotate, profile.guard.threshold, profile.detection, profile.preprocess])}
              profile={profile}
              locked={false}
              onProfile={save}
            />
          </section>
          </div>
          <section className="card">
            <div className="card-head">
              <h2 className="panel-title">{cs.profilesPanel}</h2>
            </div>
            <ProfilesPanel locked={false} onSwitched={reloadProfile} />
          </section>
        </div>
      )}
    </div>
  );
}
