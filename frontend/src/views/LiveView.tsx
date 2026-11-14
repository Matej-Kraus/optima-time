import { useState } from "react";
import { api, type LiveState, type Profile } from "../api";
import { EventLog } from "../components/EventLog";
import { FieldRows } from "../components/FieldRows";
import { OnAirBoard } from "../components/OnAirBoard";
import { OutputCard } from "../components/OutputCard";
import { Overlay } from "../components/Overlay";
import { useStreamKey } from "../hooks";
import { cs } from "../i18n/cs";

interface Props {
  profile: Profile;
  live: LiveState | null;
  tick: number;
}

/** During a match: what is on air, the output, manual holds. Nothing here moves the setup. */
export function LiveView({ profile, live, tick }: Props) {
  const [details, setDetails] = useState(false);
  const [preview, setPreview] = useState(false);
  const [events, setEvents] = useState(false);
  const [streamKey, reconnect] = useStreamKey(live !== null);
  const hasFrame = live?.frame != null;

  return (
    <div className="live-view">
      <div className="live-top">
        <OnAirBoard fields={profile.fields} live={live} />
        <OutputCard live={live} path={profile.outputs.xml_file.path} />
      </div>

      <section className="values">
        <header className="section-head">
          <h2>{cs.valuesTitle}</h2>
          <button className="link" onClick={() => setDetails((d) => !d)} aria-expanded={details}>
            {details ? cs.hideReadDetails : cs.showReadDetails}
          </button>
        </header>
        <FieldRows fields={profile.fields.filter((f) => f.enabled)} live={live} details={details} tick={tick} />
      </section>

      <div className="toggles">
        <button className="link" onClick={() => setPreview((p) => !p)} aria-expanded={preview}>
          {preview ? cs.hidePreview : cs.showPreview}
        </button>
        <button className="link" onClick={() => setEvents((e) => !e)} aria-expanded={events}>
          {events ? cs.hideEvents : cs.showEvents}
        </button>
      </div>
      {preview && (
        <section className="preview">
          <Overlay src={hasFrame ? api.previewUrl("rectified", streamKey) : null} emptyText={cs.noFrame} onImageError={reconnect}>
            {profile.fields.map((f) => (
              <rect key={f.id} className={`field-rect ${live?.fields[f.id]?.read_status ?? ""}`} x={f.roi.x} y={f.roi.y} width={f.roi.w} height={f.roi.h} />
            ))}
          </Overlay>
        </section>
      )}
      {events && (
        <section>
          <EventLog />
        </section>
      )}
    </div>
  );
}
