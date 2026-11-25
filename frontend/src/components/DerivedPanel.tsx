import { FIELD_ID_PATTERN, type LiveState, type Profile } from "../api";
import { cs } from "../i18n/cs";
import { templateFieldNames } from "../setupTools";

interface Props {
  profile: Profile;
  live: LiveState | null;
  locked: boolean;
  onProfile: (p: Profile) => void;
}

/** Extra XML columns made from the read values by a template ("{scoreh} : {scorea}"). The
 * backend checks every template; a bad one comes back as an error and isn't saved. */
export function DerivedPanel({ profile, live, locked, onProfile }: Props) {
  const derived = profile.derived ?? [];
  const fieldIds = new Set(profile.fields.map((f) => f.id));
  const taken = new Set([...fieldIds, ...derived.map((d) => d.id)]);

  const update = (i: number, patch: Partial<Profile["derived"][number]>) => {
    const next = structuredClone(profile);
    next.derived = derived.map((d, j) => (j === i ? { ...d, ...patch } : d));
    onProfile(next);
  };
  const add = (id: string, template: string) => {
    let name = id;
    for (let n = 2; taken.has(name); n++) name = `${id}${n}`;
    onProfile({ ...structuredClone(profile), derived: [...derived, { id: name, template, enabled: true }] });
  };
  // offer only examples whose fields exist in this profile
  const examples = cs.derived.examples.filter((ex) => templateFieldNames(ex.template).every((n) => fieldIds.has(n)));

  return (
    <div className="derived-panel">
      <p className="hint">{cs.derived.hint}</p>
      {derived.length > 0 && (
        <ul className="derived-list">
          {derived.map((d, i) => (
            <li key={`${i}-${d.id}`}>
              <input type="checkbox" checked={d.enabled} disabled={locked} onChange={(e) => update(i, { enabled: e.target.checked })} aria-label={cs.enabled} />
              <input
                className={FIELD_ID_PATTERN.test(d.id) ? "did" : "did invalid"}
                defaultValue={d.id}
                disabled={locked}
                aria-label={cs.derived.id}
                onBlur={(e) => e.target.value !== d.id && update(i, { id: e.target.value.trim() })}
              />
              <input
                className="tpl mono"
                defaultValue={d.template}
                disabled={locked}
                aria-label={cs.derived.template}
                onBlur={(e) => e.target.value !== d.template && update(i, { template: e.target.value })}
              />
              <span className="result mono" title={cs.derived.result}>
                {d.enabled ? (live?.derived?.[d.id] ?? "") || "∅" : "—"}
              </span>
              <button className="ghost" disabled={locked} onClick={() => onProfile({ ...structuredClone(profile), derived: derived.filter((_, j) => j !== i) })}>
                {cs.derived.remove}
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="row">
        <button disabled={locked} onClick={() => add("pole", "")}>
          {cs.derived.add}
        </button>
      </div>
      {examples.length > 0 && (
        <div className="row examples">
          <span className="dim">{cs.derived.examplesTitle}</span>
          {examples.map((ex) => (
            <button key={ex.id} className="ghost" disabled={locked} onClick={() => add(ex.id, ex.template)}>
              + {ex.label}
            </button>
          ))}
        </div>
      )}
      <details>
        <summary>{cs.derived.template}: nápověda</summary>
        <p className="hint mono">{cs.derived.help}</p>
      </details>
    </div>
  );
}
