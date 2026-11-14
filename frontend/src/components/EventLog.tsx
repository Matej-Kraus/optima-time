import { useCallback } from "react";
import { api, type LoggedEvent } from "../api";
import { translateDetail } from "../events";
import { usePoll } from "../hooks";
import { cs } from "../i18n/cs";

export function EventLog() {
  const get = useCallback(() => api.getEvents(60), []);
  const events = usePoll<LoggedEvent[]>(get, 1000) ?? [];
  return (
    <div className="events">
      {events.map((e) => (
        <div key={e.mono_ns} className={`event ${e.kind}`}>
          <span className="time">{e.wall.slice(11, 19)}</span>
          <span className="kind">{cs.eventKinds[e.kind] ?? e.kind}</span>
          <span className="fid">{e.field}</span>
          <span className="text">{e.text}</span>
          <span className="detail">{translateDetail(e.detail)}</span>
        </div>
      ))}
    </div>
  );
}
