import type { GuardHistory } from "./api";

/** "18:42.4" -> ["18:42", ".4"], so the tenths can be drawn smaller and in green. */
export function splitTenths(text: string): [string, string] {
  const m = /^(.*?)([.,]\d)$/.exec(text);
  return m ? [m[1], m[2]] : [text, ""];
}

export const CHART_SECONDS = 24;
/** The chart shows scores from 0.5 to 1; lower ones sit on the bottom edge. */
export const CHART_MIN = 0.5;

export function chartY(score: number, h: number): number {
  const t = (score - CHART_MIN) / (1 - CHART_MIN);
  return (1 - Math.max(0, Math.min(1, t))) * h;
}

/** Polyline paths for the worst anchor score over time; gaps (no score) split the line. */
export function chartPaths(points: GuardHistory["points"], w: number, h: number): string[] {
  const paths: string[] = [];
  let current: string[] = [];
  for (const p of [...points].sort((a, b) => b.ago - a.ago)) {
    if (p.score == null || p.ago > CHART_SECONDS) {
      if (current.length > 1) paths.push(current.join(" "));
      current = [];
      continue;
    }
    const x = w - (p.ago / CHART_SECONDS) * w;
    const y = chartY(p.score, h);
    current.push(`${x.toFixed(1)},${y.toFixed(1)}`);
  }
  if (current.length > 1) paths.push(current.join(" "));
  return paths;
}

