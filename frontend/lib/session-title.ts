/** Default titles written when creating a session in each UI locale. */
const DEFAULT_SESSION_TITLES = new Set([
  "新会话", // zh-CN
  "New session", // en
  "新對話", // zh-TW
]);

/**
 * Show the current UI's default label when the stored title is a known
 * "new session" placeholder; otherwise keep the custom title as stored.
 */
export function localizedSessionTitle(
  stored: string | null | undefined,
  localizedDefault: string,
  emptyFallback: string
): string {
  const title = (stored || "").trim();
  if (!title) return emptyFallback;
  if (DEFAULT_SESSION_TITLES.has(title)) return localizedDefault;
  return title;
}
