import { useCallback, useState } from "react";
import { api, type LoggedEvent } from "../api";
import { eventLevel, eventMatches, translateDetail, type EventFilter } from "../events";
import { usePoll } from "../hooks";
import { cs } from "../i18n/cs";

const FILTERS: EventFilter[] = ["all", "change", "guard", "warn"];

function Line({ e, compact }: { e: LoggedEvent; compact?: boolean }) {
  const kind = cs.eventKinds[e.kind] ?? e.kind;
  return (
    <div className="event-line">
      <span className="time">{e.wall.slice(11, 19)}</span>
      {!compact && <span className="kind">{kind}</span>}
      <span className="msg">
        {compact && `${kind}: `}
        {e.field && <b>{e.field} </b>}
        {e.text}
      </span>
      <span className="side">{translateDetail(e.detail)}</span>
    </div>
  );
}

/** A few latest events, one line each (Live tab). */
export function CompactEventLog({ limit = 6 }: { limit?: number }) {
  const get = useCallback(() => api.getEvents(limit), [limit]);
  const events = usePoll<LoggedEvent[]>(get, 1000) ?? [];
  if (!events.length) return <p className="dim">{cs.log.empty}</p>;
  return (
    <div className="events">
      {events.map((e) => (
        <div key={e.mono_ns} className={`event compact lvl-${eventLevel(e.kind)}`}>
          <Line e={e} compact />
        </div>
      ))}
    </div>
  );
}

/** The full log: filter by group, search, click an event to see its raw record. */
export function EventLog() {
  const get = useCallback(() => api.getEvents(300), []);
  const events = usePoll<LoggedEvent[]>(get, 1000) ?? [];
  const [filter, setFilter] = useState<EventFilter>("all");
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState<number | null>(null);
  const shown = events.filter((e) => eventMatches(e, filter, search));
  return (
    <div>
      <div className="filters" role="group" aria-label="Filtr">
        {FILTERS.map((f) => (
          <button key={f} className={f === filter ? "on" : undefined} aria-pressed={f === filter} onClick={() => setFilter(f)}>
            {cs.log.filters[f]}
          </button>
        ))}
      </div>
      <input className="search" type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder={cs.log.search} aria-label={cs.log.search} />
      <div className="events">
        {shown.length === 0 && <p className="dim">{cs.log.empty}</p>}
        {shown.map((e) => (
          <div
            key={e.mono_ns}
            className={`event lvl-${eventLevel(e.kind)}`}
            role="button"
            tabIndex={0}
            aria-expanded={open === e.mono_ns}
            onClick={() => setOpen((o) => (o === e.mono_ns ? null : e.mono_ns))}
            onKeyDown={(k) => {
              if (k.key === "Enter" || k.key === " ") {
                k.preventDefault();
                setOpen((o) => (o === e.mono_ns ? null : e.mono_ns));
              }
            }}
          >
            <Line e={e} />
            {open === e.mono_ns && <pre>{JSON.stringify(e, null, 2)}</pre>}
          </div>
        ))}
      </div>
      <div className="log-foot">
        <span>{cs.log.count(shown.length, events.length)}</span>
        <span className="ok">● {cs.log.live}</span>
      </div>
    </div>
  );
}
