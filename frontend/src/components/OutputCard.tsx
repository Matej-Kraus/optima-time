import { api, type LiveState } from "../api";
import { useNow } from "../hooks";
import { cs } from "../i18n/cs";

/** Where the values go, whether writing works, and the output controls used during a match. */
export function OutputCard({ live, path }: { live: LiveState | null; path: string }) {
  const mode = live?.outputs.mode ?? "live";
  const w = live?.outputs.workers.xml_file;
  const now = useNow();
  const ago = w?.last_ok_wall ? Math.max(0, now - w.last_ok_wall) : null;
  const file = path.split(/[\\/]/).pop();
  return (
    <section className="output-card">
      <h2>{cs.outputTitle}</h2>
      {path ? (
        <p className="target" title={path}>
          {cs.writesTo} <strong>{file}</strong>
          <br />
          <span className={`mode ${mode}`}>{cs.modes[mode]}</span>
          {ago !== null && <> · {cs.lastWrite.toLowerCase()} {cs.agoSeconds(ago)}</>}
        </p>
      ) : (
        <p className="target warn">{cs.noOutputYet}</p>
      )}
      <div className="actions">
        {mode === "live" ? (
          <button onClick={() => api.output("pause")}>{cs.pause}</button>
        ) : (
          <button className="primary" onClick={() => api.output("live")}>
            {mode === "test" ? cs.backToLive : cs.resume}
          </button>
        )}
        <button onClick={() => api.output("test")}>{cs.testData}</button>
        <button onClick={() => api.output("test-clear")}>{cs.testClear}</button>
        <button className="quiet" onClick={() => api.clearValues()}>
          {cs.clearValues}
        </button>
      </div>
    </section>
  );
}
