import { useCallback, useState } from "react";
import { api, errorText, type GuardHistory, type LiveState, type Profile, type RecorderStatus } from "../api";
import { EventLog } from "../components/EventLog";
import { chartPaths, chartY } from "../display";
import { usePoll } from "../hooks";
import { cs } from "../i18n/cs";

interface Props {
  live: LiveState | null;
  profile: Profile;
  tick: number;
}

function AnchorChart({ live, profile }: { live: LiveState | null; profile: Profile }) {
  const get = useCallback(() => api.guardHistory(), []);
  const history = usePoll<GuardHistory>(get, 1000);
  const threshold = history?.threshold ?? profile.guard.threshold;
  const W = 240;
  const H = 100;
  const limitY = chartY(threshold, H);
  if (!profile.guard.anchors.length) return <p className="hint">{cs.diag.noAnchors}</p>;
  return (
    <>
      <p className="hint">{cs.diag.anchorChartHint(threshold)}</p>
      <svg className="chart" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" aria-label={cs.diag.anchorChart}>
        <rect className="below" x={0} y={limitY} width={W} height={H - limitY} />
        <line className="limit" x1={0} x2={W} y1={limitY} y2={limitY} />
        {chartPaths(history?.points ?? [], W, H).map((d, i) => (
          <polyline key={i} className="line" points={d} />
        ))}
      </svg>
      <div className="anchor-scores">
        {profile.guard.anchors.map((_, i) => {
          const s = live?.guard?.scores[i];
          return (
            <span key={i}>
              {cs.diag.anchorN(i + 1)}
              <b style={{ color: s != null && s < threshold ? "var(--accent-danger)" : undefined }}>{s != null ? s.toFixed(3) : "—"}</b>
            </span>
          );
        })}
      </div>
    </>
  );
}

function Crops({ live, profile, tick }: Props) {
  const [mode, setMode] = useState<"otsu" | "raw">("otsu");
  return (
    <>
      <div className="seg-tabs" role="group">
        {(["otsu", "raw"] as const).map((m) => (
          <button key={m} className={m === mode ? "on" : undefined} aria-pressed={m === mode} onClick={() => setMode(m)}>
            {cs.diag[m]}
          </button>
        ))}
      </div>
      <div className="crops">
        {profile.fields
          .filter((f) => f.enabled)
          .map((f) => {
            const s = live?.fields[f.id];
            return (
              <div key={f.id} className={`crop-card ${f.type === "clock" && !/penalt|trest/i.test(f.id) ? "wide" : ""}`}>
                <div className="head">
                  <span>{f.id}</span>
                  <span className="pct">{s?.confidence != null ? `${Math.round(s.confidence * 100)} %` : "—"}</span>
                </div>
                <img src={api.cropUrl(f.id, tick, mode)} alt={f.id} />
                <div className="reading">
                  <b>{s?.read_text ?? s?.raw ?? "—"}</b>
                  <span className="dim">
                    {cs.contrast} {s?.contrast ?? "—"}
                  </span>
                </div>
              </div>
            );
          })}
      </div>
    </>
  );
}

export function DiagnosticsView({ live, profile, tick }: Props) {
  const getRec = useCallback(() => api.sampleStatus(), []);
  const rec = usePoll<RecorderStatus>(getRec, 1000);
  const [error, setError] = useState<string | null>(null);
  const p = live?.process;
  const src = live?.source;

  return (
    <div>
      <section className="card">
        <div className="card-head">
          <h2 className="panel-title">
            {cs.diag.title}
            {live?.version && (
              <span className="aside">
                {cs.diag.version} {live.version}
              </span>
            )}
          </h2>
          <div className="actions">
            <button
              className="danger"
              disabled={rec?.active}
              onClick={async () => {
                try {
                  await api.recordSample(60);
                  setError(null);
                } catch (e) {
                  setError(errorText(e));
                }
              }}
            >
              {rec?.active ? `${cs.tools.recording} ${Math.round(rec.seconds)} s` : cs.diag.record}
            </button>
            <a className="button" href={api.diagnosticsUrl} download>
              {cs.diag.bundle}
            </a>
            <a className="button" href="/api/events?limit=5000" download="udalosti.json">
              {cs.diag.events}
            </a>
          </div>
        </div>
        {rec?.folder && (
          <p className="hint">
            {rec.active ? cs.tools.recording : cs.tools.recorded} <code>{rec.folder}</code> · {rec.frames} {cs.tools.frames}
            {rec.error && ` · ${rec.error}`}
          </p>
        )}
        {error && <p className="problem bad">{error}</p>}
        <div className="metrics">
          <Metric label={cs.diag.frameMs} value={p?.frame_ms_p50} unit="ms" sub={cs.diag.frameMsSub(p?.frame_ms_p95 ?? null)} />
          <Metric
            label={cs.diag.dropped}
            value={src?.dropped ?? 0}
            cls={(src?.dropped ?? 0) > 0 ? "warn" : "plain"}
            sub={cs.diag.droppedSub(src?.received ?? 0)}
          />
          <Metric label={cs.diag.jitter} value={p?.frame_jitter_ms} unit="ms" cls="cyan" sub={cs.diag.jitterSub} />
          <Metric
            label={cs.diag.cpu}
            value={p?.cpu_percent}
            unit="%"
            cls="plain"
            sub={p ? cs.diag.cpuSub(p.cpu_count, p.rss_mb, p.threads) : ""}
          />
        </div>
        {p && p.supervisor_restarts > 0 && (
          <p className="hint section-gap">
            {cs.diag.restarts}: {p.supervisor_restarts}
          </p>
        )}
      </section>

      <div className="diag-grid">
        <section className="card">
          <div className="card-head">
            <h2 className="panel-title">{cs.diag.crops}</h2>
          </div>
          <Crops live={live} profile={profile} tick={tick} />
        </section>
        <div className="side-col">
          <section className="card">
            <div className="card-head">
              <h2 className="panel-title">{cs.diag.anchorChart}</h2>
            </div>
            <AnchorChart live={live} profile={profile} />
          </section>
          <section className="card">
            <div className="card-head">
              <h2 className="panel-title">{cs.eventsPanel}</h2>
            </div>
            <EventLog />
          </section>
        </div>
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
  unit,
  sub,
  cls = "",
}: {
  label: string;
  value: number | null | undefined;
  unit?: string;
  sub: string;
  cls?: string;
}) {
  return (
    <div className="metric">
      <div className="label-mono">{label}</div>
      <div className={`value ${cls}`}>
        {value ?? "—"}
        {unit && value != null && <span className="unit">{unit}</span>}
      </div>
      <div className="hint">{sub}</div>
    </div>
  );
}
