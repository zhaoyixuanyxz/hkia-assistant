"use client";

import { Libre_Baskerville, Outfit } from "next/font/google";
import { useLocale, useTranslations } from "next-intl";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, apiFetch } from "@/lib/api";
import { splitAssistantMessage } from "@/lib/chat-disclaimer";
import { getToken } from "@/lib/auth";
import type { ConversationDetail, Message } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Link, useRouter } from "@/i18n/navigation";

const outfit = Outfit({
  subsets: ["latin"],
  variable: "--font-chat-ui",
  weight: ["400", "500", "600", "700"],
});

const libre = Libre_Baskerville({
  subsets: ["latin"],
  variable: "--font-chat-display",
  weight: ["400", "700"],
});

export default function ChatPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const locale = useLocale();
  const t = useTranslations("chat");
  const id = Number(params.id);
  const [detail, setDetail] = useState<ConversationDetail | null>(null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editDraft, setEditDraft] = useState("");
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const load = useCallback(async () => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    try {
      const d = await apiFetch<ConversationDetail>(`/conversations/${id}`);
      setDetail(d);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) router.replace("/login");
      else setError(t("loadFail"));
    }
  }, [id, router, t]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [detail?.messages?.length, loading]);

  async function send() {
    const text = input.trim();
    if (!text || loading) return;
    setError(null);
    setLoading(true);
    try {
      await apiFetch<Message[]>(`/conversations/${id}/messages`, {
        method: "POST",
        body: JSON.stringify({ content: text, locale }),
      });
      setInput("");
      await load();
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) router.replace("/login");
      else setError(t("sendFail"));
    } finally {
      setLoading(false);
    }
  }

  function startEdit(m: Message) {
    setEditingId(m.id);
    setEditDraft(m.content);
    setError(null);
  }

  function cancelEdit() {
    setEditingId(null);
    setEditDraft("");
  }

  async function saveEdit() {
    const text = editDraft.trim();
    if (!text || loading || editingId == null) return;
    setError(null);
    setLoading(true);
    try {
      await apiFetch<Message[]>(
        `/conversations/${id}/messages/${editingId}`,
        {
          method: "PATCH",
          body: JSON.stringify({ content: text, locale }),
        },
      );
      cancelEdit();
      await load();
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) router.replace("/login");
      else setError(t("editFail"));
    } finally {
      setLoading(false);
    }
  }

  const roundCount =
    detail?.messages.filter((m) => m.role === "user").length ?? 0;

  return (
    <div
      className={cn(
        "relative flex min-h-0 flex-1 flex-col overflow-hidden text-foreground",
        outfit.variable,
        libre.variable,
      )}
      style={{
        fontFamily: "var(--font-chat-ui), var(--font-sans), system-ui, sans-serif",
      }}
    >
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 overflow-hidden"
      >
        <div className="absolute -left-1/4 top-0 h-[min(80%,520px)] w-[min(120%,720px)] rounded-full bg-[radial-gradient(ellipse_at_center,_oklch(0.94_0.04_85/0.55),_transparent_65%)] blur-3xl" />
        <div className="absolute -right-1/5 bottom-0 h-[min(70%,480px)] w-[min(100%,640px)] rounded-full bg-[radial-gradient(ellipse_at_center,_oklch(0.93_0.035_238/0.35),_transparent_68%)] blur-3xl" />
        <div className="absolute inset-0 bg-[linear-gradient(165deg,_oklch(1_0_98)_0%,_oklch(0.985_0.012_92)_42%,_oklch(0.965_0.022_88)_100%)]" />
        <div className="absolute inset-0 bg-[url('data:image/svg+xml,%3Csvg_viewBox=\'0_0_256_256\'_xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cfilter_id=\'n\'%3E%3CfeTurbulence_type=\'fractalNoise\'_baseFrequency=\'0.8\'_numOctaves=\'4\'_stitchTiles=\'stitch\'/%3E%3C/filter%3E%3Crect_width=\'100%25\'_height=\'100%25\'_filter=\'url(%23n)\'_opacity=\'0.035\'/%3E%3C/svg%3E')]" />
      </div>

      <div className="relative z-10 flex min-h-0 flex-1 flex-col gap-4 p-4 lg:flex-row lg:gap-6 lg:p-6">
        <section className="flex min-h-0 min-w-0 flex-1 flex-col">
          <header className="mb-3 flex flex-shrink-0 flex-wrap items-start justify-between gap-3">
            <div className="space-y-1">
              <p className="text-[10px] font-semibold tracking-[0.18em] text-amber-900/75">
                {t("headerEyebrow")}
              </p>
              <h1
                className="max-w-2xl text-balance text-xl font-semibold tracking-tight text-foreground md:text-2xl"
                style={{
                  fontFamily:
                    "var(--font-chat-display), var(--font-serif), Georgia, serif",
                }}
              >
                {detail?.title ?? t("fallbackTitle")}
              </h1>
              <p className="text-xs text-muted-foreground">
                {t("userRounds", { count: roundCount })}
              </p>
            </div>
            <Link
              href={`/conversations/${id}/report`}
              className={cn(
                buttonVariants({ variant: "secondary", size: "sm" }),
                "border border-amber-800/25 bg-amber-500/12 text-amber-950 shadow-sm backdrop-blur-sm hover:bg-amber-500/22",
              )}
            >
              {t("openReport")}
            </Link>
          </header>

          <div
            className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-2xl border border-border/80 bg-card/95 shadow-[0_0_0_1px_oklch(0_0_0/0.04)_inset,0_18px_48px_-20px_oklch(0_0_0/0.08)] backdrop-blur-xl"
          >
            <ScrollArea className="min-h-0 flex-1 px-1 sm:px-2">
              <div
                role="log"
                aria-relevant="additions"
                aria-label={t("chatLogLabel")}
                className="space-y-4 px-3 py-5 sm:px-5"
              >
                {detail?.messages.length === 0 ? (
                  <p className="animate-in fade-in text-center text-sm text-muted-foreground duration-500">
                    {t("emptyState")}
                  </p>
                ) : null}
                {detail?.messages.map((m, idx) => {
                  const stagger = Math.min(idx, 8);
                  if (m.role === "user") {
                    const active = editingId === m.id;
                    return (
                      <div
                        key={m.id}
                        className={cn(
                          "animate-in fade-in slide-in-from-bottom-2 ml-auto flex max-w-[min(92%,42rem)] flex-col gap-1 duration-300",
                        )}
                        style={{ animationDelay: `${stagger * 40}ms` }}
                      >
                        <div className="flex items-center justify-end gap-2 px-1">
                          <span className="text-right text-[10px] font-medium uppercase tracking-widest text-amber-900/55">
                            {t("roleUser")}
                          </span>
                          {!active ? (
                            <button
                              type="button"
                              onClick={() => startEdit(m)}
                              disabled={loading}
                              className="text-[10px] font-medium uppercase tracking-widest text-amber-900/70 underline-offset-2 hover:text-amber-950 hover:underline disabled:opacity-40"
                            >
                              {t("edit")}
                            </button>
                          ) : null}
                        </div>
                        <div
                          className={cn(
                            "rounded-2xl rounded-tr-md border border-amber-800/18 bg-gradient-to-br from-amber-500/14 via-card to-muted/30 px-4 py-3 text-[15px] leading-relaxed text-foreground shadow-md",
                          )}
                        >
                          {active ? (
                            <div className="space-y-2">
                              <Textarea
                                value={editDraft}
                                onChange={(e) => setEditDraft(e.target.value)}
                                disabled={loading}
                                rows={4}
                                className="min-h-[96px] resize-y border-input bg-background text-[15px] text-foreground caret-amber-700 placeholder:text-muted-foreground selection:bg-amber-500/25 selection:text-foreground focus-visible:border-amber-600/45 focus-visible:ring-amber-500/25"
                              />
                              <div className="flex flex-wrap justify-end gap-2">
                                <Button
                                  type="button"
                                  variant="secondary"
                                  size="sm"
                                  disabled={loading}
                                  onClick={cancelEdit}
                                  className="border border-border bg-muted/50"
                                >
                                  {t("editCancel")}
                                </Button>
                                <Button
                                  type="button"
                                  size="sm"
                                  disabled={
                                    loading || !editDraft.trim()
                                  }
                                  onClick={() => void saveEdit()}
                                  className="bg-amber-700 text-amber-50 hover:bg-amber-600"
                                >
                                  {loading
                                    ? t("processing")
                                    : t("editSave")}
                                </Button>
                              </div>
                            </div>
                          ) : (
                            <div className="whitespace-pre-wrap">
                              {m.content}
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  }
                  const { body, disclaimer } = splitAssistantMessage(m.content);
                  const assistantPrimary =
                    disclaimer && !body.trim()
                      ? t("disclaimerOnlyBodyFallback")
                      : disclaimer
                        ? body
                        : m.content;
                  return (
                    <div
                      key={m.id}
                      className={cn(
                        "animate-in fade-in slide-in-from-bottom-2 mr-auto flex max-w-[min(94%,48rem)] gap-0 duration-300",
                      )}
                      style={{ animationDelay: `${stagger * 40}ms` }}
                    >
                      <div
                        className="mt-1 hidden w-1 shrink-0 rounded-full bg-gradient-to-b from-amber-600/90 to-amber-700/35 sm:block"
                        aria-hidden
                      />
                      <div className="min-w-0 flex-1 space-y-2">
                        <span className="block px-1 text-[10px] font-medium uppercase tracking-widest text-muted-foreground/70">
                          {t("roleAssistant")}
                        </span>
                        <div
                          className={cn(
                            "rounded-2xl rounded-tl-md border border-border/90 bg-muted/35 px-4 py-3 text-[15px] leading-relaxed text-foreground shadow-inner",
                          )}
                        >
                          {disclaimer ? (
                            <>
                              <div className="whitespace-pre-wrap">
                                {assistantPrimary}
                              </div>
                              <p
                                className={cn(
                                  "mt-3 border-t border-border pt-3 font-mono text-[10px] leading-relaxed tracking-tight text-muted-foreground",
                                )}
                                aria-label={t("legalNoticeLabel")}
                              >
                                {disclaimer}
                              </p>
                            </>
                          ) : (
                            <div className="whitespace-pre-wrap">
                              {m.content}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
                <div ref={bottomRef} className="h-1 w-full shrink-0" aria-hidden />
              </div>
            </ScrollArea>

            <Separator className="bg-border" />
            <div className="shrink-0 space-y-2 p-3 sm:p-4">
              {error ? (
                <p className="text-sm text-destructive" role="alert">
                  {error}
                </p>
              ) : null}
              <Textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={t("placeholder")}
                rows={3}
                disabled={loading}
                className="min-h-[88px] resize-none border-input bg-background text-[15px] text-foreground caret-amber-700 placeholder:text-muted-foreground selection:bg-amber-500/25 selection:text-foreground focus-visible:border-amber-600/45 focus-visible:ring-amber-500/25"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    void send();
                  }
                }}
              />
              <div className="flex items-center justify-between gap-2">
                <span className="text-[10px] text-muted-foreground/70">
                  Enter {t("sendHint")}
                </span>
                <Button
                  type="button"
                  onClick={() => void send()}
                  disabled={loading || !input.trim()}
                  className="bg-amber-700 text-amber-50 hover:bg-amber-600"
                >
                  {loading ? t("processing") : t("send")}
                </Button>
              </div>
            </div>
          </div>
        </section>

        <aside className="flex w-full shrink-0 flex-col gap-3 lg:w-[340px] lg:max-w-[40vw] lg:pt-12">
          <div
            className={cn(
              "rounded-2xl border border-border/80 bg-card/95 p-4 shadow-md backdrop-blur-xl",
            )}
          >
            <h2 className="text-[11px] font-semibold uppercase tracking-[0.18em] text-amber-900/80">
              {t("profileTitle")}
            </h2>
            <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">
              {detail?.profile_summary || t("profileEmpty")}
            </p>
            {detail?.profile_structured &&
            typeof detail.profile_structured === "object" &&
            detail.profile_structured.dimensions &&
            typeof detail.profile_structured.dimensions === "object" ? (
              <div className="mt-4 rounded-xl border border-border/70 bg-muted/40 p-3">
                <div className="mb-2 text-xs font-medium text-foreground">
                  {t("dimensionsTitle")}
                </div>
                <ul className="space-y-2 text-[13px] leading-snug text-muted-foreground">
                  {Object.entries(
                    detail.profile_structured.dimensions as Record<
                      string,
                      unknown
                    >,
                  )
                    .filter(([, v]) => typeof v === "string" && String(v).trim())
                    .slice(0, 8)
                    .map(([k, v]) => (
                      <li
                        key={k}
                        className="flex gap-2 border-b border-border/60 pb-2 last:border-0 last:pb-0"
                      >
                        <span className="shrink-0 text-[11px] uppercase tracking-wide text-amber-900/55">
                          {k}
                        </span>
                        <span className="text-foreground">
                          {String(v)}
                        </span>
                      </li>
                    ))}
                </ul>
              </div>
            ) : null}
          </div>

          <div
            className={cn(
              "rounded-2xl border border-border/80 bg-card/95 p-4 shadow-md backdrop-blur-xl",
            )}
          >
            <h2 className="text-[11px] font-semibold uppercase tracking-[0.18em] text-amber-900/80">
              {t("memoriesTitle")}
            </h2>
            <div className="mt-3 text-sm text-muted-foreground">
              {detail?.key_memories?.length ? (
                <ul className="space-y-2">
                  {detail.key_memories.map((mem) => (
                    <li
                      key={mem}
                      className="flex gap-2 rounded-lg border border-border/60 bg-muted/35 px-2.5 py-2 text-[13px] leading-snug text-foreground"
                    >
                      <span
                        className="mt-1.5 size-1.5 shrink-0 rounded-full bg-amber-600"
                        aria-hidden
                      />
                      {mem}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs">{t("memoriesHint")}</p>
              )}
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
