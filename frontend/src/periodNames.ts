/** "1=1. tretina; 4=predĺženie" <-> {1: "1. tretina", 4: "predĺženie"} (null = invalid text). */
export function parseNames(text: string): Record<string, string> | null {
  const out: Record<string, string> = {};
  for (const part of text.split(";")) {
    if (!part.trim()) continue;
    const m = part.match(/^\s*(\d)\s*=\s*(.+?)\s*$/);
    if (!m) return null;
    out[m[1]] = m[2];
  }
  return out;
}

export function formatNames(names: unknown): string {
  if (!names || typeof names !== "object") return "";
  return Object.entries(names as Record<string, string>)
    .map(([k, v]) => `${k}=${v}`)
    .join("; ");
}
