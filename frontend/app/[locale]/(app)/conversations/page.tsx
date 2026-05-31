"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState, type MouseEvent } from "react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ApiError, apiFetch } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { Link, useRouter } from "@/i18n/navigation";
import type { ConversationSummary } from "@/lib/types";

export default function ConversationsPage() {
  const router = useRouter();
  const t = useTranslations("conversations");
  const tc = useTranslations("chat");
  const [list, setList] = useState<ConversationSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    apiFetch<ConversationSummary[]>("/conversations")
      .then(setList)
      .catch((e: unknown) => {
        if (e instanceof ApiError && e.status === 401) router.replace("/login");
        else setError(t("loadError"));
      });
  }, [router, t]);

  useEffect(() => {
    load();
  }, [load]);

  async function createConversation() {
    setError(null);
    try {
      const c = await apiFetch<{ id: number }>("/conversations", {
        method: "POST",
        body: JSON.stringify({ title: tc("newSessionTitle") }),
      });
      router.push(`/conversations/${c.id}/chat`);
    } catch {
      setError(t("createError"));
    }
  }

  async function togglePin(c: ConversationSummary, e: MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    setError(null);
    try {
      await apiFetch(`/conversations/${c.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_pinned: !c.is_pinned }),
      });
      load();
    } catch {
      setError(t("pinError"));
    }
  }

  async function removeConversation(id: number, e: MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (!confirm(t("deletedConfirm"))) return;
    setError(null);
    try {
      await apiFetch(`/conversations/${id}`, { method: "DELETE" });
      load();
    } catch {
      setError(t("deleteError"));
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-8 px-0 py-1">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="font-serif text-2xl font-semibold tracking-tight text-foreground sm:text-[1.65rem]">
            {t("title")}
          </h1>
          <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>
        <Button type="button" size="sm" onClick={createConversation}>
          {t("newChat")}
        </Button>
      </div>
      {error ? (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}
      <div className="space-y-3">
        {list.length === 0 ? (
          <Card>
            <CardHeader>
              <CardTitle>{t("emptyTitle")}</CardTitle>
              <CardDescription>{t("emptyHint")}</CardDescription>
            </CardHeader>
          </Card>
        ) : (
          list.map((c) => (
            <Card
              key={c.id}
              className="flex flex-row items-stretch overflow-hidden transition-colors hover:bg-muted/20"
            >
              <Link
                href={`/conversations/${c.id}/chat`}
                className="flex min-w-0 flex-1 flex-col justify-center px-4 py-3"
              >
                <CardTitle className="flex items-center gap-2 text-base font-medium">
                  {c.is_pinned ? (
                    <span className="rounded bg-primary/15 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-primary">
                      {t("pinned")}
                    </span>
                  ) : null}
                  <span className="truncate">{c.title}</span>
                </CardTitle>
                <CardDescription className="text-xs">
                  {t("updatedAt")} {new Date(c.updated_at).toLocaleString()}
                </CardDescription>
              </Link>
              <div className="flex shrink-0 flex-col justify-center gap-1 border-l border-border px-2 py-2">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-8 px-2 text-xs"
                  onClick={(ev) => togglePin(c, ev)}
                >
                  {c.is_pinned ? t("unpin") : t("pin")}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-8 px-2 text-xs text-destructive hover:text-destructive"
                  onClick={(ev) => removeConversation(c.id, ev)}
                >
                  {t("delete")}
                </Button>
              </div>
            </Card>
          ))
        )}
      </div>
    </div>
  );
}
