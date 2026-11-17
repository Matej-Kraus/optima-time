import { useState } from "react";
import type { LiveState, Profile, VmixApiConfig } from "../api";
import { useNow } from "../hooks";
import { cs } from "../i18n/cs";
import { formatTitleNames, parseTitleNames } from "../setupTools";

interface Props {
  profile: Profile;
  live: LiveState | null;
  locked: boolean;
  onProfile: (p: Profile) => void;
}

const DEFAULT: VmixApiConfig = { enabled: false, host: "127.0.0.1", port: 8099, input: "", suffix: ".Text", names: {} };

/** Push values straight into a vMix title over the TCP API, next to the XML file. */
export function VmixApiPanel({ profile, live, locked, onProfile }: Props) {
  const cfg = profile.outputs.vmix_api ?? DEFAULT;
  const [draft, setDraft] = useState(cfg);
  const status = live?.outputs.workers.vmix_api;
  const now = useNow();
  const save = (patch: Partial<VmixApiConfig>) => {
    const next = { ...draft, ...patch };
    setDraft(next);
    if (JSON.stringify(next) === JSON.stringify(cfg)) return;
    const p = structuredClone(profile);
    p.outputs.vmix_api = next;
    onProfile(p);
  };
  const problems = Object.entries(status?.problems ?? {});
  return (
    <div className="vmix-panel">
      <p className="hint">{cs.vmixApi.hint}</p>
      <label className="check">
        <input type="checkbox" checked={draft.enabled} disabled={locked} onChange={(e) => save({ enabled: e.target.checked })} />
        {cs.vmixApi.enabled}
      </label>
      <div className="row">
        <label className="grow">
          {cs.vmixApi.host}
          <input defaultValue={draft.host} disabled={locked} onBlur={(e) => save({ host: e.target.value.trim() || "127.0.0.1" })} />
        </label>
        <label>
          {cs.vmixApi.port}
          <input type="number" defaultValue={draft.port} disabled={locked} onBlur={(e) => save({ port: Number(e.target.value) || 8099 })} />
        </label>
      </div>
      <label>
        {cs.vmixApi.input}
        <input defaultValue={draft.input} disabled={locked} placeholder="Skore" onBlur={(e) => save({ input: e.target.value.trim() })} />
      </label>
      <label>
        {cs.vmixApi.suffix}
        <input defaultValue={draft.suffix} disabled={locked} onBlur={(e) => save({ suffix: e.target.value.trim() })} />
        <small>{cs.vmixApi.suffixHelp}</small>
      </label>
      <label>
        {cs.vmixApi.names}
        <input defaultValue={formatTitleNames(draft.names)} disabled={locked} onBlur={(e) => save({ names: parseTitleNames(e.target.value) })} />
        <small>{cs.vmixApi.namesHelp}</small>
      </label>
      {draft.enabled && status && (
        <p className={status.ok ? "ready-ok" : "problem bad"}>
          {status.ok
            ? `${cs.vmixApi.connected} ${cs.agoSeconds(status.last_ok_wall ? Math.max(0, now - status.last_ok_wall) : 0)}`
            : `${cs.vmixApi.notConnected}: ${status.message}`}
        </p>
      )}
      {problems.length > 0 && (
        <p className="problem bad">
          {cs.vmixApi.problems}: {problems.map(([k, v]) => `${k} (${v})`).join(", ")}
        </p>
      )}
    </div>
  );
}
