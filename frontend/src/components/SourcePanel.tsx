import { useState } from "react";
import { api, errorText, type Profile, type SourceConfig, type SourcesList } from "../api";
import { cs } from "../i18n/cs";

interface Props {
  profile: Profile;
  locked: boolean;
  onProfile: (p: Profile) => void;
}

/** Choose the video source: a file, an NDI source (vMix output) or a capture device. */
export function SourcePanel({ profile, locked, onProfile }: Props) {
  const src = profile.source;
  const [list, setList] = useState<SourcesList | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const set = (patch: Partial<SourceConfig>) => {
    const next = structuredClone(profile);
    next.source = { ...next.source, ...patch };
    onProfile(next);
  };

  const refresh = async () => {
    setBusy(true);
    try {
      setList(await api.getSources());
      setError(null);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="source-panel">
      <label>
        {cs.source.type}
        <select
          value={src.type}
          disabled={locked}
          onChange={(e) => {
            set({ type: e.target.value as SourceConfig["type"] });
            if (e.target.value === "ndi" || e.target.value === "device") refresh();
          }}
        >
          {Object.entries(cs.source.types).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
      </label>

      {src.type === "file" && (
        <label>
          {cs.source.path}
          <input defaultValue={src.path} disabled={locked} onBlur={(e) => e.target.value !== src.path && set({ path: e.target.value })} />
        </label>
      )}

      {src.type === "stream" && (
        <label>
          {cs.source.url}
          <input
            defaultValue={src.url}
            disabled={locked}
            placeholder="srt://192.168.1.20:9000?mode=caller"
            onBlur={(e) => e.target.value !== src.url && set({ url: e.target.value.trim() })}
          />
          <small>{cs.source.urlHelp}</small>
        </label>
      )}

      {src.type === "ndi" && (
        <label>
          {cs.source.ndiName}
          <div className="row">
            <select value={src.ndi_name} disabled={locked} onChange={(e) => set({ ndi_name: e.target.value })}>
              {src.ndi_name && <option value={src.ndi_name}>{src.ndi_name}</option>}
              {(list?.ndi ?? []).filter((n) => n !== src.ndi_name).map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
              {!src.ndi_name && (list?.ndi?.length ?? 0) === 0 && <option value="">{cs.source.none}</option>}
            </select>
            <button onClick={refresh} disabled={busy || locked}>
              {busy ? cs.source.searching : cs.source.refresh}
            </button>
          </div>
          <small>{list?.ndi_error ?? cs.source.ndiHelp}</small>
        </label>
      )}

      {src.type === "device" && (
        <>
          <label>
            {cs.source.device}
            <div className="row">
              <select
                value={String(src.device_index)}
                disabled={locked}
                onChange={(e) => {
                  const d = list?.devices.find((x) => x.index === Number(e.target.value));
                  if (d) set({ device_index: d.index, device_name: d.name });
                }}
              >
                {src.device_index >= 0 && (
                  <option value={String(src.device_index)}>{src.device_name || src.device_index}</option>
                )}
                {(list?.devices ?? [])
                  .filter((d) => d.index !== src.device_index)
                  .map((d) => (
                    <option key={d.index} value={String(d.index)}>
                      {d.name} ({d.backend})
                    </option>
                  ))}
                {src.device_index < 0 && (list?.devices.length ?? 0) === 0 && <option value="-1">{cs.source.none}</option>}
              </select>
              <button onClick={refresh} disabled={busy || locked}>
                {busy ? cs.source.searching : cs.source.refresh}
              </button>
            </div>
          </label>
          <div className="row">
            <label>
              {cs.source.resolution}
              <div className="row">
                <input type="number" defaultValue={src.width} disabled={locked} onBlur={(e) => set({ width: Number(e.target.value) })} />
                ×
                <input type="number" defaultValue={src.height} disabled={locked} onBlur={(e) => set({ height: Number(e.target.value) })} />
              </div>
            </label>
            <label>
              {cs.source.fps}
              <input type="number" defaultValue={src.fps} disabled={locked} onBlur={(e) => set({ fps: Number(e.target.value) })} />
            </label>
            <label>
              {cs.source.fourcc}
              <input defaultValue={src.fourcc} maxLength={4} disabled={locked} onBlur={(e) => set({ fourcc: e.target.value })} />
            </label>
          </div>
        </>
      )}

      <label>
        {cs.source.deinterlace}
        <select
          value={src.deinterlace}
          disabled={locked}
          onChange={(e) => set({ deinterlace: e.target.value as SourceConfig["deinterlace"] })}
        >
          {Object.entries(cs.source.deinterlaceModes).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
      </label>
      {error && <div className="problem bad">{error}</div>}
    </div>
  );
}
