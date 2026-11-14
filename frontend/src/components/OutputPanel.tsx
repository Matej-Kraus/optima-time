import { useCallback, useState } from "react";
import { api, type Profile } from "../api";
import { usePoll } from "../hooks";
import { cs } from "../i18n/cs";

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
