import { useState } from "react";
import { api, errorText, type LiveState, type Profile } from "../api";
import { cs } from "../i18n/cs";
import { useNow } from "../hooks";
import { compareNames, readiness, xmlLeafNames, type NameCheck, type ReadyItem } from "../setupTools";

/** An item turns red only after it has been failing for `holdS` seconds, so a single unsure
 * read (an animation, a passing player) doesn't make the checklist flicker. */
function useSettled(items: ReadyItem[], holdS = 3): ReadyItem[] {
  const now = useNow(500);
  const [lastOk, setLastOk] = useState<Record<string, number>>({});
  const [at, setAt] = useState(0);
  if (at !== now) {
    setAt(now);
    const next = { ...lastOk };
    for (const i of items) if (i.ok) next[i.key] = now;
    setLastOk(next);
  }
  return items.map((i) => ({ ...i, ok: i.ok || (lastOk[i.key] != null && now - lastOk[i.key] < holdS) }));
}

/** "Ready for broadcast": every point green before the match. */
export function ReadyList({ profile, live }: { profile: Profile; live: LiveState | null }) {
  const items = useSettled(readiness(profile, live));
  const missing = items.filter((i) => i.required && !i.ok).length;
  return (
    <div>
      <p className={missing ? "hint" : "ready-ok"}>{missing ? cs.ready.missing(missing) : cs.ready.allOk}</p>
      <ul className="ready-list">
        {items.map((i) => {
          const [label, hint] = cs.ready.items[i.key];
          return (
            <li key={i.key} className={i.ok ? "ok" : i.required ? "bad" : "warn"}>
              <span className="mark" aria-hidden>
                {i.ok ? "✓" : i.required ? "✗" : "!"}
              </span>
              <span>
                {label}
                {!i.required && <span className="dim"> ({cs.ready.recommended})</span>}
                {!i.ok && <small>{hint}</small>}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** Lock or unlock the setup (the backend refuses setup changes while locked). */
export function LockButton({ live, onError }: { live: LiveState | null; onError: (m: string | null) => void }) {
  const locked = live?.locked === true;
  return (
    <button
      className={locked ? "warn" : "cyan"}
      onClick={async () => {
        if (locked && !window.confirm(cs.lock.unlockConfirm)) return;
        try {
          await api.lock(!locked);
          onError(null);
        } catch (e) {
          onError(errorText(e));
        }
      }}
    >
      {locked ? `🔓 ${cs.lock.unlock}` : `🔒 ${cs.lock.lock}`}
    </button>
  );
}

/** Compare field ids with the XML vMix uses today; offers renaming for case-only differences. */
export function XmlCheck({ ids, onRename }: { ids: string[]; onRename: (from: string, to: string) => void }) {
  const [names, setNames] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const check: NameCheck | null = names ? compareNames(names, ids) : null;
  const allOk = check && !check.caseOnly.length && !check.missing.length && check.ok.length > 0;
  return (
    <div className="xml-check">
      <p className="hint">{cs.xmlCheck.hint}</p>
      <label className="button file-button">
        {cs.xmlCheck.choose}
        <input
          type="file"
          accept=".xml,text/xml,application/xml"
          onChange={async (e) => {
            const file = e.target.files?.[0];
            if (!file) return;
            try {
              setNames(xmlLeafNames(await file.text()));
              setError(null);
            } catch {
              setError(cs.xmlCheck.readError);
            }
          }}
        />
      </label>
      {error && <p className="problem bad">{error}</p>}
      {names && names.length === 0 && <p className="problem bad">{cs.xmlCheck.none}</p>}
      {check && names && names.length > 0 && (
        <ul className="ready-list">
          {allOk && (
            <li className="ok">
              <span className="mark">✓</span>
              <span>{cs.xmlCheck.allOk}</span>
            </li>
          )}
          {check.ok.length > 0 && (
            <li className="ok">
              <span className="mark">✓</span>
              <span>
                {cs.xmlCheck.ok}: <code>{check.ok.join(", ")}</code>
              </span>
            </li>
          )}
          {check.caseOnly.map((c) => (
            <li key={c.ours} className="bad">
              <span className="mark">✗</span>
              <span>
                {cs.xmlCheck.caseOnly}: <code>{c.ours}</code> ≠ <code>{c.theirs}</code>
                <button className="ghost" onClick={() => onRename(c.ours, c.theirs)}>
                  {cs.xmlCheck.rename(c.theirs)}
                </button>
              </span>
            </li>
          ))}
          {check.missing.length > 0 && (
            <li className="warn">
              <span className="mark">!</span>
              <span>
                {cs.xmlCheck.missing}: <code>{check.missing.join(", ")}</code>
              </span>
            </li>
          )}
          {check.extra.length > 0 && (
            <li className="warn">
              <span className="mark">!</span>
              <span>
                {cs.xmlCheck.extra}: <code>{check.extra.join(", ")}</code>
              </span>
            </li>
          )}
        </ul>
      )}
    </div>
  );
}
