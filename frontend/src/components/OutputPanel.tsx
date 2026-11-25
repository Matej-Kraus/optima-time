import { useCallback, useState } from "react";
import { api, type Profile } from "../api";
import { usePoll } from "../hooks";
import { cs } from "../i18n/cs";
import { formatTitleNames, parseTitleNames } from "../setupTools";

interface Props {
  profile: Profile;
  locked: boolean;
  onProfile: (p: Profile) => void;
}

export function OutputPanel({ profile, locked, onProfile }: Props) {
  const xml = profile.outputs.xml_file;
  const [path, setPath] = useState(xml.path); // the parent remounts this panel when the saved path changes
  const getXml = useCallback(() => api.getXml(), []);
  const content = usePoll(getXml, 1000);
  const url = `${window.location.origin}/data/values.xml`;

  const savePath = () => {
    if (path === xml.path) return;
    const next = structuredClone(profile);
    next.outputs.xml_file.path = path;
    onProfile(next);
  };

  return (
    <div className="output-panel">
      <label>
        {cs.xmlPath}
        <input value={path} disabled={locked} onChange={(e) => setPath(e.target.value)} onBlur={savePath} />
        <small>{cs.xmlPathHelp}</small>
      </label>
      <label>
        {cs.xmlNames}
        <input
          defaultValue={formatTitleNames(xml.names ?? {})}
          disabled={locked}
          placeholder="Time=Clock; scoreh=HomeScore"
          onBlur={(e) => {
            const names = parseTitleNames(e.target.value);
            for (const [field, name] of Object.entries(names)) if (field === name) delete names[field];
            if (JSON.stringify(names) === JSON.stringify(xml.names ?? {})) return;
            const next = structuredClone(profile);
            next.outputs.xml_file.names = names;
            onProfile(next);
          }}
        />
        <small>{cs.xmlNamesHelp}</small>
      </label>
      <label>
        {cs.delay}
        <input
          type="number"
          min={0}
          max={10000}
          step={20}
          defaultValue={profile.outputs.delay_ms ?? 0}
          disabled={locked}
          onBlur={(e) => {
            const ms = Math.max(0, Math.min(10000, Math.round(Number(e.target.value) || 0)));
            if (ms === (profile.outputs.delay_ms ?? 0)) return;
            const next = structuredClone(profile);
            next.outputs.delay_ms = ms;
            onProfile(next);
          }}
        />
        <small>{cs.delayHelp}</small>
      </label>
      <div className="meta">
        {cs.httpUrl}: <code>{url}</code>
      </div>
      <details>
        <summary>{cs.xmlPreview}</summary>
        <pre>{content ?? ""}</pre>
      </details>
      <p className="hint">{cs.vmixHint}</p>
    </div>
  );
}
