import { useState } from "react";
import { api, type LiveState, type Profile } from "../api";
import { CompactEventLog } from "../components/EventLog";
import { FieldRows, HoldForm } from "../components/FieldRows";
import { OnAirBoard } from "../components/OnAirBoard";
import { Overlay } from "../components/Overlay";
import { useNow, useStreamKey } from "../hooks";
import { cs } from "../i18n/cs";

interface Props {
  profile: Profile;
  live: LiveState | null;
  tick: number;
}

/** During a match: what is on air, manual holds, the output. Nothing here moves the setup. */
export function LiveView({ profile, live }: Props) {
  const [selected, setSelected] = useState<string | null>(null);
  const [preview, setPreview] = useState(true);
  const [events, setEvents] = useState(true);
  const [streamKey, reconnect] = useStreamKey(live !== null);
  const hasFrame = live?.frame != null;
  const fields = profile.fields.filter((f) => f.enabled);
  const mode = live?.outputs.mode ?? "live";
  const xml = live?.outputs.workers.xml_file;
  const now = useNow();
  const ago = xml?.last_ok_wall ? Math.max(0, now - xml.last_ok_wall) : null;
  const path = profile.outputs.xml_file.path;
  const scores = live?.guard?.scores ?? [];

  return (
    <div>
      <div className="live-grid">
        <section className="card" aria-label={cs.onAir}>
          <div className="card-head">
            <h2 className="panel-title">
              {cs.onAir}
              <span className="aside">{cs.onAirHint}</span>
            </h2>
            <span className={`badge ${mode === "live" ? "" : "warn"}`}>{cs.modes[mode]}</span>
          </div>
          <OnAirBoard fields={profile.fields} live={live} onHold={setSelected} />
        </section>

        <div className="side-col">
          <section className="card">
            <div className="card-head">
              <h2 className="panel-title">{cs.live.fieldsTitle}</h2>
            </div>
            <FieldRows fields={fields} live={live} selected={selected} onSelect={setSelected} />
            <HoldForm key={selected ?? ""} id={selected} live={live} />
          </section>

          <section className="card">
            <div className="card-head">
              <h2 className="panel-title">{cs.live.quickTitle}</h2>
            </div>
            <p className="hint" title={path}>
              {path ? (
                <>
                  {cs.writesTo} <b className="mono">{path.split(/[\\/]/).pop()}</b>
                  {ago !== null && <> · {cs.lastWrite.toLowerCase()} {cs.agoSeconds(ago)}</>}
                </>
              ) : (
                cs.noOutputYet
              )}
            </p>
            <div className="quick">
              {mode === "live" ? (
                <button className="danger" onClick={() => api.output("pause")}>
                  {cs.pause}
                </button>
              ) : (
                <button className="primary" onClick={() => api.output("live")}>
                  {mode === "test" ? cs.backToLive : cs.resume}
                </button>
              )}
              <button className="cyan" onClick={() => api.output("test")}>
                {cs.testData}
              </button>
              <button onClick={() => api.output("test-clear")}>{cs.testClear}</button>
              <button onClick={() => api.clearValues()}>{cs.clearValues}</button>
            </div>
          </section>
        </div>
      </div>

      <div className="bottom-grid">
        <section className="card">
          <div className="card-head">
            <h2 className="panel-title">{cs.live.previewTitle}</h2>
            <button className="ghost" onClick={() => setPreview((p) => !p)} aria-expanded={preview}>
              {preview ? cs.live.hide : cs.live.showMore}
            </button>
          </div>
          {preview && (
            <>
              <Overlay
                src={hasFrame ? api.previewUrl("rectified", streamKey) : null}
                emptyText={cs.noFrame}
                onImageError={reconnect}
                labels={profile.fields.map((f) => (
                  <span key={f.id} style={{ left: `${f.roi.x * 100}%`, top: `${f.roi.y * 100}%` }}>
                    {f.id}
                  </span>
                ))}
              >
                {profile.fields.map((f) => (
                  <rect
                    key={f.id}
                    className={`field-rect ${live?.fields[f.id]?.read_status ?? ""}`}
                    x={f.roi.x}
                    y={f.roi.y}
                    width={f.roi.w}
                    height={f.roi.h}
                  />
                ))}
              </Overlay>
              <div className="preview-foot">
                <span>
                  {cs.live.guardScore}:{" "}
                  {scores.length ? (
                    <span className={live?.guard?.state === "ok" ? "ok" : "bad"}>{Math.min(...scores).toFixed(2)}</span>
                  ) : (
                    "—"
                  )}
                </span>
                <span>
                  {live?.rectified_size ? `${live.rectified_size[0]}×${live.rectified_size[1]}` : ""}
                </span>
              </div>
            </>
          )}
        </section>

        <section className="card">
          <div className="card-head">
            <h2 className="panel-title">{cs.live.eventsTitle}</h2>
            <span className="row">
              {events && (
                <a className="mono" href="#diagnostics">
                  {cs.diag.title}
                </a>
              )}
              <button className="ghost" onClick={() => setEvents((e) => !e)} aria-expanded={events}>
                {events ? cs.live.hide : cs.live.showMore}
              </button>
            </span>
          </div>
          {events && <CompactEventLog limit={8} />}
        </section>
      </div>
    </div>
  );
}
