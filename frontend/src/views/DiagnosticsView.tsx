import type { LiveState } from "../api";
import { EventLog } from "../components/EventLog";
import { ToolsPanel } from "../components/ToolsPanel";
import { cs } from "../i18n/cs";

export function DiagnosticsView({ live }: { live: LiveState | null }) {
  const p = live?.process;
  const t = live?.frame?.timings_ms;
  return (
    <div className="diag-view">
      <section className="panel">
        <h2>{cs.processTitle}</h2>
        {p && <p>{cs.processLine(p.cpu_percent, p.rss_mb, p.threads)}</p>}
        {t && (
          <p className="muted">
            Snímek: {t.total?.toFixed(1)} ms celkem, čtení {t.ocr?.toFixed(1) ?? "0"} ms ({t.ocr_fields ?? 0} polí)
          </p>
        )}
        {live?.source && (
          <p className="muted">
            Zdroj: {live.source.state}
            {live.source.width ? `, ${live.source.width}×${live.source.height} při ${live.source.fps?.toFixed(1)} sn./s` : ""}
            {live.source.dropped ? `, zahozeno ${live.source.dropped}` : ""}
          </p>
        )}
      </section>
      <section className="panel">
        <h2>{cs.toolsPanel}</h2>
        <ToolsPanel />
      </section>
      <section className="panel wide">
        <h2>{cs.eventsPanel}</h2>
        <EventLog />
      </section>
    </div>
  );
}
