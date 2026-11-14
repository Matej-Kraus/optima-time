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
