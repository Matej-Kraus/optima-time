import { useEffect, useState, type RefObject } from "react";

/** A counter that increases every `ms` milliseconds (to refresh preview images). */
export function useTick(ms: number): number {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), ms);
    return () => clearInterval(id);
  }, [ms]);
  return tick;
}

/** Poll an async function every `ms` milliseconds; keeps the last successful value. */
export function usePoll<T>(fn: () => Promise<T>, ms: number): T | null {
  const [value, setValue] = useState<T | null>(null);
  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    const loop = async () => {
      try {
        const v = await fn();
        if (alive) setValue(v);
      } catch {
        // keep the last value; the status bar shows the source state
      }
      if (alive) timer = setTimeout(loop, ms);
    };
    loop();
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [fn, ms]);
  return value;
}

/** The element's current size, kept up to date with a ResizeObserver. */
export function useElementSize(ref: RefObject<HTMLElement | null>): { width: number; height: number } {
  const [size, setSize] = useState({ width: 0, height: 0 });
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      setSize({ width, height });
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [ref]);
  return size;
}

/** A key for live streams (MJPEG): changes when the backend comes back after an outage, and on
 * demand (e.g. the image reported an error), so a stream that ended reconnects instead of
 * freezing on its last frame. */
export function useStreamKey(online: boolean): [number, () => void] {
  const [key, setKey] = useState(0);
  const [wasOnline, setWasOnline] = useState(online);
  if (online !== wasOnline) {
    setWasOnline(online);
    if (online) setKey((k) => k + 1);
  }
  useEffect(() => {
    const id = setInterval(() => setKey((k) => k + 1), 5 * 60_000); // safety net
    return () => clearInterval(id);
  }, []);
  return [key, () => setTimeout(() => setKey((k) => k + 1), 1000)];
}

/** The current time in seconds, refreshed every `ms` (for "před 3 s" texts). */
export function useNow(ms = 1000): number {
  const [now, setNow] = useState(() => Date.now() / 1000);
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now() / 1000), ms);
    return () => clearInterval(id);
  }, [ms]);
  return now;
}
