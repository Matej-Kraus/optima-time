// The traffic light (SPEC 13.2): source, processing, layout guard, XML writing.
// Every problem is a plain sentence with what to do about it.
import type { LiveState } from "./api";
import { cs } from "./i18n/cs";

export type Level = "ok" | "warn" | "bad" | "off";

export interface Light {
  key: "source" | "processing" | "guard" | "output";
  level: Level;
  label: string;
}

export interface Problem {
  level: "warn" | "bad";
  text: string;
}

export function lights(s: LiveState | null): { lights: Light[]; problems: Problem[] } {
  const problems: Problem[] = [];
  if (!s) {
    return {
      lights: [{ key: "source", level: "bad", label: cs.lights.noBackend }],
      problems: [{ level: "bad", text: cs.problems.noBackend }],
    };
  }
  // source
  let source: Level = "ok";
  if (s.source.state === "none") {
    source = "bad";
    problems.push({ level: "bad", text: s.source.error ? `${cs.problems.sourceError} ${s.source.error}` : cs.problems.noSource });
  } else if (s.source.state === "lost") {
    source = "bad";
    problems.push({ level: "bad", text: cs.problems.sourceLost });
  } else if (s.source.state === "ended") {
    source = "warn";
    problems.push({ level: "warn", text: cs.problems.sourceEnded });
  } else if (s.source.state === "connecting") {
    source = "warn";
  }
  // processing
  let processing: Level = "ok";
  const fps = s.source.fps ?? 0;
  if (source === "ok" && fps > 0 && s.processing_fps < fps * 0.8) {
    processing = "warn";
    problems.push({ level: "warn", text: cs.problems.slow(s.processing_fps, fps) });
  }
  // layout guard
  let guard: Level = "off";
  if (s.guard && s.guard.state !== "off") {
    guard = s.guard.state === "ok" ? "ok" : s.guard.state === "recovering" ? "warn" : "bad";
    if (s.guard.state === "lost") problems.push({ level: "warn", text: cs.problems.guardLost });
  }
  // outputs
  let output: Level = "off";
  const workers = Object.values(s.outputs.workers);
  if (workers.length === 0) {
    problems.push({ level: "warn", text: cs.problems.noOutput });
  }
  for (const w of workers) {
    if (w.ok === false) {
      output = "bad";
      problems.push({ level: "bad", text: `${cs.problems.writeFailed} ${w.message}` });
    } else if (w.slow_writes > 0 && w.message.startsWith("slow")) {
      output = output === "bad" ? output : "warn";
      problems.push({ level: "warn", text: `${cs.problems.writeSlow} (${w.message})` });
    } else if (w.ok) {
      output = output === "off" ? "ok" : output;
    }
  }
  if (s.outputs.mode === "paused") {
    output = "warn";
    problems.push({ level: "warn", text: cs.problems.paused });
  } else if (s.outputs.mode === "test") {
    output = "warn";
    problems.push({ level: "warn", text: cs.problems.testData });
  }
  return {
    lights: [
      { key: "source", level: source, label: cs.lights.source },
      { key: "processing", level: processing, label: `${cs.lights.processing} ${s.processing_fps} ${cs.fps}` },
      { key: "guard", level: guard, label: cs.lights.guard },
      { key: "output", level: output, label: cs.lights.output },
    ],
    problems,
  };
}
