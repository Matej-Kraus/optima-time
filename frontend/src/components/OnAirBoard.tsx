import type { FieldConfig, LiveState } from "../api";
import { boardLayout } from "../board";
import { cs } from "../i18n/cs";

/** What vMix gets right now, laid out like the board in the hall. */
export function OnAirBoard({ fields, live }: { fields: FieldConfig[]; live: LiveState | null }) {
  const b = boardLayout(fields);
  const cell = (f: FieldConfig | null, cls: string) => {
    if (!f) return <div className={`cell ${cls} absent`} />;
    const s = live?.fields[f.id];
    const text = s?.text ?? "";
    const state = s?.held ? "held" : s?.status === "stale" ? "stale" : s?.status === "pending" ? "pending" : "";
    return (
      <div className={`cell ${cls} ${state} ${text ? "" : "empty"}`} title={`${f.id}${f.label ? ` (${f.label})` : ""}`}>
        {text || "—"}
      </div>
    );
  };
  return (
    <section className="onair" aria-label={cs.onAir}>
      <header>
        <h2>{cs.onAir}</h2>
        <p>{cs.onAirHint}</p>
      </header>
      <div className="board">
        <div className="team">
          <span className="team-name">{cs.home}</span>
          {cell(b.home, "score")}
          <div className="penalties">{b.homePenalties.map((f) => <div key={f.id}>{cell(f, "penalty")}</div>)}</div>
        </div>
        <div className="center">
          {cell(b.clock, "clock")}
          {b.period && (
            <div className="period">
              <span>{cs.periodLabel}</span>
              {cell(b.period, "period-value")}
            </div>
          )}
        </div>
        <div className="team">
          <span className="team-name">{cs.away}</span>
          {cell(b.away, "score")}
          <div className="penalties">{b.awayPenalties.map((f) => <div key={f.id}>{cell(f, "penalty")}</div>)}</div>
        </div>
      </div>
      {b.other.length > 0 && (
        <div className="other">
          {b.other.map((f) => (
            <div key={f.id}>
              <span>{f.label || f.id}</span>
              {cell(f, "other-value")}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
