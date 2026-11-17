import { useEffect, useRef, useState } from "react";
import { api, NEUTRAL_IMAGE, type ImageConfig, type Profile } from "../api";
import { cs } from "../i18n/cs";

interface Props {
  profile: Profile;
  save: (p: Profile) => void;
  onNotice: (text: string | null) => void;
}

const SLIDERS: { key: keyof ImageConfig; label: string; min: number; max: number; step: number }[] = [
  { key: "brightness", label: cs.image.brightness, min: -100, max: 100, step: 1 },
  { key: "contrast", label: cs.image.contrast, min: 0.2, max: 3, step: 0.05 },
  { key: "gamma", label: cs.image.gamma, min: 0.3, max: 3, step: 0.05 },
  { key: "sharpen", label: cs.image.sharpen, min: 0, max: 3, step: 0.1 },
  { key: "net_removal", label: cs.image.netRemoval, min: 0, max: 6, step: 1 },
];

/** Brightness, contrast, gamma … of the straightened board. After a change the anchors'
 * patterns are taken again from the adjusted picture, so the layout guard keeps matching. */
export function ImagePanel({ profile, save, onNotice }: Props) {
  const img = profile.image ?? NEUTRAL_IMAGE;
  const [draft, setDraft] = useState<ImageConfig>(img);
  const recapture = useRef<ReturnType<typeof setTimeout>>(undefined);
  const anchors = profile.guard.anchors;

  useEffect(() => () => clearTimeout(recapture.current), []);

  const apply = (next: ImageConfig) => {
    setDraft(next);
    save({ ...profile, image: next });
    clearTimeout(recapture.current);
    if (!anchors.length) return;
    // wait until frames with the new settings arrive, then retake each anchor's pattern
    recapture.current = setTimeout(async () => {
      for (const [i, a] of anchors.entries()) await api.updateAnchor(i, a.roi).catch(() => null);
      onNotice(cs.image.anchorsRecaptured);
    }, 1500);
  };

  return (
    <div className="image-panel">
      <p className="hint">{cs.image.hint}</p>
      {SLIDERS.map((s) => (
        <label key={s.key} className="slider">
          <span>
            {s.label} <b className="mono">{String(draft[s.key])}</b>
          </span>
          <input
            type="range"
            min={s.min}
            max={s.max}
            step={s.step}
            value={Number(draft[s.key])}
            onChange={(e) => apply({ ...draft, [s.key]: Number(e.target.value) })}
          />
        </label>
      ))}
      <label className="check">
        <input type="checkbox" checked={draft.invert} onChange={(e) => apply({ ...draft, invert: e.target.checked })} />
        {cs.image.invert}
      </label>
      <button onClick={() => apply({ ...NEUTRAL_IMAGE })}>{cs.image.reset}</button>
    </div>
  );
}
