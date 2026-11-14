import type { Profile } from "../api";
import { cs } from "../i18n/cs";

interface Props {
  profile: Profile;
  locked: boolean;
  onProfile: (p: Profile) => void;
}

/** Profile-wide settings that rarely change: rotation, blending, guard, detection, XML format. */
export function AdvancedPanel({ profile, locked, onProfile }: Props) {
  const edit = (fn: (p: Profile) => void) => {
    const next = structuredClone(profile);
    fn(next);
    onProfile(next);
  };
  const num = (label: string, value: number, step: number, apply: (p: Profile, v: number) => void) => (
    <label>
      {label}
      <input
        type="number"
        step={step}
        defaultValue={value}
        disabled={locked}
        onBlur={(e) => {
          const v = Number(e.target.value);
          if (e.target.value !== "" && Number.isFinite(v) && v !== value) edit((p) => apply(p, v));
        }}
      />
    </label>
  );
  return (
    <details className="advanced-panel">
      <summary>{cs.advancedPanel}</summary>
      <p className="hint">{cs.advancedHint}</p>
      <div className="grid">
        <label>
          {cs.rotate}
          <select
            value={String(profile.geometry.rotate)}
            disabled={locked}
            onChange={(e) => edit((p) => (p.geometry.rotate = Number(e.target.value)))}
          >
            {Object.entries(cs.rotations).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </label>
        {num(cs.blendFrames, profile.preprocess.blend_frames, 1, (p, v) => (p.preprocess.blend_frames = v))}
        <label>
          {cs.blendMode}
          <select
            value={profile.preprocess.blend_mode}
            disabled={locked}
            onChange={(e) => edit((p) => (p.preprocess.blend_mode = e.target.value as "max" | "mean"))}
          >
            {Object.entries(cs.blendModes).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
          <small>{cs.blendHint}</small>
        </label>
        {num(cs.guardThreshold, profile.guard.threshold, 0.05, (p, v) => (p.guard.threshold = v))}
        {num(cs.guardRecover, profile.guard.recover_frames, 1, (p, v) => (p.guard.recover_frames = v))}
        <label className="check">
          <input
            type="checkbox"
            checked={profile.detection.enabled}
            disabled={locked}
            onChange={(e) => edit((p) => (p.detection.enabled = e.target.checked))}
          />
          {cs.detectionEnabled}
        </label>
        {num(cs.detectionThreshold, profile.detection.threshold, 0.01, (p, v) => (p.detection.threshold = v))}
        {num(cs.detectionMaxAge, profile.detection.max_age_ms, 100, (p, v) => (p.detection.max_age_ms = v))}
        <label>
          {cs.newline}
          <select
            value={profile.outputs.xml_file.newline}
            disabled={locked}
            onChange={(e) => edit((p) => (p.outputs.xml_file.newline = e.target.value))}
          >
            {Object.entries(cs.newlines).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={profile.outputs.xml_file.clear_on_exit}
            disabled={locked}
            onChange={(e) => edit((p) => (p.outputs.xml_file.clear_on_exit = e.target.checked))}
          />
          {cs.clearOnExit}
        </label>
      </div>
    </details>
  );
}
