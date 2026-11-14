import { cs } from "./i18n/cs";

const PHRASES = Object.entries(cs.eventDetails).sort((a, b) => b[0].length - a[0].length);

/** Event details from the backend are short English phrases; show them in Czech.
 * Longer phrases first, so "unexpected" isn't translated as "un" + "expected". */
export function translateDetail(detail: string): string {
  let out = detail;
  for (const [en, csText] of PHRASES) out = out.split(en).join(csText);
  return out;
}

export type EventLevel = "change" | "info" | "warn" | "bad";
export type EventFilter = "all" | "change" | "guard" | "warn";

const LEVELS: Record<string, EventLevel> = {
  changed: "change",
  held: "change",
  released: "change",
  cleared: "change",
  guard_ok: "info",
  source_ok: "info",
  rejected: "warn",
  guard_lost: "warn",
  thread_restarted: "warn",
  source_lost: "bad",
  pipeline_stuck: "bad",
  alert: "bad",
  alert_ok: "info",
  locked: "info",
  unlocked: "info",
};

/** How an event is coloured in the log. Unknown kinds are informational. */
export function eventLevel(kind: string): EventLevel {
  return LEVELS[kind] ?? "info";
}

/** Whether an event passes the log filter and the search text (field, value, kind, detail). */
export function eventMatches(
  e: { kind: string; field: string; text: string; detail: string },
  filter: EventFilter,
  search: string,
): boolean {
  const level = eventLevel(e.kind);
  if (filter === "change" && level !== "change") return false;
  if (filter === "guard" && !/^(guard|source)_/.test(e.kind)) return false;
  if (filter === "warn" && level !== "warn" && level !== "bad") return false;
  const q = search.trim().toLowerCase();
  if (!q) return true;
  const kindText = cs.eventKinds[e.kind] ?? e.kind;
  return [e.field, e.text, e.detail, translateDetail(e.detail), kindText].some((s) => s.toLowerCase().includes(q));
}
