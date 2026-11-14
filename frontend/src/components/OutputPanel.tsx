import { useCallback, useState } from "react";
import { api, type LiveState, type Profile } from "../api";
import { usePoll } from "../hooks";
import { cs } from "../i18n/cs";

interface Props {
  profile: Profile;
  live: LiveState | null;
  locked: boolean;
  onProfile: (p: Profile) => void;
}

export function OutputPanel({ profile, live, locked, onProfile }: Props) {
  const xml = profile.outputs.xml_file;
  const [path, setPath] = useState(xml.path); // the parent remounts this panel when the saved path changes
  const getXml = useCallback(() => api.getXml(), []);
  const content = usePoll(getXml, 1000);
  const mode = live?.outputs.mode ?? "live";
  const w = live?.outputs.workers.xml_file;
  const url = `${window.location.origin}/data/values.xml`;

  const savePath = () => {
    if (path === xml.path) return;
    const next = structuredClone(profile);
    next.outputs.xml_file.path = path;
    onProfile(next);
  };

  return (
    <div className="output-panel">
      <label>
        {cs.xmlPath}
        <input value={path} disabled={locked} onChange={(e) => setPath(e.target.value)} onBlur={savePath} />
        <small>{cs.xmlPathHelp}</small>
      </label>
      <div className="meta">
        {cs.httpUrl}: <code>{url}</code>
      </div>
      <div className="meta">
        {cs.lastWrite}: {w?.last_ok_wall ? new Date(w.last_ok_wall * 1000).toLocaleTimeString("cs-CZ") : cs.never}
        {w?.last_write_ms != null && ` · ${cs.writeMs} ${w.last_write_ms.toFixed(1)} ms`} · {cs.modes[mode]}
      </div>
      <div className="buttons">
        {mode === "live" ? (
          <button onClick={() => api.output("pause")}>{cs.pause}</button>
        ) : (
          <button className="active" onClick={() => api.output("live")}>
            {mode === "test" ? cs.backToLive : cs.resume}
          </button>
        )}
        <button onClick={() => api.clearValues()}>{cs.clearValues}</button>
        <button onClick={() => api.output("test")}>{cs.testData}</button>
        <button onClick={() => api.output("test-clear")}>{cs.testClear}</button>
      </div>
      <details>
        <summary>{cs.xmlPreview}</summary>
        <pre>{content ?? ""}</pre>
      </details>
    </div>
  );
}
