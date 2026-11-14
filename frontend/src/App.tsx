import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorText, type LiveState, type Profile } from "./api";
import { Sidebar, TopBar } from "./components/Shell";
import { Problems } from "./components/StatusBar";
import { usePoll, useTick } from "./hooks";
import { TABS, type SaveState, type Tab } from "./tabs";
import { DiagnosticsView } from "./views/DiagnosticsView";
import { LiveView } from "./views/LiveView";
import { SetupView } from "./views/SetupView";

function tabFromHash(): Tab {
  const t = window.location.hash.slice(1).split("/")[0] as Tab;
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
    <div className="shell">
      <TopBar live={live} tab={tab} saveState={saveState} />
      <Sidebar live={live} profile={profile} />
      <main>
        <Problems live={live} />
        {error && <p className="error-bar">{error}</p>}
        {!profile ? (
          <p className="dim">…</p>
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
          <DiagnosticsView live={live} profile={profile} tick={tick} />
        )}
      </main>
    </div>
  );
}
