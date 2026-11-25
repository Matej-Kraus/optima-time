// Setup helpers (pure, tested): the floorball field template, checking field names against the
// XML vMix already uses, and the "ready for broadcast" checklist.
import type { FieldConfig, LiveState, Profile } from "./api";

/** The usual floorball board (SPEC 5): ids as in the production XML, rectangles where they sit on
 * a typical board. The operator then moves the rectangles onto the real values. */
export const FLOORBALL: FieldConfig[] = [
  { id: "Time", label: "Čas", type: "clock", roi: { x: 0.27, y: 0.03, w: 0.46, h: 0.27 }, enabled: true, tenths: true, style: "no_leading_zero" },
  { id: "period", label: "Třetina", type: "period", roi: { x: 0.45, y: 0.45, w: 0.1, h: 0.16 }, enabled: true },
  { id: "scoreh", label: "Góly domácí", type: "number", roi: { x: 0.04, y: 0.45, w: 0.24, h: 0.25 }, enabled: true, style: "strip_zeros" },
  { id: "scorea", label: "Góly hosté", type: "number", roi: { x: 0.72, y: 0.45, w: 0.24, h: 0.25 }, enabled: true, style: "strip_zeros" },
  { id: "penaltyh1", label: "Trest domácí 1", type: "clock", roi: { x: 0.04, y: 0.73, w: 0.24, h: 0.12 }, enabled: true, blank: "clear", style: "as_is" },
  { id: "penaltyh2", label: "Trest domácí 2", type: "clock", roi: { x: 0.04, y: 0.87, w: 0.24, h: 0.12 }, enabled: true, blank: "clear", style: "as_is" },
  { id: "penaltya1", label: "Trest hosté 1", type: "clock", roi: { x: 0.72, y: 0.73, w: 0.24, h: 0.12 }, enabled: true, blank: "clear", style: "as_is" },
  { id: "penaltya2", label: "Trest hosté 2", type: "clock", roi: { x: 0.72, y: 0.87, w: 0.24, h: 0.12 }, enabled: true, blank: "clear", style: "as_is" },
];

/** Add the template's fields that the profile doesn't have yet (by id, ignoring case). */
export function addTemplate(fields: FieldConfig[], template = FLOORBALL): { fields: FieldConfig[]; added: string[] } {
  const have = new Set(fields.map((f) => f.id.toLowerCase()));
  const missing = template.filter((t) => !have.has(t.id.toLowerCase()));
  return { fields: [...fields, ...missing.map((t) => structuredClone(t))], added: missing.map((t) => t.id) };
}

/** Names of the value elements in an XML file: elements with text only (no child elements),
 * in document order, without duplicates. Works for vMix data source files like <root><Time>…</root>. */
export function xmlLeafNames(text: string): string[] {
  const names: string[] = [];
  const leaf = /<([A-Za-z_][\w.-]*)(?:\s[^<>]*?)?(?:\/>|>[^<]*<\/\1\s*>)/g;
  const body = text.replace(/<\?[\s\S]*?\?>|<!--[\s\S]*?-->/g, "");
  for (const m of body.matchAll(leaf)) if (!names.includes(m[1])) names.push(m[1]);
  return names;
}

export interface NameCheck {
  ok: string[]; // same name in both
  caseOnly: { ours: string; theirs: string }[]; // differ only in upper/lower case: vMix won't match
  missing: string[]; // in vMix's XML, no field here
  extra: string[]; // our fields vMix's XML doesn't have
}

export function compareNames(theirs: string[], ours: string[]): NameCheck {
  const result: NameCheck = { ok: [], caseOnly: [], missing: [], extra: [] };
  const oursLower = new Map(ours.map((o) => [o.toLowerCase(), o]));
  const matched = new Set<string>();
  for (const t of theirs) {
    const o = oursLower.get(t.toLowerCase());
    if (o === undefined) result.missing.push(t);
    else {
      matched.add(o);
      if (o === t) result.ok.push(t);
      else result.caseOnly.push({ ours: o, theirs: t });
    }
  }
  result.extra = ours.filter((o) => !matched.has(o));
  return result;
}

export type ReadyKey = "source" | "fields" | "reading" | "anchors" | "xml" | "test" | "live" | "profile" | "lock";

export interface ReadyItem {
  key: ReadyKey;
  ok: boolean;
  required: boolean; // false: recommended
}

/** The "ready for broadcast" checklist (OPERATOR.md part B), from the profile and the live state. */
export function readiness(profile: Profile, live: LiveState | null): ReadyItem[] {
  const enabled = profile.fields.filter((f) => f.enabled);
  const reading = enabled.every((f) => {
    const s = live?.fields[f.id];
    return s != null && s.status !== "rejected" && s.status !== "stale" && s.read_status !== "invalid" && s.read_status !== "low_confidence";
  });
  const xml = live?.outputs.workers.xml_file;
  return [
    { key: "source", ok: live?.source.state === "ok", required: true },
    { key: "fields", ok: enabled.length > 0, required: true },
    { key: "reading", ok: enabled.length > 0 && reading, required: true },
    { key: "anchors", ok: profile.guard.anchors.length > 0 && live?.guard?.state === "ok", required: true },
    { key: "xml", ok: !!profile.outputs.xml_file.path && xml?.ok === true, required: true },
    { key: "test", ok: live?.last_test_wall != null, required: true },
    { key: "live", ok: live?.outputs.mode === "live", required: true },
    { key: "profile", ok: !!profile.name && profile.name !== "default", required: false },
    { key: "lock", ok: live?.locked === true, required: false },
  ];
}

/** vMix title field names: {Time: "Cas.Text"} <-> "Time=Cas.Text; …". */
export function formatTitleNames(names: Record<string, string>): string {
  return Object.entries(names)
    .map(([k, v]) => `${k}=${v}`)
    .join("; ");
}

/** "Time=Cas.Text; scoreh=Domaci.Text" -> {Time: "Cas.Text", scoreh: "Domaci.Text"}. */
export function parseTitleNames(text: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const part of text.split(/[;\n]/)) {
    const [k, ...rest] = part.split("=");
    const v = rest.join("=").trim();
    if (k.trim() && v) out[k.trim()] = v;
  }
  return out;
}


const PLACEHOLDER = /\{([^{}|]*)/g;

/** Field names a derived-field template uses: "{scoreh} {count:penaltyh1,penaltyh2|map:0=}"
 * -> ["scoreh", "penaltyh1", "penaltyh2"]. "{{" is a literal brace, not a placeholder. */
export function templateFieldNames(template: string): string[] {
  const names: string[] = [];
  for (const m of template.replaceAll("{{", "").matchAll(PLACEHOLDER)) {
    const head = m[1].trim();
    const agg = /^(count|sum):(.*)$/.exec(head);
    for (const n of agg ? agg[2].split(",") : [head]) if (n.trim()) names.push(n.trim());
  }
  return names;
}
