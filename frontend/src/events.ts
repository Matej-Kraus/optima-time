import { cs } from "./i18n/cs";

const PHRASES = Object.entries(cs.eventDetails).sort((a, b) => b[0].length - a[0].length);

/** Event details from the backend are short English phrases; show them in Czech.
 * Longer phrases first, so "unexpected" isn't translated as "un" + "expected". */
export function translateDetail(detail: string): string {
  let out = detail;
  for (const [en, csText] of PHRASES) out = out.split(en).join(csText);
  return out;
}
