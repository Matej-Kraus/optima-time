import type { LiveState } from "../api";
import { lights } from "../status";

export function StatusBar({ live }: { live: LiveState | null }) {
  const { lights: ls, problems } = lights(live);
  return (
    <>
      <span className="lights">
        {ls.map((l) => (
          <span key={l.key} className="light">
            <span className={`dot ${l.level}`} /> {l.label}
          </span>
        ))}
      </span>
      {problems.length > 0 && (
        <div className="problems">
          {problems.map((p, i) => (
            <div key={i} className={`problem ${p.level}`}>
              {p.text}
            </div>
          ))}
        </div>
      )}
    </>
  );
}
