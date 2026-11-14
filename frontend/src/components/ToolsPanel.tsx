import { useCallback, useState } from "react";
import { api, errorText, type RecorderStatus } from "../api";
import { usePoll } from "../hooks";
import { cs } from "../i18n/cs";

/** Record a sample (SPEC 13.3) and download the diagnostic bundle. */
export function ToolsPanel() {
  const [seconds, setSeconds] = useState(60);
  const [error, setError] = useState<string | null>(null);
  const get = useCallback(() => api.sampleStatus(), []);
  const status = usePoll<RecorderStatus>(get, 1000);

  return (
    <div className="tools-panel">
      <div className="row">
        <button
          disabled={status?.active}
          onClick={async () => {
            try {
              await api.recordSample(seconds);
              setError(null);
            } catch (e) {
              setError(errorText(e));
            }
          }}
        >
          {status?.active ? cs.tools.recording : cs.tools.record}
        </button>
        <input type="number" min={1} max={1800} value={seconds} onChange={(e) => setSeconds(Number(e.target.value))} />
        {cs.tools.seconds}
      </div>
      {status?.folder && (
        <small>
          {status.active ? cs.tools.recording : cs.tools.recorded} <code>{status.folder}</code> · {status.frames}{" "}
          {cs.tools.frames}
          {status.error && ` · ${status.error}`}
        </small>
      )}
      <a className="button" href={api.diagnosticsUrl} download>
        {cs.tools.diagnostics}
      </a>
      <small>{cs.tools.diagnosticsHelp}</small>
      {error && <div className="problem bad">{error}</div>}
    </div>
  );
}
