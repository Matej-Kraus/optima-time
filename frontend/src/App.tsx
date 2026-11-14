import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorText, type LiveState, type Profile } from "./api";
import { Problems, StatusLights } from "./components/StatusBar";
import { usePoll, useTick } from "./hooks";
import { cs } from "./i18n/cs";
import { DiagnosticsView } from "./views/DiagnosticsView";
import { LiveView } from "./views/LiveView";
import { SetupView } from "./views/SetupView";

type Tab = "live" | "setup" | "diagnostics";
type SaveState = "idle" | "saving" | "saved" | "error";
const TABS: Tab[] = ["live", "setup", "diagnostics"];

function tabFromHash(): Tab {
  const t = window.location.hash.slice(1) as Tab;
  return TABS.includes(t) ? t : "live";
}

export default function App() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [tab, setTab] = useState<Tab>(tabFromHash);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [error, setError] = useState<string | null>(null);
  const tick = useTick(400);
  const getState = useCallback(() => api.getState(), []);
  const live = usePoll<LiveState>(getState, 300);
  const saveTimer = useRef<ReturnType<typeof setTimeout>>(undefined);

  const reloadProfile = useCallback(() => {
    api.getProfile().then(setProfile);
  }, []);

  useEffect(reloadProfile, [reloadProfile]);

  useEffect(() => {
    const onHash = () => setTab(tabFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const save = useCallback((next: Profile) => {
    setProfile(next);
    clearTimeout(saveTimer.current);
    setSaveState("saving");
    saveTimer.current = setTimeout(async () => {
      try {
        setProfile(await api.putProfile(next));
        setSaveState("saved");
        setError(null);
      } catch (e) {
        setSaveState("error");
        setError(errorText(e));
      }
    }, 250);
  }, []);

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo">Optima Time</span>
          {profile && <span className="profile-name">{profile.name}</span>}
        </div>
        <nav className="tabs" aria-label="Sekce">
          {TABS.map((t) => (
            <a key={t} href={`#${t}`} className={t === tab ? "active" : undefined} aria-current={t === tab ? "page" : undefined}>
              {cs.tabs[t]}
            </a>
          ))}
        </nav>
        <StatusLights live={live} />
        <span className={`save ${saveState}`} aria-live="polite">
          {saveState === "saving" ? cs.saving : saveState === "saved" ? cs.saved : saveState === "error" ? cs.saveError : ""}
        </span>
      </header>
      <Problems live={live} />
      {error && <p className="error-bar">{error}</p>}
      <main>
        {!profile ? (
          <p className="muted">…</p>
        ) : tab === "live" ? (
          <LiveView profile={profile} live={live} tick={tick} />
        ) : tab === "setup" ? (
          <SetupView
            profile={profile}
            live={live}
            tick={tick}
            save={save}
            setProfile={setProfile}
            reloadProfile={reloadProfile}
            onError={setError}
          />
        ) : (
          <DiagnosticsView live={live} />
        )}
      </main>
    </div>
  );
}
