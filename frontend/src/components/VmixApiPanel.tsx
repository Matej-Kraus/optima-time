import { useState } from "react";
import type { LiveState, Profile, VmixAction, VmixApiConfig, VmixCommand } from "../api";
import { useNow } from "../hooks";
import { cs } from "../i18n/cs";
import { formatTitleNames, parseTitleNames } from "../setupTools";

interface Props {
  profile: Profile;
  live: LiveState | null;
  locked: boolean;
  onProfile: (p: Profile) => void;
}

const DEFAULT: VmixApiConfig = { enabled: false, host: "127.0.0.1", port: 8099, input: "", suffix: ".Text", names: {}, commands: [] };
const ACTIONS = Object.keys(cs.vmixApi.actions) as VmixAction[];

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
  const commands = draft.commands ?? [];
  const valueIds = [...profile.fields.map((f) => f.id), ...(profile.derived ?? []).map((d) => d.id)];
  const setCommand = (i: number, patch: Partial<VmixCommand>) =>
    save({ commands: commands.map((c, j) => (j === i ? { ...c, ...patch } : c)) });
  const addCommand = () =>
    save({
      commands: [
        ...commands,
        { value: valueIds[0] ?? "", action: "image_visible", target: "Pozadi.Source", input: "", enabled: true },
      ],
    });
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
      <div className="vmix-commands">
        <strong>{cs.vmixApi.commandsTitle}</strong>
        <p className="hint">{cs.vmixApi.commandsHint}</p>
        {commands.length > 0 && (
          <ul className="vmix-command-list">
            {commands.map((c, i) => (
              <li key={i}>
                <input type="checkbox" checked={c.enabled} disabled={locked} aria-label={cs.enabled} onChange={(e) => setCommand(i, { enabled: e.target.checked })} />
                <select value={c.value} disabled={locked} aria-label={cs.vmixApi.commandValue} onChange={(e) => setCommand(i, { value: e.target.value })}>
                  {!valueIds.includes(c.value) && <option value={c.value}>{c.value}</option>}
                  {valueIds.map((id) => (
                    <option key={id} value={id}>
                      {id}
                    </option>
                  ))}
                </select>
                <select value={c.action} disabled={locked} aria-label={cs.vmixApi.commandAction} onChange={(e) => setCommand(i, { action: e.target.value as VmixAction })}>
                  {ACTIONS.map((a) => (
                    <option key={a} value={a}>
                      {cs.vmixApi.actions[a]}
                    </option>
                  ))}
                </select>
                <input
                  className="mono"
                  defaultValue={c.target}
                  disabled={locked}
                  aria-label={cs.vmixApi.commandTarget}
                  placeholder={cs.vmixApi.commandTarget}
                  onBlur={(e) => e.target.value.trim() && e.target.value.trim() !== c.target && setCommand(i, { target: e.target.value.trim() })}
                />
                <input
                  defaultValue={c.input}
                  disabled={locked}
                  aria-label={cs.vmixApi.commandInput}
                  placeholder={cs.vmixApi.commandInput}
                  onBlur={(e) => e.target.value.trim() !== c.input && setCommand(i, { input: e.target.value.trim() })}
                />
                <button
                  className="ghost remove"
                  disabled={locked}
                  aria-label={cs.vmixApi.removeCommand}
                  title={cs.vmixApi.removeCommand}
                  onClick={() => save({ commands: commands.filter((_, j) => j !== i) })}
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        )}
        <div className="row">
          <button disabled={locked || valueIds.length === 0} onClick={addCommand}>
            {cs.vmixApi.addCommand}
          </button>
        </div>
      </div>
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
