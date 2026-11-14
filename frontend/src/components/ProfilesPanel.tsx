import { useCallback, useRef, useState } from "react";
import { api, errorText, type ProfilesList } from "../api";
import { usePoll } from "../hooks";
import { cs } from "../i18n/cs";

/** Profiles (SPEC 13.3): load, save as, export, import. Changes autosave. */
export function ProfilesPanel({ locked, onSwitched }: { locked: boolean; onSwitched: () => void }) {
  const get = useCallback(() => api.getProfiles(), []);
  const list = usePoll<ProfilesList>(get, 3000);
  const [error, setError] = useState<string | null>(null);
  const file = useRef<HTMLInputElement>(null);

  const act = async (fn: () => Promise<unknown>) => {
    try {
      await fn();
      setError(null);
      onSwitched();
    } catch (e) {
      setError(errorText(e));
    }
  };

  return (
    <div className="profiles-panel">
      <div>
        {cs.profiles.current}: <strong>{list?.current.name ?? "…"}</strong>
        <small> · {cs.profiles.autosave}</small>
      </div>
      <div className="row">
        <select
          disabled={locked}
          value=""
          onChange={(e) => e.target.value && act(() => api.loadProfile(e.target.value))}
        >
          <option value="">{cs.profiles.load}…</option>
          {list?.profiles.map((p) => (
            <option key={p.path} value={p.name}>
              {p.name} ({p.modified})
            </option>
          ))}
        </select>
        <button
          disabled={locked}
          onClick={() => {
            const name = window.prompt(cs.profiles.saveAsPrompt);
            if (name) act(() => api.saveProfileAs(name));
          }}
        >
          {cs.profiles.saveAs}
        </button>
        <a className="button" href={api.exportUrl} download>
          {cs.profiles.export}
        </a>
        <button disabled={locked} onClick={() => file.current?.click()}>
          {cs.profiles.import}
        </button>
        <input
          ref={file}
          type="file"
          accept=".json,application/json"
          hidden
          onChange={async (e) => {
            const f = e.target.files?.[0];
            e.target.value = "";
            if (!f) return;
            const name = window.prompt(cs.profiles.importPrompt, f.name.replace(/\.json$/i, ""));
            if (!name) return;
            act(async () => api.importProfile(name, JSON.parse(await f.text())));
          }}
        />
      </div>
      <small>
        {cs.profiles.folder}: <code>{list?.folder}</code>
      </small>
      {error && <div className="problem bad">{error}</div>}
    </div>
  );
}
