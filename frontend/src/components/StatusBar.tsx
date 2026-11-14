import type { LiveState } from "../api";
import { lights } from "../status";

export function StatusLights({ live }: { live: LiveState | null }) {
  const { lights: ls } = lights(live);
  return (
    <ul className="lights" aria-label="Stav">
      {ls.map((l) => (
        <li key={l.key} className={l.level}>
          <span className="dot" aria-hidden /> {l.label}
        </li>
      ))}
    </ul>
  );
}

export function Problems({ live }: { live: LiveState | null }) {
  const { problems } = lights(live);
  if (!problems.length) return null;
  return (
    <div className="problems" role="status">
      {problems.map((p, i) => (
        <p key={i} className={p.level}>
          {p.text}
        </p>
      ))}
    </div>
  );
}
