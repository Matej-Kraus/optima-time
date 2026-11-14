import { api, type LiveState, type Profile } from "../api";
import { useNow } from "../hooks";
import { cs } from "../i18n/cs";
import { lights, type Level } from "../status";

import { TABS, type SaveState, type Tab } from "../tabs";

interface TopBarProps {
  live: LiveState | null;
  tab: Tab;
  saveState: SaveState;
}

/** Logo, telemetry chips (the traffic light with numbers), tabs, clock and the output switch. */
export function TopBar({ live, tab, saveState }: TopBarProps) {
  const level = Object.fromEntries(lights(live).lights.map((l) => [l.key, l.level])) as Partial<Record<string, Level>>;
  const now = useNow();
  const mode = live?.outputs.mode ?? "live";
  const xml = live?.outputs.workers.xml_file;
  const scores = live?.guard?.scores ?? [];
  const p50 = live?.process?.frame_ms_p50 ?? live?.frame?.timings_ms.total;
  return (
    <header className="topbar">
      <div className="brand">
        <span className={`dot ${level.source === "ok" && level.output !== "bad" ? "ok" : (level.source ?? "bad")}`} aria-hidden />
        <span className="logo">{cs.appName}</span>
        {live?.version && <span className="chip">v{live.version}</span>}
      </div>
      <div className="telemetry" aria-label="Stav">
        <Chip label={cs.telemetry.source} level={level.source} value={live ? (cs.sourceStates[live.source.state] ?? live.source.state) : "—"} />
        <Chip label={cs.telemetry.ocr} level={level.processing} value={p50 != null ? `${Math.round(p50)} ms` : "—"} />
        <Chip label={cs.telemetry.anchors} level={level.guard} value={scores.length ? Math.min(...scores).toFixed(2) : "vyp."} />
        <Chip
          label={cs.telemetry.vmix}
          level={level.output}
          value={mode !== "live" ? cs.modes[mode] : xml?.last_write_ms != null ? `${Math.round(xml.last_write_ms)} ms` : "—"}
        />
      </div>
      <nav className="tabs" aria-label="Sekce">
        {TABS.map((t) => (
          <a
            key={t}
            href={`#${t}`}
            className={t === tab ? `active ${t}` : undefined}
            aria-current={t === tab ? "page" : undefined}
          >
            {cs.tabs[t]}
          </a>
        ))}
      </nav>
      <span className={`save-state ${saveState}`} aria-live="polite">
        {saveState === "saving" ? cs.saving : saveState === "saved" ? cs.saved : saveState === "error" ? cs.saveError : ""}
      </span>
      <span className="clock">{new Date(now * 1000).toLocaleTimeString("cs-CZ")}</span>
      {mode === "live" ? (
        <button className="danger solid" onClick={() => api.output("pause")}>
          {cs.shell.pauseOutput}
        </button>
      ) : (
        <button className="primary" onClick={() => api.output("live")}>
          {mode === "test" ? cs.shell.backToLive : cs.shell.resumeOutput}
        </button>
      )}
    </header>
  );
}

function Chip({ label, value, level }: { label: string; value: string; level?: Level }) {
  return (
    <span className={`tchip ${level ?? "off"}`}>
      <span className="dot" aria-hidden />
      {label} <b>{value}</b>
    </span>
  );
}

function sourceName(p: Profile): string {
  const s = p.source;
  if (s.type === "ndi") return s.ndi_name || "NDI";
  if (s.type === "device") return s.device_name || `#${s.device_index}`;
  return s.path.split(/[\\/]/).pop() || cs.source.types.file;
}

/** Where the picture comes from, where the values go, and the numbers behind the lights. */
export function Sidebar({ live, profile }: { live: LiveState | null; profile: Profile | null }) {
  const src = live?.source;
  const srcLevel = src?.state === "ok" ? "ok" : src?.state === "connecting" || src?.state === "ended" ? "warn" : "bad";
  const mode = live?.outputs.mode ?? "live";
  const xml = live?.outputs.workers.xml_file;
  const outLevel = !xml ? "bad" : xml.ok === false ? "bad" : mode !== "live" ? "warn" : "ok";
  const xmlFile = profile?.outputs.xml_file.path.split(/[\\/]/).pop();
  return (
    <aside className="sidebar">
      <div className="label-mono">{cs.shell.channels}</div>
      {profile && (
        <>
          <div className="side-item active" title={sourceName(profile)}>
            <span>
              {cs.shell.sourceItem}
              <br />
              <span className="mono dim">{sourceName(profile)}</span>
            </span>
            <span className={`mono ${srcLevel}`}>{src ? (cs.sourceStates[src.state] ?? src.state) : "—"}</span>
          </div>
          <div className="side-item" title={profile.outputs.xml_file.path}>
            <span>
              {cs.shell.outputItem}
              <br />
              <span className="mono dim">{xmlFile || "—"}</span>
            </span>
            <span className={`mono ${outLevel}`}>{xml ? cs.modes[mode] : "—"}</span>
          </div>
          <div className="side-card">
            <strong>
              {cs.shell.profile}
              {live?.locked && <span className="badge warn lock-badge">🔒 {cs.lock.badge}</span>}
            </strong>
            <span className="mono">{profile.name}</span>
            <br />
            <a className="mono" href="#setup">
              {cs.shell.changeProfile}
            </a>
          </div>
        </>
      )}
      <div className="side-stats">
        <span>
          {cs.shell.stats.streamFps}{" "}
          <b>
            {src?.width ? `${src.width}×${src.height}` : "—"} {src?.fps ? `@ ${src.fps.toFixed(1)}` : ""}
          </b>
        </span>
        <span>
          {cs.shell.stats.processed} <b>{live ? `${live.processing_fps} ${cs.fps}` : "—"}</b>
        </span>
        <span>
          {cs.shell.stats.dropped} <b>{src?.dropped ?? 0}</b>
        </span>
        {live?.process && (
          <span>
            CPU <b>{live.process.cpu_percent} %</b> · <b>{Math.round(live.process.rss_mb)} MB</b>
          </span>
        )}
      </div>
    </aside>
  );
}
