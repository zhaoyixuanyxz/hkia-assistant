"use client";

import { usePathname } from "@/i18n/navigation";

type Scene = "conversations" | "knowledge" | "market" | "guide" | "auth" | "default";

function resolveScene(path: string): Scene {
  const p = path || "/";
  if (p.includes("/guide")) return "guide";
  if (p.includes("/reference")) return "guide";
  if (
    p.includes("/login") ||
    p.includes("/register") ||
    p === "/" ||
    p.endsWith(`/`)
  )
    return "auth";
  if (p.includes("/conversations")) return "conversations";
  if (p.includes("/knowledge")) return "knowledge";
  if (p.includes("/market")) return "market";
  return "default";
}

const SCENE_CLASSES: Record<Scene, string> = {
  conversations: "ambient-scene-conv",
  knowledge: "ambient-scene-know",
  market: "ambient-scene-mkt",
  guide: "ambient-scene-guide",
  auth: "ambient-scene-auth",
  default: "ambient-scene-default",
};

export function AmbientBackground() {
  const pathname = usePathname();
  const scene = resolveScene(pathname ?? "/");
  return (
    <div
      className={`ambient-root pointer-events-none fixed inset-0 -z-10 overflow-hidden ${SCENE_CLASSES[scene]}`}
      aria-hidden
    >
      <div className="ambient-blob ambient-blob-1 rounded-full blur-3xl" />
      <div className="ambient-blob ambient-blob-2 rounded-full blur-3xl" />
      <div className="ambient-blob ambient-blob-3 rounded-full blur-3xl" />
      <div className="ambient-orb ambient-orb-1" />
      <div className="ambient-orb ambient-orb-2" />
      <div className="ambient-line ambient-line-1" />
      <div className="ambient-line ambient-line-2" />
      <div className="ambient-dots ambient-dots-1" />
      <svg className="ambient-svg" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <pattern
            id="dotGrid"
            width="20"
            height="20"
            patternUnits="userSpaceOnUse"
          >
            <circle cx="1" cy="1" r="1" fill="currentColor" />
          </pattern>
        </defs>
      </svg>
    </div>
  );
}
