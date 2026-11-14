import type { LiveState } from "../api";
import { lights } from "../status";

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
