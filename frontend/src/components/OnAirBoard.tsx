import { useState } from "react";
import type { FieldConfig, FieldState, LiveState } from "../api";
import { boardLayout } from "../board";
import { splitTenths } from "../display";
import { useNow } from "../hooks";
import { cs } from "../i18n/cs";

/** Visual state of a value: held by hand (dashed), stale (dimmed). */
function mark(s: FieldState | undefined): string {
  return s?.held ? "held-mark" : s?.status === "stale" ? "stale-mark" : "";
}

/** The clock runs when its value changed in the last 1.5 s. */
function useRunning(text: string): boolean {
  const now = useNow(250);
  const [prev, setPrev] = useState(text);
  const [changedAt, setChangedAt] = useState(0);
  if (text !== prev) {
    setPrev(text);
    setChangedAt(now);
  }
  return text !== "" && now - changedAt < 1.5;
}

interface Props {
  fields: FieldConfig[];
  live: LiveState | null;
  onHold: (id: string) => void;
}

/** What vMix gets right now, laid out like the board in the hall. */
export function OnAirBoard({ fields, live, onHold }: Props) {
  const b = boardLayout(fields);
  const st = (f: FieldConfig | null) => (f ? live?.fields[f.id] : undefined);
  const clock = st(b.clock);
  const clockText = clock?.text ?? "";
  const running = useRunning(clockText);
  const [main, tenths] = splitTenths(clockText);
  const conf = clock?.confidence;

  const team = (f: FieldConfig | null, away: boolean) => {
    const s = st(f);
    return (
      <div className={`team ${away ? "away" : ""}`} title={f?.id}>
        <div>
          <div className="team-side">{away ? cs.away : cs.home}</div>
          <div className="label-mono">{f?.id ?? "—"}</div>
        </div>
        <div className={`team-score ${mark(s)}`}>{s?.text || "—"}</div>
      </div>
    );
  };

  const penalties = (list: FieldConfig[], away: boolean) => (
    <div className="penalty-col">
      {list.map((f, i) => {
        const s = st(f);
        return (
          <div key={f.id} className={`penalty ${s?.text ? "" : "empty"}`} title={f.id}>
            <span className={`tag ${away ? "away" : ""}`}>
              {away ? "H" : "D"}
              {i + 1}
            </span>
            <span className="label-mono">{f.id}</span>
            <span className={`ptime ${mark(s)}`}>{s?.text || cs.live.noPenalty}</span>
          </div>
        );
      })}
    </div>
  );

  return (
    <>
      <div className="onair-top">
        <div className="tile">
          <div className="tile-head">
            <span className="label-mono">{b.clock?.id ?? "—"}</span>
            {b.clock && (
              <span className={`label-mono ${running ? "running" : "stopped"}`}>
                ● {running ? cs.live.clockRunning : cs.live.clockStopped}
              </span>
            )}
          </div>
          <div className="time-row">
            <div className={`big-time ${mark(clock)}`}>
              {main || "—"}
              {tenths && <span className="tenths">{tenths}</span>}
            </div>
            {b.clock && (
              <div className="conf">
                <span className="label-mono">{cs.live.readConfidence}</span>
                <span className={`conf-value ${conf != null && conf < 0.8 ? "low" : ""}`}>
                  {conf != null ? `${Math.round(conf * 100)} %` : "—"}
                </span>
                <button className="warn" onClick={() => onHold(b.clock!.id)}>
                  {cs.live.holdClock}
                </button>
              </div>
            )}
          </div>
        </div>
        <div className="tile">
          <span className="label-mono">{cs.periodLabel}</span>
          <div className={`big-period ${mark(st(b.period))}`}>{st(b.period)?.text || "—"}</div>
          <span className="label-mono">{b.period?.id ?? ""}</span>
        </div>
      </div>
      <div className="teams">
        {team(b.home, false)}
        {team(b.away, true)}
      </div>
      {(b.homePenalties.length > 0 || b.awayPenalties.length > 0) && (
        <div className="penalty-row">
          {penalties(b.homePenalties, false)}
          {penalties(b.awayPenalties, true)}
        </div>
      )}
      {b.other.length > 0 && (
        <div className="penalty-row">
          {b.other.map((f) => (
            <div key={f.id} className="penalty">
              <span className="label-mono">{f.label || f.id}</span>
              <span className={`ptime ${mark(st(f))}`}>{st(f)?.text || "—"}</span>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
