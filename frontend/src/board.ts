import type { FieldConfig } from "./api";

export interface BoardLayout {
  clock: FieldConfig | null;
  period: FieldConfig | null;
  home: FieldConfig | null;
  away: FieldConfig | null;
  homePenalties: FieldConfig[];
  awayPenalties: FieldConfig[];
  other: FieldConfig[];
}

const PENALTY = /penalt|trest/i;
const HOME = /(^|[^a-z])(h\d*|home|dom)|h\d*$|domác/i;
const AWAY = /(^|[^a-z])(a\d*|away|host)|a\d*$|host/i;

/** Arrange the profile's fields like a scoreboard: the game clock in the middle, the home score
 * left, away right, penalties under them, the period under the clock. Anything that doesn't fit
 * is listed under the board. Recognised by type and by id/label (Time, scoreh, penaltya1 …). */
export function boardLayout(fields: FieldConfig[]): BoardLayout {
  const enabled = fields.filter((f) => f.enabled);
  const used = new Set<string>();
  const take = (f: FieldConfig | undefined) => {
    if (f) used.add(f.id);
    return f ?? null;
  };
  const text = (f: FieldConfig) => `${f.id} ${f.label}`;
  const clock = take(enabled.find((f) => f.type === "clock" && !PENALTY.test(text(f))));
  const period = take(enabled.find((f) => f.type === "period"));
  const numbers = enabled.filter((f) => f.type === "number");
  const home = take(numbers.find((f) => HOME.test(f.id) || /dom/i.test(f.label)) ?? numbers[0]);
  const away = take(numbers.find((f) => !used.has(f.id) && (AWAY.test(f.id) || /host/i.test(f.label))) ?? numbers.find((f) => !used.has(f.id)));
  const penalties = enabled.filter((f) => f.type === "clock" && PENALTY.test(text(f)));
  const homePenalties = penalties.filter((f) => /h\d*$|dom/i.test(f.id) || /dom/i.test(f.label));
  homePenalties.forEach((f) => used.add(f.id));
  const awayPenalties = penalties.filter((f) => !used.has(f.id));
  awayPenalties.forEach((f) => used.add(f.id));
  return { clock, period, home, away, homePenalties, awayPenalties, other: enabled.filter((f) => !used.has(f.id)) };
}
